# PRD — EII: ERP Incident Intelligence

**Versão:** 2.0
**Status:** Phase 2 completa · Phase 3 planejada
**Autor:** Edson · Senior IT Systems Analyst
**Última atualização:** 2026-03-14

---

## 1. Problem Statement

### Contexto

Empresas brasileiras com folha de pagamento são obrigadas a transmitir eventos ao **eSocial** —
o sistema federal de escrituração digital das obrigações trabalhistas, previdenciárias e fiscais.
O webservice da RFB devolve XMLs de retorno com códigos de erro (E428, E469, E312, etc.) quando
um evento é rejeitado.

### O Problema

**Diagnosticar a causa raiz de uma rejeição eSocial é caro e lento:**

- Cada código de erro exige conhecimento cruzado de legislação trabalhista, leiautes eSocial
  (versões 2.5 / S-1.0 / S-1.1), e regras de negócio específicas da RFB
- Analistas gastam 30–90 minutos por incidente pesquisando documentação, fóruns e histórico
- Erros de diagnóstico levam a retransmissões incorretas, multas por atraso e inconsistências
  no CNIS do trabalhador
- Sistemas HCM (Senior, Totvs, SAP, Workday) não fornecem diagnóstico — apenas repassam
  o XML de erro para o analista

### Solução

O EII transforma o XML de retorno em um **diagnóstico técnico estruturado em segundos**,
com causa raiz, passos de resolução acionáveis e nível de confiança calibrado.
Um analista humano aprova ou rejeita o diagnóstico antes de qualquer ação ser executada.

---

## 2. Personas

### Persona 1 — Analista de RH/DP

| Campo | Detalhe |
|---|---|
| **Nome** | Camila, Analista de Departamento Pessoal |
| **Experiência** | 5 anos em folha de pagamento, usuária do sistema Senior HCM |
| **Dor principal** | Recebe XMLs de erro do eSocial e precisa de 30–60 min para diagnosticar cada um |
| **Expectativa** | Diagnóstico claro em português, com passos numerados, em menos de 30 segundos |
| **Restrição** | Não tem perfil técnico de TI; não lê XML bruto; precisa de linguagem DP, não dev |
| **Comportamento HITL** | Quer revisar o diagnóstico antes de executar — tem medo de retransmitir errado |

### Persona 2 — Desenvolvedor / Consultor HCM

| Campo | Detalhe |
|---|---|
| **Nome** | Rafael, Consultor de Implementação HCM |
| **Experiência** | 8 anos integrando sistemas HCM com o governo |
| **Dor principal** | Clientes abrem chamado com XML de erro; precisa diagnosticar rapidamente sem acessar o ambiente |
| **Expectativa** | Diagnóstico técnico com referência ao leiaute, causa raiz precisa e validação |
| **Restrição** | Atende múltiplos clientes simultaneamente; não pode gastar horas por incidente |
| **Comportamento HITL** | Usa o EII como primeiro nível de triagem; decide rapidamente se o diagnóstico está correto |

---

## 3. Arquitetura

### Pipeline de Diagnóstico

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT                                     │
│  XML de retorno eSocial (paste ou upload)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  xml_parser.py │  Detecta formato · Extrai campos
                    │                │  Aplica scrub_pii() (LGPD)
                    └───────┬────────┘
                            │ ParsedXML
                    ┌───────▼────────────────────────────────────┐
                    │         crag_pipeline.py — CRAG             │
                    │                                             │
                    │  Step 1: retrieve()                         │
                    │    ChromaDB query → top-5 docs KB           │
                    │                                             │
                    │  Step 2: grade()  [MODEL_ROUTER — 8b]       │
                    │    LLM: RELEVANTE / IRRELEVANTE por doc      │
                    │                                             │
                    │  Step 3: generate() [MODEL_GENERATOR — 70b] │
                    │    LLM: JSON diagnóstico completo            │
                    │                                             │
                    │  ADR-001: confidence_score()                 │
                    │    logprobs P(SIM) → sobrescreve confianca   │
                    └───────┬────────────────────────────────────┘
                            │ diagnosis dict
                    ┌───────▼────────┐
                    │  SQLite DB     │  _db_save_pending()
                    │  (PENDING)     │  Incidente retido para revisão
                    └───────┬────────┘
                            │
                    ┌───────▼────────────────┐
                    │  Human-in-the-Loop ✋   │  Analista revisa diagnóstico
                    │  Gradio Tab Aprovação   │  Aprova ou Rejeita com notas
                    └───────┬────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Audit Log     │  _db_decide() → status final
                    │  SQLite DB     │  Registro imutável com decided_at
                    └────────────────┘
