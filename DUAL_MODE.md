# 🎭 DUAL_MODE.md — Arquitetura Dual do EII

> **Regra de ouro:** O EII tem duas faces. Este documento explica qual usar quando.
> Consulte ANTES de modificar `app.py`, `app_hf.py` ou criar variantes.

---

## 🎯 Conceito

O EII vive em **um único repositório** mas serve **dois públicos diferentes** com necessidades opostas:

```
┌─────────────────────────────────────────────────────────────────┐
│                    eii-erp-incident-intelligence                │
│                                                                 │
│   ┌───────────────────────┐         ┌────────────────────────┐ │
│   │      app.py           │         │      app_hf.py         │ │
│   │   (LOCAL — INTERNO)   │         │  (HUGGINGFACE — VITRINE)│ │
│   │                       │         │                        │ │
│   │  Edson + equipe interna  │         │  Recrutadores + público │ │
│   │  Dados sensíveis OK   │         │  Sem dados reais       │ │
│   │  Ollama habilitado    │         │  Apenas Groq cloud     │ │
│   └───────────────────────┘         └────────────────────────┘ │
│              │                               │                  │
│              └───────────┬───────────────────┘                  │
│                          ▼                                       │
│           ┌──────────────────────────────────┐                  │
│           │  CÓDIGO COMPARTILHADO             │                  │
│           │  • crag_pipeline.py               │                  │
│           │  • smartrouter/                   │                  │
│           │  • knowledge_base.py              │                  │
│           │  • xml_parser.py                  │                  │
│           │  • mcp_server.py                  │                  │
│           └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Comparação Lado a Lado

| Característica | `app.py` (LOCAL) | `app_hf.py` (PÚBLICO) |
| --- | --- | --- |
| **Tamanho do arquivo** | 29 KB | 4.5 KB |
| **Versão Gradio** | 4.44.0 | >= 5.0.0 |
| **Python** | 3.11 (Codespace) ou 3.13 (PC) | 3.13 (HF Docker) |
| **Autenticação** | ✅ Login (edson.oliveira) + senha | ❌ Acesso aberto |
| **Pipeline** | CRAG completo + Deep Agents v0.5 | Chamada Groq direta |
| **LLM Backend** | SmartRouter (9 LLMs) + Ollama opcional | `llama-3.1-8b-instant` (Groq) |
| **Modo Mentor + HITL** | ✅ Disponível | ❌ Removido |
| **Roteamento LGPD** | ✅ Forçar Local (Ollama) | ❌ Não tem |
| **Observabilidade** | LangSmith `@traceable` | Nenhuma |
| **Rate limiting** | 10 req / 60s por sessão | ❌ Não tem |
| **Session timeout** | 30 min | ❌ Não tem |
| **Audit trail** | SQLite com hash de auditoria | ❌ Não tem |
| **Encoding fix Windows** | ✅ UTF-8 forçado | ❌ Não precisa |
| **Vai para HuggingFace?** | ❌ NUNCA | ✅ Sim (deploy automático) |

---

## 🚀 Como Rodar Cada Versão

### Versão LOCAL (`app.py`)

**Quando usar:** desenvolvimento, demonstração interna, testes com dados reais, validação do caminho LGPD.

```powershell
cd C:\Projetos\eii-erp-incident-intelligence

# Garantir que .env está configurado (auth + secrets)
# Não suba .env para o git!

# Rodar
python app.py

# Acesse http://127.0.0.1:7860
# Login: edson.oliveira + senha do .env
```

**Variáveis de ambiente esperadas no `.env`:**
- `GROQ_API_KEY` (obrigatória)
- `QDRANT_URL`, `QDRANT_API_KEY` (recomendadas)
- `EII_RETRIEVAL_BACKEND=qdrant`
- `LANGSMITH_API_KEY` (para observability)
- `OLLAMA_BASE_URL=http://localhost:11434` (se rodar Ollama local)
- `EII_USERNAME`, `EII_PASSWORD_HASH` (auth)

### Versão PÚBLICA (`app_hf.py`)

**Quando usar:** quando o HuggingFace Space rebuilda. Você não roda esta manualmente — ela é executada pelo HF a partir do `Dockerfile`.

```bash
# Esta versão NÃO é para rodar localmente.
# Ela existe para o HF Space:
# https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence
```

**Variáveis de ambiente esperadas no Space:**
- `GROQ_API_KEY` (única obrigatória, configurada como Secret no HF)

---

## 📦 O Que Cada Versão Contém

### `app.py` (LOCAL) inclui:
- `import` de `crag_pipeline`, `smartrouter`, `mcp_server`, `observability`
- Tela de login com hash de senha
- Sessão com expiração
- Rate limiting por IP/usuário
- Modo Mentor (checklist HITL)
- Forçar Local (Ollama)
- Audit trail SQLite
- Tudo o que o `eii-brasil` tinha

### `app_hf.py` (PÚBLICO) inclui:
- Apenas: `gradio`, `requests`, chamada HTTP para Groq
- Função `call_groq(prompt)` simples
- Interface mínima de demonstração
- Sem autenticação
- Sem rate limit
- Mensagem clara de "demo de portfólio"

---

## 🛡️ Regras de Manutenção

### REGRA 1 — `app.py` NUNCA vai para o HuggingFace

A versão local tem dependências pesadas (Ollama, LangSmith, smartrouter completo) que tornariam o Space lento e potencialmente quebrado. Mantenha sempre `app_hf.py` como entry point no `Dockerfile` do HF.

### REGRA 2 — Mudanças no "miolo" afetam os dois

Se você editar:
- `crag_pipeline.py`
- `smartrouter/`
- `knowledge_base.py`
- `xml_parser.py`
- `mcp_server.py`

