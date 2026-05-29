# Auditoria de Arquitetura — EII v3.1.0

> **Data da auditoria:** 2026-05-28  
> **Modo:** SOMENTE-LEITURA (nenhum arquivo modificado)  
> **Auditor:** Kimi K2.6 (CLI)  
> **Branch auditada:** `main` (commit base `af4d602`)

---

## RESUMO EXECUTIVO

| Métrica | Valor Real | Memória (STATUS.md/CLAUDE.md) | Status |
|---|---|---|---|
| **Nº real de nós LangGraph** | **8** | 8 ("7 nós" em alguns docs, "8 nós" em outros) | ✅ CONFIRMADO |
| **Nº real de agentes especializados ativos** | **1** (`IntelAgent`) | Vários mencionados (`DiagnosticAgent`, `EvaluatorAgent`, etc.) | ⚠️ DIVERGÊNCIA |
| **Nº real de LLMs no SmartRouter** | **9 providers configurados** (3 são aliases Groq) | 9 LLMs | ✅ CONFIRMADO (com ressalvas) |
| **SmartRouter em uso** | `smartrouter/` (raiz) | "9 LLMs roteados" | ✅ CONFIRMADO |
| **Nº de incidentes na KB** | **93** (KB001–KB093) | 93 | ✅ CONFIRMADO |
| **Fases do SmartRouter** | **1 implementada** (Rules) | 3 fases (Rules → Cerebras Classify → Adaptive) | ⚠️ DIVERGÊNCIA |

### 3 maiores divergências memória-vs-código

1. **Agentes especializados:** A documentação menciona `DiagnosticAgent`, `EvaluatorAgent`, `ReflexionAgent`, `EscalationAgent`, `IngestAgent`. No código existe **apenas 1 classe de agente** (`IntelAgent`). Os demais são rótulos conceituais aplicados a funções procedurais do pipeline CRAG ou a linhas de tabela em `eii_integration.py`.
2. **Fases do SmartRouter:** A memória diz "3 fases (Rules → Cerebras Classify → Adaptive)". O código tem **apenas a Fase 1 (Rules-based keyword matching)**. Fase 2 é um comentário `TODO` e Fase 3 existe só em READMEs.
3. **Aba HITL na UI:** O `app.py` menciona "Aprove ou rejeite na aba de Aprovação HITL" (`app.py:1201`), mas **não há aba funcional de aprovação HITL** na interface Gradio. O HITL só é acessível via API REST, MCP ou SQLite direto.

---

## PARTE A — Deep Agents / LangGraph

### A1. Definição do Grafo

**Arquivo único:** `src/deep_agents/graph.py:1-38`

- `StateGraph` instanciado em `graph.py:13`
- `compile()` em `graph.py:36`
- Grafo exposto como `eii_agent_graph` em `graph.py:38`

### A2. Nós (add_node) — 8 nós confirmados

| # | Nome Exato | Função Importada | Arquivo:Linha |
|---|------------|------------------|---------------|
| 1 | `parse` | `parse_xml_node` | `src/deep_agents/graph.py:14` |
| 2 | `router` | `smart_router_node` | `src/deep_agents/graph.py:15` |
| 3 | `retrieve` | `retrieve_node` | `src/deep_agents/graph.py:16` |
| 4 | `generate` | `generate_node` | `src/deep_agents/graph.py:17` |
| 5 | `evaluate` | `evaluate_node` | `src/deep_agents/graph.py:18` |
| 6 | `reflexion` | `reflexion_node` | `src/deep_agents/graph.py:19` |
| 7 | `finalize` | `finalize_node` | `src/deep_agents/graph.py:20` |
| 8 | `intel` | `intel_node` | `src/deep_agents/graph.py:21` |

**Comparação com a memória:** A memória alterna entre "7 nós" (`STATUS.md:130`: "7 nós implementados") e "8 nós" (`STATUS.md:33`: "8 nos (Phase 4 + intel_node)"; `CLAUDE.md:74-84`). O código real tem **8 nós**. A confusão provavelmente vem de contar sem o nó `intel` (adicionado posteriormente).

