# Changelog

All notable changes to EII — ERP Incident Intelligence are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Planned
- Expansão da KB para 100+ incidentes documentados
- Suporte a EFD-Reinf (R-xxxx series)
- Upload de arquivo XML (além de paste)
- Dashboard de métricas (MTTR, taxa de resolução automática, escalation rate)
- API REST para integração com ticketing (JIRA, ServiceNow)
- Notificação por e-mail quando incidente aguarda aprovação HITL

---

## [2.0.0] — Phase 2: Intelligence & Compliance

### Added
- **PII Scrubbing (LGPD — Privacy by Design)**
  - `scrub_pii()` em `xml_parser.py` mascara CPF, CNPJ e NIS/PIS antes de qualquer
    persistência ou envio ao LLM
  - Formatos cobertos: bare (11/14 dígitos), formatado (`###.###.###-##`, `##.###.###/####-##`, `###.#####.##-#`)
  - Aplicado automaticamente em `nr_inscricao` e em todas as `ocorrencias.descricao` no parse
  - CNPJ (14 dígitos) tem prioridade sobre CPF (11 dígitos) — sem dupla substituição

- **SQLite Persistence Layer**
  - `DB_PATH` configurável via variável de ambiente; padrão `eii_incidents.db`
  - Fallback automático: se `/data` não existir (HuggingFace Spaces sem volume montado),
    `os.makedirs` cria o diretório; se falhar, cai para arquivo local
  - Funções: `_db_save_pending`, `_db_fetch_pending`, `_db_decide`, `_db_audit_log`
  - Audit log imutável com `decided_at`, `status` (APROVADO/REJEITADO) e notas do analista

- **Cost-Optimized Model Routing**
  - `MODEL_ROUTER = llama-3.1-8b-instant` — usado em `grade()` (tarefa binária RELEVANTE/IRRELEVANTE)
  - `MODEL_GENERATOR = llama-3.3-70b-versatile` — usado em `generate()` (diagnóstico JSON completo)
  - Ambos configuráveis via `EII_MODEL_ROUTER` / `EII_MODEL_GENERATOR` env vars
  - Redução de custo estimada em ~60% vs. usar 70B para todos os passos

- **Logprobs Confidence Score (ADR-001)**
  - `_groq_logprobs()`: chama Groq com `logprobs=True, max_tokens=1, top_logprobs=5`
  - Mede P(SIM) somando `exp(logprob)` dos tokens afirmativos {SIM, S, YES, Y}
  - `_prob_to_label()`: P ≥ 0.80 → ALTA | P ≥ 0.45 → MÉDIA | P < 0.45 → BAIXA
  - `confidence_score()` sobrescreve o campo `confianca` gerado pelo LLM — logprob é fonte de verdade
  - `_meta.logprob_sim` exposto no audit log para rastreabilidade

- **Automated Test Suite — 46 testes**
  - `tests/test_phase2.py` — stdlib + `unittest.mock`, zero chamadas reais à API Groq
  - `TestScrubPII` (10): CNPJ bare/fmt, CPF bare/fmt, NIS, misto, sem PII, vazio, sem dupla substituição
  - `TestParsedXMLScrubbing` (6): nr_inscricao e ocorrencias scrubbed, todos os SAMPLE_XMLs, parse error
  - `TestSQLiteDB` (10): save/fetch, decide, audit log, restart simulation, ordering, limit, isolamento
  - `TestModelRouting` (7): grade→8b, generate→70b, max_tokens pequeno, env override
  - `TestLogprobs` (13): thresholds, fallbacks, somas de tokens, confidence_score, run_crag integration

### Changed
- `_db_conn()` em `app.py` — adicionado fallback `/data` com `os.makedirs` e catch `OSError`

---

## [1.0.0] — Phase 1: Foundation

### Added
- **Gradio UI** (`app.py`)
  - Tab 🚨 Diagnóstico: input XML, seleção de exemplos, output markdown estruturado
  - Tab ✋ Aprovação HITL: campos ID do incidente + notas do analista, botões Aprovar/Rejeitar
  - Tab 📋 Log de Auditoria: histórico das decisões com severidade, confiança e fonte
  - Tab 🏗️ Arquitetura: documentação inline do pipeline e stack
  - Tema dark IBM Plex Mono/Sans com CSS customizado

- **XML Parser** (`xml_parser.py`)
  - Suporte a 4 formatos: `retornoEnvioLoteEventos`, `retornoProcessamentoEvento`,
    `retornoEvento`, genérico
  - Detecção automática de tipo de evento (S-1200, S-2200, etc.) via tag e atributo `Id`
  - Extração de `cdResposta`, `descResposta`, `nrInsc`, `nrRec`, `ocorrencias`
  - 5 XMLs de exemplo cobrindo E428, E469, E214, E312, E500

- **CRAG Pipeline** (`crag_pipeline.py`)
  - Step 1 Retrieve: ChromaDB in-memory com sentence-transformers (all-MiniLM-L6-v2)
  - Step 2 Grade: LLM avalia relevância de cada doc KB (RELEVANTE/IRRELEVANTE)
  - Step 3 Generate: LLM gera diagnóstico JSON estruturado com causa raiz e passos
  - Fallback `LLM_FALLBACK` quando nenhum doc KB é relevante

- **Knowledge Base** (`knowledge_base.py`)
  - 20 incidentes eSocial documentados cobrindo retificação, certificado, vínculo,
    remuneração, afastamento, transmissão, tabelas e CAT

- **Docker + HuggingFace Spaces**
  - `Dockerfile` com Python 3.11, porta 7860 exposta
  - Deploy automático via `git push origin main`
  - README.md com YAML front-matter obrigatório para HF Spaces

---

*EII — Desenvolvido por Edson · Senior IT Systems Analyst*
