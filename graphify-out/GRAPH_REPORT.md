# Graph Report - .  (2026-07-03)

## Corpus Check
- Corpus is ~20,657 words - fits in a single context window. You may not need a graph.

## Summary
- 50 nodes · 25 edges · 34 communities (4 shown, 30 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Pipeline Core & RAG|Pipeline Core & RAG]]
- [[_COMMUNITY_Deployment & Ingestion|Deployment & Ingestion]]
- [[_COMMUNITY_Security & Enforcement|Security & Enforcement]]
- [[_COMMUNITY_Webhook & Observability|Webhook & Observability]]
- [[_COMMUNITY_Auth Core|Auth Core]]
- [[_COMMUNITY_App Layout|App Layout]]
- [[_COMMUNITY_Root Layout|Root Layout]]
- [[_COMMUNITY_Homepage|Homepage]]
- [[_COMMUNITY_Auth Layout|Auth Layout]]
- [[_COMMUNITY_Auth Guard|Auth Guard]]
- [[_COMMUNITY_API Error Type|API Error Type]]
- [[_COMMUNITY_Auth Token Clear|Auth Token Clear]]
- [[_COMMUNITY_Auth Token Get|Auth Token Get]]
- [[_COMMUNITY_Auth Token Set|Auth Token Set]]
- [[_COMMUNITY_Auth Session Hook|Auth Session Hook]]
- [[_COMMUNITY_Agent Type|Agent Type]]
- [[_COMMUNITY_Agent Create Input|Agent Create Input]]
- [[_COMMUNITY_Agent Stats|Agent Stats]]
- [[_COMMUNITY_Dashboard Stats|Dashboard Stats]]
- [[_COMMUNITY_Flagged Account|Flagged Account]]
- [[_COMMUNITY_GitHub Installation|GitHub Installation]]
- [[_COMMUNITY_GitHub Install Result|GitHub Install Result]]
- [[_COMMUNITY_GitHub Repo|GitHub Repo]]
- [[_COMMUNITY_LLM Provider|LLM Provider]]
- [[_COMMUNITY_PR Decision|PR Decision]]
- [[_COMMUNITY_PR Event|PR Event]]
- [[_COMMUNITY_PR Layer|PR Layer]]
- [[_COMMUNITY_Token|Token]]
- [[_COMMUNITY_Vector DB Type|Vector DB Type]]
- [[_COMMUNITY_Utility Function|Utility Function]]
- [[_COMMUNITY_PR Guardian Root|PR Guardian Root]]
- [[_COMMUNITY_Badge Component|Badge Component]]
- [[_COMMUNITY_Button Component|Button Component]]
- [[_COMMUNITY_Input Component|Input Component]]

## God Nodes (most connected - your core abstractions)
1. `Multi-Layer LangGraph PR Pipeline` - 6 edges
2. `Layer 1: Spam and Useless PR Detection` - 4 edges
3. `Account Flagging and Auto-Ban System` - 4 edges
4. `Layer 2: Malicious Code Detection` - 3 edges
5. `Layer 3: Hijack-Proof Detection` - 3 edges
6. `Layer 4: Summary and Title Rewriting` - 3 edges
7. `RAG Knowledge Base (Repo + Issues)` - 3 edges
8. `RAG Ingestion and Chunk Embedding Pipeline` - 3 edges
9. `GitHub Webhook Receiver` - 3 edges
10. `Belt-and-Suspenders Decline Logic` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Opt-In Ollama Local LLM Profile` --semantically_similar_to--> `LLM Provider Abstraction (Ollama or Gemini)`  [INFERRED] [semantically similar]
  docker-compose.yml → README.md
- `Async-First Python Ecosystem` --conceptually_related_to--> `Multi-Layer LangGraph PR Pipeline`  [INFERRED]
  backend/requirements.txt → README.md
- `Session` --references--> `User`  [EXTRACTED]
  frontend/lib/auth.ts → frontend/lib/types.ts

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Sequential PR Detection Pipeline Flow** — pr_guardian_readme_layer1_spam, pr_guardian_readme_layer2_malicious, pr_guardian_readme_layer3_hijack, pr_guardian_readme_layer4_summary, pr_guardian_readme_account_flagging, pr_guardian_readme_multi_layer_pipeline [EXTRACTED 1.00]
- **Docker Compose Service Topology** — pr_guardian_docker_compose_deployment, pr_guardian_docker_compose_ollama_profile, pr_guardian_readme_github_webhook, pr_guardian_readme_pr_guardian [INFERRED 0.75]

## Communities (34 total, 30 thin omitted)

### Community 0 - "Pipeline Core & RAG"
Cohesion: 0.40
Nodes (6): Async-First Python Ecosystem, Conventional Commits PR Title Format, Layer 1: Spam and Useless PR Detection, Layer 4: Summary and Title Rewriting, Multi-Layer LangGraph PR Pipeline, RAG Knowledge Base (Repo + Issues)

### Community 1 - "Deployment & Ingestion"
Cohesion: 0.40
Nodes (5): Multi-Container Docker Compose Deployment, Opt-In Ollama Local LLM Profile, 512-Token Overlapping Chunk Strategy, LLM Provider Abstraction (Ollama or Gemini), RAG Ingestion and Chunk Embedding Pipeline

### Community 2 - "Security & Enforcement"
Cohesion: 0.67
Nodes (4): Account Flagging and Auto-Ban System, Belt-and-Suspenders Decline Logic, Layer 2: Malicious Code Detection, Layer 3: Hijack-Proof Detection

### Community 3 - "Webhook & Observability"
Cohesion: 0.50
Nodes (4): GitHub Webhook Receiver, System Hardening Strategy, HMAC-SHA256 Webhook Signature Verification, Prometheus Metrics Endpoint

## Knowledge Gaps
- **37 isolated node(s):** `AppLayout`, `AuthLayout`, `RootLayout`, `HomePage`, `AuthGuard` (+32 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RAG Knowledge Base (Repo + Issues)` connect `Pipeline Core & RAG` to `Deployment & Ingestion`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `Multi-Layer LangGraph PR Pipeline` connect `Pipeline Core & RAG` to `Security & Enforcement`, `Webhook & Observability`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `RAG Ingestion and Chunk Embedding Pipeline` connect `Deployment & Ingestion` to `Pipeline Core & RAG`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **What connects `AppLayout`, `AuthLayout`, `RootLayout` to the rest of the system?**
  _37 weakly-connected nodes found - possible documentation gaps or missing edges._