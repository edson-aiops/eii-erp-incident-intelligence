---
title: EII — ERP Incident Intelligence
themoji: ⚙️
colorFrom: red
colorTo: red
sdk: docker
pinned: true
license: mit
short_description: eSocial XML Diagnostics with CRAG + Human-in-the-Loop
---

# ⚙️ EII — ERP Incident Intelligence

**Automated eSocial rejection diagnostics powered by AI**  
eSocial · CRAG Pipeline · SmartRouter Multi-LLM · Human-in-the-Loop · LGPD

> ⚠️ **Status:** Technical portfolio prototype. Not validated in production with real data.  
> The Knowledge Base covers the most common cases. Results vary based on event and context.

---

## 🎯 The Problem

When an eSocial event is rejected by the government, the analyst receives an XML error code.
Diagnosing the root cause and the correct resolution steps requires specific expertise in labor law,
eSocial layouts, and IRS (Receita Federal) business rules.

EII transforms that XML into a structured diagnosis in seconds — with automatic routing
of sensitive data to ensure LGPD compliance.

---

## 💡 How to Use

1. Access the **🚨 Diagnostics** tab
2. Paste the XML return from eSocial (or load an example)
3. Click **🔍 Analyze XML**
4. Review the generated diagnosis — root cause + resolution steps
5. Access **✋ Approval (HITL)** to register your decision as an analyst

---

## 🏗️ Architecture

```
Rejected XML
      │
      ▼
[xml_parser.py] → extracts event, error code, fields
      │
      ▼
[pii_detector.py] → detects CPF / CNPJ / NIS
      │
   ┌──┴──┐
PII?    Clean
 │        │
Ollama  Groq    ← SmartRouter (3 phases)
gemma2  Llama 3.3 70B
  └──┬──┘
     │
     ▼
[CRAG Pipeline]
 Retrieve → Grade → Generate → Evaluate (80%) → Reflexion
     │
     ▼
[HITL Gate] → analyst validates before closing
     │
     ▼
[SQLite Audit Log] + LangSmith @traceable
```

**CRAG (Corrective RAG):** retrieves documents from vector KB → LLM evaluates relevance →
generates diagnosis with filtered context → EvaluatorAgent validates quality (80% threshold) →
Reflexion auto-corrects if necessary.

---

## 📚 Knowledge Base

73 manually curated eSocial incidents:

| Priority | Range | Examples |
| --- | --- | --- |
| 🔴 Critical | KB001–KB020 | S-1200/MA-100, S-2200/E469, S-5001 |
| 🟡 High | KB021–KB053 | DCTFWeb, EFD-Reinf, E214, E215 |
| 🟢 Medium | KB054–KB073 | S-1000/E100, S-1005, registration validations |

Each item contains: event, error code, root cause, resolution steps, tags, and
`validacoes` counter for confidence boost in Qdrant.

---

## ⚙️ Configuration

Add the Secret in HuggingFace Space:

```
GROQ_API_KEY=your_key_here
```

Free key at: [console.groq.com](https://console.groq.com)

> The public demo uses Groq with PII scrubbing before sending.  
> For use with real data, run the local version with Ollama (full LGPD).

---

## 🔒 Human-in-the-Loop as a Design Principle

> No resolution is marked as executed without explicit approval from a human analyst.

In eSocial contexts, automated actions without oversight can cause inconsistencies in CNIS,
tax assessments, and labor liabilities. HITL is an intentional design decision — not
a technical limitation.

For incidents with **CRITICAL** severity, the system requires confirmation of 3 checkboxes before
recording any resolution.

---

## 🛠️ Stack

| Layer | Technology |
| --- | --- |
| Primary LLM | Llama 3.3 70B via Groq API |
| LGPD LLM (local) | gemma2:2b via Ollama |
| SmartRouter | 9 providers — Groq, Claude, Gemini, Kimi, Cerebras, Qwen, DeepSeek, Mistral, Ollama |
| Vector Store | Qdrant Cloud (prod) / ChromaDB (dev) |
| Embeddings | all-MiniLM-L6-v2 (384 dims, Cosine) |
| UI | Gradio 4.44.0 |
| Observability | LangSmith @traceable (6 steps) |
| Persistence | SQLite + audit trail |
| MCP Server | fastmcp — `eii_query` and `eii_escalate` |
| Deploy | HuggingFace Spaces (Docker) |

---

## 🔌 MCP Server

EII is exposed as an MCP server via **fastmcp**, allowing integration with Claude and other
LLM agents:

```json
{
  "mcpServers": {
    "eii": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {"GROQ_API_KEY": "your-key"}
    }
  }
}
```

Available tools: `eii_query(xml)` and `eii_escalate(incident_id, status, notes)`.

---

## 🚀 Roadmap

### ✅ Completed (Phase 1–3)

- [x] Base CRAG pipeline with ChromaDB
- [x] KB with 73 curated eSocial incidents
- [x] EvaluatorAgent (80% threshold) + Reflexion auto-correction
- [x] SmartRouter multi-LLM (9 providers, 3 phases)
- [x] ResilientLLM circuit breaker (Groq → Claude → GPT)
- [x] Automatic LGPD routing (PII → Ollama local)
- [x] MCP Server via fastmcp
- [x] Batch processing (ThreadPoolExecutor)
- [x] Mentor Mode + HITL 3-checkbox
- [x] LangSmith @traceable OBS-001
- [x] Dev Container for GitHub Codespaces
- [x] 72 automated tests

### 🔄 In Progress (Phase 4)

- [ ] Migration to Deep Agents v0.5 (`create_deep_agent`)
- [ ] Fork-Join async: 1 subagent per eSocial event in Batch

### ⏳ Planned (Phase 5)

- [ ] Metrics dashboard with real pilot data
- [ ] `/audit/traces` API for auditing
- [ ] IntelAgent — autonomous KB curation
- [ ] Support for EFD-Reinf (R-xxxx) and DCTFWeb
- [ ] REST API for ticketing integration (JIRA, ServiceNow)

---

## 📄 Documentation

| Doc | Description |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | Version history by phase |
| [docs/PRD.md](docs/PRD.md) | Complete Product Requirements Document |
| [CLAUDE.md](CLAUDE.md) | Context for Claude Code — architecture and MCP |
| [smartrouter/README.md](smartrouter/README.md) | SmartRouter documentation |

---

## 👨‍💻 Developer

*Edson Oliveira · Senior IT Systems Analyst · 12+ years in HCM/ERP*  
*AI applied to compliance and HR operations in Brazil · Targeting NOC 21221 — Canada*

[![GitHub](https://img.shields.io/badge/GitHub-eii--erp--incident--intelligence-181717?style=for-the-badge&logo=github)](https://github.com/edson-aiops/eii-erp-incident-intelligence)  
[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-eii--erp--incident--intelligence-FFD21E?style=for-the-badge)](https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence)

---

[![GitHub Repo](https://img.shields.io/badge/GitHub-Full_Code-181717?style=for-the-badge&logo=github)](https://github.com/edson-aiops/eii-erp-incident-intelligence)  
[![Tests](https://img.shields.io/badge/Tests-72_passing-22C55E?style=for-the-badge)](https://github.com/edson-aiops/eii-erp-incident-intelligence/blob/main/tests/test_phase2.py)  
[![MIT License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)  
[![LGPD](https://img.shields.io/badge/LGPD-Privacy_by_Design-009B7D?style=for-the-badge)](docs/PRD.md)  
[![Phase](https://img.shields.io/badge/Phase-3_Complete-3776AB?style=for-the-badge)](CHANGELOG.md)