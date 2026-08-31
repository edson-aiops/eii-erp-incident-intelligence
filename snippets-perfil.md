# Snippets prontos — correções manuais (você, não o Kimi)

Cole-e-adapte. Cada bloco indica onde vai.

---

## 1. Tabela de métricas do perfil (`edson-aiops/edson-aiops` → README)

Substituir a tabela atual "Metric | Result" por:

**PT:**

```markdown
### Metas de design (PRD)

| Métrica | Meta (PRD) | Status |
|---|---|---|
| MTTR de incidentes eSocial | Redução de 70% | 🎯 Meta — instrumentação de medição em desenvolvimento |
| Resolução automática | ≥ 70% dos eventos R-* | 🎯 Meta — benchmark em dataset sintético versionado planejado |
| Escalonamento HITL | ≤ 30% | 🎯 Meta |
| Suíte de testes | — | ✅ **120 testes verdes no CI** ([badge](https://github.com/edson-aiops/eii-erp-incident-intelligence/actions)) |

> Metas viram resultados quando houver medição real (baseline + N documentados).
> Compromisso do projeto: nenhum número de performance publicado sem benchmark reproduzível.
```

**EN:**

```markdown
### Design targets (PRD)

| Metric | Target (PRD) | Status |
|---|---|---|
| eSocial incident MTTR | 70% reduction | 🎯 Target — measurement instrumentation in progress |
| Auto-resolution rate | ≥ 70% of R-* events | 🎯 Target — benchmark on versioned synthetic dataset planned |
| HITL escalation | ≤ 30% | 🎯 Target |
| Test suite | — | ✅ **120 tests green in CI** |

> Targets become results only with real measurements (documented baseline + N).
> Project commitment: no performance number published without a reproducible benchmark.
```

**Por quê:** a nota de rodapé transforma a limitação em diferencial — rigor de
medição é exatamente o que se espera de um Systems Analyst sênior. Em entrevista,
"defini metas e estou construindo a instrumentação para medi-las" é uma resposta
forte; "-70%" sem baseline é uma armadilha.

---

## 2. Badge do HuggingFace no perfil

O badge atual aponta para `EdsonPO/eii-incident-intelligence`; o repo aponta
para `EdsonPO/eii-erp-incident-intelligence`. **Teste os dois no navegador**
e padronize TODOS os links para o slug que funciona:

```markdown
[![HF Space](https://img.shields.io/badge/🤗%20Demo-HuggingFace%20Spaces-yellow)](https://huggingface.co/spaces/EdsonPO/SLUG_CORRETO_AQUI)
```

Se os dois existirem (um Space antigo órfão), delete/pause o antigo no HF —
dois Spaces com nomes quase iguais confundem e dividem tráfego.

---

## 3. Linha de localização do perfil

De:

```markdown
São Paulo, BR → Saskatoon, SK, CA
```

Para:

```markdown
São Paulo, BR · open to global remote
```

**Por quê:** consistente com a limpeza de relocation que você já fez no repo
(commit 26/06), não sinaliza saída iminente para o processo híbrido em SP,
e não amarra publicamente a uma província que deixou de ser a frente principal.

---

## 4. Legenda do GIF (README do EII, logo abaixo da imagem)

**PT:**

```markdown
> 🔒 Os dados pessoais visíveis como `[REMOVIDO]` na demo são mascarados
> **automaticamente** pela camada de PII scrubbing (LGPD by design) antes de
> qualquer chamada a LLM. Todos os XMLs da demonstração são sintéticos.
```

**EN:**

```markdown
> 🔒 Personal data shown as `[REDACTED]` in the demo is masked **automatically**
> by the PII scrubbing layer (LGPD/privacy by design) before any LLM call.
> All XML files in the demo are synthetic.
```

**Antes de colar:** conferir o GIF frame a frame (abra em
https://ezgif.com/split ou similar) — inclusive o painel de INPUT, antes do
scrub. Qualquer CPF/CNPJ real → regravar com `tests/batch_samples/`.

---

## 5. Claims de teste no README do EII

Buscar por "72" no `README.md` e `README_EN.md` e substituir a afirmação por:

```markdown
**120 automated tests** (core pipeline + SmartRouter), running on every push via GitHub Actions.
```

**Regra permanente:** o README só afirma o que o badge prova.

---

## 6. Arquivar repos iniciantes (gh CLI)

```bash
gh repo archive edson-aiops/Calculator_Python --yes
gh repo archive edson-aiops/automate_fly --yes
gh repo archive edson-aiops/Analise_Ciencia_engenharia_dados --yes
```

`gerador-5w2h-ia`: ou arquiva junto, ou corrige (clone URL aponta para
usuário `oedsonpereira` — quebrado — e o padrão "API key da Anthropic no
localStorage do browser" expõe a chave, contradizendo seu posicionamento
LGPD/segurança). Recomendação: arquivar agora, reescrever com backend
mínimo depois, se valer o esforço.
