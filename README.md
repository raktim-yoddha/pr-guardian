# PR Guardian — RAG-Powered Agentic PR Manager

PR Guardian automatically reviews GitHub Pull Requests through a multi-layer AI pipeline. Create agents tied to GitHub repos, and every incoming PR is scanned for spam, malicious code, and prompt-injection attempts before being approved or declined.

## Architecture

```
GitHub Webhook → FastAPI → LangGraph Pipeline → 4 Detection Layers
                                                        │
                                                    ┌───────┤
                                                    ▼       ▼
                                              [Clean PR]  [Flagged PR]
                                              Rewrite     Decline +
                                              title/body  Flag account
                                              → GitHub    → GitHub
```

### Pipeline Layers
1. **Spam Detection** — heuristic checks + RAG-informed LLM scoring
2. **Malicious Code** — regex static scan + LLM analysis of high-risk hunks
3. **Hijack-Proof** — prompt injection detection (regex + base64 decode + LLM)
4. **Summary & Approval** — rewrites PR title/description in conventional-commits format

A PR that fails any layer is **immediately declined** and never reaches the next layer.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) + Shadcn UI + Tailwind |
| Backend | FastAPI (Python 3.11+) + SQLAlchemy 2.x async |
| Database | PostgreSQL 16 + pgvector |
| Orchestration | LangGraph |
| LLM | Ollama (local) or Gemini Flash |
| Auth | JWT (python-jose) + bcrypt |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Ollama running locally for the LLM backend

### 1. Clone & Configure

```bash
git clone <repo-url> pr-guardian
cd pr-guardian
cp .env.example backend/.env
# Edit backend/.env with your real values (SECRET_KEY, GITHUB_WEBHOOK_SECRET, etc.)
```

### 2. Start with Docker Compose

```bash
docker compose up -d
```

This starts: PostgreSQL (pgvector), backend (FastAPI), frontend (Next.js), and nginx reverse proxy on port 80.

For local LLM support:
```bash
docker compose --profile ollama up -d
docker exec prguardian-ollama ollama pull llama3
docker exec prguardian-ollama ollama pull nomic-embed-text
```

### 3. Local Development (without Docker)

```bash
# Start PostgreSQL (with pgvector)
docker compose up -d postgres

# Backend
cd backend
python -m venv .venv
.venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### 4. Set Up GitHub Integration

**Option A: Personal Access Token (quickest for dev)**
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Generate a token with `repo` scope
3. Add `GITHUB_TOKEN=<your-token>` to `backend/.env`

**Option B: GitHub App (recommended for production)**
1. Create a GitHub App at https://github.com/settings/apps
2. Set the webhook URL to `http://your-domain/webhooks/github`
3. Generate a private key, save as `backend/github-app.pem`
4. Add `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY_PATH` to `.env`
5. Install the app on the repos you want to guard

## Endpoints

| Endpoint | Description |
|---|---|
| `POST /webhooks/github` | GitHub webhook receiver (HMAC-validated) |
| `POST /api/auth/register` | Register a new user |
| `POST /api/auth/login` | Login, returns JWT access token |
| `GET /api/agents` | List current user's agents |
| `POST /api/agents` | Create an agent (triggers repo ingestion) |
| `POST /api/agents/{id}/sync` | Re-sync the knowledge base |
| `GET /api/events` | Paginated PR event log |
| `GET /api/dashboard/stats` | Aggregate stats (approved/declined/flagged) |
| `GET /api/dashboard/flagged-accounts` | Flagged GitHub accounts |
| `GET /metrics` | Prometheus-style metrics |
| `GET /health` | Liveness probe |

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing key (generate a long random string)
- `GITHUB_WEBHOOK_SECRET` — Shared secret for GitHub webhook HMAC validation
- `GITHUB_TOKEN` or `GITHUB_APP_ID` + private key — GitHub API authentication
- `LLM_PROVIDER` — `ollama` (local) or `gemini` (cloud)

## Project Structure

```
pr-guardian/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/       # Route handlers
│   │   ├── core/      # Config, database, security, metrics
│   │   ├── models/    # SQLAlchemy ORM models
│   │   ├── pipeline/  # LangGraph orchestration (4 layers)
│   │   ├── schemas/   # Pydantic request/response schemas
│   │   └── services/  # GitHub client, LLM, RAG, ingestion
│   └── alembic/       # DB migrations
├── frontend/          # Next.js 14 App Router
│   ├── app/           # Pages (dashboard, agents, events)
│   ├── components/    # Shadcn UI + custom components
│   └── lib/           # API client, types, auth
├── nginx/             # Reverse proxy config
├── docker-compose.yml
└── .env.example
```

## License

MIT
