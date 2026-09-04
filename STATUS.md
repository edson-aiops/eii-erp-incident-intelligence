# STATUS.md — EII ERP Incident Intelligence

> **REGRA ABSOLUTA:** Este arquivo e o CHANGELOG.md sao as fontes da verdade do projeto.
> Toda mudanca no codigo, arquitetura, credenciais, dependencias ou decisao de design
> DEVE ser registrada aqui antes do merge na `main`. Sem excecao.

---

## Onde Estamos Agora

**Versao atual:** v3.1 (local) | v3.0 (HuggingFace publico)
**Data de referencia:** 2026-08-31
**Branch ativa:** `feature/claude-mandatory-pii-scrubber`
**App local rodando:** http://127.0.0.1:7860
**App publico (HF):** https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence

### Estado por componente

| Componente | Status | Observacao |
|---|---|---|
| `app.py` (local) | Funcionando | v3.0.1 — tema Default, CSS legível, SmartRouter Groq ativo |
| `app_hf.py` (publico) | Funcionando | versao demo minima para HuggingFace |
| `crag_pipeline.py` | Funcionando | CRAG completo com logprobs |
| `smartrouter/` | Funcionando | 9 providers configurados (~6 LLMs distintos; Kimi/Qwen/DeepSeek compartilham API Groq) |
| `xml_parser.py` | Funcionando | 4 formatos eSocial + PII scrub |
| `knowledge_base.py` | Funcionando | 93 incidentes documentados (eSocial + EFD-Reinf) |
| `mcp_server.py` | Funcionando | fastmcp stdio |
| `eii_handlers.py` | Funcionando | handlers puros sem Gradio |
| `secure_secrets.py` | Funcionando | Windows Credential Manager |
| `batch_processor.py` | Funcionando | processamento paralelo |
| `observability.py` | Parcial | LangSmith opcional |
| `smartrouter_v2/` | ~~Removido~~ | código morto eliminado em 2026-05-28 |
| `src/deep_agents/` | Funcionando | pipeline LangGraph 8 nos (Phase 4 + intel_node) |
| `src/intel_agent/` | Funcionando | analise proativa pos-diagnostico (Phase 4) |
| `api.py` | Funcionando | REST API FastAPI para integracao ERP/HCM |
| `src/` | Em desenvolvimento | estrutura modular futura |
| `src/privacy/scrubber.py` | Funcionando | PII Scrubber obrigatório v2 — S-2200, Id condicional a tpInsc, rede de segurança v2 |

### Agentes ativos no projeto

| Agente | Status | Ultima atividade | Branch atual |
|--------|--------|------------------|--------------|
| Claude (web) | Ativo | Fase 4/5 | feature/claude-* |
| Claude Code (CLI) | Ativo | Fase 4/5 | feature/claude-* |
| Qwen Coder | Ativo | Fase 3/4 | feature/qwen-* |
| **Kimi K2.6** | **Ativo** | **Health check + fixes Fase 5.1 (feature/kimi-healthcheck-fixes mergeada)** | **main** |
| Cowork | Ativo | Fase 3 | feature/cowork-* |
| Edson (humano) | Guardiao | Orquestracao | main |

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

## Branches Abertas

| Branch | Agente | Tarefa | Status | Desde |
|--------|--------|--------|--------|-------|
| `feature/claude-deep-agents-phase4` | Claude | Fase 4 Deep Agents (entregue, aguardando merge ou cleanup) | Pendente review | 2026-05-09 |
| `feature/claude-fix-auth-fallback` | Claude | Fix auth fallback ctypes (entregue, provavelmente mergeado) | Pendente review | 2026-05-08 |
| `feature/qwen-fix-smartrouter-export` | Qwen | Fix smartrouter export (entregue, provavelmente mergeado) | Pendente review | 2026-05-09 |
| `feature/claude-smartrouter-scrubber` | Claude | A3 — SmartRouter com PIIScrubber obrigatório (implementado, aguardando review) | Em progresso | 2026-08-31 |
| `feature/claude-eii-api-deep-agents` | Claude | A3.5 — eii_api.py ligado ao Deep Agents + scrubber obrigatório (implementado, aguardando review) | Em progresso | 2026-09-03 |

