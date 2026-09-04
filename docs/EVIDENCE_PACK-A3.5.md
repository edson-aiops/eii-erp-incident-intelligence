# EVIDENCE_PACK — A3.5: eii_api.py ligado ao Deep Agents

| Item | Valor |
|---|---|
| **Feature** | `feature/claude-eii-api-deep-agents` |
| **Base** | `feature/claude-smartrouter-scrubber` (A3) |
| **Spec** | `docs/A3.5-LIGAR-EII-API-SPEC.md` (v1.0, entregue por Edson) |
| **Commit** | `0e66bac` |
| **Executor** | Kimi Code CLI |
| **Release owner** | Edson (única autoridade de push/merge) |
| **Data** | 2026-09-03 |

---

## 1. Contexto da adaptação (spec vs. realidade)

A spec A3.5 descreve a refatoração de um `eii_api.py` existente que usava
`glm_router` (`qwen_local`/`glm_remote`). **Esse arquivo nunca existiu no repo**
(verificado com `git log --all` e busca em todos os branches). O que existia:

- `api.py` — REST API v1 (`POST /v1/diagnose` → `eii_handlers.query_incident`,
  síncrono, sem scrubber, sem Deep Agents)
- `glm_router.py` — **nunca existiu** em nenhum branch

Decisão (alinhada com Edson no ciclo): criar `eii_api.py` como **API v2 nova**,
fiel ao contrato da spec §3 (rotas, modelos, invariantes) e aos testes
black-box entregues. `api.py` (v1) ficou **inalterado**.

### Reconciliações aplicadas (código, não testes)

1. **Status 202**: os testes exigem `202` no POST; a spec §3 não fixava o
   código. Decorator com `status_code=202`.
2. **Fail-closed estrutural**: o scrubber (A23) **não levanta exceção** em XML
   malformado/evento não mapeado — retorna `ScrubResult` fail-closed
   (`is_safe_for_remote=False`, `token_map={}`). Para honrar o invariante 2
   ("se scrubber falha, retorna erro"), `run_analysis_deep_agents()` trata
   `not is_safe and not token_map` como erro de job. XML válido com PII
   não-seguro (`token_map` não vazio) segue para o Deep Agents com
   `force_local=True`.
3. **Fixture `client`/`app`**: adicionadas em `tests/conftest.py` conforme
   autorizado no PASSO 4 da tarefa.
4. **Dado de teste**: o `Id` dos XMLs de teste tinha **37 caracteres**; o
   formato eSocial exige **36** (`_scrub_id` fail-closed corretamente). Corrigido
   para 36 chars em 2 XMLs (`XML_S2200_COM_CPF`, `XML_ESTRUTURAL`). Sem essa
   correção, o scrubber correto rejeita o payload.
5. **Quantidade de testes**: o arquivo entregue tem **12** testes (a tarefa
   falava em 16).

---

## 2. Diff

```
 CHANGELOG.md                      |  14 ++
 STATUS.md                         |   1 +
 docs/A3.5-LIGAR-EII-API-SPEC.md   | 414 ++++++++++++++++++++++++++++++++++++++
 eii_api.py                        | 208 ++++++++++++++++++++
 tests/conftest.py                 |  18 ++-
 tests/test_eii_api_deep_agents.py | 322 +++++++++++++++++++++++++++++
 6 files changed, 976 insertions(+), 1 deletion(-)
```

Arquivos novos: `eii_api.py`, `docs/A3.5-LIGAR-EII-API-SPEC.md`,
`tests/test_eii_api_deep_agents.py`.
Arquivos alterados: `tests/conftest.py` (fixtures `app`/`client`),
`STATUS.md`, `CHANGELOG.md`.

Blast radius de código de produção: **1 arquivo novo** (`eii_api.py`).
Nenhum arquivo existente de produção foi alterado.

---

## 3. Testes A3.5 (12/12 verdes)

