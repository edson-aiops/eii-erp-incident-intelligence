# CONTEXT.md — EII (ERP Incident Intelligence)

> Contexto permanente do projeto. Qualquer IA/ferramenta que trabalhe neste
> repositório deve ler este arquivo primeiro (junto com ROADMAP.md e CONVENTIONS.md).
> Última atualização: 2026-09 — fusão do histórico Claude (mar–set/2026) + sessões Kimi.

## O que é

EII é um **sistema agêntico de produção para diagnóstico de rejeições de XML do eSocial**
(eventos S-xxxx e EFD-Reinf R-*), com HITL, audit trail e conformidade LGPD.
Objetivo central: **reduzir MTTR** de incidentes de folha/eSocial.

- **Autor:** Edson Oliveira — Senior HCM Analyst & AI/Agentic Engineer (15+ anos em folha/eSocial)
- **Repo:** github.com/edson-aiops/eii-erp-incident-intelligence (MIT, Open Core: código público, KB fechada)
- **Demo:** huggingface.co/spaces/EdsonPO/eii-incident-intelligence
- **Versão atual:** v3.1 (Fases 1–5 concluídas; Fase 5.2 NOAA em spec; Fase 6 SaaS planejada)

## Decisão de escopo (fundacional)

Pivot de mar/2026: de "HCM genérico (multi-vendor)" para **foco exclusivo em rejeições
eSocial/EFD-Reinf** — domínio defensável; HCM genérico era commodity.

## Arquitetura atual

- **Pipeline:** upload XML de retorno → parser unificado `parse_xml_auto` (detecta 4 formatos:
  retornoEnvioLoteEventos, retornoProcessamentoEvento, retornoEvento, genérico; eSocial vs
  EFD-Reinf automático) → extração (evento, código de erro, CNPJ, ocorrências) →
  **CRAG** (Retrieve k=5 → Grade → Generate) → diagnóstico → **HITL** → audit trail
- **Nós LangGraph (Deep Agents):** parse→router→retrieve→generate→evaluate→reflexion→finalize→intel
  (8 nós) + IntelAgent proativo pós-diagnóstico (sem LLM, SQLite)
- **KB:** 93 itens (eSocial 001–073, EFD-Reinf 074–093) no **Qdrant Cloud** (cluster
  `eii-esocial`, GCP N. Virginia), embedding all-MiniLM-L6-v2 (384 dims, Cosine);
  `confidence_tier` via contador `validacoes` no payload
- **SmartRouter v3:** 9 provedores, 3 fases (Rules → Cerebras Classification → Adaptive);
  timeout 8s → fallback → circuit breaker (3 falhas = 10 min bloqueio)
- **LLMs:** GLM-5.3 via OpenRouter (primário); GLM-5.3-Flash (diagnóstico padrão);
  Qwen3 14B local no Contabo = pré-processador assíncrono de tarefas curtas
  (parse/classificar/extrair/scrubbing, 10–15s) — ~3,75 tok/s em CPU, inviável como
  motor do loop agêntico de 8 nós
- **HITL:** portão por rubrica de severidade + confiança + OR-trigger de Reflexion
  (CRÍTICO OR logprob<0.45 OR LLM_FALLBACK); audit trail SQLite; notificações por e-mail
- **Interfaces:** FastAPI (`/analyze`, `/health`, :8000) + MCP server (fastmcp:
  `eii_query`, `eii_escalate`) + Gradio UI (:7860) + CLI IntelAgent
- **Arquitetura dual:** `app.py` = local interno (auth, HITL, dados reais, NUNCA vai pra HF) /
  `app_hf.py` = demo pública (keyword lookup + LLM, sem auth, rotulada como demo simplificada)

## Infraestrutura

- **Produção real:** Contabo VPS 8 (24GB RAM, 8 vCPU, 300GB NVMe, US$13,44/mês,
  Ubuntu 24.04, Ollama nativo via systemd, firewall ufw 22/8000/7860, deploy `/opt/eii` via git+SSH)
