# 🛠️ WORKFLOW.md — Guia de Desenvolvimento EII

> **Regra de ouro:** este arquivo é a fonte da verdade do fluxo de trabalho.
> Consulte ANTES de começar qualquer tarefa nova. Não improvise.

---

## 📋 Estrutura de Branches

```
main                     → Estado oficial. Sempre estável. Sempre alinhado GitHub + HuggingFace.
  │
  ├── feature/claude-*   → Trabalho usando Claude (Anthropic)
  ├── feature/qwen-*     → Trabalho usando Qwen
  ├── feature/kimi-*     → Trabalho usando Kimi (Moonshot AI)
  ├── feature/cowork-*   → Trabalho usando Claude Cowork
  └── fix/*              → Hotfixes pontuais
```

**Regra absoluta:** ninguém desenvolve direto na `main`.

---

## 🎯 Fluxo Padrão (toda vez igual)

### 1️⃣ Antes de começar qualquer tarefa

```powershell
cd C:\Projetos\eii-erp-incident-intelligence

# Sincronizar com remotes
git checkout main
git pull origin main
git pull hf main
```

### 2️⃣ Criar branch para a tarefa

Use o prefixo da ferramenta que vai usar:

```powershell
# Trabalhando com Claude
git checkout -b feature/claude-<descricao-curta>

# Trabalhando com Qwen
git checkout -b feature/qwen-<descricao-curta>

# Trabalhando com Kimi
git checkout -b feature/kimi-<descricao-curta>

# Trabalhando com Cowork
git checkout -b feature/cowork-<descricao-curta>
```

### 3️⃣ Trabalhar e commitar

Use mensagens no padrão Conventional Commits:

```powershell
git add .
git commit -m "feat: descrição clara do que foi adicionado"
git commit -m "fix: descrição do bug corrigido"
git commit -m "docs: atualização de documentação"
git commit -m "chore: limpeza/manutenção"
git commit -m "test: novos testes"
```

### 4️⃣ Quando terminar e estiver tudo testado

```powershell
# Voltar para main
git checkout main
git pull origin main

# Mergear feature branch
git merge feature/claude-<nome>

# Push para AMBOS os remotes
git push origin main
git push hf main

# Apagar branch local (já foi mergeada)
git branch -d feature/claude-<nome>

# Apagar branch remota (se foi pushada)
git push origin --delete feature/claude-<nome>
```

---

## 🛡️ Regras Anti-Retrocesso

### ❌ NUNCA faça

1. **Não trabalhe direto na `main`** — sempre crie feature branch
2. **Não use `git push --force` na `main`** — exceto em emergências graves
3. **Não use `git filter-branch` na `main`** — reescreve histórico
4. **Não delete tags de versão** (`v1.x`, `v2.x`) — são marcos imutáveis
5. **Não misture trabalho de Claude e Qwen na mesma branch**
6. **Não misture trabalho de Kimi e Claude na mesma branch**
7. **Não commite arquivos `.env`** — checked pelo `.gitignore`
8. **Não commite arquivos de backup** (`*.bak`, `README_v*.md`)

### ✅ SEMPRE faça

1. **Antes de qualquer push, rode `git status`** — confirme que só está mandando o que quer
2. **Antes de qualquer push forçado, alerte** — me consulte se for absolutamente necessário
3. **Crie tag para milestones importantes** — `v2.3`, `v3.0`, etc.
4. **Mantenha `main` linear** — sempre fast-forward, nunca merge complicado

---

## 🚨 Comandos de Emergência

### Se a `main` ficou bagunçada

⛔ **PARE** e me avise antes de qualquer `--force`.

Comandos seguros para diagnosticar:
```powershell
git log --oneline -20
git log --all --graph --oneline
git status
git branch -a
```

### Se commitou algo errado mas ainda não fez push

```powershell
# Desfaz último commit, mantém alterações
git reset --soft HEAD~1

# Desfaz último commit, descarta alterações (CUIDADO)
git reset --hard HEAD~1
```

### Se commitou e fez push de algo errado

⛔ **PARE** e me avise. Reescrever histórico em main pública é arriscado.

