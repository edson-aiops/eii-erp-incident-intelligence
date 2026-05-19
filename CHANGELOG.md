# Changelog

All notable changes to EII — ERP Incident Intelligence are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — Fase 5.1

### Added

- **docs(agents): integrar Kimi K2.6 ao protocolo multi-agente**
  - `AGENTS.md` v1.1 — adicionado Kimi K2.6 na tabela de agentes, regras de convivência,
    fluxo padrão, cenários reais, e mapa de arquivos de coordenação
  - `WORKFLOW.md` — adicionado `feature/kimi-*` nos exemplos de branch, cheatsheet,
    e regras anti-retrocesso (6 agentes agora)
  - `KIMI.md` (novo) — contexto técnico específico para sessões Kimi, similar a `CLAUDE.md`:
    stack resumida, arquivos chave, ADRs, comandos comuns, limitações conhecidas,
    MCP server do EII, matriz de uso Kimi vs outros agentes, checklist de sessão
  - `STATUS.md` — adicionada tabela "Agentes ativos no projeto", Fase 5.1 em progresso,
    branch `feature/kimi-agents-update` em "Branches Abertas"
  - Kimi K2.6: 262K context window, arquitetura 1T MoE/32B ativos/384 experts,
    swarm 300 sub-agentes, MCP nativo, open-weight (Modified MIT),
    compatível OpenAI + Anthropic APIs

---

## [3.1] — 2026-05-09

### Changed

- **chore(roadmap): Fase 5 encerrada como [CONCLUIDA] — Fase 6 criada**
  - Fase 5 entregou: LangSmith traces, dashboard métricas, KB 93 incidentes,
    suporte EFD-Reinf (parser + integração), notificador e-mail HITL
  - Itens não priorizados movidos para Fase 6 (SaaS & Integrações `v4.0`):
    Multitenancy, pipeline EFD-Reinf deep agents, app_hf.py v2
  - RAGAS evaluation e API JIRA/ServiceNow descartados do roadmap —
    sem prioridade de negócio identificada no momento
  - Versão bumped: v3.0.1 → v3.1

---

## [3.0.1] — 2026-05-09

### Fixed

- **fix(ui): tema Monochrome causava texto branco em fundo branco** (`app.py`)
  - Substituído `gr.themes.Monochrome()` por `gr.themes.Default()` (tema claro neutro)
  - CSS expandido com overrides explícitos `color: #0f172a !important` para inputs,
    textareas, labels e prose — elimina conflito de variáveis CSS do Gradio 6

- **fix(smartrouter): modelo qwen-qwq-32b descontinuado no Groq** (`smartrouter/config.py`)
  - `ProviderID.QWEN`: `qwen-qwq-32b` → `gemma2-9b-it` (Groq, ainda disponível)
  - `ProviderID.DEEPSEEK`: `qwen-qwq-32b` → `llama-3.3-70b-versatile` (Groq)
  - Modelo causava `Error code: 400 — model_decommissioned`, derrubando todo o pipeline
    e forçando fallback para Ollama mesmo com GROQ_API_KEY configurada

- **fix(smartrouter): pipeline caía para ollama-fallback por assinatura errada** (`crag_pipeline_smartrouter.py`, `app.py`)
  - `app.py` importava `run_crag` (recebe `col, parsed_xml`) mas chamava com
    `xml_content=xml, incident_id=...` — TypeError capturado silenciosamente, resultado: Ollama
  - Adicionado wrapper `diagnosticar_incidente(xml_content, incident_id, ...)` em
    `crag_pipeline_smartrouter.py` — mesma assinatura de `crag_pipeline.diagnosticar_incidente`,
    inclui parse do XML, lazy cache do vector store e retorno `{"success": True, "diagnosis": {...}}`
  - Import em `app.py` atualizado: `run_crag` → `diagnosticar_incidente`
  - Pipeline agora usa Groq (llama-3.3-70b-versatile) corretamente e retorna `Backend: smartrouter`