### A3. Arestas (add_edge / add_conditional_edges)

**Arestas diretas (`add_edge`):**

| Origem | Destino | Arquivo:Linha |
|--------|---------|---------------|
| `parse` → `router` | `graph.py:24` |
| `router` → `retrieve` | `graph.py:25` |
| `retrieve` → `generate` | `graph.py:26` |
| `generate` → `evaluate` | `graph.py:27` |
| `reflexion` → `generate` | `graph.py:32` |
| `finalize` → `intel` | `graph.py:33` |
| `intel` → `END` | `graph.py:34` |

**Aresta condicional (`add_conditional_edges`):**

| Origem | Função de Roteamento | Destinos | Arquivo:Linha |
|--------|---------------------|----------|---------------|
| `evaluate` | `should_reflexion` | `"reflexion"` ou `"finalize"` | `graph.py:28-31` |

**Loop encontrado:** `evaluate` → `reflexion` → `generate` → `evaluate`. Máximo de iterações: `MAX_ITERATIONS = 2` (`src/deep_agents/nodes/evaluate_node.py:7`).

### A4. O que cada nó faz (1 linha)

| Nó | Função |
|----|--------|
| `parse` | Parseia XML eSocial/EFD-Reinf, detecta PII, extrai metadados (`parse_node.py:11`). |
| `router` | Classifica severidade e decide roteamento (`deep_reasoning`, `validation`, `sensitive_data`) (`router_node.py:36`). |
| `retrieve` | Constrói query, recupera docs do vector store, aplica grading (`retrieve_node.py:8`). |
| `generate` | Delega ao `crag_pipeline.generate()` para produzir diagnóstico JSON (`generate_node.py:8`). |
| `evaluate` | Avalia qualidade do diagnóstico via `evaluate_diagnosis()`; define `needs_refinement` (`evaluate_node.py:10`). |
| `reflexion` | Auto-crítica: chama `reflect()` para gerar hint corretiva, incrementa `iteration_count` (`reflexion_node.py:8`). |
| `finalize` | Aplica gate de confiança ADR-001 (`confidence_score`), monta `final_result` (`finalize_node.py:8`). |
| `intel` | Executa `IntelAgent.run()` para insights proativos (padrões históricos, risco de recorrência) (`intel_node.py:15`). |

### A5. Qual arquivo o app.py realmente usa

O `app.py` importa o grafo em:

- `app.py:96` — `from src.deep_agents.graph import create_deep_agent_graph as _create_graph`
- `app.py:98` — `_eii_agent_graph = _create_graph()`
- `app.py:515` — invocado por `_diagnose_deep_agents(...)` (função assíncrona)
- `app.py:621` — chamado condicionalmente quando `use_deep_agents=True`

**Arquivo órfão detectado:** `src/deep_agents/nodes/reflexion_finalize_nodes.py` contém stubs de `reflexion_node` e `finalize_node`, mas **não é importado** pelo grafo. O grafo usa os arquivos separados `reflexion_node.py` e `finalize_node.py`.

---

## PARTE B — Agentes Especializados

### B1-B2. Mapeamento completo

| Nome | Arquivo:Linha da Definição | Importado/Chamado por | Classificação | O que faz |
|------|---------------------------|----------------------|---------------|-----------|
| **`IntelAgent`** | `src/intel_agent/intel_agent.py:36` | `app.py:110`, `app.py:612`, `src/deep_agents/nodes/intel_node.py:17` | ✅ **IMPLEMENTADO E USADO** | Análise proativa de padrões históricos via SQLite (sem chamadas a LLM). |
| `DiagnosticAgent` | **Não localizado** (classe/função) | N/A | 📝 **SÓ EM DOCS/COMENTÁRIOS** | Rótulo conceitual para `generate()` do CRAG. |
| `EvaluatorAgent` | **Não localizado** (classe/função) | N/A | 📝 **SÓ EM DOCS/COMENTÁRIOS** | Rótulo conceitual para `evaluate_diagnosis()` do CRAG (`crag_pipeline.py:454`). |
| `ReflexionAgent` | **Não localizado** (classe/função) | N/A | 📝 **SÓ EM DOCS/COMENTÁRIOS** | Rótulo conceitual para `reflect()` do CRAG e nó `reflexion_node`. |
| `EscalationAgent` | **Não localizado** (classe/função) | N/A | 📝 **SÓ EM DOCS** | Rótulo de tabela em `smartrouter/eii_integration.py:16` (categoria `general`). |
| `IngestAgent` | **Não localizado** (classe/função) | N/A | 📝 **SÓ EM DOCS** | Rótulo de tabela em `smartrouter/eii_integration.py:17` (categoria `sensitive_data`). |
| `IngestionAgent` | **Não localizado** em lugar algum | N/A | ❌ **NÃO EXISTE** | — |

