# STATUS.md — EII ERP Incident Intelligence

> **REGRA ABSOLUTA:** Este arquivo e o CHANGELOG.md sao as fontes da verdade do projeto.
> Toda mudanca no codigo, arquitetura, credenciais, dependencias ou decisao de design
> DEVE ser registrada aqui antes do merge na `main`. Sem excecao.

---

## Onde Estamos Agora

**Versao atual:** v3.1 (local) | v3.0 (HuggingFace publico)
**Data de referencia:** 2026-05-09
**Branch ativa:** `main`
**App local rodando:** http://127.0.0.1:7860
**App publico (HF):** https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence

### Estado por componente

| Componente | Status | Observacao |
|---|---|---|
| `app.py` (local) | Funcionando | v3.0.1 — tema Default, CSS legível, SmartRouter Groq ativo |
| `app_hf.py` (publico) | Funcionando | versao demo minima para HuggingFace |
| `crag_pipeline.py` | Funcionando | CRAG completo com logprobs |
| `smartrouter/` | Funcionando | 9 LLMs roteados |
| `xml_parser.py` | Funcionando | 4 formatos eSocial + PII scrub |
| `knowledge_base.py` | Funcionando | 20 incidentes documentados |
| `mcp_server.py` | Funcionando | fastmcp stdio |
| `eii_handlers.py` | Funcionando | handlers puros sem Gradio |
| `secure_secrets.py` | Funcionando | Windows Credential Manager |
| `batch_processor.py` | Funcionando | processamento paralelo |
| `observability.py` | Parcial | LangSmith opcional |
| `smartrouter_v2/` | Em desenvolvimento | nao integrado ainda |
| `src/deep_agents/` | Funcionando | pipeline LangGraph 8 nos (Phase 4 + intel_node) |
| `src/intel_agent/` | Funcionando | analise proativa pos-diagnostico (Phase 4) |
| `api.py` | Funcionando | REST API FastAPI para integracao ERP/HCM |
| `src/` | Em desenvolvimento | estrutura modular futura |

### Credenciais configuradas (Windows Credential Manager)

| Secret | Configurado | Como configurar |
|---|---|---|
| `GROQ_API_KEY` | Sim | `python -c "import keyring; keyring.set_password('EII_Project','GROQ_API_KEY','gsk_...')"` |
| `EII_ADMIN_USER` | Sim (edson.oliveira) | `python -c "import keyring; keyring.set_password('EII_Project','EII_ADMIN_USER','seu_usuario')"` |
| `EII_ADMIN_PASS` | Sim | `python -c "import keyring; keyring.set_password('EII_Project','EII_ADMIN_PASS','sua_senha')"` |
| `QDRANT_API_KEY` | Nao | idem acima |
| `LANGCHAIN_API_KEY` | Nao | idem acima |
| `QWEN_API_KEY` | Nao | idem acima |

> NUNCA use `cmdkey /add` para guardar credenciais do EII.
> `cmdkey` usa CRED_TYPE_DOMAIN_PASSWORD cujo blob e inacessivel a aplicacoes.
> Use sempre `keyring.set_password()` ou `python secure_secrets.py set KEY VALUE`.

---

## Roadmap Detalhado

### Fase 1 — Foundation [CONCLUIDA] `v1.0`

- [x] Gradio UI com tabs: Diagnostico, Aprovacao HITL, Log de Auditoria, Arquitetura
- [x] XML Parser — 4 formatos eSocial
- [x] CRAG Pipeline — Retrieve > Grade > Generate
- [x] Knowledge Base — 20 incidentes documentados
- [x] Docker + HuggingFace Spaces deploy
- [x] Tema dark IBM Plex Mono/Sans

---

### Fase 2 — Intelligence & Compliance [CONCLUIDA] `v2.0`

- [x] PII Scrubbing LGPD — CPF, CNPJ, NIS mascarados antes de qualquer envio ao LLM
- [x] SQLite Persistence — audit trail imutavel com decided_at, status, notas
- [x] Cost-Optimized Model Routing — 8b para grade, 70b para generate
- [x] Logprobs Confidence Score (ADR-001) — P(SIM) via tokens afirmativos
- [x] Suite de testes — 46 testes, zero chamadas reais a API

