# 🤖 AGENTS.md — Protocolo Multi-Agente do EII

> **Regra de ouro:** Claude, Qwen e Cowork não conversam entre si. Eles se coordenam **através deste repositório**.
> Este arquivo é o protocolo. Todo agente DEVE ler antes de começar qualquer tarefa.

---

## 🎯 Quem são os agentes neste projeto

| Agente | Onde roda | Forte em | Branch |
| --- | --- | --- | --- |
| **Claude (chat web)** | claude.ai | Estratégia, arquitetura, debugging, análise crítica | `feature/claude-*` |
| **Claude Code (CLI)** | Terminal local ou Codespace | Implementação extensa, refactoring, multi-arquivo | `feature/claude-*` |
| **Qwen Coder** | CLI ou IDE local | Implementação rápida, testes, scripts | `feature/qwen-*` |
| **Cowork** | Desktop app | Automação de arquivos, deploys, organização | `feature/cowork-*` |
| **Edson (humano)** | PowerShell, terminal | Orquestração, push final, decisões críticas | `main` (guardião) |

---

## 📋 Protocolo de Início de Sessão (OBRIGATÓRIO)

Todo agente, em toda sessão nova, executa em ordem:

### Passo 1 — Sincronizar com estado oficial

```bash
git checkout main
git pull origin main
```

### Passo 2 — Ler arquivos de coordenação (em ordem)

1. `STATUS.md` — situação atual, branches abertas, próxima tarefa
2. `WORKFLOW.md` — regras de fluxo de trabalho git
3. `DUAL_MODE.md` — arquitetura local (app.py) vs HF (app_hf.py)
4. `AGENTS.md` — este arquivo
5. `CHANGELOG.md` — mudanças recentes

### Passo 3 — Verificar git

```bash
git log --oneline -10        # últimos commits
git branch -a                # branches ativas
git status                   # working tree
```

### Passo 4 — Confirmar entendimento (responder antes de agir)

1. Qual é a versão atual do projeto?
2. Qual é a próxima tarefa prioritária no STATUS.md?
3. Existem branches `feature/*` abertas? Quais?
4. Em qual branch eu estou agora?

**Se a IA não puder responder os 4 itens, ela não leu. Não execute mudanças.**

---

## 🛡️ Regras Rígidas de Convivência

### REGRA 1 — Toda mudança em feature branch
```bash
# Claude (web ou Code)
git checkout -b feature/claude-<descricao>

# Qwen
git checkout -b feature/qwen-<descricao>

# Cowork
git checkout -b feature/cowork-<descricao>

# Bugfixes urgentes (qualquer agente)
git checkout -b fix/<descricao>
```

**NUNCA modificar `main` diretamente.**

### REGRA 2 — Atualizar STATUS.md ao iniciar e terminar

**Ao iniciar:**
- Adicionar entrada em "Branches Abertas" com nome do agente
- Mover task de "Pendentes" para "Em Progresso"

**Ao terminar:**
- Mover para "Recentemente Concluído"
- Atualizar timestamp no topo do arquivo

### REGRA 3 — Conventional Commits identificando o agente

```bash
# Formato: tipo(escopo): mensagem
git commit -m "feat(crag): adicionar Reflexion loop"
git commit -m "fix(smartrouter): corrigir modelo deprecated"
git commit -m "docs(readme): atualizar para v3.1"
git commit -m "test(parser): adicionar casos EFD-Reinf"
git commit -m "refactor(kb): consolidar imports"
git commit -m "chore(deps): atualizar gradio"
```

Tipos válidos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `style`.

### REGRA 4 — Edson é o único que pode mergear na main

Qualquer agente:
1. Cria feature branch
2. Faz mudanças
3. Commita na feature branch
4. **Pergunta ao Edson antes do merge**

Edson decide:
- Aprovar e mergear
- Pedir ajustes
- Reverter

### REGRA 5 — NUNCA push --force em main

Push forçado **só** em feature branches próprias. A `main` é sagrada.

### REGRA 6 — NUNCA commitar secrets ou arquivos sensíveis

Bloqueados pelo `.gitignore` (e por bom senso):
- `.env`, `.env.local`, `.env.production`
- `*.bak`, `*.backup`
- `__pycache__/`, `venv/`, `.venv/`
- `*.log`, `*.sqlite-journal`
- `.claude/` (configuração local Claude Code)
- Credenciais reais, tokens, API keys

---

## 🚦 Fluxo Padrão (todos os agentes)

```
1. SYNC      → git checkout main && git pull origin main
2. READ      → STATUS.md, WORKFLOW.md, DUAL_MODE.md, AGENTS.md
3. BRANCH    → git checkout -b feature/<agente>-<task>
4. UPDATE    → STATUS.md em "Branches Abertas"
5. WORK      → fazer mudanças
6. TEST      → pytest tests/ -v (se aplicável)
7. COMMIT    → git commit -m "tipo(escopo): msg"
8. PUSH BR   → git push origin feature/<agente>-<task>
9. CONFIRM   → pedir aprovação do Edson para merge
10. MERGE    → (Edson) git checkout main && git merge feature/<agente>-<task>
11. DEPLOY   → (Edson) git push origin main && git push hf main
12. CLEANUP  → git branch -d feature/<agente>-<task>
13. UPDATE   → STATUS.md em "Recentemente Concluído"
```