### B3. Status específico de IngestAgent e EscalationAgent

**Não existem como código.** Aparecem apenas como strings em uma tabela markdown dentro de `smartrouter/eii_integration.py` (`linha 16-17`) e suas cópias em `smartrouter_v2/`. São rótulos arquiteturais para categorias de roteamento (`general` e `sensitive_data`), não agentes implementados.

### B4. Agentes não mencionados

**Nenhum.** A busca por `class *Agent`, `Agent(`, `*Agent` em todo o codebase (exceto `.venv/`) retornou **apenas `IntelAgent`**.

---

## PARTE C — SmartRouter

### C1. Os 3 caminhos suspeitos

| Caminho | Existe? | config.py? | Importado por código de produção? |
|---------|---------|-----------|-----------------------------------|
| `smartrouter/` | ✅ Sim | ✅ Sim (234 linhas) | ✅ **SIM** — usado por `app.py`, `crag_pipeline.py`, `crag_pipeline_smartrouter.py`, `batch_processor.py` |
| `smartrouter_v2/` | ✅ Sim | ✅ Sim (234 linhas) | ❌ **NÃO** — nenhum import encontrado |
| `smartrouter_v2/smartrouter/` | ✅ Sim | ✅ Sim (234 linhas) | ❌ **NÃO** — nenhum import encontrado |

**SmartRouter REALMENTE em uso:** `smartrouter/` (raiz). `smartrouter_v2/` e sua subpasta são **código morto** — existem no disco mas nenhum arquivo de produção os importa.

Rastreamento de imports confirmado:
- `app.py:80` → `from crag_pipeline_smartrouter import diagnosticar_incidente as diagnosticar_incidente_sr`
- `crag_pipeline.py:18` → `from smartrouter.smart_router import SmartRouter`
- `crag_pipeline.py:124` → `from smartrouter.eii_integration import create_eii_llms`
- `crag_pipeline_smartrouter.py:129` → `from smartrouter.eii_integration import create_eii_llms`
- `batch_processor.py:16` → `from smartrouter.smart_router import SmartRouter`

### C2. Providers/LLMs configurados no SmartRouter em uso

**Fonte:** `smartrouter/config.py:28-111`

**Total: 9 providers configurados**

| # | ProviderID | Nome | Modelo | api_key_env |
|---|------------|------|--------|-------------|
| 1 | `KIMI` | Llama 3.3 70B (Groq — fallback geral) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| 2 | `QWEN` | Llama 3.1 8B (via Groq) | `llama-3.1-8b-instant` | `GROQ_API_KEY` |
| 3 | `CEREBRAS` | Cerebras (Llama 3.1 8B) | `llama3.1-8b` | `CEREBRAS_API_KEY` |
| 4 | `GEMINI` | Gemini 2.5 Pro (Google) | `gemini-2.5-flash` | `GOOGLE_AI_API_KEY` |
| 5 | `GROQ` | Groq (Llama 3.3 70B) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| 6 | `MISTRAL` | Mistral Large 3 | `mistral-large-latest` | `MISTRAL_API_KEY` |
| 7 | `DEEPSEEK` | Llama 3.3 70B reasoning (via Groq) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| 8 | `CLAUDE` | Claude Sonnet 4.6 (Anthropic) | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| 9 | `OLLAMA` | Gemma 4 26B (Ollama local) | `gemma4:26b` | `OLLAMA_API_KEY` (dummy) |