---

## Recentemente Concluído

| Branch | Agente | Tarefa | Mergeado em |
|--------|--------|--------|-------------|
| `feature/kimi-agents-update` | Kimi K2.6 | Integrar Kimi ao protocolo multi-agente (KIMI.md, STATUS.md) | 2026-05-19 |
| `feature/kimi-update-devcontainer` | Kimi K2.6 | Atualizar devcontainer para Python 3.13 + docs | 2026-05-19 |
| `feature/kimi-healthcheck-fixes` | Kimi K2.6 | Health check: fix smartrouter exports, modelo deprecado, configs | 2026-05-19 |

---

## Roadmap Detalhado

### Fase 1 — Foundation [CONCLUIDA] `v1.0`

- [x] Gradio UI com tabs: Diagnostico, Aprovacao HITL, Log de Auditoria, Arquitetura
- [x] XML Parser — 4 formatos eSocial
- [x] CRAG Pipeline — Retrieve > Grade > Generate
- [x] Knowledge Base — 93 incidentes documentados (eSocial + EFD-Reinf)
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

- [x] SmartRouter — 9 providers configurados (Groq, Cerebras, Mistral, Google AI, Anthropic, Ollama; Kimi/Qwen/DeepSeek usam API Groq)
- [x] MCP Server — fastmcp expondo `eii_query` e `eii_escalate`
- [x] eii_handlers.py — camada pura Python sem Gradio para uso pelo MCP
- [x] Autenticacao local — login com hash SHA-256, session token, rate limit, timeout
- [x] Modo Mentor — checklist HITL didatico para analistas juniores
- [x] Modo Dual — `app.py` (local/interno) vs `app_hf.py` (publico/vitrine)
- [x] Encoding fix Windows — UTF-8 forcado no terminal
- [x] Avaliacao automatica de qualidade do diagnostico (nó evaluate do pipeline CRAG)
- [x] Batch Processor — analise paralela de multiplos XMLs
- [x] **fix(auth): fallback ctypes para Windows Credential Manager** ← FEITO 2026-05-08
- [x] **fix(smartrouter): qwen-qwq-32b descontinuado substituido** ← FEITO 2026-05-09
- [x] **fix(smartrouter): wrapper diagnosticar_incidente adicionado** ← FEITO 2026-05-09
- [x] **fix(ui): tema Gradio e CSS corrigidos** ← FEITO 2026-05-09

---

### Fase 4 — Deep Agents [CONCLUIDA] `v2.3`

- [x] SmartRouter v2 — refatoracao modular em `smartrouter_v2/` (produzido pelo Qwen, revisado)
- [x] Deep Agents pipeline — LangGraph StateGraph 8 nos implementados em `src/deep_agents/` (parse, router, retrieve, generate, evaluate, reflexion, finalize, intel)
- [x] IntelAgent — agente de inteligencia proativa em `src/intel_agent/`
- [x] Integracao com sistema ERP/HCM real via API — REST API FastAPI em `api.py`
- [x] Tela de admin — painel admin em aba dedicada (Sessoes, Estatisticas, Alterar Senha)
- [x] Upload de arquivo XML — gr.File + handler load_xml_file em app.py

**Responsavel:** Edson + Claude
**Dependencias:** SmartRouter v2 estavel, estrutura `src/` definida

---

### Fase 5 — Observability & Scale [CONCLUIDA] `v3.1`

- [x] LangSmith traces completos — um span por agente
- [x] Dashboard de metricas — MTTR, taxa de resolucao automatica, escalation rate
- [x] KB expandida — 93 incidentes (era 73), EFD-Reinf cobertura completa
- [x] Suporte a EFD-Reinf — parser xml_parser.py com 20 eventos R-* e parse_xml_auto
- [x] Notificacao por e-mail — alerta quando incidente aguarda HITL

---

