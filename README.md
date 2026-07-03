# PR Guardian

> Your AI-powered Pull Request bouncer — catches spam, malicious code, and injection attacks before they reach human reviewers.

PR Guardian is a RAG-powered GitHub Pull Request management system. Users connect their GitHub accounts via OAuth, then create agents tied to specific repositories. Each agent ingests the full repo and its issues as a knowledge base using hybrid BM25 + vector search, then autonomously reviews incoming PRs through a multi-layer agentic pipeline — declining dangerous PRs (and closing them) and polishing clean ones before they ever reach a human reviewer.

## 🚀 How to Use

**1. Sign Up & Connect GitHub**
Register an account, then connect your GitHub account via OAuth from the sidebar. This grants PR Guardian full permissions to manage your repositories and pull requests.

**2. Create an Agent**
Select a connected GitHub account, choose a repository from your accessible repos, then configure the LLM provider (Ollama or Gemini) and vector database. The system immediately begins ingesting the repo's source code and all issues into its knowledge base using the bge-m3 embedding model.

**3. Pipeline Reviews PRs Automatically**
Each incoming PR passes through four sequential detection layers — spam, malicious code, hijack-proof, and summary. If any layer flags the PR, it's automatically closed with a comment explaining the reason, and the author's GitHub account gets a strike. Clean PRs get their title and description rewritten in conventional-commits format.

**4. Monitor from the Dashboard**
The modern sidebar-oriented dashboard shows aggregate stats (total PRs, approval rate, flagged accounts), a per-agent breakdown, an immutable event log with every decision, and a flagged-accounts panel showing users who've been caught.

**5. Manage Agents**
Pause, resume, or delete agents. Edit LLM provider and vector DB settings. Trigger manual knowledge-base re-syncs from the agent settings page.

## 🧠 Implementation Process

### System Architecture

```mermaid
flowchart TD
    A[GitHub Webhook] --> B[FastAPI Backend]
    B --> C{Valid HMAC-SHA256?}
    C -->|No| D[Reject 401]
    C -->|Yes| E{Rate Limited?}
    E -->|Yes| F[Auto-Flag Account]
    E -->|No| G{Payload > 500KB?}
    G -->|Yes| H[Ignore]
    G -->|No| I[Run Pipeline]
    I --> J[Layer 1: Spam Detection]
    J -->|Declined| K[Flag Account]
    K --> L[Decline PR]
    J -->|Clean| M[Layer 2: Malicious Code]
    M -->|Declined| K
    M -->|Clean| N[Layer 3: Hijack-Proof]
    N -->|Declined| K
    N -->|Clean| O[Layer 4: Summary]
    O --> P[Rewrite Title/Body]
    P --> Q[Post to GitHub]
    Q --> R[Approve PR]
```

### RAG Ingestion Flow

```mermaid
flowchart TD
    A[Agent Created] --> B[Fetch Repo File Tree]
    B --> C[Download Text Blobs]
    C --> D[Fetch Issues + Comments]
    D --> E[Chunk Content<br/>512 tokens, 50 overlap]
    E --> F[Embed Chunks<br/>via Ollama/Gemini]
    F --> G[Store in pgvector<br/>KnowledgeChunk table]
    G --> H[Agent Status: done]
```

### Key Algorithms & Logic

**Spam Detection (Layer 1):**
- Heuristic pre-checks: empty body with no linked issue, trivial diff (< 5 changed lines), bot-like regex patterns (promo links, crypto spam)
- Hybrid RAG retrieval (BM25 + vector search) using PR title + first 500 chars of diff as query against the knowledge base
- LLM scoring 0.0–1.0 with repository context; threshold > 0.75 → decline
- Belt-and-suspenders: either heuristic OR LLM triggers a decline

**Malicious Code Detection (Layer 2):**
- Static regex scan of the diff: `eval()`, `exec()`, `subprocess`, `os.system`, `base64.b64decode`, hardcoded IPs, secret exfiltration patterns, reverse shells, keyloggers, pickle deserialization, ctypes shellcode
- High-risk hunks sent to the LLM for deeper analysis
- Either static scan OR LLM detection → decline (no consensus required)

**Hijack-Proof Detection (Layer 3):**
- Regex pattern library: "ignore previous instructions", "you are now", role-play overrides, system role injection, base64-encoded payloads, URL-encoded payloads
- Decode-and-scan: base64 and URL-decoded strings are re-scanned against high-signal patterns
- LLM analysis with injection-resistant system prompt — all untrusted content wrapped in `<pr_content>` XML delimiters
- Any detection → immediate decline + flag (no LLM needed for regex hits)