**Observação crítica:** 3 dos 9 providers (`KIMI`, `QWEN`, `DEEPSEEK`) são **aliases que compartilham a mesma API da Groq** (`base_url="https://api.groq.com/openai/v1"`). Não há provider usando `MOONSHOT_API_KEY`, apesar do comentário inicial do `config.py:7` mencionar `MOONSHOT_API_KEY`.

### C3. As "3 fases" (Rules → Classify → Adaptive)

| Fase | Existe no código? | Onde? | Status real |
|------|------------------|-------|-------------|
| **Fase 1: Rules Engine** | ✅ Sim | `smartrouter/router.py:48` (`# ── Task Classifier (Phase 1: Rules-based)`) | **IMPLEMENTADA** — keyword matching via `CLASSIFICATION_KEYWORDS` (`config.py:179`) |
| **Fase 2: Smart Classification** | ⚠️ Parcialmente | `smartrouter/router.py:54` — comentário: *"Phase 2: Will add Cerebras LLM classification for ambiguous cases"* | **NÃO IMPLEMENTADA** — apenas comentário `TODO` |
| **Fase 3: Adaptive Routing** | ❌ Não | `smartrouter/README.md:119` e `README_EII_Completo.md:264` | **NÃO IMPLEMENTADA** — o código tem `_history` (`router.py:333`) e `get_stats()` (`router.py:480`), mas **não há lógica de aprendizado** que modifique as regras |

**Veredito:** Apenas **1 fase** está implementada. A memória de "3 fases" é **falsa** no que tange ao código real.

### C4. Provider "Kimi" usa `api_key_env="GROQ_API_KEY"`?

**✅ SIM.** Confirmado em:
- `smartrouter/config.py:35`
- `smartrouter_v2/config.py:35`
- `smartrouter_v2/smartrouter/config.py:35`

**Outros mapeamentos cruzados:**
- `QWEN` → `GROQ_API_KEY` (`config.py:44`)
- `DEEPSEEK` → `GROQ_API_KEY` (`config.py:87`)

---

## PARTE D — Pipeline CRAG e Fluxo Principal

### D1. Pipelines CRAG existentes

| Pipeline | Arquivo | Status |
|----------|---------|--------|
| **CRAG Padrão** | `crag_pipeline.py` | ✅ Funcionando (fallback quando SmartRouter falha) |
| **CRAG SmartRouter** | `crag_pipeline_smartrouter.py` | ✅ Funcionando (padrão do `app.py`) |
| **Deep Agents (LangGraph)** | `src/deep_agents/graph.py` | ✅ Funcionando (caminho alternativo em `app.py`) |
| **CRAG-lite (Público)** | `app_hf.py` | ✅ Funcionando (demo HF, sem CRAG propriamente dito) |

**Qual o `app.py` usa por padrão?**
- `app.py:80` importa `diagnosticar_incidente` do `crag_pipeline_smartrouter` (com fallback para `crag_pipeline` em `app.py:86`)
- `app.py:669` chama `diagnosticar_incidente_sr(...)` como caminho padrão

**Diferença entre `crag_pipeline.py` e `crag_pipeline_smartrouter.py`:**
- `crag_pipeline_smartrouter.py` tem **cache de vector store** (`_col_cache`, `_get_col()` em `crag_pipeline_smartrouter.py:794-800`)
- `crag_pipeline_smartrouter.py` usa `observability.traceable` (shim próprio)
- `crag_pipeline.py` reconstrói o vector store a cada chamada
- Ambos implementam os mesmos 5 passos: Retrieve → Grade → Generate → Evaluate → Reflexion

### D2. Fluxo de um diagnóstico (clique em "Diagnosticar" até resposta)

Rastreado a partir de `app.py`:

