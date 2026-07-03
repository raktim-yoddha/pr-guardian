"""Async GitHub API client.

Supports two auth modes, picked automatically from config:
  1. GitHub App  — signs a JWT with the app private key, exchanges it for an
     installation access token for the target repo.
  2. PAT fallback — uses ``settings.GITHUB_TOKEN`` directly (handy for local dev).

In Phase 1 we only need repo metadata + issue listing + PR diff fetching.
Higher-level operations (posting review comments, rewriting PR titles) are added
in Phase 3.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import settings
from app.services.resilience import retry_async

GITHUB_API = "https://api.github.com"


class GithubError(RuntimeError):
    """Raised when the GitHub API returns an unrecoverable error."""


@dataclass
class RepoMeta:
    full_name: str
    description: str | None
    default_branch: str | None
    stargazers_count: int
    open_issues_count: int
    html_url: str


def _sign_jwt_with_app_key(private_key_pem: str) -> str:
    """Create a GitHub App JWT (RS256) signed with the app's private key."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(),
        password=None,
        backend=default_backend(),
    )

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": settings.GITHUB_APP_ID}

    header = {"alg": "RS256", "typ": "JWT"}
    import base64
    import json

    def b64(obj: dict[str, Any]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode()
        )

    signing_input = f"{b64(header)}.{b64(payload)}".encode()
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


