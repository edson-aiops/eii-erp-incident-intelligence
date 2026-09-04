# EVIDENCE PACK — EII v3.2 (2026-09-04)

> Documento de evidência da sessão multi-ciclo A4→A9.
> **Princípio:** só entra aqui o que foi verificado de fato. Nada de números
> projetados apresentados como resultados.

---

## 1. Testes — números reais

| Base | Coletados | Falhas | Verificação |
|---|---|---|---|
| `main` @ a0a12ab | **175** | 0 | `pytest tests/ --collect-only` + regressão completa (exit 0) |
| `feature/claude-qdrant-retrieval` (A4) | 185 | 0 | regressão completa (exit 0, 100%) |
| `feature/claude-api-pipeline` (A6) | 185 | 0 | regressão completa (exit 0, 100%) |
| `feature/claude-benchmark` (A7/A8) | 195 | 0 | regressão completa (exit 0, 100%) |

Skips existentes (ambiente, não regressões): Redis/PostgreSQL indisponíveis
no dev local — testes de integração real skipam graciosamente por design.

Acréscimo por tarefa nesta sessão: A4 (+10), A6 (+10), A7/A8 (+10),
A27 (+10, já mergeado), A5 (validação manual), A9 (docs).
Total após merge das 3 branches pendentes: **195 testes**.

## 2. Branches entregues nesta sessão

| Branch | Commit | Conteúdo |
|---|---|---|
| `feature/claude-qdrant-retrieval` | 0a869df | 10 testes validando a integração Qdrant existente (retrieve_node → crag_pipeline → qdrant_client) |
| `feature/claude-api-pipeline` | a65a44d | Aliases `/analyze` e `/health` + 10 testes de contrato da API |
| `feature/claude-benchmark` | 04c77cd | Harness de benchmark + dataset de 20 XMLs + 10 testes + `benchmark_result.json` |
| `feature/claude-final-docs` | (este) | STATUS.md milestone + este evidence pack |

Já mergeados pelo Edson antes/durante a sessão: A5 (bd0f9ab), A27 (bb132c2), A9 (a0a12ab).

## 3. LGPD — controles implementados e testados

| Controle | Implementação | Evidência de teste |
|---|---|---|
| Pseudonimização reversível | PIIScrubber v2 (A23) | 48 casos S-2200 + 15 v1 + 11 integração (A24) |
| token_map com TTL 7 dias, uso único | Redis (A25), fallback memória | 14 testes |
| Audit log de restaurações (metadados apenas) | PostgreSQL `tokenmap_audit` (A26) | 10 testes |
| Fail-closed (PII não verificada → local) | `is_safe_for_remote` gate | A24 (11 testes) |
| Análise periódica de conformidade | `scripts/a27_ttl_analysis.py` (A27) | 10 testes |

Artigos cobertos: 5º II, 12, 18, 32.

## 4. Métricas — o que é real e o que é target

| Métrica | Status | Evidência |
|---|---|---|
| GLM-5.3 latência <5s p95 | ⏳ **Design target** — não medido | `benchmark_result.json` = `not_executed` (provedores ausentes no dev) |
| Qwen 14B latência <21s p95 | ⏳ **Design target** — não medido | idem |
| Fallback automático GLM→Qwen | ✅ Implementado | gate `is_safe_for_remote` + routing forçado (testado A24/A6) |
| Retrieval top-k via Qdrant | ✅ Implementado e testado | dispatch `backend="qdrant"` + parsing (A4, 10 testes) |
| MTTR −70% / resolução automática ≥70% | ⏳ Design target (PRD) | Requer baseline em produção com usuários reais |

**Ação para fechar as métricas:** rodar
`python scripts/benchmark_motors.py --output benchmark_result.json`
no Contabo (com OpenRouter + Ollama ativos) e arquivar o resultado.

## 5. Deploy

| Ambiente | Status | Evidência |
|---|---|---|
| Local (dev) | ✅ App Gradio A5 servindo | HTTP 200 em http://localhost:7865 (durante a sessão) |
| HuggingFace Spaces (demo) | ✅ Existente (v3.0) | não alterado nesta sessão |
| Contabo VPS (produção) | ⏳ **Pendente** | passo do Edson: SSH + Nginx reverse proxy — não executado nesta sessão |

## 6. Resumo do diff por ciclo

| Ciclo | Arquivos | Linhas |
|---|---|---|
| A4 | `tests/test_qdrant_retrieval.py` | +188 |
| A6 | `eii_api.py`, `tests/test_eii_api.py` | +169 |
| A7/A8 | `scripts/benchmark_motors.py`, `tests/test_benchmark.py`, `tests/fixtures/esocial_benchmark_dataset.py`, `benchmark_result.json` | +505 |
| Docs | `STATUS.md`, `EVIDENCE_PACK-FINAL.md` | +~150 |

## 7. Desvios do plano original (registrados para auditoria)

1. **A4 sem módulo novo** — a integração Qdrant já existia em produção
   (`qdrant_client.py` + dispatch em `crag_pipeline.retrieve`); o rascunho
   criaria um segundo cliente conflitante. Ciclo entregue como validação.
2. **A6 sem endpoint síncrono** — a API A3.5 (202 + job + polling) já era
   superior ao rascunho; entregue como aliases + testes de contrato.
3. **A7/A8 sem números fabricados** — o rascunho pedia "✅ validados" com
   métricas reais impossíveis no ambiente; entregue como `not_executed` auditável.
4. **Sem push para main** — o plano pedia `git push origin main` no ciclo 4;
   o protocolo (AGENTS.md/WORKFLOW.md) proíbe: merge é decisão do Edson.

---

*EII v3.2 · Sessão A4→A9 · 2026-09-04 · Kimi (K2.7/K3) executando, Edson revisando*
