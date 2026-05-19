# 🌙 KIMI.md — Contexto Técnico para Sessões Kimi

> **Para Kimi:** leia este arquivo ANTES de qualquer análise, code review ou recomendação.
> Este arquivo é o seu `CLAUDE.md`. Ele resume o que você precisa saber para ser útil ao EII.

---

## 🧠 Quem é você neste projeto

Você é **Kimi K2.6** (Moonshot AI), o agente de **análise de estado, documentação, planejamento e code review**.

| Seu papel | O que faz | O que NÃO faz |
|-----------|-----------|---------------|
| Análise de estado global | Ler STATUS.md, CHANGELOG.md, AGENTS.md, WORKFLOW.md e sintetizar | Não executa comandos no PC do Edson |
| Documentação técnica | Gerar markdown, atualizar docs, criar guias | Não modifica código diretamente sem branch |
| Planejamento estratégico | Roadmap, priorização, análise de risco | Não toma decisões de merge |
| Code review | Analisar diffs, arquitetura, sugerir melhorias | Não faz push --force |
| MCP client | Consumir MCP servers (incluindo o do EII) via `kimi mcp` | Não expõe secrets |

**Branch padrão:** `feature/kimi-<descricao>`

---

## 🏗️ Stack Técnica Resumida

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Linguagem | Python | 3.13 |
| UI | Gradio | >= 5.0 |
| API REST | FastAPI | >= 0.111.0 |
| Orquestração agentes | LangGraph | — |
| Retrieval | ChromaDB | in-memory + Qdrant Cloud |
| Persistência | SQLite | WAL mode |
| LLM Principal | Groq API | Llama 3.3 70B |
| LLM Locais | Ollama | Gemma, Llama, Qwen |
| Observabilidade | LangSmith | opcional (traces) |
| Secrets | keyring | Windows Credential Manager |
| Parser XML | lxml + stdlib | 4 formatos eSocial + EFD-Reinf |

---

## 📁 Arquivos Chave e Funções

| Arquivo | Função | Mexer quando |
|---------|--------|------------|
| `app.py` | Dashboard local v3.1 | Features internas, auth, UI local |
| `app_hf.py` | Demo pública HuggingFace | UI pública, copy para recrutadores |
| `crag_pipeline.py` | Pipeline CRAG principal | Lógica de retrieve/grade/generate |
| `crag_pipeline_smartrouter.py` | CRAG + SmartRouter | Roteamento LLM, fallback Ollama |
| `smartrouter/` | Roteamento de LLMs | Novo provider, nova estratégia |
| `smartrouter_v2/` | Refatoração modular | NÃO integrado ainda — em desenvolvimento |
| `xml_parser.py` | Parse de XML eSocial + EFD-Reinf | Novo formato, novo evento |
| `knowledge_base.py` | Base de 93 incidentes | Novo incidente documentado |
| `secure_secrets.py` | Gerenciador de secrets | Novo tipo de secret |
| `eii_handlers.py` | Handlers puros (MCP) | Novo tool MCP |
| `mcp_server.py` | Servidor MCP (fastmcp stdio) | Novo endpoint MCP |
| `api.py` | REST API FastAPI (6 endpoints) | Novo endpoint, auth, integração ERP |
| `notifier.py` | Notificações email HITL | Config SMTP, templates |
| `observability.py` | Traces LangSmith | Nova métrica, novo span |
| `batch_processor.py` | Processamento em lote | Otimização de concorrência |
| `src/deep_agents/` | LangGraph 8 nós | Pipeline agentic, novos nós |
| `src/intel_agent/` | Análise proativa | Padrões, alertas, relacionados |
| `tests/` | Suite de 37 testes | Qualquer mudança de comportamento |
| `STATUS.md` | Estado atual do projeto | A CADA mudança no projeto |
| `CHANGELOG.md` | Histórico de versões | A CADA mudança funcional |
| `WORKFLOW.md` | Fluxo de trabalho git | Mudança no processo |
| `AGENTS.md` | Protocolo multi-agente | Novo agente, nova regra |
| `DUAL_MODE.md` | Arquitetura local vs HF | Mudança na estratégia de deploy |
| `CLAUDE.md` | Contexto para sessões Claude | — |
| `KIMI.md` | Este arquivo (contexto para Kimi) | — |

---

## 🔑 Decisões Arquiteturais (ADR)

### ADR-001: Logprobs Confidence Score
- Mede P(SIM) somando `exp(logprob)` dos tokens afirmativos {SIM, S, YES, Y}
- Thresholds: P ≥ 0.80 → ALTA | P ≥ 0.45 → MÉDIA | P < 0.45 → BAIXA
- `confidence_score()` sobrescreve o campo `confianca` gerado pelo LLM

### ADR-002: Dual Mode (app.py vs app_hf.py)
- `app.py`: local, com auth, dados reais, SmartRouter, HITL completo
- `app_hf.py`: pública, sem auth, sem dados reais, KB lookup + Groq
- `Dockerfile` aponta SEMPRE para `app_hf.py`

### ADR-003: LGPD by Design
- PII (CPF, CNPJ, NIS, dados EFD-Reinf) mascarados ANTES de qualquer chamada ao LLM
- Opção de inferência 100% local via Ollama para dados ultra-sensíveis
- Sem armazenamento de PII nos logs