1. `app.py:1250` — `diagnose_btn.click(fn=diagnose_handler_secure, ...)`
2. `app.py:565` — `diagnose_handler_secure(...)` valida sessão, rate limit, log seguro
3. `app.py:600` — chama `_diagnose_internal(...)`
4. `app.py:621` — `_diagnose_internal(...)` decide o pipeline:
   - **Caminho A (LGPD/Local):** `force_local=True` → `call_ollama_direct` (`app.py:311`)
   - **Caminho B (Deep Agents):** `use_deep_agents=True` → `_diagnose_deep_agents` (`app.py:515`)
   - **Caminho C (Padrão):** `diagnosticar_incidente_sr` (CRAG SmartRouter)
5. No Caminho C, dentro do pipeline:
   - `crag_pipeline_smartrouter.py:803` — `diagnosticar_incidente` parseia XML
   - `crag_pipeline_smartrouter.py:828` — chama `run_crag(...)`
   - `crag_pipeline_smartrouter.py:682` — `run_crag` executa: retrieve → grade → generate → evaluate → (opcional) reflect
   - `crag_pipeline_smartrouter.py:750` — aplica `confidence_score()`
6. Retorno ao `app.py`:
   - `format_output()` (`app.py:356`) ou `format_output_deep_agents()` (`app.py:398`)
   - `_run_intel_agent()` (`app.py:607`) opcionalmente enriquece com insights
   - `apply_mentor_mode()` (`app.py:43`) — **no-op**, retorna texto inalterado
7. UI renderiza resultado nos componentes `output`, `insights_output`, `error_output`

### D3. HITL (Human-in-the-Loop)

**NÃO há agente dedicado.** O HITL é **lógica inline** espalhada por múltiplos arquivos:

- **Geração do alerta:** `crag_pipeline.py:741-747` e `crag_pipeline_smartrouter.py:741-747` — preenche `diagnosis["alerta_hitl"]` quando o avaliador automático não aprova
- **Persistência:** `eii_handlers.py:148` — salva como `PENDING` no SQLite
- **Decisão (aprovação/rejeição):** `eii_handlers.py:169` — `escalate_incident()` atualiza para `APROVADO`/`REJEITADO`
- **API REST:** `api.py:381` (approve) e `api.py:407` (reject)
- **MCP:** `mcp_server.py:60` — tool `eii_escalate()`
- **Notificação e-mail:** `notifier.py:212` — `send_hitl_alert()` em background thread
- **UI Gradio:** ⚠️ **NÃO há aba funcional de aprovação HITL** no `app.py`. O texto em `app.py:1201` menciona a aba, mas ela não existe na interface atual.

---

## PARTE E — Stack e Números Verificáveis

### E1. Versões reais

| Componente | Versão declarada | Fonte |
|------------|-----------------|-------|
| **Python (Docker)** | `3.11` | `Dockerfile:2,16` |
| **Python (DevContainer)** | `3.13` | `.devcontainer/devcontainer.json:3` |
| **Gradio** | `>=5.0.0` | `requirements.txt:1`, `pyproject.toml:9` |
| **LangGraph** | `>=0.2.0` | `requirements.txt:10`, `pyproject.toml:18` |
| **LangChain (core)** | `>=0.1.0` (reqs) / `>=0.3.0` (pyproject) | `requirements.txt:9`, `pyproject.toml:17` |
| **ChromaDB** | `>=0.6` | `requirements.txt:2`, `pyproject.toml:10` |
| **FastAPI** | `>=0.111.0` | `requirements.txt:12`, `pyproject.toml:20` |
| **LangSmith** | `>=0.1.0` | `requirements.txt:5`, `pyproject.toml:13` |
| **sentence-transformers** | `==3.1.1` | `requirements.txt:3`, `pyproject.toml:11` |
| **OpenAI** | `>=1.0.0` | `requirements.txt:6`, `pyproject.toml:14` |
| **anthropic** | `>=0.30` | `requirements.txt:18`, `pyproject.toml:26` |