- **fix(debug): print de debug removido do login_page** (`app.py`)
  - Removido `import hashlib as _hl` e `print(f"[DEBUG-LOGIN] ...")` adicionados na sessão anterior
  - Linha servia para diagnóstico de hash mismatch no login — problema resolvido, código limpo

---

## [Unreleased] — Fase 5

### Added (Fase 5 — v3.0 em progresso)

- **feat(parser): suporte a EFD-Reinf — parse_xml_auto unificado** (2026-05-09)
  - `xml_parser.py`: `EFDREINF_EVENTS` com 20 eventos R-* (R-1000..R-9001) e mapa evt→tag XML
  - `parse_efdreinf_xml`: 3 formatos — retornoLoteEventos, retornoEvt* direto, genérico
    - Suporta `cdRetorno`/`descRetorno` (EFD-Reinf) além de `cdResposta`/`descResposta`
    - `sistema='efdreinf'` no `ParsedXML`, `evento_ids` extraídos do atributo `id=`
  - `parse_xml_auto`: entrada unificada — detecta eSocial vs EFD-Reinf por namespace/tag raiz
    - `parse_xml` alias atualizado para `parse_xml_auto` (backward compat mantida)
  - `ParsedXML.sistema`: novo campo `'esocial'|'efdreinf'`
  - `_extract_ocorrencias`: normaliza tipo `'1'/'2'/'3'` → `'ERROR'/'AVISO'/'INFO'` (EFD-Reinf)
    e suporta tag `<localizacao>` além de `<localizacaoErro>`
  - `scrub_pii`: máscaras LGPD para `cnpjPrestador`, `cnpjTomador`, `cnpjContri`, `cpfProdRural`
  - `SAMPLE_XMLS`: 3 exemplos EFD-Reinf (R-1000/ERF001, R-2010/ERF010, R-2060/ERF021)
  - `tests/test_efdreinf_parser.py`: 29 testes novos — suite total 37 passed

- **feat(notifier): alertas HITL por e-mail** (2026-05-09)
  - `notifier.py` novo — stdlib pura, zero dependencias novas (smtplib + email.mime)
  - Config via keyring: `EII_SMTP_HOST`, `EII_SMTP_PORT`, `EII_SMTP_USER`,
    `EII_SMTP_PASS`, `EII_ALERT_EMAIL` (suporta multiplos destinatarios, virgula)
  - Suporta TLS (porta 587, starttls) e SSL (porta 465, SMTP_SSL)
  - `send_hitl_alert(incident)` envia em background thread — nao bloqueia pipeline
  - E-mail HTML dark-mode com badge de severidade, causa raiz, passos e CTA para dashboard
  - Sem config: log debug silencioso, pipeline continua normalmente (graceful fallback)
  - Integrado em `eii_handlers.query_incident()` — dispara apos `_db_save_pending()`
  - Import lazy com fallback: `eii_handlers` continua funcional mesmo sem `notifier.py`

- **feat(kb): KB expandida — 93 incidentes com cobertura completa EFD-Reinf** (2026-05-09)
  - `knowledge_base.py`: 20 novos incidentes EFD-Reinf adicionados (KB074-KB093)
  - Eventos cobertos: R-1000 (contribuinte), R-2010/R-2020 (serviços tomados/prestados),
    R-2050 (produção rural/FUNRURAL), R-2060 (CPRB/desoneração folha),
    R-2098/R-2099 (reabertura/encerramento período), R-4010/R-4020/R-4040/R-4080/R-4099
    (pagamentos PF/PJ/não identificados/cessão mão de obra), R-9001 (advertências)
  - Erros documentados: ERF001-ERF050 (CNPJ inativo, retenção indevida Simples Nacional,
    tabela progressiva desatualizada, limite exportação CPRB, duplicidade NF, etc.)
  - Cada incidente com: causa_raiz detalhada, passos_resolucao step-by-step,
    validacao, tempo_estimado, impacto e tags para busca semântica
  - KB passa de 73 (apenas eSocial) para 93 incidentes (eSocial + EFD-Reinf)

