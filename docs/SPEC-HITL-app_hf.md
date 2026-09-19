# SPEC — HITL real no `app_hf.py` (demo pública)

> **Tipo:** spec + testes black-box (escrita SEM ler a implementação atual)
> **Decisão:** A — implementar portão real (ROADMAP.md, item urgente)
> **Data:** 2026-09 · Especificador: Kimi · Executor: Aider · Merge: Edson

## 1. Problema

A demo pública (`app_hf.py`) anuncia HITL que não implementa: o LLM retorna
"confiança Alta" até em entrada ambígua, e toda análise termina como
"auto-resolvida". Isso viola a regra de métricas honestas (CONVENTIONS.md).

## 2. Objetivo

Toda análise da demo deve passar por um **portão de decisão determinístico**
(pós-LLM, não-LLM) que classifica o resultado em dois estados:

- `AUTO_RESOLVIDO` — diagnóstico exibido normalmente;
- `ESCALADO_HUMANO` — diagnóstico exibido com selo visível de escalonamento
  e aviso de que requer revisão de analista.

## 3. Regras do portão (determinísticas, sem heurística de maquiagem)

O portão recebe a saída estruturada do diagnóstico e escala para humano
quando **qualquer** condição for verdadeira (OR-trigger, espelhando o
padrão do app interno):

1. `severidade == "CRITICO"`; ou
2. `confiança < 0.70` (limiar da demo; o app interno usa 0.45 com logprobs —
   a demo não tem logprobs confiáveis cross-provider, então usa o score
   de confiança declarado pelo modelo); ou
3. `fonte == "LLM_FALLBACK"` (o retrieval não encontrou caso na KB e a
   resposta veio só do LLM); ou
4. `evento_nao_mapeado == True` (evento S-xxxx/R-* fora da KB de 93 itens).

**Explicitamente proibido:** usar contagem de ocorrências ("múltiplas
ocorrências = HITL") como regra — decisão já registrada como maquiagem.

## 4. Contrato de saída

O diagnóstico da demo deve produzir (no mínimo) os campos:

```python
{
  "evento": str,            # ex.: "S-2200"
  "severidade": str,        # "CRITICO" | "ALTO" | "MEDIO" | "BAIXO"
  "confianca": float,       # 0.0–1.0
  "fonte": str,             # "KB" | "LLM_FALLBACK"
  "evento_nao_mapeado": bool,
  "status_hitl": str,       # "AUTO_RESOLVIDO" | "ESCALADO_HUMANO"  ← NOVO
  "motivo_escalonamento": list[str],  # regras que dispararam; [] se auto  ← NOVO
}
```

`status_hitl` e `motivo_escalonamento` são derivados **exclusivamente**
pelo portão (função pura), nunca escritos pelo LLM.

## 5. Requisitos de UI (Gradio)

- Estado `ESCALADO_HUMANO`: banner/selo visível (ex.: 🟠 "Escalado para
  analista humano") + lista do(s) motivo(s); o diagnóstico continua visível
  (a demo não bloqueia informação, apenas sinaliza).
- Estado `AUTO_RESOLVIDO`: selo 🟢 discreto.
- O texto da UI não pode afirmar "resolvido automaticamente" em estado
  escalado.

## 6. Audit trail

Cada análise registra (na estrutura de persistência já existente da demo —
HF Datasets, conforme ADR-006): timestamp, evento, severidade, confiança,
fonte, status_hitl, motivo_escalonamento. Sem PII (a demo já usa dados
sintéticos; scrubbing incondicional se aplica — CONVENTIONS.md).

## 7. Arquitetura exigida

- Função pura `hitl_gate(diagnostico: dict) -> tuple[str, list[str]]`
  (sem LLM, sem I/O, testável deterministicamente);
- O portão roda DEPOIS do diagnóstico e ANTES da renderização/persistência;
- Se a saída do LLM não puder ser parseada nos campos do contrato:
  `status_hitl = ESCALADO_HUMANO`, motivo `"PARSE_FALHOU"` (fail-closed).

## 8. Critérios de aceite

1. `hitl_gate` cobre as 4 regras + fail-closed de parse (ver testes);
2. Fixture ambígua (confiança 0.5) → `ESCALADO_HUMANO` (antes da mudança,
   a demo dizia "confiança Alta" — esse é o bug que a spec corrige);
3. Fixture limpa (KB, severidade BAIXO, confiança 0.95) → `AUTO_RESOLVIDO`;
4. Suíte completa verde, zero regressão; nenhum teste existente alterado;
5. UI mostra selo correto nos dois estados (verificação manual com print
   no EVIDENCE_PACK);
6. README da demo/Space atualizado: HITL descrito como portão real com as
   4 regras (sem target disfarçado de métrica).

## 9. Fora de escopo

- Notificações por e-mail (app interno apenas);
- Aprovação/rejeição interativa por analista (demo não tem auth);
- Mudanças no pipeline CRAG, KB ou SmartRouter.
