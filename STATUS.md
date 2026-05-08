# STATUS.md — EII ERP Incident Intelligence

> **REGRA ABSOLUTA:** Este arquivo e o CHANGELOG.md sao as fontes da verdade do projeto.
> Toda mudanca no codigo, arquitetura, credenciais, dependencias ou decisao de design
> DEVE ser registrada aqui antes do merge na `main`. Sem excecao.

---

## Onde Estamos Agora

**Versao atual:** v2.2 (local) | v1.0 (HuggingFace publico)
**Data de referencia:** 2026-05-08
**Branch ativa:** `main`
**App local rodando:** http://127.0.0.1:7860
**App publico (HF):** https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence

### Estado por componente

| Componente | Status | Observacao |
|---|---|---|
| `app.py` (local) | Funcionando | v2.2 com auth + SmartRouter + HITL |
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

---

### Fase 4 — Deep Agents [EM PROGRESSO] `v2.3` (previsto)

- [ ] SmartRouter v2 — refatoracao modular em `smartrouter_v2/`
- [ ] IntelAgent — agente de inteligencia para sugestao proativa
- [ ] ReflexionAgent — auto-avaliacao e reescrita do diagnostico
- [ ] Deep Agents pipeline — orquestracao multi-agente com LangGraph
- [ ] Integracao com sistema interno real — conectar ao ambiente corporativo
- [ ] Tela de admin — gerenciamento de usuarios e permissoes em `app.py`
- [ ] Upload de arquivo XML — alem de paste direto

**Responsavel:** Edson + Claude
**Dependencias:** SmartRouter v2 estavel, estrutura `src/` definida

---

### Fase 5 — Observability & Scale [PLANEJADO] `v3.0`

- [ ] LangSmith traces completos — um span por agente
- [ ] RAGAS evaluation — faithfulness + relevancy por colecao KB
- [ ] Dashboard de metricas — MTTR, taxa de resolucao automatica, escalation rate
- [ ] KB expandida — 100+ incidentes, cobertura EFD-Reinf (R-xxxx)
- [ ] Suporte a EFD-Reinf — eventos R-2010, R-2020, R-4010, etc.
- [ ] API REST — integracao com JIRA e ServiceNow
- [ ] Notificacao por e-mail — alerta quando incidente aguarda HITL
- [ ] Multitenancy — isolar dados por empresa (para virar SaaS)

**Dependencias:** Fase 4 concluida, validacao com empresa real

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

**Ultima atualizacao:** 2026-05-08
**Autor:** Edson Oliveira
**Mantido por:** obrigatorio — qualquer mudanca no projeto atualiza este arquivo