class GithubClient:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        # Per-installation token cache: {installation_id: (token, expires_at)}
        self._install_tokens: dict[int, tuple[str, float]] = {}
        # Thread a per-call installation_id so _resolve_token can use it.
        self._installation_id: int | None = None

    # ------------------------------------------------------------------ auth

    def _read_app_key(self) -> str | None:
        path = settings.GITHUB_APP_PRIVATE_KEY_PATH
        if not path:
            return None
        try:
            with open(path, "rb") as fh:
                return fh.read().decode()
        except OSError:
            return None

    async def _resolve_token(self, repo_full_name: str, *, installation_id: int | None = None) -> str | None:
        """Return the best available auth token for ``repo_full_name``.

        If ``installation_id`` is provided (from the Agent row), it's used
        directly to mint a per-installation token. Otherwise falls back to
        auto-discovery via the repo/owner endpoints, then PAT fallback.
        """
        # PAT fallback first (local dev).
        if settings.GITHUB_TOKEN:
            return settings.GITHUB_TOKEN

        # GitHub App path.
        app_key = self._read_app_key()
        if not app_key or not settings.GITHUB_APP_ID:
            return None

        app_jwt = _sign_jwt_with_app_key(app_key)

        # Fast path: use the per-agent installation_id if we have one.
        iid = installation_id or self._installation_id
        if iid is None:
            # Auto-discover: look up installation by repo/owner.
            owner = repo_full_name.split("/", 1)[0]
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                try:
                    resp = await client.get(
                        f"{GITHUB_API}/repos/{repo_full_name}/installation",
                        headers={"Authorization": f"Bearer {app_jwt}"},
                    )
                    resp.raise_for_status()
                    iid = resp.json()["id"]
                except httpx.HTTPError:
                    try:
                        resp = await client.get(
                            f"{GITHUB_API}/users/{owner}/installation",
                            headers={"Authorization": f"Bearer {app_jwt}"},
                        )
                        resp.raise_for_status()
                        iid = resp.json()["id"]
                    except httpx.HTTPError as exc:
                        raise GithubError(
                            f"Could not locate GitHub App installation for {repo_full_name}"
                        ) from exc

        # Cache check.
        cached = self._install_tokens.get(iid)
        if cached and cached[1] > time.time() + 60:
            return cached[0]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{GITHUB_API}/app/installations/{iid}/access_tokens",
                headers={"Authorization": f"Bearer {app_jwt}"},
            )
            resp.raise_for_status()
            data = resp.json()
            token = data["token"]
            expires_at = time.time() + 3600  # tokens last 1h
            self._install_tokens[iid] = (token, expires_at)
            return token

    async def _headers(self, repo_full_name: str) -> dict[str, str]:
        token = await self._resolve_token(repo_full_name)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pr-guardian",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _check(resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code >= 400:
            raise GithubError(
                f"GitHub API {resp.request.method} {resp.request.url.path} "
                f"-> {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json() if resp.content else {}

    # ----------------------------------------------------------------- public

    async def get_repo(self, repo_full_name: str) -> RepoMeta:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_repo_raw(repo_full_name, headers),
            description=f"get_repo({repo_full_name})",
        )

    async def _fetch_repo_raw(self, repo_full_name: str, headers: dict[str, str]) -> RepoMeta:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{GITHUB_API}/repos/{repo_full_name}", headers=headers)
            data = self._check(resp)
        return RepoMeta(
            full_name=data["full_name"],
            description=data.get("description"),
            default_branch=data.get("default_branch"),
            stargazers_count=data.get("stargazers_count", 0),
            open_issues_count=data.get("open_issues_count", 0),
            html_url=data["html_url"],
        )

    async def list_issues(
        self, repo_full_name: str, state: str = "all", per_page: int = 100
    ) -> list[dict[str, Any]]:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_issues_raw(repo_full_name, state, per_page, headers),
            description=f"list_issues({repo_full_name})",
        )

    async def _fetch_issues_raw(self, repo_full_name: str, state: str, per_page: int, headers: dict[str, str]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/issues",
                params={"state": state, "per_page": per_page},
                headers=headers,
            )
            return self._check(resp)

    async def get_pr(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_pr_raw(repo_full_name, pr_number, headers),
            description=f"get_pr({repo_full_name}#{pr_number})",
        )

    async def _fetch_pr_raw(self, repo_full_name: str, pr_number: int, headers: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}", headers=headers
            )
            return self._check(resp)

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        headers = await self._headers(repo_full_name)
        headers["Accept"] = "application/vnd.github.v3.diff"
        return await retry_async(
            lambda: self._fetch_diff_raw(repo_full_name, headers),
            description=f"get_pr_diff({repo_full_name}#{pr_number})",
        )

    async def _fetch_diff_raw(self, repo_full_name: str, headers: dict[str, str]) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}", headers=headers
            )
            if resp.status_code >= 400:
                raise GithubError(
                    f"GitHub API get_pr_diff -> {resp.status_code}: {resp.text[:300]}"
                )
            return resp.text

    # ------------------------------------------------------ ingestion helpers

    async def get_tree_blobs(
        self, repo_full_name: str, branch: str | None = None
    ) -> list[dict[str, Any]]:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_tree_raw(repo_full_name, branch, headers),
            description=f"get_tree_blobs({repo_full_name})",
        )

    async def _fetch_tree_raw(self, repo_full_name: str, branch: str | None, headers: dict[str, str]) -> list[dict[str, Any]]:
        """Return the flat list of blob file entries for a repo.

        Uses the recursive tree endpoint. Each entry has ``path``, ``size``,
        ``sha``, ``type``. Only ``type == "blob"`` entries are returned.
        """
        ref = branch or (await self.get_repo(repo_full_name)).default_branch or "HEAD"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/git/trees/{ref}?recursive=1",
                headers=headers,
            )
            data = self._check(resp)
        return [e for e in data.get("tree", []) if e.get("type") == "blob"]

    async def get_blob_content(
        self, repo_full_name: str, file_sha: str
    ) -> str:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_blob_raw(repo_full_name, file_sha, headers),
            description=f"get_blob_content({file_sha[:8]})",
        )

    async def _fetch_blob_raw(self, repo_full_name: str, file_sha: str, headers: dict[str, str]) -> str:
        """Fetch the decoded text content of a single file blob."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/git/blobs/{file_sha}",
                headers=headers,
            )
            data = self._check(resp)
        import base64

        content = data.get("content") or ""
        if data.get("encoding") == "base64":
            # GitHub base64 may include newlines; normalize before decoding.
            return base64.b64decode(content.replace("\n", "")).decode(
                "utf-8", errors="replace"
            )
        return content

    async def get_issue_comments(
        self, repo_full_name: str, issue_number: int
    ) -> list[dict[str, Any]]:
        headers = await self._headers(repo_full_name)
        return await retry_async(
            lambda: self._fetch_comments_raw(repo_full_name, issue_number, headers),
            description=f"get_issue_comments({issue_number})",
        )

    async def _fetch_comments_raw(self, repo_full_name: str, issue_number: int, headers: dict[str, str]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/issues/{issue_number}/comments",
                params={"per_page": 100},
                headers=headers,
            )
            return self._check(resp)

    # ------------------------------------------------- PR write operations

    async def post_pr_comment(
        self, repo_full_name: str, pr_number: int, body: str
    ) -> None:
        headers = await self._headers(repo_full_name)
        await retry_async(
            lambda: self._post_comment_raw(repo_full_name, pr_number, body, headers),
            description=f"post_pr_comment({repo_full_name}#{pr_number})",
        )

    async def _post_comment_raw(self, repo_full_name: str, pr_number: int, body: str, headers: dict[str, str]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments",
                json={"body": body},
                headers=headers,
            )
            self._check(resp)

    async def update_pr(
        self,
        repo_full_name: str,
        pr_number: int,
        *,
        title: str | None = None,
        body: str | None = None,
    ) -> None:
        headers = await self._headers(repo_full_name)
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if not payload:
            return
        await retry_async(
            lambda: self._patch_pr_raw(repo_full_name, pr_number, payload, headers),
            description=f"update_pr({repo_full_name}#{pr_number})",
        )

    async def _patch_pr_raw(self, repo_full_name: str, pr_number: int, payload: dict[str, Any], headers: dict[str, str]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(
                f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}",
                json=payload,
                headers=headers,
            )
            self._check(resp)


github_client = GithubClient()
