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

---

## MCP Exposure (Phase 3)

EII is exposed as an MCP server via **fastmcp**, enabling Claude and other MCP-compatible clients to call the CRAG diagnostic pipeline directly — without the Gradio UI.

### New files

| File | Role |
|------|------|
| `eii_handlers.py` | Pure Python handlers — no Gradio. Extracted `query_incident()` and `escalate_incident()` with their own DB layer (same SQLite file via `DB_PATH` env var). |
| `mcp_server.py` | fastmcp server exposing `eii_query` and `eii_escalate` as MCP tools. |

### Run the MCP server

```bash
# Requires: GROQ_API_KEY set in environment
pip install fastmcp
python mcp_server.py
```

The server starts in stdio mode (default for MCP clients). To use with Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eii": {
      "command": "python",
      "args": ["/path/to/eii-brasil/mcp_server.py"],
      "env": { "GROQ_API_KEY": "your-key-here" }
    }
  }
}
```

### Tool contracts

**`eii_query(xml_rejeicao: str) → dict`**

Analyzes an eSocial XML return through the CRAG pipeline. Persists result as `PENDING`.

| Output field | Type | Description |
|---|---|---|
| `incident_id` | str | Generated ID, e.g. `INC-20250307-143022` |
| `evento` | str | eSocial event code, e.g. `S-1200` |
| `codigo_erro` | str | Error codes from the XML response |
| `severidade` | str | `CRÍTICO` \| `ALTO` \| `MÉDIO` \| `BAIXO` |
| `confianca` | str | `ALTA` \| `MÉDIA` \| `BAIXA` (calibrated via logprobs) |
| `fonte` | str | `KB_MATCH` \| `LLM_FALLBACK` |
| `causa_raiz` | str | Technical root cause explanation |
| `passos_resolucao` | list[str] | Ordered resolution steps |
| `alerta_hitl` | str | Human review alert / escalation reason |
| `_meta` | dict | Pipeline metadata (logprob_sim, eval_iterations, reflexion, etc.) |

**`eii_escalate(incident_id: str, status: str, notes: str = "") → dict`**

Records analyst decision for a `PENDING` incident (Human-in-the-Loop).

| Arg | Values |
|---|---|
| `status` | `"APROVADO"` or `"REJEITADO"` |
| `notes` | Analyst rationale (recommended for audit trail) |

Returns: `{ incident_id, status, decided_at, message }`

### Test locally (no GROQ_API_KEY needed for unit tests)

```bash
# Run all 72 unit tests — zero network calls
python -m pytest tests/test_phase2.py -v

# Smoke-test the handler layer directly
python -c "
import os; os.environ['GROQ_API_KEY'] = 'your-key'
from eii_handlers import query_incident
print(query_incident('<your-xml-here>'))
"
```

### Design constraints

- `app.py`, `crag_pipeline.py`, and `tests/` are **not modified** by the MCP layer.
- `eii_handlers.py` mirrors the DB schema and `DB_PATH` resolution from `app.py` exactly — both share the same SQLite file when run in the same environment.
- The MCP server is stateless per request; the `_collection` (ChromaDB) is lazily initialized once per process.