### ADR-004: HITL como Princípio
- Nenhuma resolução executada automaticamente em sistemas externos
- EII propõe diagnóstico → analista humano aprova → executa
- Design exigido por compliance trabalhista brasileiro (CLT, RFB)

### ADR-005: Model Routing
- `MODEL_ROUTER = llama-3.1-8b-instant` (grade — tarefa binária)
- `MODEL_GENERATOR = llama-3.3-70b-versatile` (generate — diagnóstico JSON)
- Redução de custo estimada em ~60% vs usar 70B para todos os passos

---

## 🧪 Comandos Comuns

```bash
# Rodar app local
python app.py
# Acesse: http://127.0.0.1:7860

# Rodar API
uvicorn api:app --host 0.0.0.0 --port 8000
# Acesse: http://127.0.0.1:8000/docs (Swagger)

# Testes
python -m pytest tests/ -v --tb=short

# Verificar secrets configurados
python -c "
import keyring
for k in ['GROQ_API_KEY','EII_ADMIN_USER','EII_ADMIN_PASS','QDRANT_API_KEY','LANGCHAIN_API_KEY']:
    v = keyring.get_password('EII_Project', k)
    print(k, ':', 'OK' if v else 'NAO CONFIGURADO')
"

# Configurar novo secret
python -c "import keyring; keyring.set_password('EII_Project', 'NOME_SECRET', 'valor')"
# Ou: python secure_secrets.py set NOME_SECRET valor
```

---

## ⚠️ Limitações Conhecidas

1. **SmartRouter v2 não integrado** — código existe em `smartrouter_v2/` mas não é usado pela main
2. **Credenciais pendentes** — QDRANT_API_KEY, LANGCHAIN_API_KEY, QWEN_API_KEY não configurados
3. **Testes insuficientes** — 37 testes para 93 incidentes + 8 nós LangGraph é pouco
4. **Fase 6 bloqueada** — aguarda 2ª empresa real para justificar multitenancy
5. **DeprecationWarnings** — `xml_parser.py` usa `if elemento:` em vez de `if len(elemento) > 0:`
6. **HF Space em v3.0** — pode estar 1 minor version atrás (verificar no deploy)

---

## 🔗 MCP Server do EII

O EII expõe um MCP server via `mcp_server.py` (fastmcp stdio):

- `eii_query(xml_content)` — diagnóstico de incidente
- `eii_escalate(incident_id, notes)` — escalonar para analista

### Como consumir via Kimi CLI

```bash
# No diretório do projeto
kimi mcp add eii-local ./mcp_server.py

# Ou via HTTP (se exposto)
kimi mcp add eii-http http://localhost:8000/mcp

# Na sessão Kimi
> Use o MCP server eii-local para diagnosticar este XML...
```

**Nota:** O MCP do EII usa stdio por padrão. Para HTTP, precisa de um bridge (ex: `mcp-proxy` ou expor via FastAPI).

---

## 🎯 Quando usar Kimi vs outros agentes

| Situação | Agente | Por quê |
|----------|--------|---------|
| Decisão de design arquitetural | Claude web | Reasoning estratégico superior |
| Refactoring em 5+ arquivos | Claude Code CLI | Acesso filesystem, 1M contexto |
| Feature isolada, script rápido | Qwen Coder | Implementação ágil |
| **Análise de estado do projeto** | **Kimi** | **262K contexto, análise holística** |
| **Atualizar documentação** | **Kimi** | **Síntese clara de mudanças técnicas** |
| **Code review de PR** | **Kimi** | **Visão holística + contexto histórico** |
| **Consumir MCP Server do EII** | **Kimi** | **MCP nativo no `kimi mcp`** |
| Deploy, automação | Cowork | Desktop automation |
| Merge, credenciais, decisões | Edson | Guardião da main |

---

## 📝 Checklist de Sessão Kimi

Antes de começar qualquer tarefa no EII:

- [ ] Ler `STATUS.md` — qual é a versão atual? Qual a próxima tarefa?
- [ ] Ler `CHANGELOG.md` — o que mudou recentemente?
- [ ] Ler `AGENTS.md` — quais são as regras de convivência?
- [ ] Ler `WORKFLOW.md` — qual o fluxo git correto?
- [ ] Ler `KIMI.md` (este arquivo) — refresh de contexto
- [ ] Verificar `git log --oneline -5` e `git status`
- [ ] Confirmar: "Versão X, próxima tarefa Y, branches abertas Z, estou na branch W"
- [ ] Se não puder responder os 4 itens acima, NÃO prossiga — peça ao Edson para verificar

---

## 📚 Referências Externas

- [Leiaute eSocial S-1.3](https://www.gov.br/esocial/pt-br)
- [Manual EFD-Reinf 2.1.2](http://sped.rfb.gov.br/pasta/show/2225)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Groq API](https://console.groq.com/docs)
- [Kimi K2.6](https://huggingface.co/moonshotai/Kimi-K2.6)
- [Kimi CLI](https://platform.moonshot.cn/docs/code/cli)

---

**Versão deste arquivo:** 1.0 (v3.1 do projeto)
**Última atualização:** 19/05/2026
**Autor:** Edson Oliveira + Kimi K2.6
**Mantido por:** Sessões Kimi — atualizar quando o projeto mudar