**Summary Layer (Layer 4):**
- Hybrid RAG retrieves top-8 chunks from issues and code similar to the diff
- LLM generates conventional-commits title (`feat|fix|refactor|...`) and structured description (what changed, why, linked issues, impact)
- Updated title and body posted back to the GitHub PR via API

**Account Flagging:**
- Every declined PR increments `flag_count` on the `GithubAccount` model
- At `flag_count >= 3`, the account is auto-banned

**Hardening (Phase 5):**
- All external API calls wrapped with exponential backoff retry (3 attempts, 0.5s base, 8s max, jitter)
- Webhook rejects payloads exceeding 500KB
- Per-account rate limit: >10 PRs/hour → auto-flag without running the pipeline
- Prometheus-style metrics at `/metrics` (pipeline runs, decisions, duration histograms)

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 14 (App Router) + Shadcn UI + Tailwind | Modern sidebar-oriented dashboard, agent management, event log |
| Backend | FastAPI (Python 3.11+) + SQLAlchemy 2.x async | REST API, pipeline orchestration, GitHub OAuth |
| Database | PostgreSQL 16 + pgvector | Primary store + vector embeddings (1024-dim) |
| Orchestration | LangGraph | Multi-layer PR review pipeline with conditional routing |
| LLM | Ollama (local) | Code analysis, spam scoring, PR summarization |
| Auth | JWT (python-jose) + bcrypt + GitHub OAuth + Google OAuth | User authentication + GitHub/Google account connection |
| Embeddings | bge-m3 (Ollama) | RAG knowledge base chunk embeddings (1024-dim) |
| Search | Hybrid BM25 + Vector Search | Improved retrieval accuracy for RAG |
| Deployment | Docker + Nginx | Multi-container production deployment |

## 📦 Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (for database or full deployment)
- Ollama (optional, for local LLM) or a Gemini API key

### Option A: Full Docker Deployment

```bash
git clone <repo-url> pr-guardian
cd pr-guardian
cp .env.example backend/.env
# Edit backend/.env with your real values
docker compose up -d
```

For local LLM support:

```bash
docker compose --profile ollama up -d
docker exec prguardian-ollama ollama pull llama3
docker exec prguardian-ollama ollama pull bge-m3
```

The app is available at `http://localhost` (nginx proxies port 80).

### Option B: Local Development

**Database:**

```bash
docker compose up -d postgres
```

**Backend:**

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your values
alembic upgrade head
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`.

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/prguardian` |
| `SECRET_KEY` | JWT signing key (use a long random string) | — |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for GitHub webhook validation | — |
| `GITHUB_TOKEN` | Personal Access Token (dev mode) | — |
| `GITHUB_APP_ID` | GitHub App ID (production mode) | — |
| `GITHUB_CLIENT_ID` | GitHub OAuth App Client ID | — |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App Client Secret | — |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | — |
| `LLM_PROVIDER` | `ollama` | `ollama` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Chat model name | `llama3` |
| `OLLAMA_EMBED_MODEL` | Embedding model name | `bge-m3` |
| `EMBEDDING_DIM` | Embedding vector dimension | `1024` |
| `SPAM_THRESHOLD` | Spam score threshold to decline | `0.75` |
| `MAX_PR_DIFF_BYTES` | Max webhook payload size | `524288` |

## 🔗 API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | No | Register a new user |
| `POST` | `/api/auth/login` | No | Login, returns JWT access token |
| `GET` | `/api/auth/me` | Yes | Get current user profile |
| `GET` | `/api/agents` | Yes | List current user's agents |
| `POST` | `/api/agents` | Yes | Create an agent (triggers repo ingestion) |
| `GET` | `/api/agents/{id}` | Yes | Get agent details |
| `PATCH` | `/api/agents/{id}` | Yes | Update agent (name, active, LLM, vector DB) |
| `DELETE` | `/api/agents/{id}` | Yes | Delete an agent |
| `POST` | `/api/agents/{id}/sync` | Yes | Trigger manual knowledge-base re-sync |
| `GET` | `/api/events` | Yes | Paginated PR event log (filter by agent, decision) |
| `GET` | `/api/events/count` | Yes | Count events matching filters |
| `GET` | `/api/dashboard/stats` | Yes | Aggregate stats (total, approved, declined, flagged) |
| `GET` | `/api/dashboard/per-agent` | Yes | Stats broken down per agent |
| `GET` | `/api/dashboard/flagged-accounts` | Yes | Flagged GitHub accounts for user's agents |
| `GET` | `/github/oauth/authorize` | Yes | Get GitHub OAuth authorization URL |
| `GET` | `/github/oauth/callback` | No | Handle GitHub OAuth callback |
| `GET` | `/github/connections` | Yes | List user's GitHub connections |
| `DELETE` | `/github/connections/{id}` | Yes | Delete a GitHub connection |
| `GET` | `/github/connections/{id}/repos` | Yes | List repos accessible via connection |
| `POST` | `/webhooks/github` | HMAC | GitHub webhook receiver |
| `POST` | `/webhooks/rotate-secret` | HMAC | Rotate webhook HMAC secret |
| `GET` | `/metrics` | No | Prometheus-style metrics |
| `GET` | `/health` | No | Liveness probe |