```
$ python -m pytest tests/test_eii_api_deep_agents.py -v

tests/test_eii_api_deep_agents.py::test_analyze_chama_deep_agents_nao_glm_router PASSED
tests/test_eii_api_deep_agents.py::test_analyze_xml_obrigatorio PASSED
tests/test_eii_api_deep_agents.py::test_analyze_status_processing PASSED
tests/test_eii_api_deep_agents.py::test_scrubber_exception_retorna_erro PASSED
tests/test_eii_api_deep_agents.py::test_scrubber_nao_envia_cloud_se_pii_nao_seguro PASSED
tests/test_eii_api_deep_agents.py::test_analyze_file_chama_deep_agents PASSED
tests/test_eii_api_deep_agents.py::test_analyze_file_arquivo_nao_existe PASSED
tests/test_eii_api_deep_agents.py::test_tokens_restaurados_na_resposta PASSED
tests/test_eii_api_deep_agents.py::test_analyze_retorna_job_id_uuid PASSED
tests/test_eii_api_deep_agents.py::test_results_endpoint_retorna_mesmo_job PASSED
tests/test_eii_api_deep_agents.py::test_glm_router_nao_e_importado PASSED
tests/test_eii_api_deep_agents.py::test_scrubber_e_importado PASSED

============================== 12 passed in 102.87s ==============================
```

Obs.: ~103s porque os testes executam o grafo Deep Agents real contra Ollama
local (gemma2:2b) — sem mocks, black-box de verdade.

---

## 4. Regressão (suíte completa)

```
$ python -m pytest tests/ -q

........................................................................ [ 59%]
.................................................                        [100%]
============================== 121 passed, 0 failed ==============================
```

- 109 testes pré-A3.5 + 12 novos = **121 testes, zero quebras, exit code 0**.
- Único warning novo: `DeprecationWarning` de `datetime.utcnow()` em
  `src/intel_agent/intel_agent.py` (código pré-existente, fora do escopo).

---

## 5. Campos cobertos

- ✅ POST /api/analyze chama Deep Agents, não glm_router
- ✅ Scrubber é mandatório (fail-closed em exceção E em fail-closed estrutural)
- ✅ POST /api/analyze-file funciona (arquivo temp + 404 se inexistente)
- ✅ Tokens restaurados na resposta (token_map nunca serializado)
- ✅ glm_router não importado (verificado por teste de invariante)
- ✅ Payload sem PII seguro para remoto (is_safe_for_remote na resposta)
- ✅ XML malformado / Id inválido → job error, nunca cloud
- ✅ api.py (REST v1) inalterado — backwards compat preservada

---

## 6. Blast radius

- **Novo**: `eii_api.py` (API v2, isolada)
- **Alterado**: `tests/conftest.py` (apenas fixtures novas), `STATUS.md`, `CHANGELOG.md`
- **Não toca**: Deep Agents (A3), scrubber (A23), SmartRouter, `api.py`, ChromaDB, Gradio
- **glm_router**: nunca existiu no repo — nada a remover (spec §1.1 estava desatualizada)

---

## 7. Rollback

```
git revert 0e66bac
```

Sem efeito colateral: o commit só adiciona arquivos novos + fixtures/docs.

---

## 8. Métrica

Pipeline único via eii_api.py: 100% das requisições /api/analyze e
/api/analyze-file passam por PIIScrubber antes do Deep Agents.
`api.py` (v1) permanece no pipeline antigo até decisão de deprecação (A25+).

---

## 9. Pendências para próximos ciclos (fora do escopo A3.5)

1. **Detector de event_type**: hoje hardcoded `"S-2200"` (spec §7.1)
2. **Jobs em DB**: hoje em memória (spec §7.2)
3. **Deprecar api.py v1** ou migrar `/v1/diagnose` para o mesmo motor
4. **Revisão humana**: Edson revisa antes do merge (A3 + A3.5 na fila)
