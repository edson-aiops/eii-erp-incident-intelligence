# EII — Arquitetura Multi-HCM
## ERP Incident Intelligence v2.0

---

## Escopo de Sistemas e Módulos

```
EII Multi-HCM Incident Intelligence
│
├── 🔵 HCM HCM
│   ├── Payroll (PT / EN)
│   ├── Benefits (PT / EN)
│   ├── Recruiting (PT / EN)
│   └── Time & Attendance (PT / EN)
│
├── 🟢 HCM
│   ├── Folha de Pagamento (PT)
│   ├── Gestão de Benefícios (PT)
│   ├── Recrutamento & Seleção (PT)
│   ├── Ponto & Jornada (PT)
│   └── eSocial / Obrigações Legais (PT)
│
└── 🟠 HCM
    ├── HCM (ex-HCM)
    │   ├── Payroll / Folha (PT / EN)
    │   ├── Benefits / Benefícios (PT / EN)
    │   └── HR Core / Dados do Funcionário (PT / EN)
    ├── HCM (PMEs)
    │   ├── Payroll / Folha (PT / EN)
    │   └── Time & Attendance / Ponto (PT / EN)
    └── HCM (Workforce Management)
        ├── Workforce Management / Escala (PT / EN)
        └── Time & Attendance / Ponto (PT / EN)
```

---

## Knowledge Base — Estrutura de Coleções ChromaDB

```
data/kb/
├── hcm_payroll_pt
├── hcm_payroll_en
├── hcm_benefits_pt
├── hcm_benefits_en
├── hcm_recruiting_pt
├── hcm_recruiting_en
├── hcm_time_attendance_pt
├── hcm_time_attendance_en
│
├── hcm_folha_pt
├── hcm_beneficios_pt
├── hcm_recrutamento_pt
├── hcm_ponto_pt
├── hcm_esocial_pt
│
├── hcm_pro_payroll_pt
├── hcm_pro_payroll_en
├── hcm_pro_benefits_pt
├── hcm_pro_benefits_en
├── hcm_pro_hr_core_pt
├── hcm_pro_hr_core_en
├── hcm_ready_payroll_pt
├── hcm_ready_payroll_en
├── hcm_ready_time_pt
├── hcm_ready_time_en
├── hcm_dimensions_workforce_pt
├── hcm_dimensions_workforce_en
├── hcm_dimensions_time_pt
└── hcm_dimensions_time_en
```

Total: **26 coleções** — roteamento automático por sistema + módulo + idioma.

---

## Fluxo do Pipeline LangGraph

```
Incident Log Input
       │
       ▼
┌──────────────────────────────┐
│   HCM Router                 │  ← Detecta: HCM | Senior | HCM
│   (LogAnalysisAgent Step 1)  │    Detecta: módulo + idioma
└──────────────┬───────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
  HCM   Senior    HCM
  KB Route  KB Route  KB Route
       │       │       │
       └───────┼───────┘
               │
               ▼
┌──────────────────────────────┐
│   LogAnalysisAgent           │  → Classifica erro por tipo
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   RootCauseDiagnosisAgent    │  → Identifica causa raiz
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   CRAG Resolution            │  → Retrieve → Evaluate → Generate
│   ├── Retrieve (KB correta)  │     ou Self-RAG se KB insuficiente
│   ├── Relevance Check        │
│   └── Generate / Correct     │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   Langfuse Trace             │  → Spans por agente + scores RAGAS
└──────────────────────────────┘
               │
               ▼
        Resolução Final
```

---

## Roadmap de Fases (atualizado)

| Fase | Entrega | Sistemas |
|------|---------|---------|
| **1 — Fundação** ✅ | App Gradio + Docker + HF Spaces | — |
| **2 — KB Multi-HCM** | Knowledge base simulada + ChromaDB + Groq | HCM + Senior + HCM |
| **3 — LangGraph** | HCM Router + LogAnalysis + RootCause + CRAG | Todos |
| **4 — Langfuse** | Traces + spans + scores por sistema/módulo | Todos |
| **5 — RAGAS** | Avaliação faithfulness/relevancy por coleção | Todos |

---

## Stack Tecnológico Final

| Componente | Tecnologia | Custo |
|---|---|---|
| Deploy | HuggingFace Spaces (Docker) | Gratuito |
| LLM | Groq API — Llama 3.1 70B | Gratuito |
| Vector Store | ChromaDB in-memory | Gratuito |
| Embeddings | Groq / nomic-embed via API | Gratuito |
| Observabilidade | Langfuse Cloud | Gratuito (5k traces/mês) |
| Avaliação | RAGAS | Gratuito |
| **Total** | | **$0/mês** |
