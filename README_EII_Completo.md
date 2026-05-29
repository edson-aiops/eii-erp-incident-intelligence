# EII — ERP Incident Intelligence

<div align="center">

[![HuggingFace Space](https://img.shields.io/badge/🤗_HuggingFace-Demo_Pública-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/EdsonPO/eii-incident-intelligence)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![LGPD](https://img.shields.io/badge/LGPD-Privacy_by_Design-009B7D?style=for-the-badge)](https://www.gov.br/lgpd)
[![LangSmith](https://img.shields.io/badge/LangSmith-OBS--001-F97316?style=for-the-badge)](https://smith.langchain.com)
[![Tests](https://img.shields.io/badge/Tests-72_passed-22C55E?style=for-the-badge)](tests/)

---

**🇧🇷 Sistema Inteligente de Diagnóstico de Incidentes eSocial com IA e Conformidade LGPD Total**

**🇬🇧 AI-Powered eSocial Incident Diagnostics with Full LGPD Compliance**

*De 15–45 minutos para ~2–5 segundos por rejeição XML · From 15–45 minutes to ~2–5 seconds per XML rejection*

</div>

---

## Índice / Table of Contents

- [🇧🇷 Versão em Português](#-versão-em-português)
  - [O Problema](#o-problema)
  - [Como Funciona na Prática](#como-funciona-na-prática)
  - [Exemplo Real de Uso](#exemplo-real-de-uso)
  - [Demo Pública vs Versão Local](#demo-pública-vs-versão-local)
  - [Arquitetura Detalhada](#arquitetura-detalhada)
  - [Como Rodar Localmente](#como-rodar-localmente)
  - [Stack Tecnológica](#stack-tecnológica)
  - [Métricas e Impacto de Negócio](#métricas-e-impacto-de-negócio)
  - [Roadmap](#roadmap)
  - [Documentação Relacionada](#documentação-relacionada)
- [🇬🇧 English Version](#-english-version)
  - [The Problem](#the-problem)
  - [How It Works](#how-it-works)
  - [Real Usage Example](#real-usage-example)
  - [Public Demo vs Local Version](#public-demo-vs-local-version)
  - [Detailed Architecture](#detailed-architecture)
  - [Running Locally](#running-locally)
  - [Technology Stack](#technology-stack)
  - [Metrics & Business Impact](#metrics--business-impact)
  - [Roadmap (EN)](#roadmap-en)
- [👨‍💻 Sobre o Desenvolvedor / About the Developer](#-sobre-o-desenvolvedor--about-the-developer)
- [📄 Licença / License](#-licença--license)
- [📞 Suporte e Contribuição / Support & Contribution](#-suporte-e-contribuição--support--contribution)

---

## 🇧🇷 Versão em Português

### O Problema

O **eSocial** é o sistema de escrituração digital das obrigações fiscais, previdenciárias e trabalhistas criado pela Receita Federal do Brasil (RFB). Empresas de todos os portes são obrigadas a enviar eventos XML com dados de folha de pagamento, admissões, demissões, afastamentos e muito mais — e qualquer erro gera uma **rejeição imediata com código de erro técnico**.

**O cenário atual nas empresas:**

| Situação | Realidade |
|----------|-----------|
| Tempo médio de diagnóstico | **15 a 45 minutos** por rejeição |
| Volume mensal de rejeições | Dezenas a centenas por empresa de médio porte |
| Custo por analista/hora | R$ 50–120/hora (folha + encargos) |
| Risco de multa por atraso | Até R$ 1.812,87 por evento |
| Dados no XML | CPF, CNPJ, NIS, salários — **dados sensíveis LGPD** |

O analista de RH ou DP recebe o XML rejeitado, precisa identificar o evento (`S-1200`, `S-2200`, `S-5001`...), localizar o código de erro (`MA-100`, `E-9999`...), consultar o Manual de Orientação do eSocial (mais de 800 páginas), cruzar com a legislação vigente, e só então montar um plano de ação — tudo isso manualmente, evento por evento.

**O EII resolve exatamente esse gargalo.**

---

### Como Funciona na Prática

O EII recebe o XML rejeitado pelo eSocial, detecta automaticamente se há dados pessoais, roteia para o processador correto (local ou nuvem), executa o pipeline CRAG e entrega um diagnóstico estruturado em segundos.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EII — FLUXO COMPLETO                         │
└─────────────────────────────────────────────────────────────────────┘

  [XML Rejeitado pelo eSocial]
           │
           ▼
  ┌─────────────────┐
  │   xml_parser.py  │  ← Parse evento, código de erro, campos
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ pii_detector.py  │  ← Detecta CPF / CNPJ / NIS via Regex
  └────────┬────────┘
           │
     ┌─────┴─────┐
     │           │
  PII Found   PII Clean
     │           │
     ▼           ▼
 [Ollama]    [Groq API]       ← SmartRouter (Fase 1: Rules implementada; Fases 2-3: roadmap)
 Local LLM   Cloud LLM
 Gemma4 26B  Llama 3.3 70B
     │           │
     └─────┬─────┘
           │
           ▼
  ┌──────────────────────────────────────┐
  │         CRAG Pipeline                │
  │                                      │
  │  1. Retrieve   → Qdrant / ChromaDB   │
  │  2. Grade      → Relevance Check     │
  │  3. Generate   → nó generate (diagnóstico) │
  │  4. Evaluate   → nó evaluate (avaliação 80%) │
  │  5. Reflexion  → Auto-correção       │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │           HITL Gate                  │
  │  ☐ Causa raiz validada               │
  │  ☐ Passos de resolução confirmados   │
  │  ☐ Risco de reincidência avaliado    │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │         Audit Log (SQLite)           │
  │  incident_id · analista_id · SHA-256 │
  │  LangSmith @traceable · versao_kb    │
  └──────────────────────────────────────┘
```

**Passo a passo do fluxo:**

1. **Upload do XML** — analista cola ou faz upload do XML rejeitado na interface Gradio
2. **Parse automático** — `xml_parser.py` extrai evento, código de erro e campos relevantes
3. **Detecção PII** — `pii_detector.py` verifica CPF/CNPJ/NIS com regex calibrada
4. **Roteamento inteligente** — SmartRouter decide: dados sensíveis → Ollama local; dados limpos → Groq
5. **Pipeline CRAG** — Recupera KB, valida relevância, gera diagnóstico, avalia qualidade (80% threshold)
6. **Reflexion** — Se confiança < threshold, o pipeline auto-corrige (ADR-002)
7. **HITL obrigatório** — Para severidade CRÍTICO, analista deve confirmar 3 checkboxes
8. **Audit trail** — Toda decisão persiste no SQLite com metadados completos

---

### Exemplo Real de Uso

**Entrada — XML eSocial Rejeitado:**

```xml
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v03_01_02_00">
  <evtRemun Id="ID1200...">
    <ideEvento>
      <indRetif>1</indRetif>
      <tpAmb>1</tpAmb>
      <procEmi>1</procEmi>
    </ideEvento>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <!-- Evento S-1200 com erro de competência -->
  </evtRemun>
  <Status>
    <cdResposta>401</cdResposta>
    <descResposta>MA-100: Data de início de vigência inválida</descResposta>
  </Status>
</eSocial>
```

**Saída — Diagnóstico EII:**

```json
{
  "incident_id": "INC-20260430-143022",
  "evento": "S-1200",
  "codigo_erro": "MA-100",
  "severidade": "ALTO",
  "confianca": "ALTA",
  "fonte": "KB_MATCH",
  "causa_raiz": "O campo <dtIniValid> contém competência anterior ao início da obrigatoriedade do empregador no eSocial. O evento S-1200 exige que a competência de início de vigência seja igual ou posterior à data de obrigatoriedade definida pelo grupo do empregador (Grupo 2: 2018-07).",
  "passos_resolucao": [
    "1. Verificar a data de obrigatoriedade do empregador no Portal eSocial",
    "2. Corrigir o campo <dtIniValid> para a competência correta",
    "3. Reenviar o evento S-1200 com o campo corrigido",
    "4. Validar no portal eSocial que o retorno é 201 (Sucesso)"
  ],
  "alerta_hitl": "Verifique se há eventos S-1200 anteriores com o mesmo CNPJ que precisam de retificação (indRetif=2)",
  "_meta": {
    "logprob_sim": 0.94,
    "eval_iterations": 1,
    "reflexion_applied": false,
    "retrieval_backend": "qdrant",
    "model_used": "llama-3.3-70b-versatile",
    "versao_kb": "a6f91c4"
  }
}
```

---

### Demo Pública vs Versão Local

| Característica | 🌐 Demo HuggingFace | 💻 Versão Local |
|----------------|---------------------|-----------------|
| URL | [spaces/EdsonPO/eii-incident-intelligence](https://huggingface.co/spaces/EdsonPO/eii-incident-intelligence) | `http://localhost:7860` |
| Arquivo | `app_hf.py` | `app.py` |
| LLM | Groq Cloud (dados anonimizados) | Ollama local (LGPD) + Groq fallback |
| PII handling | Scrubbing antes do envio | Processamento 100% local |
| LGPD compliance | Parcial (dados scrubbed) | **Total** (dados nunca saem da rede) |
| Quando usar | Demonstração, PoC, avaliação | **Produção com dados reais** |
| Custo de infra | Zero (HF Free Tier) | Hardware próprio ou servidor interno |
| Autenticação | Pública | Recomendado: VPN + auth corporativa |

> ⚠️ **Importante:** Para uso com XMLs reais contendo CPF, CNPJ ou dados de empregados, **sempre use a versão local** (`app.py`) com o Ollama configurado. A demo pública aplica scrubbing mas não é certificada para compliance LGPD em produção.

---

### Arquitetura Detalhada

#### Módulo 1: `xml_parser.py` — Parser eSocial

Responsável por extrair informações estruturadas do XML rejeitado. Identifica:

- **Tipo de evento** (S-1000 a S-9999) via namespace e tag raiz
- **Código de erro** (`cdResposta` + `descResposta`)
- **Campos problemáticos** (parsing XPath dos elementos mencionados no erro)
- **Metadados do empregador** (tipo de inscrição, ambiente prod/homolog)

```python
# Exemplo de extração
evento = parser.extract_event_type(xml)  # "S-1200"
codigo = parser.extract_error_code(xml)  # "MA-100"
campos = parser.extract_fields(xml)       # {"dtIniValid": "2017-01", ...}
```

#### Módulo 2: `pii_detector.py` — Detecção de Dados Sensíveis

Aplica regex calibrada para detecção de PII (Personally Identifiable Information) conforme LGPD:

| Tipo de PII | Regex Pattern | Ação |
|-------------|---------------|------|
| CPF | `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` | → Ollama local |
| CNPJ | `\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}` | → Scrub + Cloud |
| NIS/PIS | `\d{3}\.?\d{5}\.?\d{2}-?\d` | → Ollama local |
| Nome completo | Heurística + contexto | → Scrub |

#### Módulo 3: `smartrouter/` — Orquestração Multi-LLM

O SmartRouter implementa roteamento por regras (Fase 1). Fases 2 e 3 estão no roadmap:

```
Fase 1: Rules Engine (implementada)
  ├── PII detectado? → Ollama (local, LGPD)
  ├── Evento crítico S-5001/S-5003? → Claude Haiku
  └── Análise padrão → Groq (Llama 3.3 70B)

Fase 2: Smart Classification (Cerebras 3000 tok/s) — roadmap
  ├── Tarefa de codegen? → Kimi K2
  ├── Contexto longo (>100k tokens)? → Gemini 2.5 Flash
  └── Raciocínio complexo? → Qwen QwQ-32B

Fase 3: Adaptive Routing — roadmap
  └── Aprende com histórico de performance por tipo de evento
```

**ResilientLLM** — Circuit Breaker em cascata:
```
Groq (primário)
  └── Falha 3x em 10min? → Claude Haiku (secundário)
        └── Falha? → GPT-4o-mini (terciário)
              └── Falha? → Modo degradado local
```

#### Módulo 4: `crag_pipeline.py` — Pipeline CRAG

O coração do EII. Implementa **Corrective RAG** com pipeline de 8 nós orquestrado por LangGraph:

| Nó / Etapa | Função | ADR |
|------------|---------|-----|
| `parse` | Parseia XML e extrai metadados | — |
| `router` | Classifica severidade e decide roteamento | — |
| `retrieve` | Busca vetorial no ChromaDB/Qdrant | — |
| `grade` | Filtra documentos irrelevantes com LLM judge | — |
| `generate` | Gera causa raiz + passos de resolução | ADR-001 |
| `evaluate` | Avalia qualidade em 5 critérios (threshold 80%) | ADR-001 |
| `reflexion` | Auto-corrige se qualidade < threshold | ADR-002 |
| `finalize` | Aplica gate de confiança e consolida resultado | ADR-001 |
| `intel` | Insights proativos via IntelAgent | — |

**ADR-001 — Avaliação automática:** 5 critérios avaliados (precisão técnica, acionabilidade, cobertura, clareza, risco), threshold de 80% para aprovação automática. 13 testes unitários.

**ADR-002 — Reflexion:** Quando o avaliador reprova, o pipeline envia o diagnóstico + crítica de volta ao nó generate para auto-correção. Máximo 2 iterações (MAX_ITER=2). 13 testes unitários.

#### Módulo 5: `observability.py` — LangSmith OBS-001

Todos os 6 steps do pipeline são decorados com `@traceable`:

```python
@traceable(name="eii.retrieve", metadata={"kb_version": KB_VERSION})
def retrieve(query: str) -> list[Document]: ...

@traceable(name="eii.evaluate", metadata={"threshold": 0.8})
def evaluate(diagnosis: str, docs: list) -> EvalResult: ...
```

Metadados capturados por run: `esocial_evento`, `codigo_erro`, `analista_id`, `versao_kb`, `logprob_sim`, `eval_iterations`, `model_used`.

#### Módulo 6: `mcp_server.py` — MCP Server (fastmcp)

Expõe o EII como servidor MCP, permitindo que Claude e outros agentes LLM chamem o pipeline diretamente:

```
Tool: eii_query(xml_rejeicao: str) → dict
  └── Executa pipeline CRAG completo, persiste como PENDING

Tool: eii_escalate(incident_id: str, status: str, notes: str) → dict
  └── Registra decisão HITL (APROVADO | REJEITADO)
```

#### Módulo 7: `batch_processor.py` — Processamento em Lote

Tab "Lote" na interface Gradio. Processa múltiplos XMLs em paralelo via `ThreadPoolExecutor`. Ideal para processar lotes de rejeições mensais da competência.

---

### Como Rodar Localmente

#### Pré-requisitos

- Python 3.13+
- [Ollama](https://ollama.ai) instalado (para modo LGPD)
- Conta Groq gratuita — [console.groq.com](https://console.groq.com)
- Conta Qdrant Cloud gratuita — [cloud.qdrant.io](https://cloud.qdrant.io) *(opcional, usa ChromaDB por padrão)*

#### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/edson-aiops/eii-erp-incident-intelligence
cd eii-erp-incident-intelligence

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure o ambiente
cp .env.example .env
# Edite o .env com suas chaves (veja seção abaixo)

# 4. Baixe o modelo LGPD local (opcional mas recomendado)
ollama pull gemma2:2b

# 5. Inicie o app
python app.py
# Interface disponível em: http://localhost:7860
```

#### Variáveis de Ambiente (`.env`)

```env
# ─── LLMs ─────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...              # Obrigatório — LLM principal
ANTHROPIC_API_KEY=sk-ant-...      # Opcional — fallback Claude Haiku
OPENAI_API_KEY=sk-...             # Opcional — fallback GPT-4o-mini

# ─── Vetorização ─────────────────────────────────────────────
QDRANT_URL=https://xxx.qdrant.io  # Opcional — padrão: ChromaDB local
QDRANT_API_KEY=eyJ...             # Obrigatório se QDRANT_URL definido
EII_RETRIEVAL_BACKEND=qdrant      # "qdrant" | "chromadb"

# ─── Observabilidade ─────────────────────────────────────────
LANGSMITH_API_KEY=lsv2_...        # Opcional — tracing OBS-001
LANGSMITH_PROJECT=eii-brasil      # Nome do projeto LangSmith

# ─── Segurança ───────────────────────────────────────────────
DB_PATH=/data/eii.db              # Caminho SQLite (padrão: ./eii.db)

# ─── Ollama (LGPD Mode) ───────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b
```

#### Docker (Opcional)

```bash
# Build
docker build -t eii .

# Run com variáveis de ambiente
docker run -p 7860:7860 --env-file .env eii

# Ou com docker-compose
docker-compose up
```

#### GitHub Codespaces

Clique em **Code → Codespaces → Create codespace** — o `devcontainer.json` configura tudo automaticamente, incluindo extensões Python e variáveis de ambiente de desenvolvimento.

#### Comandos de Teste

```bash
# Suite completa — 72 testes, zero chamadas de rede
python -m pytest tests/test_phase2.py -v

# Teste E2E contra o HuggingFace Space
python scripts/test_e2e_hf.py

# Ingestão da KB no Qdrant
python scripts/ingest_qdrant.py

# Verificação rápida do ambiente
python -c "from crag_pipeline import run_crag; print('OK')"
```

---

### Stack Tecnológica

#### Backend & Aplicação

| Tecnologia | Versão | Papel |
|------------|--------|-------|
| Python | 3.13 | Runtime principal |
| Gradio | 4.44.0 | Interface web (UI + API) |
| FastAPI | integrado | Endpoints REST via Gradio |
| Pydantic | ≥2.0 | Validação de schemas |
| SQLite | stdlib | Audit log de incidentes |
| fastmcp | latest | MCP Server |

#### IA / ML / LLMs

| Tecnologia | Versão | Papel |
|------------|--------|-------|
| LangChain Core | ≥0.1.0 | Orchestration framework |
| LangSmith | ≥0.1.0 | Observabilidade + tracing |
| sentence-transformers | 3.1.1 | Embeddings (all-MiniLM-L6-v2) |
| ChromaDB | ≥0.6 | Vector store local |
| Qdrant Cloud | — | Vector store produção (384 dims, Cosine) |
| Groq API | ≥1.0.0 | LLM principal (Llama 3.3 70B) |
| Ollama | local | LLM LGPD (Gemma4 26B / gemma2:2b) |
| OpenAI SDK | ≥1.0.0 | Fallback GPT-4o-mini |

#### Segurança & Compliance

| Tecnologia | Papel |
|------------|-------|
| SHA-256 | Hash de `analista_id` e `versao_kb` |
| Regex PII | Detecção CPF/CNPJ/NIS antes do LLM |
| Ollama local | Processamento LGPD — dados não saem da rede |
| Rate Limiting | 10 req/min por sessão |
| Session Timeout | 30 minutos de inatividade |
| Graceful Degradation | Fallback em cascata sem perda de dados |

#### Infra & DevOps

| Tecnologia | Papel |
|------------|-------|
| Docker | Containerização + HF Spaces deploy |
| GitHub Actions | CI/CD |
| HuggingFace Spaces | Demo pública (app_hf.py) |
| GitHub Codespaces | Ambiente de desenvolvimento cloud |
| Tenacity | Retry automático com backoff exponencial |

---

### Métricas e Impacto de Negócio

| Métrica | Antes do EII | Com EII | Melhoria |
|---------|-------------|---------|----------|
| Tempo de diagnóstico | 15–45 min | ~2–5 seg | **−97%** |
| Auto-resolve rate | 0% | ≥70% (alvo) | +70pp |
| Escalações HITL | 100% | ≤30% (alvo) | −70pp |
| MTTR (Mean Time to Resolve) | Horas | Minutos | **−70%** |
| Testes automatizados | 0 | 72 | +72 |
| Cobertura da KB | Manual | 73 incidentes curados | Estruturada |
| Confiança do diagnóstico | Subjetiva | `ALTA/MÉDIA/BAIXA` (logprobs) | Mensurável |

**Estimativa de economia:**
- 50 rejeições/mês × 30 min × R$ 80/h = **R$ 2.000/mês economizados por empresa**
- Auto-resolve de 70% = **35 incidentes sem intervenção humana**

---

### Roadmap

#### ✅ Phase 1 — Foundation (Concluída)
- [x] Gradio UI + Docker + HuggingFace Spaces deploy
- [x] Estrutura de projeto + CLAUDE.md
- [x] Pipeline CRAG base com ChromaDB

#### ✅ Phase 2 — Core Intelligence (Concluída)
- [x] Knowledge Base com 73 incidentes eSocial curados
- [x] Avaliação automática de qualidade com threshold 80% (ADR-001)
- [x] Reflexion auto-correção (ADR-002)
- [x] PII scrubbing (CPF/CNPJ/NIS)
- [x] Logprobs confidence calibration
- [x] SQLite persistence + audit trail
- [x] Suite de 72 testes automatizados

#### ✅ Phase 3 — Production (Concluída)
- [x] Qdrant Cloud backend (384 dims, all-MiniLM-L6-v2, Cosine)
- [x] SmartRouter multi-LLM (9 providers, Fase 1 implementada)
- [x] ResilientLLM circuit breaker (Groq→Claude→GPT)
- [x] LGPD Mode — Ollama/Gemma4 local inference
- [x] MCP Server via fastmcp (`eii_query`, `eii_escalate`)
- [x] Batch processing ThreadPoolExecutor
- [x] Mentor Mode + HITL 3-checkbox
- [x] LangSmith @traceable OBS-001
- [x] Dev Container para GitHub Codespaces
- [x] E2E smoke test contra HF Space
- [x] LangChain adapter (`SmartRouterLLM` extends `BaseChatModel`)

#### 🔄 Phase 4 — Deep Agents (Em Progresso)
- [ ] Migração para `create_deep_agent` (Deep Agents v0.5)
- [ ] Fork-Join assíncrono: 1 subagent por evento eSocial no Lote
- [ ] MCP tools nativos via Deep Agents (`eii_query`, `eii_escalate`)
- [ ] LangSmith tracing integrado (LangSmith Sandbox)
- [ ] Git worktrees para ring-fencing por evento
- [ ] Claude Code Skills: `/eii-diagnose`, `/eii-ingest`, `/eii-audit`

#### ⏳ Phase 5 — Enterprise Observability (Planejada)
- [ ] LangSmith dashboards com métricas de produção
- [ ] S3 parquet — retenção 5 anos (CLT art.11)
- [ ] API `/audit/traces` para auditoria
- [ ] IntelAgent — curadoria autônoma da KB
- [ ] SourceCollector + RelevanceFilter + DigestGenerator
- [ ] `verify_kb_urls.py` — Feynman Verifier (73 itens Qdrant)

---

### Documentação Relacionada

| Documento | Descrição |
|-----------|-----------|
| [`docs/PRD.md`](docs/PRD.md) | Product Requirements Document completo (FR/NFR/ADR/métricas) |
| [`CHANGELOG.md`](CHANGELOG.md) | Histórico completo de releases (Phase 1–3) |
| [`CLAUDE.md`](CLAUDE.md) | Contexto para Claude Code — arquitetura, MCP, comandos |
| [`docs/RAGFLOW_POC.md`](docs/RAGFLOW_POC.md) | PoC do backend RAGFlow Cloud |
| [`smartrouter/README.md`](smartrouter/README.md) | Documentação do SmartRouter multi-LLM |
| [`tests/test_phase2.py`](tests/test_phase2.py) | Suite de 72 testes (PII, SQLite, CRAG, Reflexion) |
| [`scripts/test_e2e_hf.py`](scripts/test_e2e_hf.py) | Smoke test E2E contra HuggingFace Space |

---

---

## 🇬🇧 English Version

### The Problem

**eSocial** is Brazil's mandatory digital reporting system created by the Federal Revenue Service (RFB) for fiscal, social security, and labor obligations. Companies of all sizes must submit XML events with payroll data, hires, terminations, and leaves — any error triggers an **immediate rejection with a technical error code**.

**Current state in enterprises:**

| Situation | Reality |
|-----------|---------|
| Average diagnosis time | **15 to 45 minutes** per rejection |
| Monthly rejection volume | Dozens to hundreds per mid-size company |
| Analyst cost/hour | R$ 50–120/hr (salary + charges) |
| Penalty risk per event | Up to R$ 1,812.87 |
| Data in XML | CPF, CNPJ, NIS, salaries — **LGPD-sensitive data** |

HR/DP analysts receive rejected XMLs, must identify the event type (`S-1200`, `S-2200`...), locate the error code, consult the 800+ page eSocial manual, cross-reference current legislation, and build an action plan — all manually, event by event.

**EII solves exactly this bottleneck.**

---

### How It Works

EII receives the rejected XML, automatically detects personal data, routes to the correct processor (local or cloud), runs the CRAG pipeline, and delivers a structured diagnosis in seconds.

```
[eSocial Rejected XML]
        │
        ▼
  [xml_parser.py]  →  Extract event type, error code, fields
        │
        ▼
  [pii_detector.py]  →  Detect CPF / CNPJ / NIS via regex
        │
     ┌──┴──┐
  PII Found  PII Clean
     │           │
  [Ollama]   [Groq API]    ←  SmartRouter (3 routing phases)
  Local LLM  Cloud LLM
     │           │
     └─────┬─────┘
           │
     [CRAG Pipeline]
      Retrieve → Grade → Generate → Evaluate (80%) → Reflexion
           │
     [HITL Gate]
      ☐ Root cause validated
      ☐ Resolution steps confirmed
      ☐ Recurrence risk assessed
           │
     [SQLite Audit Log]
      incident_id · analyst_id · SHA-256 · LangSmith traces
```

---

### Real Usage Example

**Input — Rejected eSocial XML:**

```xml
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v03_01_02_00">
  <Status>
    <cdResposta>401</cdResposta>
    <descResposta>MA-100: Invalid validity start date</descResposta>
  </Status>
</eSocial>
```

**Output — EII Structured Diagnosis:**

```json
{
  "incident_id": "INC-20260430-143022",
  "evento": "S-1200",
  "codigo_erro": "MA-100",
  "severidade": "ALTO",
  "confianca": "ALTA",
  "fonte": "KB_MATCH",
  "causa_raiz": "The <dtIniValid> field contains a period prior to the employer's eSocial enrollment date. Event S-1200 requires the validity start date to be equal to or later than the employer group's mandatory enrollment date.",
  "passos_resolucao": [
    "1. Check employer enrollment date at the eSocial Portal",
    "2. Correct the <dtIniValid> field to the valid competency period",
    "3. Resubmit S-1200 with the corrected field",
    "4. Validate that the portal returns HTTP 201 (Success)"
  ],
  "_meta": {
    "logprob_sim": 0.94,
    "eval_iterations": 1,
    "model_used": "llama-3.3-70b-versatile"
  }
}
```

---

### Public Demo vs Local Version

| Feature | 🌐 HuggingFace Demo | 💻 Local Version |
|---------|---------------------|-----------------|
| URL | [spaces/EdsonPO/eii-incident-intelligence](https://huggingface.co/spaces/EdsonPO/eii-incident-intelligence) | `http://localhost:7860` |
| Entry file | `app_hf.py` | `app.py` |
| LLM | Groq Cloud (anonymized data) | Ollama local (LGPD) + Groq fallback |
| PII handling | Scrubbed before sending | 100% local processing |
| LGPD compliance | Partial (data scrubbed) | **Full** (data never leaves the network) |
| When to use | Demo, PoC, evaluation | **Production with real data** |
| Infra cost | Zero (HF Free Tier) | Own hardware or internal server |

---

### Detailed Architecture

#### CRAG Pipeline — 8 nós LangGraph

| Node | Function | Design Decision |
|------|----------|-----------------|
| `parse` | Parses XML and extracts metadata | — |
| `router` | Classifies severity and routing decision | — |
| `retrieve` | Vector search in ChromaDB/Qdrant | Cosine similarity |
| `grade` | Filters irrelevant docs with LLM judge | Binary grade |
| `generate` | Generates root cause + resolution steps | ADR-001 |
| `evaluate` | Evaluates quality on 5 criteria (80% threshold) | ADR-001, 13 tests |
| `reflexion` | Auto-corrects if quality < threshold | ADR-002, 13 tests |
| `finalize` | Applies confidence gate and consolidates result | ADR-001 |
| `intel` | Proactive insights via IntelAgent | — |

#### SmartRouter — 9 LLM Providers

| Provider | Specialty | Mode |
|----------|-----------|------|
| Groq / Llama 3.3 70B | Primary — speed + accuracy | Cloud |
| Claude Haiku | Architecture decisions | Cloud |
| Kimi K2 | Complex coding | Cloud |
| Cerebras | 3000 tok/s validation loops | Cloud |
| Gemini 2.5 Flash | 1M token context | Cloud |
| Qwen QwQ-32B | Complex reasoning | Cloud |
| DeepSeek R1 | Technical analysis | Cloud |
| Mistral Large 3 | Multilingual | Cloud |
| Ollama / Gemma4 26B | **LGPD mode — local inference** | **Local** |

#### ResilientLLM — Circuit Breaker

```
Groq (primary)
  └── 3 failures in 10min? → Claude Haiku (secondary)
        └── Failure? → GPT-4o-mini (tertiary)
              └── Failure? → Degraded local mode
```

#### MCP Server Integration

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "eii": {
      "command": "python",
      "args": ["/path/to/eii-erp-incident-intelligence/mcp_server.py"],
      "env": { "GROQ_API_KEY": "your-key-here" }
    }
  }
}
```

---

### Running Locally

```bash
# Clone
git clone https://github.com/edson-aiops/eii-erp-incident-intelligence
cd eii-erp-incident-intelligence

# Install
pip install -r requirements.txt
cp .env.example .env  # Fill in your API keys

# Optional: LGPD local model
ollama pull gemma2:2b

# Run
python app.py  # http://localhost:7860

# Tests (72 tests, zero network calls)
python -m pytest tests/test_phase2.py -v
```

#### Environment Variables

```env
GROQ_API_KEY=gsk_...                  # Required
QDRANT_URL=https://xxx.qdrant.io      # Optional (uses ChromaDB by default)
QDRANT_API_KEY=eyJ...                 # Required if QDRANT_URL is set
LANGSMITH_API_KEY=lsv2_...            # Optional (tracing)
EII_RETRIEVAL_BACKEND=qdrant          # "qdrant" | "chromadb"
ANTHROPIC_API_KEY=sk-ant-...          # Optional (fallback)
OPENAI_API_KEY=sk-...                 # Optional (fallback)
```

---

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Runtime** | Python 3.13, Gradio 4.44.0, FastAPI, Pydantic ≥2.0 |
| **AI/ML** | LangChain, sentence-transformers 3.1.1, LangSmith |
| **Vector Stores** | Qdrant Cloud (prod), ChromaDB ≥0.6 (dev) |
| **LLMs** | Groq, Claude Haiku, Ollama/Gemma4, GPT-4o-mini, Qwen, Kimi, Cerebras |
| **Storage** | SQLite (audit log), Qdrant (vectors) |
| **Infra** | Docker, HuggingFace Spaces, GitHub Codespaces |
| **Agent Protocol** | MCP via fastmcp, LangChain BaseChatModel adapter |
| **Security** | SHA-256, Regex PII detection, Rate limiting, Session timeout, Graceful degradation |
| **Observability** | LangSmith @traceable (6 CRAG steps), logprobs confidence |

---

### Metrics & Business Impact

| Metric | Before EII | With EII | Improvement |
|--------|-----------|---------|-------------|
| Diagnosis time | 15–45 min | ~2–5 sec | **−97%** |
| Auto-resolve rate | 0% | ≥70% (target) | +70pp |
| HITL escalations | 100% | ≤30% (target) | −70pp |
| MTTR | Hours | Minutes | **−70%** |
| Automated tests | 0 | 72 | +72 |
| KB coverage | Manual | 73 curated incidents | Structured |
| Diagnosis confidence | Subjective | `HIGH/MEDIUM/LOW` (logprobs) | Measurable |

---

### Roadmap (EN)

| Phase | Status | Deliverables |
|-------|--------|-------------|
| **1 — Foundation** | ✅ Done | Gradio UI + Docker + HF Spaces |
| **2 — Core Intelligence** | ✅ Done | 73-item KB + CRAG + avaliação automática + reflexão |
| **3 — Production** | ✅ Done | Qdrant + SmartRouter + MCP + Batch + LGPD |
| **4 — Deep Agents** | 🔄 In Progress | `create_deep_agent` + async Fork-Join Lote |
| **5 — Observability** | ⏳ Planned | LangSmith dashboards + S3 + IntelAgent |

---

## 👨‍💻 Sobre o Desenvolvedor / About the Developer

<div align="center">

**Edson Oliveira**

*Senior IT Systems Analyst — HCM/ERP & AI Engineering*

12+ anos de experiência em implementação de sistemas HCM/ERP com especialização emergente em AI/Agentic Engineering. O EII é o projeto principal do meu portfólio técnico, demonstrando a convergência entre expertise em compliance brasileiro (eSocial, LGPD, CLT) e engenharia de sistemas agentic modernos.

*12+ years of HCM/ERP implementation experience with emerging specialization in AI/Agentic Engineering. EII is the flagship project of my technical portfolio, demonstrating the convergence of Brazilian compliance expertise (eSocial, LGPD, CLT) with modern agentic systems engineering.*

[![GitHub](https://img.shields.io/badge/GitHub-edson--aiops-181717?style=for-the-badge&logo=github)](https://github.com/edson-aiops)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-EdsonPO-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/EdsonPO)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Edson_Oliveira-0A66C2?style=for-the-badge&logo=linkedin)](https://linkedin.com/in/edson-oliveira)

</div>

---

## 📄 Licença / License

Este projeto é licenciado sob a **MIT License** — você pode usar, copiar, modificar e distribuir livremente, inclusive para fins comerciais, desde que mantenha o aviso de copyright.

*This project is licensed under the **MIT License** — free to use, copy, modify, and distribute, including for commercial purposes, as long as the copyright notice is maintained.*

```
MIT License — Copyright (c) 2024-2026 Edson Oliveira

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

[Ver licença completa / See full license](LICENSE)

---

## 📞 Suporte e Contribuição / Support & Contribution

### Reportar um Bug / Report a Bug

Abra uma [Issue](https://github.com/edson-aiops/eii-erp-incident-intelligence/issues) com o template:

```markdown
**Versão:** (git log --oneline -1)
**Ambiente:** Local / HuggingFace / Docker
**Evento eSocial:** S-XXXX
**Código de erro:** MA-XXX / E-XXXX
**Comportamento esperado:** ...
**Comportamento observado:** ...
**Logs relevantes:** (sem dados pessoais/PII)
```

### Contribuir / Contributing

1. Fork o repositório
2. Crie uma branch: `git checkout -b feat/minha-feature`
3. Execute os testes: `pytest tests/test_phase2.py -v`
4. Commit com [Conventional Commits](https://conventionalcommits.org): `feat(kb): add S-5003 incident`
5. Abra um Pull Request

### Adicionar Incidentes à KB / Add Incidents to KB

A Knowledge Base aceita contribuições de incidentes eSocial reais (sem PII). Use o template em [`docs/PRD.md`](docs/PRD.md) para estruturar novos itens.

---

<div align="center">

[![HuggingFace Space](https://img.shields.io/badge/🤗_Demo_Pública-HuggingFace-FFD21E?style=flat-square)](https://huggingface.co/spaces/EdsonPO/eii-incident-intelligence)
[![GitHub](https://img.shields.io/badge/Source-GitHub-181717?style=flat-square&logo=github)](https://github.com/edson-aiops/eii-erp-incident-intelligence)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MIT](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)

*EII — Transformando horas em segundos no diagnóstico de rejeições eSocial*  
*EII — Turning hours into seconds for eSocial rejection diagnostics*

</div>
