# PR Guardian

> An AI guardian that screens every GitHub pull request before a human ever sees it.

PR Guardian points an autonomous agent at a GitHub repository. Each agent ingests the repo's code and issues into a RAG knowledge base, then runs every incoming PR through a four-layer security pipeline — blocking prompt injection, malicious code, and spam, and rewriting the good ones into clean, reviewer-ready descriptions. Built for maintainers and teams who want a reliable first-pass reviewer that runs for free on CPU.

- Four-layer review pipeline: prompt injection → spam → malicious code → summarize & approve
- Repo + issue RAG with local CPU embeddings (fastembed) and hybrid BM25 + vector retrieval
- Bring-your-own LLM: Groq, Gemini, or local Ollama — with per-user, encrypted API keys
- Auto-flag and ban abusive GitHub accounts across repeated violations
- Webhook-driven, in-process background processing (no Celery/Redis/worker)
- Next.js dashboard with live PR progress, decisions, and flagged accounts (dark + light)

## 📑 Table of Contents

- [🚀 How to Use](#-how-to-use)
- [🧠 Implementation Overview](#-implementation-overview)
- [🛠️ Tech Stack](#️-tech-stack)
- [⚙️ Setup & Installation](#️-setup--installation)
- [🔌 API Endpoints](#-api-endpoints)
- [📁 Project Structure](#-project-structure)

## 🚀 How to Use

- **Sign up / sign in** — email + password, or GitHub / Google OAuth.
- **Connect GitHub** — link an account from the sidebar; PR Guardian lists the repos it can access.
- **Create an agent** — pick a connected account, choose a repo, and select an LLM provider. The agent immediately ingests the repo's source and issues into its knowledge base.
- **Set your provider key (optional)** — in **Settings**, choose Groq / Gemini / Ollama and paste your own API key (stored encrypted). No key → the server default provider is used.
- **Let it review** — open PRs are picked up via webhook (and a startup scan), run through the pipeline, and either declined + flagged or rewritten + approved on GitHub.
- **Watch the dashboard** — live per-PR progress, decisions, layer results, and a flagged-accounts view with unban controls.

## 🧠 Implementation Overview

Review pipeline — a strict sequential gate ([`backend/app/pipeline/graph.py`](backend/app/pipeline/graph.py)). A PR that fails any layer never reaches the next; it routes straight to flag + decline.

```mermaid
flowchart LR
    W[Webhook / startup scan] --> PI[Prompt injection]
    PI -->|pass| SP[Spam & quality]
    SP -->|pass| MC[Malicious code]
    MC -->|pass| SU[Summarize] --> AP[Approve + rewrite PR]
    PI -->|fail| FL[Flag account]
    SP -->|fail| FL
    MC -->|fail| FL
    FL --> DC[Decline PR]
```

RAG knowledge base — ingestion embeds on CPU; retrieval is hybrid ([`backend/app/services/ingestion.py`](backend/app/services/ingestion.py), [`backend/app/services/rag.py`](backend/app/services/rag.py)).

```mermaid
flowchart LR
    R[Repo files + issues] --> C[Chunk] --> E[Embed on CPU<br/>fastembed bge-small] --> V[(pgvector)]
    Q[PR query] --> H[Hybrid BM25 + vector] 
    V --> H --> CTX[Context for LLM]
```

- **Provider + key resolution** — chat routes to Groq / Gemini / Ollama; the agent owner's encrypted key wins, else the env default. Resolved once per run and carried on pipeline state. See [`backend/app/services/llm.py`](backend/app/services/llm.py).
- **Local embeddings, graceful fallback** — `fastembed` runs an ONNX model on CPU (no key, no GPU). If it can't load, retrieval degrades to BM25-only. See [`backend/app/services/embeddings.py`](backend/app/services/embeddings.py).
- **Detection layers** — regex/static fast-paths plus an LLM judge with robust JSON parsing; dual-use code patterns are sent to the model instead of auto-declined. See [`backend/app/pipeline/nodes/`](backend/app/pipeline/nodes/).
- **Background processing** — PRs run in-process via FastAPI `BackgroundTasks`; a startup scan self-heals PRs missed during downtime. See [`backend/app/tasks.py`](backend/app/tasks.py).
- **Encrypted secrets** — user API keys are Fernet-encrypted at rest, keyed off `SECRET_KEY`. See [`backend/app/core/security.py`](backend/app/core/security.py).

## 🛠️ Tech Stack

| Category | Technology | Purpose |
| --- | --- | --- |
| Backend framework | FastAPI + Uvicorn | Async HTTP API + in-process background tasks |
| Pipeline | LangGraph | Stateful multi-layer PR review graph |
| Database | PostgreSQL 16 + pgvector | Relational data + vector similarity search |
| ORM / migrations | SQLAlchemy (async) + asyncpg + Alembic | Data access and schema migrations |
| Embeddings | fastembed (`BAAI/bge-small-en-v1.5`, 384-dim) | Local CPU RAG embeddings, no external service |
| LLM | Groq / Google Gemini / Ollama | Injection detection, spam scoring, PR summarization |
| Retrieval | Hybrid BM25 + pgvector cosine | Repo/issue context for the pipeline |
| Auth | JWT (python-jose) + bcrypt, GitHub/Google OAuth | Accounts and sessions |
| Secrets | cryptography (Fernet) | Encrypt user-supplied API keys at rest |
| Frontend | Next.js 14 + React 18 + TypeScript | Dashboard SPA (App Router) |
| UI | Tailwind CSS + shadcn/ui (Radix) + lucide-react | Components, theming (dark/light) |
| Data fetching | SWR | Client-side data fetching + caching |
| Deployment | Vercel (frontend) + Render (backend) + Neon (Postgres) | Free-tier friendly hosting |

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with the `pgvector` extension (local install, or a free Neon database)
- A Groq API key (free — [console.groq.com/keys](https://console.groq.com/keys)); Gemini key or local Ollama optional

### Environment

The root `.env.example` documents every variable. Copy it to `backend/.env`:

```bash
cp .env.example backend/.env
```

Then set at minimum:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/prguardian
SECRET_KEY=<long-random-string>
LLM_PROVIDER=groq
GROQ_API_KEY=<your-groq-key>
EMBED_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384
```

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000` (`/docs` for the OpenAPI UI). Embeddings download once on first use (~130 MB) and run on CPU. PR processing happens in-process — no separate worker.

### Frontend

```bash
cd frontend
cp .env.example .env.local   # optional — defaults to http://localhost:8000
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`. It targets `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

### Deploying

- **Frontend → Vercel** — set root dir `frontend`, env `NEXT_PUBLIC_API_BASE_URL=<backend-url>`.
- **Database → Neon** — free Postgres + pgvector. Use `postgresql+asyncpg://…` and drop `?sslmode=require`.
- **Backend → Render** — a native-Python blueprint ships in [`render.yaml`](render.yaml) (no Docker). Python is pinned to 3.11 via [`backend/runtime.txt`](backend/runtime.txt) so fastembed's wheels install cleanly. Migrations auto-run on boot.

fastembed needs ~300–400MB RAM; on a 512MB instance it may fall back to BM25-only retrieval (the app keeps working).

### Testing the flow locally

1. Open `http://localhost:3000`, create an account, and sign in.
2. Connect a GitHub account and create an agent on a repo you own; wait for ingestion to finish on the agent page.
3. Expose the backend for webhooks (e.g. `ngrok http 8000`) and point a GitHub webhook at `<public-url>/webhooks/github` (event: Pull requests, secret = `GITHUB_WEBHOOK_SECRET`). No public URL? Use the agent's **Detect PRs** / **Sync** action to pull open PRs manually.
4. Open a test PR on the repo. Watch it move through the pipeline on the dashboard; a malicious/spam/injection PR is declined, a clean one is rewritten and approved.

## 🔌 API Endpoints

Base URL `http://localhost:8000`. Auth is a Bearer JWT unless noted.

| Method | Endpoint | Description | Auth |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | Create an account | None |
| POST | `/api/auth/login` | Get an access token | None |
| GET | `/api/auth/me` | Current user | Bearer |
| GET | `/api/settings` | Read LLM provider + which keys are set | Bearer |
| PUT | `/api/settings` | Set provider + bring-your-own API keys | Bearer |
| GET | `/api/agents` | List your agents | Bearer |
| POST | `/api/agents` | Create an agent (starts ingestion) | Bearer |
| GET | `/api/agents/{id}` | Get an agent | Bearer |
| PATCH | `/api/agents/{id}` | Update an agent | Bearer |
| DELETE | `/api/agents/{id}` | Delete an agent | Bearer |
| POST | `/api/agents/{id}/sync` | Re-ingest + detect open PRs | Bearer |
| POST | `/api/agents/{id}/detect-prs` | Detect + process open PRs | Bearer |
| GET | `/api/agents/{id}/progress` | Ingestion + PR progress | Bearer |
| GET | `/api/agents/{id}/ingestion-logs` | Ingestion step logs | Bearer |
| GET | `/api/events` | List PR decision events | Bearer |
| GET | `/api/events/processing-status` | Live per-PR processing status | Bearer |
| GET | `/api/events/pr-detail/{agent_id}/{pr_number}` | Full PR detail | Bearer |
| GET | `/api/dashboard/stats` | Aggregate stats | Bearer |
| GET | `/api/dashboard/per-agent` | Per-agent stats | Bearer |
| GET | `/api/dashboard/flagged-accounts` | Flagged / banned accounts | Bearer |
| POST | `/api/dashboard/flagged-accounts/{username}/unflag` | Unflag an account | Bearer |
| GET | `/api/github/oauth/authorize` | Start GitHub OAuth | Bearer |
| GET | `/api/github/connections` | List GitHub connections | Bearer |
| GET | `/api/github/connections/{id}/repos` | List repos for a connection | Bearer |
| GET | `/api/google/oauth/authorize` | Start Google OAuth | Bearer |
| POST | `/webhooks/github` | GitHub PR webhook receiver | HMAC signature |

## 📁 Project Structure

```text
PR Guardian/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI app, lifespan, startup scan
│   │   ├── tasks.py               # In-process background PR processing
│   │   ├── api/                   # Route handlers (auth, agents, settings, webhooks, …)
│   │   ├── core/                  # config, database, security, metrics
│   │   ├── models/                # SQLAlchemy models (user, agent, pr_event, …)
│   │   ├── schemas/               # Pydantic request/response schemas
│   │   ├── pipeline/
│   │   │   ├── graph.py           # LangGraph wiring (the review gate)
│   │   │   ├── runner.py          # Pipeline entrypoint + state build
│   │   │   └── nodes/             # prompt_injection, spam, malicious_code, summary, …
│   │   └── services/              # llm, embeddings, rag, ingestion, github, vectorstore
│   ├── alembic/                   # Migrations
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Marketing landing page
│   │   ├── (auth)/                # login, signup, oauth callback
│   │   └── (app)/                 # dashboard, agents, flagged, settings
│   ├── components/                # ui/ (shadcn) + custom/ (sidebar, app-shell, theme)
│   ├── lib/                       # api client, types, auth helpers
│   └── package.json
├── render.yaml                    # Render backend blueprint (native Python)
└── .env.example
```