---

### Fase 3 — Production [CONCLUIDA] `v2.2`

- [x] SmartRouter — 9 LLMs (Groq, Qwen, Cerebras, Moonshot, Mistral, Google AI, Ollama)
- [x] MCP Server — fastmcp expondo `eii_query` e `eii_escalate`
- [x] eii_handlers.py — camada pura Python sem Gradio para uso pelo MCP
- [x] Autenticacao local — login com hash SHA-256, session token, rate limit, timeout
- [x] Modo Mentor — checklist HITL didatico para analistas juniores
- [x] Modo Dual — `app.py` (local/interno) vs `app_hf.py` (publico/vitrine)
- [x] Encoding fix Windows — UTF-8 forcado no terminal
- [x] EvaluatorAgent — avaliacao automatica de qualidade do diagnostico
- [x] Batch Processor — analise paralela de multiplos XMLs
- [x] **fix(auth): fallback ctypes para Windows Credential Manager** ← FEITO 2026-05-08
  - `_read_wincred()` via `advapi32.CredReadW` — le GENERIC e DOMAIN_PASSWORD
  - resolve incompatibilidade entre `keyring` e credenciais no Vault
  - PR #2 mergeado em `main`
- [x] **fix(smartrouter): qwen-qwq-32b descontinuado substituido** ← FEITO 2026-05-09
  - `gemma2-9b-it` (QWEN) + `llama-3.3-70b-versatile` (DEEPSEEK) em `smartrouter/config.py`
- [x] **fix(smartrouter): wrapper diagnosticar_incidente adicionado** ← FEITO 2026-05-09
  - `crag_pipeline_smartrouter.py` — assinatura compatível com `crag_pipeline.diagnosticar_incidente`
  - Pipeline agora usa Groq corretamente (antes caía em ollama-fallback por TypeError silencioso)
- [x] **fix(ui): tema Gradio e CSS corrigidos** ← FEITO 2026-05-09
  - `Monochrome` → `Default` + overrides CSS explícitos para texto escuro em fundo claro

---

### Fase 4 — Deep Agents [EM PROGRESSO] `v2.3` (previsto)

- [x] SmartRouter v2 — refatoracao modular em `smartrouter_v2/` (produzido pelo Qwen, revisado)
- [x] Deep Agents pipeline — LangGraph StateGraph 7 nos implementados em `src/deep_agents/`
  - parse_node: reutiliza xml_parser.parse_esocial_xml() + PII scrub
  - router_node: roteia por severidade do evento eSocial (CRITICAL/HIGH->deep_reasoning, PII->sensitive_data)
  - retrieve_node: ChromaDB + grade() de crag_pipeline.py
  - generate_node: crag_pipeline.generate() com corrective_hint da reflexao
  - evaluate_node: crag_pipeline.evaluate_diagnosis() com guarda MAX_ITERATIONS
  - reflexion_node: crag_pipeline.reflect() -> corrective_hint para proxima iteracao
  - finalize_node: ADR-001 logprobs confidence gate + final_result estruturado
- [x] IntelAgent — agente de inteligencia proativa em `src/intel_agent/`
  - analyze_patterns: frequencia/taxa aprovacao/MTTR/tendencia via SQLite
  - suggest_related: incidentes KB por sobreposicao de tags
  - build_alerts: alertas automaticos por thresholds
  - intel_node: no LangGraph pos-finalize, adiciona proactive_insights ao AgentState
- [x] Integracao com sistema ERP/HCM real via API — REST API FastAPI em `api.py`
  - GET /health, POST /v1/diagnose, GET /v1/incidents, GET /v1/incidents/{id}
  - POST /v1/incidents/{id}/approve, POST /v1/incidents/{id}/reject
  - Auth via X-API-Key (keyring EII_API_KEY)
- [x] Tela de admin — painel admin em aba dedicada (Sessoes, Estatisticas, Alterar Senha)
- [x] Upload de arquivo XML — gr.File + handler load_xml_file em app.py

**Responsavel:** Edson + Claude
**Dependencias:** SmartRouter v2 estavel, estrutura `src/` definida

---

### Fase 5 — Observability & Scale [CONCLUIDA] `v3.1`