- **Demo:** HF Space (Docker, `app_hf.py`, free tier)
- **CI:** GitHub Actions (matriz Python 3.11/3.13, 205+ testes)
- **Pendente de infra:** Redis/PostgreSQL no Contabo (token map com TTL + audit log LGPD)

## LGPD / Segurança (diferencial central)

- **Pseudonimização** (nunca "anonimização"): token map reversível que NUNCA sai do servidor
- Scrubbing PII **incondicional** (não é flag desligável) antes de qualquer chamada remota
- Scrubber por **allowlist dentro dos blocos de titular** (denylist por caminho não fecha —
  layout muda por versão); 4 classes: PRESERVAR / TOKENIZAR / CLASSIFICAR / GENERALIZAR
- **Fail-closed:** degrada para modelo local, não aborta
- "Modo 100% local" é flag separada do scrubbing
- Guardrails ADR-010 (OWASP LLM01/02/08); secrets via `keyring.set_password()`
- OpenRouter NUNCA no fluxo LGPD — só perfil `mode=test` com dado sintético e provider fixado

## ADRs (governança)

- **ADR-001:** HITL obrigatório com confiança (precisão/rastreabilidade > velocidade)
- **ADR-002:** CRAG em vez de RAG simples
- **ADR-003→003n:** KB Demo pública (5 itens) separada da Full privada; KB no Qdrant Cloud
- **ADR-004:** TOCL (Tool Output Compression Layer) — pendente
- **ADR-006:** feedback HITL persistido em HF Datasets (Space é stateless)
- **ADR-007:** LGPD desde o início como diferencial de engenharia
- **ADR-008:** deploy HF Spaces → evoluiu para Contabo VPS
- **ADR-009:** Open Core (código MIT público, KB fechada — o ativo valioso)
- **ADR-010:** guardrails OWASP

## Framework de escolha de LLM (4 eixos, em ordem)

1. **Sensibilidade do dado** (LGPD define local vs nuvem)
2. **Complexidade** (extração → 4–14B; raciocínio agêntico → 27–32B)
3. **Latência** (denso vs MoE)
4. **Custo** (local = fixo + $0/token; nuvem = $/token)

## Regras inegociáveis

1. **Métricas honestas:** só benchmark real sobre dataset sintético versionado vai a público;
   MTTR −70%, auto-resolve ≥70%, HITL ≤30% são **design targets**, sempre rotulados
2. **Privacidade retroativa:** nunca nomear empregador atual nem vendors ERP/HCM em
   artefatos públicos — apenas "ERP"/"HCM" genérico
3. **Gap aberto assumido:** `app_hf.py` anuncia HITL que não implementa — decisão A
   (implementar portão real) ou B (remover alegação) está pendente; heurística
   "múltiplas ocorrências = HITL" foi explicitamente rejeitada como maquiagem

## Projetos irmãos (ecossistema)

- **SmartRouter/ResilientLLM** — roteamento multi-LLM reutilizado pelo EII e CFI
- **PayrollBench** — benchmark público + leaderboard HF (3 baselines: LLM puro, RAG naive, EII Reference)
- **eSocial DocWatch** — spider Scrapy monitorando docs do eSocial → `delta.jsonl` para IntelAgent
- **CFI (Career Fit Intelligence)** — MatchGraph 8 nós, reuso de SmartRouter/TOCL
- **wfm-mcp** — MCP de Workforce Management (tenant sintético, 40 funcionários, 8 anomalias)
- **ContextCore** — framework de contexto agêntico (publicado)
- **ORCHESTRATOR ∞** — repo separado; só para lote (Fase 4, 200+ XMLs); overengineering para XML único
- **Livro:** *AI Agents for Workforce Compliance* (Vol. 1, ASIN B0H9GGGQC3) — documenta o EII
- **TCC FMU:** DSR/Hevner; contribuição = HITL com gate de confiança; 3 baselines