## 📁 Project Structure

```
pr-guardian/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── agents.py
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   ├── deps.py
│   │   │   ├── events.py
│   │   │   ├── github.py
│   │   │   ├── github_oauth.py
│   │   │   └── webhooks.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── metrics.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── agent.py
│   │   │   ├── github_account.py
│   │   │   ├── github_connection.py
│   │   │   ├── knowledge_chunk.py
│   │   │   ├── pr_event.py
│   │   │   └── user.py
│   │   ├── pipeline/
│   │   │   ├── graph.py
│   │   │   ├── runner.py
│   │   │   ├── state.py
│   │   │   └── nodes/
│   │   │       ├── spam.py
│   │   │       ├── malicious_code.py
│   │   │       ├── hijack_proof.py
│   │   │       ├── summary.py
│   │   │       ├── flag_account.py
│   │   │       ├── approve_pr.py
│   │   │       └── decline_pr.py
│   │   ├── schemas/
│   │   │   ├── agent.py
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   └── event.py
│   │   ├── services/
│   │   │   ├── chunker.py
│   │   │   ├── github.py
│   │   │   ├── ingestion.py
│   │   │   ├── llm.py
│   │   │   ├── rag.py
│   │   │   ├── resilience.py
│   │   │   └── vectorstore.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_knowledge_chunks.py
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── (app)/
│   │   │   ├── dashboard/
│   │   │   │   ├── page.tsx
│   │   │   │   └── events/page.tsx
│   │   │   ├── agents/
│   │   │   │   ├── new/page.tsx
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx
│   │   │   │       └── settings/page.tsx
│   │   │   └── layout.tsx
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── custom/
│   │   │   ├── app-shell.tsx
│   │   │   ├── auth-guard.tsx
│   │   │   └── sidebar.tsx
│   │   └── ui/
│   │       ├── badge.tsx
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── input.tsx
│   │       ├── label.tsx
│   │       └── select.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── types.ts
│   │   └── utils.ts
│   ├── Dockerfile
│   ├── next.config.mjs
│   └── package.json
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
└── .env.example
```

## 📤 Exports

### Backend (Python)

| Module | Export | Type |
|---|---|---|
| `app.pipeline` | `PRState` | TypedDict — shared pipeline state schema |
| `app.pipeline.graph` | `pipeline` | Compiled LangGraph `CompiledGraph` |
| `app.pipeline.runner` | `run_pipeline()` | Async entrypoint: `repo_full_name, pr_number, pr_url, author → dict` |
| `app.services.llm` | `get_llm_response()` | Async: `prompt, system, provider, model, temperature → str` |
| `app.services.llm` | `get_embedding()` | Async: `text, provider, model → list[float]` |
| `app.services.llm` | `embed_batch()` | Async: `texts, provider → list[list[float]]` |
| `app.services.llm` | `resolve_provider()` | `agent → "ollama" \| "gemini"` |
| `app.services.rag` | `retrieve()` | Async: `agent, query, k, alpha → list[ChunkHit]` (hybrid BM25 + vector) |
| `app.services.rag` | `retrieve_texts()` | Async: `agent, query, k → list[str]` |
| `app.services.vectorstore` | `vector_store` | `PgVectorStore` singleton — `search()`, `add()`, `reset()` |
| `app.services.resilience` | `retry_async()` | Async: `func, attempts, base_delay, max_delay → T` |
| `app.core.metrics` | `serialize_metrics()` | Returns Prometheus text-format metrics string |
| `app.core.metrics` | `inc_counter()` | Increment a named counter with optional labels |
| `app.core.metrics` | `observe_histogram()` | Record a value in a named histogram |

### Frontend (TypeScript)

| Module | Export | Type |
|---|---|---|
| `lib/api` | `api` | Object with all API methods (login, agents, events, dashboard) |
| `lib/api` | `getToken()` / `setToken()` / `clearToken()` | JWT token localStorage helpers |
| `lib/auth` | `useSession` | React hook for authentication state |
| `lib/types` | `Agent`, `PREvent`, `DashboardStats`, etc. | All shared TypeScript interfaces |

## 📄 License

MIT
