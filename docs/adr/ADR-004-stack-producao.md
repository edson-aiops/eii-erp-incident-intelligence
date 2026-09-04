# ADR-004: Stack de Produção Consolidado

**Data:** 2026-09-04
**Status:** Aceita
**Decisor:** Edson Oliveira
**Contexto:** Tarefa A9 — sincronização da documentação com a stack real

---

## 1. Contexto

O EII acumulou três stacks em paralelo ao longo do desenvolvimento:

- **Groq** — descartado em ago/26 (risco de decommissioning, custo opaco)
- **Azure (Container Apps)** — spec IaC pronta, nunca deployada (overhead de
  infra gerenciada sem necessidade)
- **Contabo VPS + Qwen 14B** — fallback local experimental que virou produção

A documentação (README, PRD) ainda declarava a stack antiga, gerando
contradições C2 (stack declarada vs. real) e C5 (status do PII scrubbing).

## 2. Decisão

Consolidar a stack de produção em:

- **Motor principal:** GLM-5.3 via OpenRouter (remoto)
- **Fallback local:** Qwen 14B via Ollama (Contabo VPS) — ativado pelo gate
  `is_safe_for_remote` (LGPD) ou por indisponibilidade do remoto
- **Infraestrutura:** Contabo VPS (Ubuntu 24.04, 8 vCPU, 24GB RAM, ~$13.44/mês)
  + HuggingFace Spaces para a demo pública

## 3. Rationale

- **Groq → GLM-5.3:** custo previsível via OpenRouter, contexto longo,
  menor risco de descontinuação do que depender de um único provider
- **Azure → Contabo:** controle total, custo fixo baixo, sem lock-in de cloud;
  a spec Azure permanece no histórico como opção documentada
- **Qwen 14B local:** garante LGPD by design — nenhum payload sensível precisa
  sair do servidor quando o scrubber não consegue verificar segurança

## 4. Consequences

- ✅ Custo previsível de produção
- ✅ Latência aceitável (alvo <5s GLM; ~21s Qwen fallback)
- ✅ Fallback automático via gate `is_safe_for_remote`
- ✅ LGPD compliance sem overhead de infra gerenciada
- ⚠️ Métricas de qualidade/latência do GLM-5.3 ainda são *design targets* —
  precisam de baseline medido em produção antes de virar claim no portfólio

## 5. LGPD

A stack consolidada sustenta a conformidade documentada no README/PRD:

- **A23** PIIScrubber v2 — pseudonimização reversível (art. 5º, II)
- **A25** Redis token_map — TTL 7 dias, uso único (art. 32)
- **A26** PostgreSQL audit — histórico de tratamento (art. 12, 18)
- **A27** TTL analysis — relatório periódico de conformidade

## 6. Related

- Contradições C2 e C5 (auditoria de documentação, A9)
- ADR A12 (pseudonimização com mapa reversível) em `docs/ADR-pseudonimizacao-reversivel.md`
- ADR-001 (logprobs) e ADR-003 (SQLite) no `docs/PRD.md` — ADR-003 não foi
  reutilizado para esta decisão justamente para evitar colisão de identificadores
