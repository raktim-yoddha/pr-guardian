/**
 * Thin fetch wrapper for the PR Guardian backend.
 *
 * The base URL points at the FastAPI backend. In dev we rely on the standard
 * Next.js dev server proxy setup (see `next.config.mjs`), but to keep it simple
 * we hit the backend directly via an env var, defaulting to localhost:8000.
 *
 * The JWT access token is stored in localStorage and attached as a Bearer
 * header on every request. On 401 we clear it and redirect to /login.
 */

import type {
  Agent,
  AgentCreateInput,
  AgentStats,
  DashboardStats,
  FlaggedAccount,
  GitHubConnection,
  GitHubRepo,
  OAuthResponse,
  PREvent,
  Token,
  User,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "prguardian.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Skip auth header (used by login/register). */
  noAuth?: boolean;
  query?: Record<string, string | number | undefined>;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, noAuth = false, query } = opts;

  let url = `${API_BASE_URL}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) params.set(k, String(v));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (!noAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !noAuth) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || data.message || JSON.stringify(data);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --------------------------------------------------------------- auth ----
export const api = {
  async register(email: string, password: string): Promise<{ token: string; user: User }> {
    const user = await request<User>("/api/auth/register", {
      method: "POST",
      body: { email, password },
      noAuth: true,
    });
    const { access_token } = await api.login(email, password);
    return { token: access_token, user };
  },
  async handleOAuthCallback(provider: "github" | "google", code: string): Promise<{ access_token: string; token_type: string; user: User }> {
    return request<{ access_token: string; token_type: string; user: User }>(`/api/${provider}/oauth/callback`, {
      query: { code },
      noAuth: true,
    });
  },
  async login(email: string, password: string): Promise<Token> {
    return request<Token>("/api/auth/login", {
      method: "POST",
      body: { email, password },
      noAuth: true,
    });
  },
  async me(): Promise<User> {
    return request<User>("/api/auth/me");
  },

  // ------------------------------------------------------------- agents
  async listAgents(): Promise<Agent[]> {
    return request<Agent[]>("/api/agents");
  },
  async getAgent(id: number): Promise<Agent> {
    return request<Agent>(`/api/agents/${id}`);
  },
  async createAgent(input: AgentCreateInput): Promise<Agent> {
    return request<Agent>("/api/agents", { method: "POST", body: input });
  },
  async updateAgent(
    id: number,
    patch: Partial<Pick<Agent, "name" | "is_active" | "llm_provider" | "vector_db_type">>,
  ): Promise<Agent> {
    return request<Agent>(`/api/agents/${id}`, { method: "PATCH", body: patch });
  },
  async deleteAgent(id: number): Promise<void> {
    await request<void>(`/api/agents/${id}`, { method: "DELETE" });
  },
  async syncAgent(id: number): Promise<Agent> {
    return request<Agent>(`/api/agents/${id}/sync`, { method: "POST" });
  },
  async getAgentProgress(id: number): Promise<any> {
    return request<any>(`/api/agents/${id}/progress`);
  },
  async getAgentIngestionLogs(id: number, limit: number = 100): Promise<any[]> {
    return request<any[]>(`/api/agents/${id}/ingestion-logs`, { query: { limit } });
  },
  async cancelAgentSync(id: number): Promise<Agent> {
    return request<Agent>(`/api/agents/${id}/cancel-sync`, { method: "POST" });
  },

  // ------------------------------------------------------------- events
  async listEvents(params: {
    agent_id?: number;
    decision?: string;
    layer_caught?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<PREvent[]> {
    return request<PREvent[]>("/api/events", { query: params });
  },
  async listProcessingStatus(params: {
    agent_id?: number;
    limit?: number;
  } = {}): Promise<any[]> {
    return request<any[]>("/api/events/processing-status", { query: params });
  },
  async getPRDetail(agentId: number, prNumber: number): Promise<any> {
    return request<any>(`/api/events/pr-detail/${agentId}/${prNumber}`);
  },

  // ----------------------------------------------------------- dashboard
  async getStats(agentId?: number): Promise<DashboardStats> {
    return request<DashboardStats>("/api/dashboard/stats", {
      query: agentId !== undefined ? { agent_id: agentId } : undefined,
    });
  },
  async getPerAgentStats(): Promise<AgentStats[]> {
    return request<AgentStats[]>("/api/dashboard/per-agent");
  },
  async listFlaggedAccounts(agentId?: number): Promise<FlaggedAccount[]> {
    return request<FlaggedAccount[]>("/api/dashboard/flagged-accounts", {
      query: agentId !== undefined ? { agent_id: agentId } : undefined,
    });
  },
  async unflagAccount(githubUsername: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/api/dashboard/flagged-accounts/${githubUsername}/unflag`, {
      method: "POST",
    });
  },

  // ----------------------------------------------------------- GitHub OAuth
  async getGitHubAuthUrl(): Promise<{ authorization_url: string }> {
    return request<{ authorization_url: string }>("/api/github/oauth/authorize");
  },
  async listGitHubConnections(): Promise<GitHubConnection[]> {
    return request<GitHubConnection[]>("/api/github/connections");
  },
  async deleteGitHubConnection(connectionId: number): Promise<{ message: string }> {
    return request<{ message: string }>(`/api/github/connections/${connectionId}`, {
      method: "DELETE",
    });
  },
  async listGitHubRepos(connectionId: number): Promise<GitHubRepo[]> {
    return request<GitHubRepo[]>(`/api/github/connections/${connectionId}/repos`);
  },

  // ----------------------------------------------------------- Google OAuth
  async getGoogleAuthUrl(): Promise<{ authorization_url: string }> {
    return request<{ authorization_url: string }>("/api/google/oauth/authorize");
  },
};
