/** Shared API types — mirror the Pydantic schemas in backend/app/schemas. */

export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export type LlmProvider = "ollama" | "gemini";
export type VectorDbType = "pgvector" | "chromadb";

export interface Agent {
  id: number;
  user_id: number;
  name: string;
  repo_full_name: string;
  llm_provider: LlmProvider;
  vector_db_type: VectorDbType;
  github_installation_id: number | null;
  is_active: boolean;
  ingestion_status: "pending" | "running" | "done" | "failed";
  last_ingested_at: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateInput {
  name: string;
  repo_full_name: string;
  llm_provider: LlmProvider;
  vector_db_type: VectorDbType;
  github_installation_id?: number | null;
}

export interface GithubRepo {
  full_name: string;
  private: boolean;
}

export interface GithubInstallResult {
  status: "installed" | "pending_approval";
  installation_id?: number;
  repos?: GithubRepo[];
  message?: string;
}

export interface GithubInstallation {
  installation_id: number;
  account_login: string;
  account_type: string;
  permissions: Record<string, string>;
}

export type PrDecision = "approved" | "declined" | "error";
export type PrLayer =
  | "spam"
  | "malicious_code"
  | "hijack_proof"
  | "summary"
  | null;

export interface PREvent {
  id: number;
  agent_id: number;
  pr_number: number;
  pr_url: string;
  author_github: string;
  decision: PrDecision;
  layer_caught: PrLayer;
  reason: string | null;
  created_at: string;
}

// ----------------------------------------------------------- dashboard ----

export interface DashboardStats {
  total_prs: number;
  approved: number;
  declined: number;
  errors: number;
  flagged_accounts: number;
  banned_accounts: number;
  approval_rate: number;
}

export interface AgentStats {
  agent_id: number;
  agent_name: string;
  repo_full_name: string;
  total_prs: number;
  approved: number;
  declined: number;
  approval_rate: number;
}

export interface FlaggedAccount {
  github_username: string;
  flag_count: number;
  account_status: string;
  banned_at: string | null;
  first_seen: string;
  updated_at: string;
}