### Fase 5.1 — Integracao Kimi K2.6 [CONCLUIDA] `v3.1`

- [x] Atualizar AGENTS.md — adicionar Kimi K2.6 na tabela de agentes
- [x] Atualizar WORKFLOW.md — adicionar feature/kimi-* nos exemplos de branch
- [x] Criar KIMI.md — contexto técnico para sessões Kimi (similar a CLAUDE.md)
- [x] Atualizar STATUS.md — registrar Kimi como agente ativo
- [ ] Merge na main — aprovação do Edson
- [ ] Push origin + hf — sincronizar todos os ambientes

**Responsavel:** Kimi K2.6 (analise + geracao docs) + Edson (merge + push)
**Branch:** `feature/kimi-agents-update`

---

### Fase 6 — SaaS & Integrações [PLANEJADO] `v4.0`

- [ ] Multitenancy — isolar dados por empresa (tenant_id em SQLite, ChromaDB e auth)
- [ ] Pipeline EFD-Reinf completo — eventos R-* no deep agents router_node
- [ ] app_hf.py v2 — demo publica com EFD-Reinf e KB lookup visivel

**Dependencias:** piloto com empresa real

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
| Novo agente integrado | Atualizar tabela "Agentes ativos no projeto" |

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
| `smartrouter/` | Roteamento de LLMs | Novo provider, nova estratégia |
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
| `DUAL_MODE.md` | Arquitetura dual local/HF | Mudanca na estratégia de deploy |
| `AGENTS.md` | Protocolo multi-agente | Novo agente, nova regra |
| `KIMI.md` | Contexto para sessoes Kimi | Mudanca no projeto que afeta contexto Kimi |
| `CLAUDE.md` | Contexto tecnico para agentes Claude | Mudanca no projeto que afeta contexto Claude |

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
| 2026-08-31 | **A3 — SmartRouter com PIIScrubber obrigatório** | Integra scrubber v2 no pipeline Deep Agents: parse_node scrubba PII, router_node usa `is_safe_for_remote`, generate_node passa flag ao SmartRouter, finalize_node restaura tokens, retrieve_node usa `scrubbed_payload`; 9 testes de integração + 109 testes totais verdes |
| 2026-08-31 | **PII Scrubber v2 — revisão A23 da seção 3 da spec** | allowlist em blocos de titular, classes TOKENIZAR/CLASSIFICAR/GENERALIZAR, Id/nrInsc condicional a tpInsc, rede de segurança v2; 48 testes s2200 + 15 testes v1 + suíte completa 183 verdes |
| 2026-05-19 | **Integrar Kimi K2.6 ao protocolo multi-agente** | 262K contexto para análise de estado, MCP nativo, open-weight, complementa Claude/Qwen |
| 2026-05-08 | `_read_wincred()` via ctypes em vez de depender so do keyring | keyring nao le credenciais salvas via cmdkey (DOMAIN_PASSWORD tem blob vazio) |
| 2026-05-08 | `cmdkey` descartado como metodo de armazenamento | blob DOMAIN_PASSWORD e inacessivel a aplicacoes por design do Windows |
| 2026-05-08 | `secure_secrets.py set` como padrao para secrets | armazena como CRED_TYPE_GENERIC, legivel pelo app |
| mai/2026 | Modo Dual app.py vs app_hf.py | separar versao interna (auth/dados reais) da vitrine publica |
| mai/2026 | SmartRouter com 9 providers configurados | resiliencia e custo: rotear por tarefa, nao usar 70B pra tudo |
| mai/2026 | SQLite para audit trail | persistencia sem dependencia externa, portavel |
| mai/2026 | Logprobs para confianca | mais confiavel que o LLM auto-reportar confianca no JSON |

---

**Ultima atualizacao:** 2026-08-31 (v3.1 — A3 SmartRouter+Scrubber implementado na branch `feature/claude-smartrouter-scrubber`, aguardando revisao de Edson)
**Autor:** Edson Oliveira
**Mantido por:** obrigatorio — qualquer mudanca no projeto atualiza este arquivo
