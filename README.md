---
title: EII — ERP Incident Intelligence
emoji: ⚙️
colorFrom: red
colorTo: red
sdk: docker
pinned: true
license: mit
short_description: Diagnóstico eSocial XML com CRAG + Human-in-the-Loop
---

# ⚙️ EII — ERP Incident Intelligence

**Protótipo de diagnóstico automatizado de rejeições eSocial com IA**  
eSocial · CRAG Pipeline · SmartRouter Multi-LLM · Human-in-the-Loop · LGPD

> ⚠️ **Status:** Protótipo técnico de portfólio. Não validado em produção com dados reais.  
> A Knowledge Base cobre os casos mais comuns. Resultados variam conforme o evento e o contexto.

---

## 🎯 O Problema

Quando um evento eSocial é rejeitado pelo governo, o analista recebe um XML com código de erro.
Diagnosticar a causa raiz e os passos corretos de resolução exige experiência específica em
legislação trabalhista, leiautes do eSocial e regras de negócio da RFB.

O EII transforma esse XML em um diagnóstico estruturado em segundos — com roteamento automático
de dados sensíveis para garantir conformidade com a LGPD.

---

## 💡 Como Usar

1. Acesse a aba **🚨 Diagnóstico**
2. Cole o XML de retorno do eSocial (ou carregue um exemplo)
3. Clique em **🔍 Analisar XML**
4. Revise o diagnóstico gerado — causa raiz + passos de resolução
5. Acesse **✋ Aprovação (HITL)** para registrar sua decisão como analista

---

## 🏗️ Arquitetura

```
XML Rejeitado
     │
     ▼
[xml_parser.py] → extrai evento, código de erro, campos
     │
     ▼
[pii_detector.py] → detecta CPF / CNPJ / NIS
     │
  ┌──┴──┐
PII?    Limpo
 │        │
Ollama  Groq    ← SmartRouter (3 fases)
gemma2  Llama 3.3 70B
  └──┬──┘
     │
     ▼
[CRAG Pipeline]
  Retrieve → Grade → Generate → Evaluate (80%) → Reflexion
     │
     ▼
[HITL Gate] → analista valida antes de fechar
     │
     ▼
[SQLite Audit Log] + LangSmith @traceable
```

**CRAG (Corrective RAG):** recupera documentos da KB vetorial → LLM avalia relevância →
gera diagnóstico com contexto filtrado → EvaluatorAgent valida qualidade (threshold 80%) →
Reflexion auto-corrige se necessário.

---

## 📚 Base de Conhecimento

73 incidentes eSocial curados manualmente:

| Prioridade | Faixa | Exemplos |
| --- | --- | --- |
| 🔴 Crítico | KB001–KB020 | S-1200/MA-100, S-2200/E469, S-5001 |
| 🟡 Alto | KB021–KB053 | DCTFWeb, EFD-Reinf, E214, E215 |
| 🟢 Médio | KB054–KB073 | S-1000/E100, S-1005, validações cadastrais |

Cada item contém: evento, código de erro, causa raiz, passos de resolução, tags e contador
`validacoes` para boost de confiança no Qdrant.

---

## ⚙️ Configuração

Adicione a Secret no HuggingFace Space:

```
GROQ_API_KEY=sua_chave_aqui
```

