# CLAUDE.md — Guia para Claude Code

> Este arquivo orienta o Claude Code ao trabalhar neste repositorio.
> Leia STATUS.md para o estado atual do projeto e WORKFLOW.md para o fluxo de trabalho.

---

## Comandos Essenciais

```powershell
# Rodar o app local
cd C:\Projetos\eii-erp-incident-intelligence
python app.py
# Acesse http://127.0.0.1:7860 | Login: edson.oliveira + senha do Credential Manager

# Rodar a REST API (separado do Gradio)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
# Docs: http://localhost:8000/docs

# Rodar testes
python -m pytest tests/ -v --tb=short

# Verificar secrets
python -c "import keyring; [print(k,':', 'OK' if keyring.get_password('EII_Project',k) else 'NAO') for k in ['GROQ_API_KEY','EII_ADMIN_USER','EII_ADMIN_PASS','EII_API_KEY','EII_SMTP_HOST']]"

# Instalar dependencias
pip install -r requirements.txt

# Build Docker
docker build -t eii .
docker run -p 7860:7860 --env-file .env eii
```

---

## Arquitetura Atual (v3.1)

O EII e um sistema de diagnostico de falhas de integracao eSocial/EFD-Reinf com pipeline CRAG,
LangGraph Deep Agents, SmartRouter multi-LLM, HITL e observabilidade via LangSmith.

### Modo Dual

```
app.py        → versao LOCAL (interno, dados reais, auth, SmartRouter completo)
app_hf.py     → versao PUBLICA (HuggingFace, demo minima, sem auth, sem dados reais)
```

Nunca faca push de `app.py` como entry point do HuggingFace. O `Dockerfile` usa `app_hf.py`.

### Pipeline Principal (CRAG)

```
XML eSocial / EFD-Reinf
    |
[xml_parser.py]         parse + PII scrub (CPF/CNPJ/NIS)
    |
[crag_pipeline.py]
    Step 1: Retrieve    ChromaDB in-memory (sentence-transformers all-MiniLM)
    Step 2: Grade       LLM 8b avalia relevancia (RELEVANTE/IRRELEVANTE)
    Step 3: Generate    LLM 70b gera diagnostico JSON estruturado
    Step 4: Evaluate    avalia qualidade, reflexion se necessario
    |
[SQLite]                persiste como PENDING
    |
[notifier.py]           e-mail de alerta HITL em background thread
    |
[HITL — app.py]         analista aprova ou rejeita
    |
[Audit Log]             registro imutavel
```

### Pipeline Deep Agents (LangGraph — src/deep_agents/)

```
parse_node → router_node → retrieve_node → generate_node
                                               |
                                         evaluate_node
                                          /         \
                                 (ok) finalize   reflexion_node (retry)
                                          |
                                      intel_node    ← IntelAgent proativo
                                          |
                                         END
```

### Knowledge Base

- **93 incidentes** em `knowledge_base.py`
- KB001-KB073: eSocial (S-1000 a S-2240, erros E001-E529)
- KB074-KB093: EFD-Reinf (R-1000, R-2010/2020/2050/2060, R-2098/2099, R-4010/4020/4040/4080/4099, R-9001)

### SmartRouter (9 providers configurados, ~6 LLMs distintos)

Roteamento automatico por tarefa e disponibilidade:
- Groq (Llama 3.1 8b, Llama 3.3 70b)
- Cerebras, Mistral, Google AI, Anthropic (Claude)
- Kimi / Qwen / DeepSeek (aliases que usam API Groq)
- Ollama (local, ativado via checkbox LGPD)

### Autenticacao (app.py)

Credenciais armazenadas no Windows Credential Manager via keyring:
- `EII_ADMIN_USER` — usuario do dashboard
- `EII_ADMIN_PASS` — senha (hash SHA-256 no runtime)

Funcao `get_config_with_fallback(key)` tenta em ordem:
1. `keyring.get_password("EII_Project", key)`
2. `_read_wincred("EII_Project", key)` via ctypes/CredReadW
3. `.env` local
4. `os.getenv(key)`

**NUNCA use `cmdkey /add`** — armazena como DOMAIN_PASSWORD com blob inacessivel.
**USE:** `python -c "import keyring; keyring.set_password('EII_Project', 'KEY', 'valor')"`

