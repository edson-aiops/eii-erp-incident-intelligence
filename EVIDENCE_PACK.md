# EVIDENCE_PACK — HITL Gate real no app_hf.py

**Data:** 2026-09-22
**Workflow 3 atores:** Kimi (especificador: spec + testes black-box) → Aider / deepseek-v4-flash `--edit-format diff` (executor) → Edson Oliveira (revisor e única autoridade de merge)

## 1. Escopo

Implementação do portão HITL determinístico na demo pública (HF Spaces), conforme `docs/SPEC-HITL-app_hf.md`. Substitui a alegação de "HITL" que era apenas texto na UI por um gate real, puro e testado.

## 2. Diff

```
 app_hf.py               | 103 +++++++++++++++++++++++++++++++++++++++++++++++-
 tests/test_hitl_gate.py |   2 +-
 2 files changed, 103 insertions(+), 2 deletions(-)
```

**app_hf.py:**
- `+hitl_gate(diagnostico: dict) -> tuple[str, list[str]]` — função pura, sem LLM/I/O. 4 regras OR: `severidade=="CRITICO"`, `confianca < 0.70`, `fonte=="LLM_FALLBACK"`, `evento_nao_mapeado==True`. Fail-closed: campos ausentes → `ESCALADO_HUMANO / PARSE_FALHOU`. Contrato de máquina uppercase sem acento: `SEVERIDADE_CRITICA`, `CONFIANCA_BAIXA`, `LLM_FALLBACK`, `EVENTO_NAO_MAPEADO`, `PARSE_FALHOU`.
- `+_KNOWN_EVENTOS` — set de eventos da KB (93 itens) para detectar evento não mapeado.
- `+_parse_diagnostico(text)` — extrai evento/severidade/confiança do markdown do LLM (alta→0.95, media→0.60, baixa→0.30; ausente→0.0, o que escala por CONFIANCA_BAIXA).
- `diagnose_public` estendida: computa `fonte` (KB se `kb_refs>0`, senão LLM_FALLBACK), `evento_nao_mapeado`, chama `hitl_gate` e anexa selo na saída: 🟠 "Escalado para analista humano" + motivos, ou 🟢 "Auto-resolvido".

**tests/test_hitl_gate.py:**
- 1 asserção corrigida pelo especificador: substring `"CRITICO"` → `"CRITICA"`, alinhando o teste ao contrato de máquina `SEVERIDADE_CRITICA` definido na SPEC. Nenhuma regra de negócio alterada.

## 3. Evidência de testes (saída real)

- `python -m py_compile app_hf.py` → OK
- `findstr` confirma preservação: `def _kb_lookup`, `def _scrub_pii`, `def hitl_gate`, `def _parse_diagnostico` — todas presentes
- `python -m pytest tests/test_hitl_gate.py -v` → **10 passed**
- `python -m pytest` (suíte completa) → **295 passed, 3 skipped, 0 failed** em 598s
- Warnings: apenas `DeprecationWarning: datetime.utcnow()` pré-existentes (débito técnico registrado, não introduzido por esta mudança)

## 4. Blast radius

- **Produção (Contabo, app.py): NÃO afetada** — mudança restrita a `app_hf.py` (demo HF Spaces)
- Funções críticas preservadas: `_kb_lookup`, `_kb_context`, `_scrub_pii`, `_call_groq`, exemplos XML, UI Gradio
- `hitl_gate` é pura: sem LLM, sem I/O, sem efeitos colaterais, determinística
- Edição cirúrgica via `--edit-format diff`: zero remoção de código existente
- Observação de processo: deepseek-v4-flash em `whole edit format` destruiu o arquivo 2x (deletou KB/_scrub_pii); em `diff` funcionou. Convenção registrada: **edições em arquivos grandes sempre com `--edit-format diff`**

## 5. Decisão

- [x] Revisado e aprovado pelo especificador (Kimi) — diff e evidências conferem com a SPEC
- [x] Aprovado para merge — Edson Oliveira