- [x] LangSmith traces completos — um span por agente
  - observability.py: suporte a LANGSMITH_API_KEY + LANGCHAIN_API_KEY, add_run_metadata()
  - router/generate/evaluate/finalize/intel nodes: add_run_metadata com campos de negocio
  - IntelAgent.run(): @traceable via observability (span EII.IntelAgent.run)
  - api.py: _traced_diagnose com @traceable (span EII.API.diagnose)
- [x] Dashboard de metricas — MTTR, taxa de resolucao automatica, escalation rate
  - admin_get_metrics() retorna (kpi_md, fig_status, fig_trend) com matplotlib
  - gr.Plot para graficos de status (barra horizontal) e tendencia (linha 30d)
  - Aba "Metricas" no painel admin do app.py
- [x] KB expandida — 93 incidentes (era 73), EFD-Reinf cobertura completa
  - KB074-KB093: 20 incidentes EFD-Reinf adicionados
  - Cobre: R-1000, R-2010, R-2020, R-2050, R-2060, R-2098, R-2099, R-4010, R-4020, R-4040, R-4080, R-4099, R-9001
  - Erros ERF001-ERF050 documentados com causa_raiz, passos_resolucao, validacao
- [x] Suporte a EFD-Reinf — parser xml_parser.py com 20 eventos R-* e parse_xml_auto
  - EFDREINF_EVENTS: R-1000, R-2010, R-2020, R-2050, R-2060, R-2098, R-2099, R-4010..R-4099, R-9001
  - parse_efdreinf_xml: retornoLoteEventos + retornoEvt* + generico; cdRetorno/descRetorno
  - parse_xml_auto: entrada unificada detecta eSocial vs EFD-Reinf automaticamente
  - PII scrubbing: cnpjPrestador, cnpjTomador, cnpjContri, cpfProdRural
  - 29 novos testes (suite total: 37 passed)
- [x] Notificacao por e-mail — alerta quando incidente aguarda HITL
  - `notifier.py`: stdlib pura (smtplib + email.mime), sem nova dependencia
  - Config: EII_SMTP_HOST/PORT/USER/PASS + EII_ALERT_EMAIL via keyring
  - Envia em background thread (nao bloqueia pipeline)
  - HTML com severidade, causa raiz, passos e link para o dashboard
  - Suporta TLS (porta 587) e SSL (porta 465); multiplos destinatarios (virgula)
  - Integrado em `eii_handlers.query_incident()` pos _db_save_pending

---

### Fase 6 — SaaS & Integrações [PLANEJADO] `v4.0`

- [ ] Multitenancy — isolar dados por empresa (tenant_id em SQLite, ChromaDB e auth)
  - Requisito: segunda empresa real solicitando acesso
  - Impacto: auth, SQLite, ChromaDB, API, app.py
- [ ] RAGAS evaluation — faithfulness + relevancy por colecao KB
  - Requisito: aprovacao de nova dependencia (`pip install ragas`) em requirements.txt
- [ ] API REST — integracao com JIRA e ServiceNow
  - Requisito: credenciais JIRA_API_KEY e SERVICENOW_URL configuradas via keyring
- [ ] Pipeline EFD-Reinf completo — eventos R-* no deep agents router_node
- [ ] app_hf.py v2 — demo publica com EFD-Reinf e KB lookup visivel

**Dependencias:** piloto com empresa real, aprovacao de dependencias externas

---

## Protocolo de Mudancas

### Toda mudanca no projeto DEVE seguir esta ordem:

```
1. Criar branch   → git checkout -b feature/claude-<descricao>
2. Desenvolver    → commits com Conventional Commits
3. Testar         → python app.py + pytest tests/
4. Atualizar docs → STATUS.md (esta secao) + CHANGELOG.md
5. PR             → gh pr create --base main
6. Merge          → gh pr merge + git push origin main
7. Push HF        → git push hf main (se afeta app_hf.py)
```

### O que registrar em STATUS.md quando mudar algo:

| Tipo de mudanca | Onde registrar |
|---|---|
| Nova feature concluida | Marcar [x] no roadmap da fase correspondente |
| Bug corrigido | Adicionar linha na fase atual com `fix(escopo): descricao` |
| Credencial nova configurada | Atualizar tabela "Credenciais configuradas" |
| Novo componente criado | Adicionar linha na tabela "Estado por componente" |
| Dependencia adicionada | Registrar em CHANGELOG.md + atualizar requirements.txt |
| Decisao de arquitetura | Registrar em CHANGELOG.md com contexto do porque |
| Fase concluida | Mover para [CONCLUIDA] + adicionar tag git |

### O que registrar em CHANGELOG.md quando mudar algo:

- **Toda** alteracao com impacto funcional
- Formato: `## [versao] — data` > `### Added / Changed / Fixed / Removed`
- Contexto tecnico suficiente para outro dev entender sem ler o codigo

---

## Arquivos Chave — Mapa Rapido

| Arquivo | Funcao | Mexer quando |
|---|---|---|
| `app.py` | Dashboard local v2.2 | Features internas, auth, UI local |
| `app_hf.py` | Demo publica HuggingFace | UI publica, copy para recrutadores |
| `crag_pipeline.py` | Pipeline CRAG principal | Logica de retrieve/grade/generate |
| `smartrouter/` | Roteamento de LLMs | Novo provider, nova estrategia |
| `xml_parser.py` | Parse de XML eSocial | Novo formato, novo evento |
| `knowledge_base.py` | Base de incidentes | Novo incidente documentado |
| `secure_secrets.py` | Gerenciador de secrets | Novo tipo de secret |
| `eii_handlers.py` | Handlers puros (MCP) | Novo tool MCP |
| `mcp_server.py` | Servidor MCP | Novo endpoint MCP |
| `batch_processor.py` | Processamento em lote | Otimizacao de concorrencia |
| `observability.py` | Traces LangSmith | Nova metrica, novo span |
| `tests/` | Suite de testes | Qualquer mudanca de comportamento |
| `STATUS.md` | Este arquivo | A CADA mudanca no projeto |
| `CHANGELOG.md` | Historico de versoes | A CADA mudanca funcional |
| `WORKFLOW.md` | Fluxo de trabalho git | Mudanca no processo |
| `DUAL_MODE.md` | Arquitetura dual local/HF | Mudanca na estrategia de deploy |

---

## Como Rodar

```powershell
# App local (desenvolvimento e uso interno)
cd C:\Projetos\eii-erp-incident-intelligence
python app.py
# Acesse: http://127.0.0.1:7860
# Login: edson.oliveira + senha configurada no Credential Manager

# Testes
python -m pytest tests/ -v --tb=short

# Verificar secrets configurados
python -c "
import keyring
for k in ['GROQ_API_KEY','EII_ADMIN_USER','EII_ADMIN_PASS','QDRANT_API_KEY']:
    v = keyring.get_password('EII_Project', k)
    print(k, ':', 'OK' if v else 'NAO CONFIGURADO')
"
```

---

## Historico Resumido de Decisoes

| Data | Decisao | Motivo |
|---|---|---|
| 2026-05-08 | `_read_wincred()` via ctypes em vez de depender so do keyring | keyring nao le credenciais salvas via cmdkey (DOMAIN_PASSWORD tem blob vazio) |
| 2026-05-08 | `cmdkey` descartado como metodo de armazenamento | blob DOMAIN_PASSWORD e inacessivel a aplicacoes por design do Windows |
| 2026-05-08 | `secure_secrets.py set` como padrao para secrets | armazena como CRED_TYPE_GENERIC, legivel pelo app |
| mai/2026 | Modo Dual app.py vs app_hf.py | separar versao interna (com auth/dados reais) da vitrine publica |
| mai/2026 | SmartRouter com 9 LLMs | resiliencia e custo: rotear por tarefa, nao usar 70B pra tudo |
| mai/2026 | SQLite para audit trail | persistencia sem dependencia externa, portavel |
| mai/2026 | Logprobs para confianca | mais confiavel que o LLM auto-reportar confianca no JSON |

---

**Ultima atualizacao:** 2026-05-09 (v3.0.1 — fixes UI tema, SmartRouter qwen-qwq-32b, pipeline signature)
**Autor:** Edson Oliveira
**Mantido por:** obrigatorio — qualquer mudanca no projeto atualiza este arquivo