---

## Estrutura de Arquivos

```
app.py                  Dashboard local v3.0 (NUNCA vai para HF)
app_hf.py               Demo publica HuggingFace (ainda v1.0)
api.py                  REST API FastAPI v1 (porta 8000, X-API-Key)
notifier.py             Alertas HITL por e-mail (smtplib stdlib)
crag_pipeline.py        Pipeline CRAG principal
smartrouter/            Roteamento multi-LLM (v1, em uso)
smartrouter_v2/         ~~Refatoracao modular~~ removido (código morto, nunca integrado)
xml_parser.py           Parser unificado eSocial + EFD-Reinf (parse_xml_auto)
knowledge_base.py       93 incidentes (eSocial + EFD-Reinf)
eii_handlers.py         Handlers puros Python (MCP + API)
mcp_server.py           Servidor MCP via fastmcp
secure_secrets.py       CLI para Windows Credential Manager
batch_processor.py      Processamento paralelo de XMLs
observability.py        Traces LangSmith + add_run_metadata()
llm_resilient.py        Cliente LLM com retry/fallback
src/deep_agents/        Pipeline LangGraph 8 nos (Phase 4)
src/intel_agent/        IntelAgent — analise proativa pos-diagnostico
tests/                  Suite de testes (pytest)
docs/                   Documentacao tecnica
STATUS.md               Estado atual + roadmap (LEIA PRIMEIRO)
CHANGELOG.md            Historico de mudancas (atualize em cada PR)
WORKFLOW.md             Fluxo de trabalho git
DUAL_MODE.md            Arquitetura dual local/HF
```

---

## Secrets Relevantes

| Secret | Uso |
|---|---|
| `GROQ_API_KEY` | LLM principal (Groq) |
| `EII_ADMIN_USER` / `EII_ADMIN_PASS` | Login dashboard local |
| `EII_API_KEY` | Auth REST API (X-API-Key) |
| `EII_SMTP_HOST/PORT/USER/PASS` | Notificacao e-mail HITL |
| `EII_ALERT_EMAIL` | Destinatario(s) do alerta (virgula para multiplos) |
| `LANGSMITH_API_KEY` | Traces LangSmith (opcional) |

---

## Regras para o Claude

### Antes de qualquer tarefa
1. Leia `STATUS.md` — entenda onde o projeto esta
2. Leia `WORKFLOW.md` — siga o fluxo de branches
3. Leia `DUAL_MODE.md` — confirme qual versao do app sera afetada

### Durante o desenvolvimento
- Crie sempre branch `feature/claude-<descricao>` a partir da `main`
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Nao commite `.env`, `*.bak`, `__pycache__/`

### Ao concluir
- Atualize `STATUS.md` — marque o que foi feito, registre decisoes
- Atualize `CHANGELOG.md` — descreva a mudanca com contexto tecnico
- Crie PR com titulo descritivo e body com test plan
- Merge na `main` somente apos testes passarem

### Segredos e credenciais
- Nunca leia ou exiba valores completos de API keys no output
- Nunca sugira usar `cmdkey /add` para credenciais do EII
- Padrao: `keyring.set_password('EII_Project', 'KEY', 'valor')`

---

## Roadmap Resumido

| Fase | Status | Versao |
|---|---|---|
| 1 — Foundation | Concluida | v1.0 |
| 2 — Intelligence & Compliance | Concluida | v2.0 |
| 3 — Production (SmartRouter + MCP + Auth) | Concluida | v2.2 |
| 4 — Deep Agents (LangGraph + IntelAgent + API + Admin) | Concluida | v2.3 |
| 5 — Observability & Scale (LangSmith + KB 93 + EFD-Reinf parser + Notifier) | Concluida | v3.1 |
| 6 — SaaS & Integracoes (Multitenancy + EFD-Reinf deep agents + app_hf.py v2) | Planejada | v4.0 |

Detalhes completos em `STATUS.md`.

---

**Ultima atualizacao:** 2026-05-09 (v3.1 — Fase 5 concluida, Fase 6 planejada)
**Autor:** Edson Oliveira + Claude
