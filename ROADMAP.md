# ROADMAP.md — EII (ERP Incident Intelligence)

> Fonte única de verdade para prioridades. Atualizar a cada sprint/decisão.
> Última atualização: 2026-09 — fusão do histórico Claude + sessões Kimi.

## 🔥 Item mais urgente

**HITL real no `app_hf.py`** — o Space público anuncia HITL que não implementa
(LLM diz "confiança Alta" até em fixture ambígua). Decisão pendente:
**A)** implementar portão real ou **B)** remover a alegação até existir.
Heurística "múltiplas ocorrências = HITL" já foi rejeitada como maquiagem.

## Foco estratégico: validação real

- [ ] Primeiro usuário/empresa externa usando o EII (consultoria como porta de entrada)
- [ ] Medição de MTTR real (antes/depois) — só números reais vão a público
- [ ] Alimentar KB (93 itens) com casos novos do uso real

---

## Fase 5.2 — Arquitetura Unificada (NOAA) — spec pronta

- [ ] Classe `IncidentEII` (dataclass com parse cacheado) + `Diagnosis` tipada
      com `ConfidenceLevel Literal` — substitui `Dict[str,Any]`, elimina parsing triplo
- Branch: `feature/claude-noaa-unified-architecture` · Tag alvo: v3.2

## Fase 4 — Lote (pendente)

- [ ] Fork-Join multi-XML (200+ XMLs) — é quando ORCHESTRATOR ∞ passa a fazer sentido
- [ ] Benchmark K2.6 vs Qwen3 (20 eventos R-*; MTTR + auto-resolve + custo/evento;
      provider fixado para reprodutibilidade; critério de migração: ≥10% MTTR melhor
      ou ≥30% mais barato)
- [ ] Benchmark 4 braços: `qwen:14b` cru / `qwen3:14b` cru / `qwen3:14b`+CRAG /
      `glm-5.3`+CRAG — gera tabela baseline-vs-CRAG do TCC

## Infra Contabo (pendente)

- [ ] Redis + PostgreSQL (token map com TTL + audit log LGPD)
- [ ] SmartRouter adaptado para Qwen+GLM (Groq descartado)
- [ ] `eii_api.py` chamar o pipeline real em vez do LLM direto (hoje é "casca")

## TOCL — ADR-004 (pendente)

- [ ] Compressores determinístico/semântico/bypass por nó LangGraph
- [ ] Métrica `tokens_saved_pct` via LangSmith
- [ ] Critério de falha objetivo: bypass se `auto_resolve_rate` degradar >3pp
- [ ] LGPD restringe a determinístico ou Gemma4 local

## Fine-tuning Qwen-esocial (plano de 4 semanas)

- [ ] SFT com labels de teacher (GLM-5.3, confiança >0.9) — NÃO destilação clássica
- [ ] LoRA r=16, alpha=32, 3 epochs no Contabo; dataset 70% real / 30% sintético
- [ ] Validar contra PayrollBench; publicar `EdsonPO/qwen-esocial-v1`
- [ ] Meta: reduzir ~30% das chamadas GLM

## Fase 6 — SaaS (aguardando gatilho)

- [ ] Multitenancy — só após 2ª empresa real
- [ ] Monetização: consultoria agora; SaaS freemium em 6–9 meses

## Trailer compiler

- [ ] Pipeline programático (Playwright + asciinema + ffmpeg, config.yaml,
      um comando regenera o vídeo); build falha se testes não estiverem verdes

## Fora do caminho crítico

- Cerebras: free tier 8K de contexto estoura com CRAG; candidato a fast-path
  dos nós baratos depois
- RAGAS e integrações JIRA/ServiceNow: descartados do roadmap (mai/2026)

---

## Concluído (marco)

- [x] Fases 1–5 (Foundation v1.0 → Observability/Scale v3.1)
- [x] 205+ testes + CI GitHub Actions (matriz 3.11/3.13)
- [x] PIIScrubber allowlist (suíte 135 verde, commit 409ee8f)
- [x] Parser unificado eSocial + EFD-Reinf (v3.1, 20 eventos R-*)
- [x] Migração Groq → GLM-5.3 via OpenRouter (set/2026)
- [x] VPS Contabo em produção após jornada de 5 falhas (ago/2026)
- [x] Análise de segurança: 3 riscos críticos corrigidos (Space privado,
      token Qdrant read-only, scrub_pii ampliado)
- [x] Consolidação de contexto: CONTEXT.md / ROADMAP.md / CONVENTIONS.md (set/2026)

## Workflow de desenvolvimento (3 atores)

1. **IA especificadora** (Kimi/DeepSeek): escreve spec + testes black-box
   (sem ler implementação)
2. **Executor local** (Aider/Kimi CLI): implementa, NUNCA altera testes,
   NUNCA faz push, escala em vez de adivinhar
3. **Edson**: única autoridade de revisão/merge/push
4. **Merge gate:** EVIDENCE_PACK.md (diff, saída real da suíte, confirmação
   de zero testes alterados, blast radius, rollback path, métrica real ou
   declaração "sem métrica nova")
