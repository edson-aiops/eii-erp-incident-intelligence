# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the app locally:**
```bash
python app/main.py
```
App runs at http://localhost:7860

**Validate project structure (Phase 1 checks):**
```bash
python tests/validate_phase1.py
```
Run from the project root — the script auto-navigates there.

**Build and run with Docker:**
```bash
docker build -t eii .
docker run -p 7860:7860 --env-file .env eii
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Architecture

EII is a **multi-HCM AIOps application** for resolving incidents in Workday, Senior HCM, and UKG systems. It is deployed to HuggingFace Spaces via Docker.

### Current State: Phase 1 (Foundation)
The app (`app/main.py`) is a single-file Gradio application with stub logic. It shows the UI and routing structure but does not yet call any LLM or vector store — all analysis responses are placeholder text.

### Target Architecture (Phases 2–5)
```
Incident Log → HCM Router → LogAnalysisAgent → RootCauseDiagnosisAgent → CRAG Resolver → Response
                  │
                  └── Routes to one of 26 ChromaDB collections by system + module + language
```

**Planned pipeline agents (LangGraph):**
- `HCMRouter` — detects system (Workday/Senior/UKG), module, and language
- `LogAnalysisAgent` — classifies error type
- `RootCauseDiagnosisAgent` — identifies root cause
- `CRAG Resolver` — Retrieve → Relevance Check → Generate/Correct with self-RAG fallback

**Observability:** Langfuse (one span per agent, RAGAS scores for faithfulness/relevancy)

### Knowledge Base Structure
26 ChromaDB collections under `data/kb/`, named `{system}_{module}_{lang}` (e.g., `workday_payroll_pt`, `senior_esocial_pt`, `ukg_pro_benefits_en`). The `data/` directory is mounted in Docker and kept empty via `.gitkeep` until Phase 2.

### Environment Variables
Required API keys (set in `.env` locally or via HuggingFace Spaces secrets):
- `GROQ_API_KEY` — Groq API for Llama 3.1 70B (LLM + embeddings)
- `LANGFUSE_SECRET_KEY` — Langfuse observability
- `LANGFUSE_PUBLIC_KEY` — Langfuse observability

### HuggingFace Spaces Deployment
The README.md contains YAML front-matter required by HuggingFace Spaces (`sdk: docker`, `title`, `emoji`, `colorFrom`). The Dockerfile exposes port 7860, which is mandatory for HF Spaces. Any `git push` to the connected Space triggers an automatic redeploy.

### Phase Roadmap
| Phase | Status | Deliverable |
|-------|--------|-------------|
| 1 — Foundation | ✅ Done | Gradio app + Docker + HF Spaces |
| 2 — KB Multi-HCM | ⏳ Next | Simulated KB + ChromaDB + Groq LLM |
| 3 — LangGraph | ⏳ | HCM Router + agents + CRAG |
| 4 — Langfuse | ⏳ | Traces + spans per agent |
| 5 — RAGAS | ⏳ | Faithfulness/relevancy evaluation per collection |