**Qdrant:** ✅ Presente no código como backend opcional:
- `qdrant_client.py` (raiz) — módulo próprio
- `crag_pipeline.py:248-250` — import condicional quando `EII_RETRIEVAL_BACKEND=qdrant`
- `scripts/ingest_qdrant.py` — script de ingestão

### E2. Knowledge Base — 93 incidentes confirmados

**Método de contagem:** `grep -o '"id": "KB[0-9]*' knowledge_base.py | sort -u | wc -l` → **93**

- IDs únicos: **KB001 a KB093**
- Última entrada: `knowledge_base.py:1941` → `"id": "KB093"`
- Distribuição:
  - KB001–KB073: eSocial (73 incidentes)
  - KB074–KB093: EFD-Reinf (20 incidentes)

**Veredito:** A memória de "93 incidentes" está **correta**.

### E3. Parser XML — tipos de evento suportados

**eSocial:**
- `ESOCIAL_EVENTS` em `xml_parser.py:158-167`
- **61 eventos S-*** listados (S-1000 a S-5513)

**EFD-Reinf:**
- `EFDREINF_EVENTS` em `xml_parser.py:170-176`
- **23 eventos R-*** listados (R-1000 a R-9015)
- `_EFDREINF_EVT_TAGS` mapeia **18 tags XML** específicas

**A memória mencionava "20 eventos R-*"** — isso refere-se aos **20 incidentes KB** (KB074–KB093), não à lista do parser. O parser declara **23 códigos R-***.

### E4. Observabilidade / LangSmith

**Arquivo:** `observability.py` (raiz)

**Integração:** Parcial/Opicional (`STATUS.md:31`: "LangSmith opcional")

**Chamadores confirmados:**
- `crag_pipeline_smartrouter.py:18`
- `api.py:280`
- `src/intel_agent/intel_agent.py:276`
- `src/deep_agents/nodes/evaluate_node.py:65`
- `src/deep_agents/nodes/finalize_node.py:63`
- `src/deep_agents/nodes/generate_node.py:72`
- `src/deep_agents/nodes/intel_node.py:39`
- `src/deep_agents/nodes/router_node.py:67`

Comportamento: se `LANGSMITH_API_KEY` (ou `LANGCHAIN_API_KEY`) não estiver configurada, retorna decorador no-op (zero overhead).

---

## PARTE F — Implementado vs Roadmap

### F1. Tabela de classificação