---

## 📦 Tags de Versão

Use tags para marcar milestones importantes:

```powershell
# Criar tag anotada
git tag -a v2.3 -m "Phase 4: Deep Agents migration"

# Push da tag
git push origin v2.3
git push hf v2.3

# Listar tags
git tag

# Ver detalhes de uma tag
git show v2.2
```

### Convenção de versionamento

- `vX.0` → Release maior (nova fase concluída)
- `vX.Y` → Release menor (feature significativa)
- `vX.Y.Z` → Patch (correção de bug)

---

## 🔄 Sincronização Multi-Remote

O projeto vive em **3 lugares**:

| Lugar | URL | Uso |
| --- | --- | --- |
| **Local** | `C:\Projetos\eii-erp-incident-intelligence` | Desenvolvimento |
| **GitHub** | `github.com/edson-aiops/eii-erp-incident-intelligence` | Source of truth, código aberto |
| **HuggingFace** | `huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence` | Deploy do app |

### Sempre que fizer push, faça nos dois remotes:

```powershell
git push origin main    # GitHub
git push hf main        # HuggingFace
```

### Tags também:

```powershell
git push origin v2.X
git push hf v2.X
```

---

## 📝 Cheatsheet Rápido

| Situação | Comando |
| --- | --- |
| **Iniciar tarefa nova (Claude)** | `git checkout main && git pull origin main && git checkout -b feature/claude-X` |
| **Iniciar tarefa nova (Qwen)** | `git checkout main && git pull origin main && git checkout -b feature/qwen-X` |
| **Iniciar tarefa nova (Kimi)** | `git checkout main && git pull origin main && git checkout -b feature/kimi-X` |
| **Iniciar tarefa nova (Cowork)** | `git checkout main && git pull origin main && git checkout -b feature/cowork-X` |
| **Salvar progresso** | `git add . && git commit -m "feat: msg"` |
| **Finalizar tarefa** | `git checkout main && git merge feature/X && git push origin main && git push hf main` |
| **Ver estado** | `git status && git log --oneline -5` |
| **Ver remotes** | `git remote -v` |
| **Ver branches** | `git branch -a` |
| **Ver tags** | `git tag` |
| **Diagnóstico completo** | Rodar `_scripts/diagnose.ps1` (criar futuramente) |

---

## 🏷️ Padrão Conventional Commits

| Tipo | Quando usar | Exemplo |
| --- | --- | --- |
| `feat` | Nova feature | `feat: add MCP eii_query tool` |
| `fix` | Correção de bug | `fix: SQLite injection in escalate handler` |
| `docs` | Apenas documentação | `docs: update README with deployment steps` |
| `chore` | Manutenção sem mudar código | `chore: update .gitignore` |
| `test` | Novos testes | `test: add Reflexion edge cases` |
| `refactor` | Refactoring sem mudar comportamento | `refactor: extract PII detector to module` |
| `perf` | Melhoria de performance | `perf: optimize Qdrant batch upsert` |
| `style` | Formatação | `style: black formatting on smartrouter` |

### Escopo opcional

```text
feat(smartrouter): add Cerebras adapter
fix(crag): handle empty KB response
docs(hf): correct YAML front-matter
```

---

## 🎯 Roadmap Atual

| Phase | Status | Tag |
| --- | --- | --- |
| 1 — Foundation | ✅ Done | — |
| 2 — KB + CRAG | ✅ Done | — |
| 3 — Production (SmartRouter + MCP + LGPD) | ✅ Done | `v2.2` |
| 4 — Deep Agents v0.5 | ✅ Done | `v2.3` |
| 5 — Observability + IntelAgent | ✅ Done | `v3.1` |
| 6 — SaaS & Integrações | ⏳ Planejado | `v4.0` (futuro) |

---

## 📞 Quando Pedir Ajuda

Cole o output destes comandos e descreva o que estava tentando fazer:

```powershell
git status
git log --oneline -10
git branch -a
git remote -v
```

---

**Última atualização:** 2026-05-19
**Autor:** Edson Oliveira
**Mantido por:** Disciplina + este arquivo