- **feat(admin): Dashboard de métricas no painel admin** (2026-05-09)
  - `app.py`: `admin_get_metrics()` retorna `(kpi_md, fig_status, fig_trend)`
  - KPIs: MTTR médio, taxa aprovação, taxa escalation, total incidentes, pendentes
  - `fig_status`: gráfico horizontal bar APPROVED/REJECTED/PENDING (matplotlib)
  - `fig_trend`: gráfico de linha dos últimos 30 dias de incidentes (matplotlib)
  - Aba "Métricas" no painel admin substituindo "Estatísticas" — gr.Plot para figuras

- **feat(observability): LangSmith traces completos — 1 span por agente** (2026-05-09)
  - `observability.py`: deteccao de key unificada (`LANGSMITH_API_KEY` ou `LANGCHAIN_API_KEY`);
    habilita `LANGCHAIN_TRACING_V2=true` automaticamente quando key presente
  - `add_run_metadata(metadata)`: novo helper — enriquece o span ativo do LangGraph
    com campos de negocio sem criar span filho duplicado; no-op gracioso quando
    LangSmith nao configurado ou `get_current_run_tree()` indisponivel
  - `router_node`: metadata — incident_id, evento, codigo_erro, severity, pii_detected, routing_decision
  - `generate_node`: metadata — incident_id, routing_decision, confianca, severidade, fonte, kb_refs
  - `evaluate_node`: metadata — eval_verdict, eval_score, eval_iteration, needs_refinement,
    criteria_passed, criteria_failed
  - `finalize_node`: metadata — confianca, severidade, logprob_sim, iteracoes, evaluation_score,
    referencias_kb, has_hitl_alert
  - `intel_node`: metadata — intel_risco_recorrencia, intel_total_90d, intel_tendencia,
    intel_alertas_count, intel_relacionados_count
  - `IntelAgent.run()`: delegado para `_run_impl()` via `@observability.traceable`
    (span `EII.IntelAgent.run`) com fallback gracioso se observability falhar
  - `api.py`: `_traced_diagnose()` wrapper com `@observability.traceable`
    (span `EII.API.diagnose`) aplicado no startup — endpoints rastreados sem
    alterar assinatura do handler FastAPI

---

## [2.2.1] — 2026-05-08

### Fixed
- **fix(auth): fallback ctypes para Windows Credential Manager** (PR #2)
  - `keyring.get_password("EII_Project", key)` retornava `None` em cenarios onde
    o backend `WinVaultKeyring` divergia do formato do Vault — especialmente apos
    tentativas de uso de `cmdkey /add`
  - Adicionado `_read_wincred(service, username)` em `app.py` que chama
    `advapi32.CredReadW` diretamente via `ctypes`, contornando a abstracao do keyring
  - Tenta `CRED_TYPE_GENERIC` (1) e `CRED_TYPE_DOMAIN_PASSWORD` (2) em sequencia;
    retorna o blob UTF-16-LE decodificado quando `CredentialBlobSize > 0`
  - Cadeia de fallback atualizada: keyring → ctypes → .env → os.getenv()
  - Sem novas dependencias (ctypes e stdlib); no-op em plataformas nao-Windows
  - Descoberta colateral: `cmdkey` armazena como `CRED_TYPE_DOMAIN_PASSWORD` com
    blob vazio por design do Windows — inacessivel a aplicacoes. Uso descartado.
    Padrao adotado: `python secure_secrets.py set KEY VALUE` (CRED_TYPE_GENERIC)

### Changed
- `DUAL_MODE.md` — atualizado com padrao de armazenamento de credenciais via keyring
- `STATUS.md` — criado como fonte da verdade do estado atual e roadmap do projeto

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
