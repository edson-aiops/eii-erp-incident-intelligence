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

# Rodar testes
python -m pytest tests/ -v --tb=short

# Verificar secrets
python -c "import keyring; [print(k,':', 'OK' if keyring.get_password('EII_Project',k) else 'NAO') for k in ['GROQ_API_KEY','EII_ADMIN_USER','EII_ADMIN_PASS']]"

# Instalar dependencias
pip install -r requirements.txt

# Build Docker
docker build -t eii .
docker run -p 7860:7860 --env-file .env eii
```

---

## Arquitetura Atual (v2.2)

O EII e um sistema de diagnostico de falhas de integracao eSocial com pipeline CRAG,
autenticacao local, SmartRouter multi-LLM e Human-in-the-Loop.

### Modo Dual

```
app.py        → versao LOCAL (interno, ProSecurity, dados reais, auth, SmartRouter completo)
app_hf.py     → versao PUBLICA (HuggingFace, demo minima, sem auth, sem dados reais)
```

Nunca faca push de `app.py` como entry point do HuggingFace. O `Dockerfile` usa `app_hf.py`.

### Pipeline Principal

```
XML eSocial
    |
[xml_parser.py]         parse + PII scrub (CPF/CNPJ/NIS)
    |
[crag_pipeline.py]
    Step 1: Retrieve    ChromaDB in-memory (sentence-transformers all-MiniLM)
    Step 2: Grade       LLM 8b avalia relevancia (RELEVANTE/IRRELEVANTE)
    Step 3: Generate    LLM 70b gera diagnostico JSON estruturado
    |
[EvaluatorAgent]        avalia qualidade, reescreve se necessario
    |
[SQLite]                persiste como PENDING
    |
[HITL — app.py]         analista aprova ou rejeita
    |
[Audit Log]             registro imutavel
```

### SmartRouter (9 LLMs)

Roteamento automatico por tarefa e disponibilidade:
- Groq (Llama 3.1 8b, Llama 3.3 70b)
- Qwen
- Cerebras
- Moonshot
- Mistral
- Google AI
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
app.py                  Dashboard local v2.2 (NUNCA vai para HF)
app_hf.py               Demo publica HuggingFace
crag_pipeline.py        Pipeline CRAG principal
smartrouter/            Roteamento multi-LLM (v1, em uso)
smartrouter_v2/         Refatoracao modular (em desenvolvimento)
xml_parser.py           Parse eSocial + PII scrub
knowledge_base.py       20 incidentes eSocial documentados
eii_handlers.py         Handlers puros Python (para MCP)
mcp_server.py           Servidor MCP via fastmcp
secure_secrets.py       CLI para Windows Credential Manager
batch_processor.py      Processamento paralelo de XMLs
observability.py        Traces LangSmith (opcional)
llm_resilient.py        Cliente LLM com retry/fallback
tests/                  Suite de testes (pytest)
docs/                   Documentacao tecnica
src/                    Estrutura modular futura
STATUS.md               Estado atual + roadmap (LEIA PRIMEIRO)
CHANGELOG.md            Historico de mudancas (atualize em cada PR)
WORKFLOW.md             Fluxo de trabalho git
DUAL_MODE.md            Arquitetura dual local/HF
```

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
| 4 — Deep Agents | Em progresso | v2.3 |
| 5 — Observability & Scale | Planejado | v3.0 |

Detalhes completos em `STATUS.md`.

---

**Ultima atualizacao:** 2026-05-08
**Autor:** Edson Oliveira + Claude