---

## ⚠️ Cenários Críticos

### Cenário A: Dois agentes querem mexer no mesmo arquivo

**Solução:** o primeiro a marcar no `STATUS.md` ganha prioridade. O segundo aguarda ou trabalha em outro escopo.

### Cenário B: Agente encontra mudanças não commitadas

**Solução:** parar imediatamente. Não tentar adivinhar o que era. Reportar ao Edson:
> "Encontrei modificações não commitadas em [arquivos]. Como devo prosseguir?"

### Cenário C: Conflito de merge

**Solução:** abortar o merge:
```bash
git merge --abort
```
Reportar ao Edson com:
```bash
git status
git log --oneline -10
```

### Cenário D: Algo quebra na main

**NÃO tentar consertar direto na main.** Em vez disso:
1. Reverter o commit problemático
   ```bash
   git revert <commit-hash>
   git push origin main && git push hf main
   ```
2. Criar branch nova para corrigir
3. Aplicar correção lá
4. Mergear de volta

---

## 🎬 Cenários Reais

### Segunda — Claude (chat web) + Edson

```
Edson: "Claude, vamos investigar por que o SmartRouter não carrega"
Claude: lê STATUS.md, AGENTS.md, WORKFLOW.md, DUAL_MODE.md
Claude: "Próxima tarefa do STATUS é EXATAMENTE essa. Branch sugerida: feature/claude-debug-smartrouter"
Edson: executa comandos PowerShell que Claude passa
Claude: investigação concluída, problema é env var faltando
Edson: faz commit, merge, push origin + hf
Edson: atualiza STATUS.md
```

### Terça — Qwen (CLI local) + Edson

```
Edson: "Qwen, leia AGENTS.md, STATUS.md, WORKFLOW.md e DUAL_MODE.md primeiro"
Qwen: lê os 4 arquivos
Qwen: "Vejo que SmartRouter foi resolvido ontem. Posso adicionar testes para o caso?"
Edson: "Sim"
Qwen: cria feature/qwen-smartrouter-tests
Qwen: implementa
Qwen: pede aprovação para merge
Edson: revisa diff, aprova
Edson: faz merge + push
Edson: atualiza STATUS.md
```

### Quarta — Claude Code (CLI no Codespace) + Edson

```
Edson abre Codespace
Edson: cola o "Sync AI Prompt"
Claude Code: lê CLAUDE.md, STATUS.md, AGENTS.md, WORKFLOW.md, DUAL_MODE.md
Claude Code: confirma versão atual, branch, próxima tarefa
Edson: "Vamos atualizar X"
Claude Code: cria feature/claude-update-X
Claude Code: implementa
Claude Code: roda pytest
Claude Code: pede aprovação
Edson: aprova
Claude Code: commita
Edson: faz merge + push do PC ou do Codespace
```

**Resultado:** três agentes em três dias, mesmo projeto, sem conflito, porque seguiram o protocolo.

---

## 🚫 O que cada agente NÃO deve fazer

### Claude (chat web) não deve:
- Executar comandos no PC do Edson (não tem acesso)
- Modificar arquivos sem seguir branch + commit + merge
- Tomar decisão estratégica sem consultar Edson

### Claude Code (CLI) não deve:
- Pular protocolo de leitura inicial
- Fazer merge na main sem aprovação
- Push em `hf` sem aprovação

### Qwen não deve:
- Fazer push --force na main
- Mergear branch sem rodar testes
- Ignorar o STATUS.md

### Cowork não deve:
- Modificar lógica de código complexo (foco é automação)
- Fazer deploys sem confirmar com Edson
- Commitar arquivos sensíveis

---

## 📚 Arquivos de Coordenação (mapa de leitura)

| Arquivo | Função | Quem atualiza |
| --- | --- | --- |
| `STATUS.md` | Estado atual, branches, avisos | Quem fizer mudança |
| `WORKFLOW.md` | Regras git e processos | Edson + Claude |
| `DUAL_MODE.md` | Arquitetura local vs HF | Edson + Claude |
| `AGENTS.md` | Este arquivo (protocolo) | Edson + Claude |
| `CLAUDE.md` | Contexto técnico para IAs | Claude |
| `CHANGELOG.md` | Histórico de versões | Quem fizer release |
| `README.md` | Apresentação pública | Edson + Claude |

---

## 🎯 Filosofia

> "Não existe coordenação automática entre agentes.
> Existe disciplina compartilhada via arquivos versionados."

Cada agente é cego ao trabalho dos outros. Mas se todos seguem o protocolo:

1. Sincronizar antes de começar
2. Ler o estado do projeto
3. Trabalhar em branch própria
4. Atualizar STATUS.md
5. Pedir aprovação antes de merge

...então o repositório vira a "memória compartilhada" e o projeto evolui sem retrocesso.

**Edson é o orquestrador final.** Sem ele, os agentes não se comunicam.

---

**Versão deste arquivo:** 1.0 (v3.1 do projeto)
**Última atualização:** 18/05/2026
**Autor:** Edson Oliveira + Claude
**Mantido por:** Disciplina + este arquivo
