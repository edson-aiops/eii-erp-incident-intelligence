# EII — Arquitetura Multi-HCM
## ERP Incident Intelligence v2.0

---

## Escopo de Sistemas e Módulos

```
EII Multi-HCM Incident Intelligence
│
├── 🔵 WORKDAY HCM
│   ├── Payroll (PT / EN)
│   ├── Benefits (PT / EN)
│   ├── Recruiting (PT / EN)
│   └── Time & Attendance (PT / EN)
│
├── 🟢 SENIOR HCM
│   ├── Folha de Pagamento (PT)
│   ├── Gestão de Benefícios (PT)
│   ├── Recrutamento & Seleção (PT)
│   ├── Ponto & Jornada (PT)
│   └── eSocial / Obrigações Legais (PT)
│
└── 🟠 UKG
    ├── UKG Pro (ex-UltiPro)
    │   ├── Payroll / Folha (PT / EN)
    │   ├── Benefits / Benefícios (PT / EN)
    │   └── HR Core / Dados do Funcionário (PT / EN)
    ├── UKG Ready (PMEs)
    │   ├── Payroll / Folha (PT / EN)
    │   └── Time & Attendance / Ponto (PT / EN)
    └── UKG Dimensions (Workforce Management)
        ├── Workforce Management / Escala (PT / EN)
        └── Time & Attendance / Ponto (PT / EN)
```

---

## Knowledge Base — Estrutura de Coleções ChromaDB

```
data/kb/
├── workday_payroll_pt
├── workday_payroll_en
├── workday_benefits_pt
├── workday_benefits_en
├── workday_recruiting_pt
├── workday_recruiting_en
├── workday_time_attendance_pt
├── workday_time_attendance_en
│
├── senior_folha_pt
├── senior_beneficios_pt
├── senior_recrutamento_pt
├── senior_ponto_pt
├── senior_esocial_pt
│
├── ukg_pro_payroll_pt
├── ukg_pro_payroll_en
├── ukg_pro_benefits_pt
├── ukg_pro_benefits_en
├── ukg_pro_hr_core_pt
├── ukg_pro_hr_core_en
├── ukg_ready_payroll_pt
├── ukg_ready_payroll_en
├── ukg_ready_time_pt
├── ukg_ready_time_en
├── ukg_dimensions_workforce_pt
├── ukg_dimensions_workforce_en
├── ukg_dimensions_time_pt
└── ukg_dimensions_time_en
```

Total: **26 coleções** — roteamento automático por sistema + módulo + idioma.

---

## Fluxo do Pipeline LangGraph

```
Incident Log Input
       │
       ▼
┌──────────────────────────────┐
│   HCM Router                 │  ← Detecta: Workday | Senior | UKG
│   (LogAnalysisAgent Step 1)  │    Detecta: módulo + idioma
└──────────────┬───────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
  Workday   Senior    UKG
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
| **2 — KB Multi-HCM** | Knowledge base simulada + ChromaDB + Groq | Workday + Senior + UKG |
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