… as mudanças aparecerão em ambas as versões automaticamente. Teste em **ambas** antes de mergear na `main`.

### REGRA 3 — Mudanças em `app.py` ficam no local

Adicionar uma feature interna (ex: novo painel admin, integração com sistema interno real) só vai em `app.py`. Não tente "portar" para `app_hf.py` se não fizer sentido publicamente.

### REGRA 4 — Mudanças em `app_hf.py` ficam no público

Melhorar a UI da demo, adicionar exemplos pré-carregados, ajustar copy para recrutadores → muda apenas `app_hf.py`. Não polua `app.py` com features só de demo.

### REGRA 5 — Nunca commitar `.env`

O `.gitignore` já bloqueia, mas reforçando: o `.env` tem credenciais (senha admin, API keys reais). Nunca suba.

---

## 🎬 Cenários Práticos

### Cenário A: "Quero adicionar suporte a um novo evento eSocial S-1210"

**Onde editar:**
- `xml_parser.py` (parsing do novo evento)
- `knowledge_base.py` (adicionar regras do S-1210)
- `crag_pipeline.py` (se mudar fluxo)

**Onde NÃO precisa mexer:**
- `app.py` e `app_hf.py` (eles consomem o pipeline)

**Resultado:** as duas versões automaticamente suportam S-1210.

---

### Cenário B: "Quero adicionar tela de admin para gerenciar usuários"

**Onde editar:**
- `app.py` apenas

**Onde NÃO mexer:**
- `app_hf.py` (versão pública não precisa de admin)

**Resultado:** local ganha tela de admin, público continua igual.

---

### Cenário C: "Quero melhorar a UI de exemplo do HF para impressionar recrutadores"

**Onde editar:**
- `app_hf.py` apenas

**Onde NÃO mexer:**
- `app.py` (local já tem UI completa)

**Resultado:** público fica mais bonito, local continua igual.

---

### Cenário D: "Quero adicionar SmartRouter na versão pública também"

**Avalie antes:**
- SmartRouter tem 9 providers, alguns pagos
- HF Space é demo, não precisa de routing complexo
- Adicionar SmartRouter pode quebrar o build do HF

**Recomendação:** mantenha o público simples. Quem quiser ver o SmartRouter funcionando, vai no GitHub e roda local.

---

## 🚦 Deploy Workflow

### Quando você modifica `app.py`:

```powershell
# Push normal (workflow padrão)
git checkout main
git merge feature/claude-X
git push origin main
git push hf main

# Resultado:
# - GitHub atualizado ✅
# - HF rebuilda mas continua usando app_hf.py ✅
# - Espaço público continua igual ✅
# - Você roda app.py atualizado localmente
```

### Quando você modifica `app_hf.py`:

```powershell
# Mesma coisa
git push origin main
git push hf main

# Resultado:
# - HF detecta mudança em app_hf.py
# - Faz rebuild do Space (3-5 min)
# - Versão pública atualizada
```

### Quando você modifica `crag_pipeline.py` ou outro código compartilhado:

```powershell
# IMPORTANTE: testar nas duas versões antes de mergear

# 1. Testar local
python app.py
# Faça testes manuais

# 2. Testar pública (se possível)
python app_hf.py  # opcional, simula o HF localmente

# 3. Se ambos OK, push
git push origin main
git push hf main

# Resultado:
# - Código compartilhado atualizado
# - Local + Público consomem nova versão
# - HF rebuilda automaticamente
```

---

## 🧪 Validação Pré-Deploy

Antes de fazer push da `main`, rode:

```powershell
# Dentro de C:\Projetos\eii-erp-incident-intelligence

# 1. Testes unitários
python -m pytest tests/ -v --tb=short

# 2. Smoke test do app.py (local)
python app.py
# Confirme: login funciona, diagnóstico funciona, encerre com Ctrl+C

# 3. Validar import do app_hf.py (verifica que não quebrou)
python -c "import app_hf; print('app_hf.py import OK')"
```

Se tudo passar, pode pushar.

---

## 📋 Checklist Mensal

Uma vez por mês, faça este check para garantir que as duas versões estão alinhadas:

```text
☐ Rodei `python app.py` e funciona end-to-end?
☐ HuggingFace Space está com status Running?
☐ Testei um XML real no app.py local?
☐ Testei um XML simples no Space público?
☐ Os testes pytest passam (8/8 na suite phase2)?
☐ O .env local não foi commitado por engano?
☐ A branch main no GitHub está alinhada com hf/main?
```

---

## 🎯 Estratégia de Evolução

### Curto prazo (próximas semanas)
- Manter `app.py` evoluindo com features avançadas (SmartRouter, Deep Agents, IntelAgent)
- Manter `app_hf.py` mínimo, focado em demonstrar diagnóstico de XML

### Médio prazo (3-6 meses)
- Quando rodar piloto com empresa real, criar branch `feature/claude-pilot-X` baseada em `app.py`
- Eventualmente, separar `app.py` em módulos menores (auth, dashboard, admin)

### Longo prazo (após validação)
- Se EII virar produto comercial, `app.py` pode virar app SaaS multitenancy
- `app_hf.py` continua como vitrine/demo gratuita

---

## 📚 Referências Cruzadas

- **Como trabalhar no repo:** `WORKFLOW.md`
- **Histórico de versões:** tags `v2.2`, `v2.3`, etc.
- **Arquitetura técnica:** `CLAUDE.md`
- **Setup do ambiente:** `.devcontainer/README.md`

---

**Última atualização:** maio/2026
**Autor:** Edson Oliveira + Claude
**Mantido por:** Disciplina + este arquivo