Chave gratuita em: [console.groq.com](https://console.groq.com)

> A demo pública usa Groq com scrubbing de PII antes do envio.  
> Para uso com dados reais, rode a versão local com Ollama (LGPD total).

---

## 🔒 Human-in-the-Loop como Princípio de Design

> Nenhuma resolução é marcada como executada sem aprovação explícita de um analista humano.

Em contextos de eSocial, ações automáticas sem supervisão podem causar inconsistências no CNIS,
autuações fiscais e passivos trabalhistas. O HITL é uma decisão intencional de design — não
uma limitação técnica.

Para incidentes com severidade **CRÍTICO**, o sistema exige confirmação de 3 checkboxes antes
de registrar qualquer resolução.

---

## 🛠️ Stack

| Camada | Tecnologia |
| --- | --- |
| LLM principal | Llama 3.3 70B via Groq API |
| LLM LGPD (local) | gemma2:2b via Ollama |
| SmartRouter | 9 providers — Groq, Claude, Gemini, Kimi, Cerebras, Qwen, DeepSeek, Mistral, Ollama |
| Vector Store | Qdrant Cloud (prod) / ChromaDB (dev) |
| Embeddings | all-MiniLM-L6-v2 (384 dims, Cosine) |
| UI | Gradio 4.44.0 |
| Observabilidade | LangSmith @traceable (6 steps) |
| Persistência | SQLite + audit trail |
| MCP Server | fastmcp — `eii_query` e `eii_escalate` |
| Deploy | HuggingFace Spaces (Docker) |

---

## 🔌 MCP Server

O EII é exposto como servidor MCP via **fastmcp**, permitindo integração com Claude e outros
agentes LLM:

```json
{
  "mcpServers": {
    "eii": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {"GROQ_API_KEY": "sua-chave"}
    }
  }
}
```

Ferramentas disponíveis: `eii_query(xml)` e `eii_escalate(incident_id, status, notes)`.

---

## 🚀 Roadmap

### ✅ Concluído (Phase 1–3)

- [x] Pipeline CRAG base com ChromaDB
- [x] KB com 73 incidentes eSocial curados
- [x] EvaluatorAgent (threshold 80%) + Reflexion auto-correção
- [x] SmartRouter multi-LLM (9 providers, 3 fases)
- [x] ResilientLLM circuit breaker (Groq → Claude → GPT)
- [x] Roteamento LGPD automático (PII → Ollama local)
- [x] MCP Server via fastmcp
- [x] Batch processing (ThreadPoolExecutor)
- [x] Mentor Mode + HITL 3-checkbox
- [x] LangSmith @traceable OBS-001
- [x] Dev Container para GitHub Codespaces
- [x] 72 testes automatizados

### 🔄 Em progresso (Phase 4)

- [ ] Migração para Deep Agents v0.5 (`create_deep_agent`)
- [ ] Fork-Join assíncrono: 1 subagent por evento eSocial no Lote

### ⏳ Planejado (Phase 5)

- [ ] Dashboard de métricas com dados reais de piloto
- [ ] API `/audit/traces` para auditoria
- [ ] IntelAgent — curadoria autônoma da KB
- [ ] Suporte a EFD-Reinf (R-xxxx) e DCTFWeb
- [ ] API REST para integração com ticketing (JIRA, ServiceNow)

---

## 📄 Documentação

| Doc | Descrição |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões por phase |
| [docs/PRD.md](docs/PRD.md) | Product Requirements Document completo |
| [CLAUDE.md](CLAUDE.md) | Contexto para Claude Code — arquitetura e MCP |
| [smartrouter/README.md](smartrouter/README.md) | Documentação do SmartRouter |

---

## 👨‍💻 Desenvolvedor

*Edson Oliveira · Senior IT Systems Analyst · 12+ anos em HCM/ERP*  
*IA aplicada a compliance e operações de RH no Brasil*

[![GitHub](https://img.shields.io/badge/GitHub-eii--erp--incident--intelligence-181717?style=for-the-badge&logo=github)](https://github.com/edson-aiops/eii-erp-incident-intelligence)
[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-eii--erp--incident--intelligence-FFD21E?style=for-the-badge)](https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence)

---

[![GitHub Repo](https://img.shields.io/badge/GitHub-Código_Completo-181717?style=for-the-badge&logo=github)](https://github.com/edson-aiops/eii-erp-incident-intelligence)
[![Tests](https://img.shields.io/badge/Tests-72_passing-22C55E?style=for-the-badge)](https://github.com/edson-aiops/eii-erp-incident-intelligence/blob/main/tests/test_phase2.py)
[![MIT License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![LGPD](https://img.shields.io/badge/LGPD-Privacy_by_Design-009B7D?style=for-the-badge)](docs/PRD.md)
[![Phase](https://img.shields.io/badge/Phase-3_Complete-3776AB?style=for-the-badge)](CHANGELOG.md)