| Componente | Status Real | Evidência |
|------------|-------------|-----------|
| **Pipeline CRAG (retrieve/grade/generate)** | ✅ IMPLEMENTADO E FUNCIONANDO | `crag_pipeline.py`, `crag_pipeline_smartrouter.py` |
| **SmartRouter v1 (smartrouter/)** | ✅ IMPLEMENTADO E FUNCIONANDO | Importado por `app.py`, `batch_processor.py` |
| **SmartRouter v2 (smartrouter_v2/)** | ❌ DEFINIDO MAS NÃO USADO | Nenhum import em código de produção |
| **Deep Agents (LangGraph 8 nós)** | ✅ IMPLEMENTADO E FUNCIONANDO | `src/deep_agents/graph.py` compilado e invocado em `app.py` |
| **IntelAgent** | ✅ IMPLEMENTADO E FUNCIONANDO | Classe real, importada em `app.py` e no grafo |
| **DiagnosticAgent (classe)** | 📝 ROADMAP/SÓ EM DOCS | Não existe como classe; função `generate()` faz o papel |
| **EvaluatorAgent (classe)** | 📝 ROADMAP/SÓ EM DOCS | Não existe como classe; função `evaluate_diagnosis()` faz o papel |
| **ReflexionAgent (classe)** | 📝 ROADMAP/SÓ EM DOCS | Não existe como classe; nó `reflexion_node` faz o papel |
| **EscalationAgent (classe)** | 📝 ROADMAP/SÓ EM DOCS | Só existe como string em `eii_integration.py:16` |
| **IngestAgent (classe)** | 📝 ROADMAP/SÓ EM DOCS | Só existe como string em `eii_integration.py:17` |
| **SmartRouter Fase 2 (Cerebras Classify)** | 📝 ROADMAP | Comentário `TODO` em `router.py:54` |
| **SmartRouter Fase 3 (Adaptive)** | 📝 ROADMAP | Só mencionado em `README.md` e `README_EII_Completo.md` |
| **Aba HITL na UI Gradio** | ❌ NÃO IMPLEMENTADO | Mencionado em `app.py:1201` mas aba não existe |
| **Modo Mentor (pós-geração)** | ⚠️ PARCIAL | Checkbox existe, mas `apply_mentor_mode` é no-op (`app.py:43`); o mentor atua apenas via system prompt no momento da geração |
| **Notifier e-mail HITL** | ✅ IMPLEMENTADO E FUNCIONANDO | `notifier.py`, chamado por `eii_handlers.py:163` |
| **API REST FastAPI** | ✅ IMPLEMENTADO E FUNCIONANDO | `api.py` (porta 8000) |
| **MCP Server** | ✅ IMPLEMENTADO E FUNCIONANDO | `mcp_server.py` (fastmcp) |
| **Auth local (login + sessão)** | ✅ IMPLEMENTADO E FUNCIONANDO | `app.py` (SHA-256 + token + timeout + rate limit) |
| **Batch Processor** | ✅ IMPLEMENTADO E FUNCIONANDO | `batch_processor.py` |
| **PII Scrubbing** | ✅ IMPLEMENTADO E FUNCIONANDO | `xml_parser.py:scrub_pii()` |
| **Qdrant backend** | ✅ IMPLEMENTADO (opcional) | `qdrant_client.py`, import condicional |
| **Multitenancy** | 📝 ROADMAP | `STATUS.md:166` (Fase 6) |
| **app_hf.py v2** | 📝 ROADMAP | `STATUS.md:169` (Fase 6) |
| **Pipeline EFD-Reinf no Deep Agents router** | 📝 ROADMAP | `STATUS.md:168` (Fase 6) |

### F2. Divergências documentação-vs-código

| Documento | Afirmação | Realidade | Severidade |
|-----------|-----------|-----------|------------|
| `STATUS.md:33` | "8 nos (Phase 4 + intel_node)" | ✅ Correto | — |
| `STATUS.md:130` | "7 nós implementados" | ❌ Incorreto — são 8 | Baixa (desatualizado) |
| `STATUS.md:24` | "9 LLMs roteados" | ⚠️ Ressalva — são 9 providers, mas 3 são aliases Groq | Média |
| `STATUS.md:26` | "20 incidentes documentados" (knowledge_base) | ❌ Incorreto — são 93 (era 20 na v1.0) | Alta (desatualizado) |
| `STATUS.md:27` | "mcp_server.py funcionando" | ✅ Correto | — |
| `STATUS.md:31` | "observability.py parcial" | ✅ Correto (LangSmith opcional) | — |
| `CLAUDE.md:86` | "93 incidentes" | ✅ Correto | — |
| `CLAUDE.md:92` | "9 LLMs" | ⚠️ Ressalva — aliases Groq | Média |
| `CLAUDE.md:75-84` | Diagrama de 8 nós | ✅ Correto | — |
| `DUAL_MODE.md:49` | "LLM Backend: SmartRouter (9 LLMs) + Ollama opcional" | ⚠️ Ressalva — Ollama já está incluso nos 9 | Baixa |
| `DUAL_MODE.md:49` | "Deep Agents v0.5" | ⚠️ Impreciso — não há versionamento interno dos Deep Agents | Baixa |
| `CHANGELOG.md:146` | "KB 93 incidentes" | ✅ Correto | — |
| `CHANGELOG.md:78` | "20 eventos R-*" | ⚠️ Ressalva — o parser tem 23 eventos R-*; os 20 referem-se aos KBs EFD-Reinf | Média |

---

## TABELA FINAL: VERDE vs AMARELO

> Use esta tabela para decidir o que pode ser publicado no diagrama/post.