```

### Componentes

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| XML Parser | `xml_parser.py` | Parse multi-formato, PII scrubbing, detecção de evento |
| CRAG Pipeline | `crag_pipeline.py` | Retrieve → Grade → Generate → Logprobs |
| Knowledge Base | `knowledge_base.py` | 20 incidentes eSocial documentados |
| Persistence | `app.py` (`_db_*`) | SQLite: pending queue, decisão, audit log |
| UI | `app.py` (Gradio) | 4 tabs: Diagnóstico, Aprovação, Audit Log, Arquitetura |

### Stack Técnica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| LLM Generator | Llama 3.3 70B (Groq) | Máxima qualidade para JSON estruturado |
| LLM Router | Llama 3.1 8B (Groq) | Baixo custo para tarefas binárias (grade) |
| Vector Store | ChromaDB in-memory | Zero infra, suficiente para KB de 20–200 docs |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 | Open-source, baixa latência |
| UI | Gradio 4.x | Deploy nativo em HuggingFace Spaces |
| Persistence | SQLite | Zero dependências externas, portável |
| Deploy | HuggingFace Spaces (Docker) | Free tier, git push → redeploy automático |

---

## 4. Requisitos Funcionais

### FR-01 — Parse de XML eSocial Multi-Formato
O sistema deve aceitar e interpretar XMLs de retorno do webservice eSocial nos formatos
`retornoEnvioLoteEventos`, `retornoProcessamentoEvento`, `retornoEvento` e genérico,
extraindo `cdResposta`, `descResposta`, `nrInsc`, `nrRec` e todas as `ocorrencias`.

### FR-02 — PII Scrubbing Automático (LGPD)
Todo CPF, CNPJ e NIS/PIS presente no XML deve ser mascarado antes de qualquer
persistência em banco ou envio ao LLM. O mascaramento deve preservar os 2 últimos dígitos
para rastreabilidade mínima (`[CPF/****01]`, `[CNPJ/****95]`).

### FR-03 — Recuperação de Contexto (Retrieve)
O sistema deve consultar a base de conhecimento ChromaDB com os dados do incidente
e retornar os top-5 documentos mais semanticamente próximos.

### FR-04 — Filtragem de Relevância (Grade)
Para cada documento recuperado, o sistema deve usar o MODEL_ROUTER para classificar
o documento como RELEVANTE ou IRRELEVANTE para o incidente específico.

### FR-05 — Geração de Diagnóstico Estruturado (Generate)
O sistema deve usar o MODEL_GENERATOR para produzir um diagnóstico JSON com os campos:
`incident_id`, `evento`, `codigo_erro`, `severidade`, `causa_raiz`, `confianca`,
`fonte`, `passos_resolucao`, `validacao`, `tempo_estimado`, `referencias_kb`, `alerta_hitl`.

### FR-06 — Score de Confiança Calibrado por Logprobs (ADR-001)
O campo `confianca` do diagnóstico deve ser determinado por P(SIM) calculada via
`top_logprobs` do Groq API — não pela auto-avaliação do LLM gerador.
Thresholds: P ≥ 0.80 → ALTA | P ≥ 0.45 → MÉDIA | P < 0.45 → BAIXA.

### FR-07 — Fila de Aprovação Pendente
Após gerar o diagnóstico, o sistema deve armazená-lo com status PENDING no SQLite
e bloquear qualquer registro como "resolvido" até aprovação humana explícita.

### FR-08 — Human-in-the-Loop: Aprovar ou Rejeitar
O analista deve poder revisar o diagnóstico, adicionar notas e registrar a decisão
(APROVADO ou REJEITADO) com timestamp e identidade do revisor.

### FR-09 — Audit Log Persistente
Todas as decisões devem ser armazenadas no SQLite com: `incident_id`, `created_at`,
`decided_at`, `status`, `diagnosis_json` completo e `notes` do analista.
O log deve ser ordenado por `decided_at DESC` e respeitar o limite configurável.

### FR-10 — Fallback Gracioso Sem API Key
Se `GROQ_API_KEY` não estiver configurada, o sistema deve exibir mensagem clara ao
usuário sem lançar exceção — nunca um traceback exposto na UI.

### FR-11 — Persistência Entre Reinicializações
O banco SQLite deve sobreviver a reinicializações do container. No HuggingFace Spaces,
o `DB_PATH` deve apontar para o volume persistente `/data/`. Em ambientes sem `/data`,
o sistema deve fazer fallback para arquivo local sem intervenção manual.

### FR-12 — Exemplos de XML Embutidos
O sistema deve fornecer ao menos 5 XMLs de exemplo prontos para uso, cobrindo
os principais cenários de erro (retificação, certificado, vínculo, timeout).

---

## 5. Requisitos Não-Funcionais

### NFR-01 — LGPD: Privacy by Design
- Nenhum CPF, CNPJ ou NIS deve ser armazenado em texto claro no banco ou enviado ao LLM
- O mascaramento deve ocorrer na camada de parse, antes de qualquer outra operação
- Auditável: os testes automatizados validam que nenhum dado sensível vaza

### NFR-02 — Custo Controlado (Cost Efficiency)
- Tarefas binárias (grade) devem usar MODEL_ROUTER (8B) — não o modelo maior
- A separação de modelos deve ser configurável via env vars sem alterar código
- Meta: custo por diagnóstico < $0.002 em condições normais de operação

### NFR-03 — Confiança Auditável
- O campo `logprob_sim` deve estar sempre presente em `_meta` e visível no audit log
- A confiança deve ser rastreável ao valor numérico P(SIM), não apenas ao label
- O override do LLM pelo logprob deve ser testado e documentado (ADR-001)

### NFR-04 — Latência de Diagnóstico
- O tempo de resposta end-to-end (parse + retrieve + grade + generate + logprobs)
  deve ser inferior a 15 segundos em condições normais de rede
- Timeouts configurados: 40s para generate, 20s para logprobs

### NFR-05 — Disponibilidade e Deploy
- Deploy contínuo: qualquer `git push origin main` deve acionar redeploy automático
- O sistema deve funcionar sem estado externo além do SQLite (sem Redis, sem Postgres)
- Compatível com HuggingFace Spaces free tier (sem GPU, 2 vCPU, 16GB RAM)

### NFR-06 — Testabilidade
- Todo componente crítico deve ter cobertura de testes automatizados
- Os testes devem usar apenas stdlib + `unittest.mock` — zero chamadas reais à API
- A suíte deve rodar em < 5 segundos em qualquer máquina sem dependências externas

---

## 6. Roadmap Faseado

| Phase | Status | Entregáveis |
|---|---|---|
| **1 — Foundation** | ✅ Completa | Gradio UI · Docker · HuggingFace Spaces deploy · XML Parser · CRAG stub · 5 exemplos |
| **2 — Intelligence & Compliance** | ✅ Completa | PII scrubbing LGPD · SQLite persistence · Model routing · Logprobs ADR-001 · 46 testes |
| **3 — LangGraph Agents** | 🔲 Planejada | HCMRouter (Workday/Senior/UKG) · LogAnalysisAgent · RootCauseDiagnosisAgent · LangGraph state machine |
| **4 — Observabilidade** | 🔲 Planejada | Langfuse integração · Spans por agente · RAGAS faithfulness/relevancy por coleção |
| **5 — KB Expansion** | 🔲 Planejada | 100+ incidentes · Suporte EFD-Reinf · Upload de arquivo XML · Multi-versão leiaute |
| **6 — Integrações** | 🔲 Planejada | API REST · Webhook JIRA/ServiceNow · Notificação e-mail HITL · Dashboard métricas |

---

## 7. Métricas de Sucesso

### Métricas Operacionais

| Métrica | Definição | Meta Phase 3 | Meta Phase 5 |
|---|---|---|---|
| **MTTR** | Mean Time To Resolution: do recebimento do XML até decisão HITL | < 5 min | < 2 min |
| **Taxa de Resolução Automática** | % de diagnósticos aprovados sem edição pelo analista | > 70% | > 85% |
| **Escalation Rate** | % de incidentes rejeitados (diagnóstico incorreto) | < 20% | < 10% |
| **Confiança Média** | Média de `logprob_sim` nos diagnósticos aprovados | > 0.75 | > 0.85 |
| **Latência P95** | 95º percentil do tempo de diagnóstico (parse→generate) | < 15s | < 10s |

### Métricas de Qualidade

| Métrica | Definição | Fonte |
|---|---|---|
| **RAGAS Faithfulness** | Diagnóstico não alucina fatos além do contexto KB | Langfuse (Phase 4) |
| **RAGAS Answer Relevancy** | Resposta endereça o incidente específico | Langfuse (Phase 4) |
| **KB Hit Rate** | % de incidentes com ao menos 1 doc KB relevante (grade=RELEVANTE) | Audit log `_meta` |
| **PII Leak Rate** | % de registros com CPF/CNPJ detectável em texto claro | Deve ser 0% (testado) |

### Métricas de Adoção

| Métrica | Meta 30 dias | Meta 90 dias |
|---|---|---|
| Incidentes diagnosticados | 50 | 500 |
| Usuários ativos (analistas) | 3 | 20 |
| Tempo médio de aprovação HITL | < 3 min | < 90 seg |

---

## 8. Decisões de Arquitetura (ADRs)

### ADR-001 — Logprobs como fonte de confiança (implementado)

**Contexto:** LLMs tendem a ser excessivamente confiantes na auto-avaliação.
O campo `confianca` gerado pelo `generate()` era pouco calibrado.

**Decisão:** Usar `logprobs` do Groq API para medir P(token afirmativo) em uma pergunta
binária de confirmação do diagnóstico. O resultado substitui o campo `confianca` do LLM.

**Consequências:** Confiança calibrada, auditável e testável. Custo adicional de 1 chamada
ao MODEL_ROUTER (8B) por diagnóstico — desprezível vs. benefício de rastreabilidade.

### ADR-002 — Human-in-the-Loop como hard gate (implementado)

**Contexto:** Em eSocial, uma retransmissão incorreta pode causar inconsistências no CNIS
e passivos trabalhistas. Automação total é inadequada neste domínio.

**Decisão:** Nenhum diagnóstico é registrado como "resolvido" sem aprovação explícita.
O SQLite mantém status PENDING até decisão do analista.

**Consequências:** Rastreabilidade total, responsabilidade clara, conformidade com
processos de auditoria trabalhista.

### ADR-003 — SQLite over managed DB (implementado)

**Contexto:** O sistema roda em HuggingFace Spaces free tier, sem acesso a Postgres/MySQL.

**Decisão:** SQLite com arquivo em `/data/` (volume persistente do HF Spaces).
Fallback para arquivo local se `/data/` não existir.

**Consequências:** Zero custo de infra, portabilidade total, suficiente para
volume esperado (< 10k incidentes/mês por instância).

---

*EII PRD v2.0 · Edson · Senior IT Systems Analyst · 12+ anos em HCM/ERP*