| Item | Pode Publicar? | Nota |
|------|---------------|------|
| "Pipeline LangGraph com 8 nós" | ✅ **VERDE** | Confirmado em `src/deep_agents/graph.py:14-21` |
| "Nós: parse → router → retrieve → generate → evaluate → reflexion → finalize → intel" | ✅ **VERDE** | Confirmado |
| "Loop reflexion→generate com max 2 iterações" | ✅ **VERDE** | Confirmado em `evaluate_node.py:7` e `graph.py:32` |
| "1 agente especializado real: IntelAgent" | ✅ **VERDE** | Confirmado em `src/intel_agent/intel_agent.py:36` |
| "DiagnosticAgent como classe" | ❌ **AMARELO** | **NÃO PUBLICAR** — não existe como classe |
| "EvaluatorAgent como classe" | ❌ **AMARELO** | **NÃO PUBLICAR** — não existe como classe |
| "ReflexionAgent como classe" | ❌ **AMARELO** | **NÃO PUBLICAR** — não existe como classe |
| "EscalationAgent / IngestAgent como classes" | ❌ **AMARELO** | **NÃO PUBLICAR** — não existem como classes |
| "SmartRouter com 9 providers" | ✅ **VERDE** | Confirmado em `smartrouter/config.py:28-111` |
| "SmartRouter com 9 LLMs distintos" | ⚠️ **AMARELO** | **REESCREVER** — são 9 providers, mas 3 (Kimi/Qwen/DeepSeek) usam a mesma API Groq; 1 é Ollama local. LLMs distintos de fato: ~6-7. |
| "SmartRouter: 3 fases de roteamento" | ❌ **AMARELO** | **NÃO PUBLICAR** — apenas 1 fase implementada (Rules). Fases 2 e 3 são roadmap. |
| "KB com 93 incidentes" | ✅ **VERDE** | Confirmado (KB001–KB093) |
| "Parser suporta 61 eventos eSocial + 23 EFD-Reinf" | ✅ **VERDE** | Confirmado em `xml_parser.py:158-176` |
| "HITL com aba de aprovação na UI" | ❌ **AMARELO** | **NÃO PUBLICAR** — HITL existe via API/MCP/SQLite, mas **não há aba funcional** no Gradio |
| "Modo Mentor com checklist didático" | ⚠️ **AMARELO** | **REESCREVER** — o checkbox existe e injeta system prompt, mas `apply_mentor_mode` em `app.py:43` é no-op. Não há checklist pós-geração. |
| "Observabilidade LangSmith completa" | ⚠️ **AMARELO** | **REESCREVER** — está implementada mas é **opcional**; só ativa se `LANGSMITH_API_KEY` configurada. |
| "Pipeline CRAG com cache de vector store" | ✅ **VERDE** | Confirmado em `crag_pipeline_smartrouter.py:794-800` |
| "Autenticação local com Windows Credential Manager" | ✅ **VERDE** | Confirmado em `app.py` + `secure_secrets.py` |
| "API REST FastAPI + MCP Server" | ✅ **VERDE** | Confirmado (`api.py` + `mcp_server.py`) |
| "Versão Python 3.11/3.13" | ✅ **VERDE** | Confirmado (`Dockerfile:2`, `.devcontainer/devcontainer.json:3`) |

---

## ANEXO — Código Morto / Órfão Detectado

| Arquivo | Por que é órfão |
|---------|-----------------|
| `src/deep_agents/nodes/reflexion_finalize_nodes.py` | Contém stubs de `reflexion_node` e `finalize_node`, mas o grafo importa os arquivos separados `reflexion_node.py` e `finalize_node.py` |
| `smartrouter_v2/` (toda a pasta) | Nenhum arquivo de produção importa esta pasta. Foi criada como refatoração modular (Qwen) mas nunca substituiu `smartrouter/` |
| `smartrouter_v2/smartrouter/` (subpasta) | Duplicação aninhada dentro de `smartrouter_v2/`, também não importada |

---

*Fim da auditoria. Nenhum arquivo foi modificado. Todos os números foram verificados contra o código real.*
