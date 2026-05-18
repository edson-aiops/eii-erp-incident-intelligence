---
title: EII — ERP Incident Intelligence
emoji: ⚙️
colorFrom: red
colorTo: red
sdk: docker
pinned: true
license: mit
short_description: Diagnóstico eSocial e EFD-Reinf com CRAG + Multi-Agent + Human-in-the-Loop
---

# ⚙️ EII — ERP Incident Intelligence

**Sistema de diagnóstico automatizado de rejeições eSocial e EFD-Reinf com IA**

eSocial · EFD-Reinf · CRAG Pipeline · SmartRouter Multi-LLM · LangGraph Deep Agents · Human-in-the-Loop · LGPD by Design

[![Version](https://img.shields.io/badge/version-3.1-blue.svg)](https://github.com/edson-aiops/eii-erp-incident-intelligence)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HuggingFace Space](https://img.shields.io/badge/🤗-HuggingFace_Space-yellow)](https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg)](https://www.python.org/)

> ⚠️ **Status:** Protótipo técnico de portfólio. Não validado em produção com dados reais.
> A Knowledge Base cobre 93 incidentes documentados (eSocial + EFD-Reinf). Resultados variam conforme o evento e o contexto.

---

## 🎯 O Problema

Quando um evento eSocial ou EFD-Reinf é rejeitado pelo governo, o analista recebe um XML com código de erro. Diagnosticar a causa raiz e os passos corretos de resolução exige experiência específica em legislação trabalhista, leiautes técnicos e regras de negócio da Receita Federal.

O EII transforma esse XML em um diagnóstico estruturado em segundos — com roteamento automático de dados sensíveis para garantir conformidade com a LGPD.

---

## ✨ Funcionalidades

### Pipeline de diagnóstico
- **CRAG (Corrective RAG):** Retrieve → Grade → Generate → Evaluate → Reflexion
- **Parser unificado:** detecta automaticamente eSocial vs EFD-Reinf (23 eventos R-* suportados: R-1000, R-1070, R-2010 a R-2099, R-4010 a R-4099, R-9000 a R-9015)
- **Knowledge Base:** 93 incidentes mapeados (KB001-KB073 eSocial + KB074-KB093 EFD-Reinf)

### Multi-agente
- **LangGraph Deep Agents:** 8 nós (parse → router → retrieve → generate → evaluate → reflexion → finalize → intel)
- **SmartRouter:** 9 provedores LLM com seleção automática por contexto (Groq Llama 3.3 70B, gemma2-9b-it, Cerebras, Mistral, Gemini, Ollama local, entre outros)
- **IntelAgent:** análise proativa pós-diagnóstico (padrões recorrentes, sem chamada extra de LLM)

### Compliance e segurança
- **PII Scrubbing LGPD:** CPF, CNPJ, NIS, campos EFD-Reinf (cnpjPrestador, cnpjContri, cpfProdRural) mascarados antes do envio ao LLM
- **Roteamento LGPD-aware:** opção de forçar inferência local (Ollama) para casos sensíveis
- **Auth SHA-256 + Windows Credential Manager (keyring)** na versão local
- **Audit trail SQLite:** hash de cada decisão para rastreabilidade
- **HITL (Human-in-the-Loop) como princípio:** nenhuma resolução executada automaticamente em sistemas externos

### Integrações
- **REST API (FastAPI):** porta 8000, autenticação X-API-Key, 6 endpoints
- **MCP Server (fastmcp):** integração com clientes compatíveis com Model Context Protocol
- **Notifier email:** alertas HITL via SMTP (smtplib stdlib, sem dependências externas)
- **Observabilidade:** LangSmith @traceable com metadata estruturada

---

## 🏗️ Arquitetura Dual

| Versão | Arquivo | Onde roda | Quem usa |
| --- | --- | --- | --- |
| **Local** | `app.py` | PC do desenvolvedor | Operação interna (auth, SmartRouter, HITL, Ollama, dados reais) |
| **Pública** | `app_hf.py` | HuggingFace Space | Demo aberta (sem auth, sem dados reais, KB lookup + Groq) |

A versão local **nunca** é publicada no HuggingFace. O `Dockerfile` aponta exclusivamente para `app_hf.py`.

---

## 🚀 Stack Técnica

| Camada | Tecnologia |
| --- | --- |
| Linguagem | Python 3.13 |
| UI | Gradio >= 5.0 |
| API REST | FastAPI |
| Orquestração agentes | LangGraph |
| Retrieval | ChromaDB (vetorial) |
| Persistência | SQLite (audit, HITL, IntelAgent) |
| LLM Provider principal | Groq API (Llama 3.3 70B) |
| LLM Locais (opcional) | Ollama (Gemma, Llama, Qwen) |
| Observabilidade | LangSmith (traces opcional) |
| Secrets management | keyring (Windows Credential Manager) |

---

## 🧪 Como testar

### Versão pública (HuggingFace Space)

🔗 **[Acesse o Space](https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence)**

1. Cole um XML eSocial ou EFD-Reinf rejeitado
2. (Opcional) Informe o código do erro
3. Receba o diagnóstico estruturado: causa raiz + passos de resolução + validação

A demo pública usa apenas Groq (cloud) e KB completa. Sem autenticação.

### Versão local (clone do repo)

```bash
git clone https://github.com/edson-aiops/eii-erp-incident-intelligence.git
cd eii-erp-incident-intelligence
pip install -r requirements.txt

# Configure secrets via keyring
python -c "import keyring; keyring.set_password('EII_Project', 'GROQ_API_KEY', 'sua-chave')"

# Rode
python app.py
# Acesse http://127.0.0.1:7860
```

A versão local exige login (admin + senha configurados via keyring).

---

## 📦 Estrutura do projeto

```
eii-erp-incident-intelligence/
├── app.py                          # Versão local (auth + SmartRouter + HITL)
├── app_hf.py                       # Versão pública (HF Space)
├── api.py                          # REST API FastAPI
├── crag_pipeline.py                # Pipeline CRAG base
├── crag_pipeline_smartrouter.py    # Pipeline CRAG + SmartRouter
├── knowledge_base.py               # KB 93 incidentes
├── xml_parser.py                   # parse_xml_auto (eSocial + EFD-Reinf)
├── notifier.py                     # Notificações email HITL
├── observability.py                # LangSmith integration
├── smartrouter/                    # 9 LLM providers
├── src/deep_agents/                # LangGraph 8 nós
├── src/intel_agent/                # Análise proativa
├── tests/                          # Suite de testes
├── CLAUDE.md                       # Contexto técnico para agentes IA
├── STATUS.md                       # Estado atual do projeto
├── WORKFLOW.md                     # Regras de trabalho git
├── DUAL_MODE.md                    # Arquitetura local vs HF
└── CHANGELOG.md                    # Histórico de versões
```

---

## 📈 Roadmap

### Fases concluídas (v3.1)

- ✅ **Fase 1 — Foundation (v1.0):** CRAG pipeline inicial, KB eSocial base
- ✅ **Fase 2 — Intelligence & Compliance (v2.0):** Reflexion loop, PII scrubbing LGPD, HITL como design
- ✅ **Fase 3 — Production (v2.2):** SmartRouter multi-LLM, MCP Server, autenticação
- ✅ **Fase 4 — Deep Agents (v2.3):** LangGraph 8 nós, IntelAgent, REST API FastAPI, admin
- ✅ **Fase 5 — Observability & Scale (v3.1):** LangSmith traces, KB 93 incidentes, parser EFD-Reinf unificado, Notifier email

### Próxima fase

🔲 **Fase 6 — SaaS & Integrações (v4.0)** (aguarda gatilho de validação real com 2ª empresa)
- Multitenancy (tenant_id em SQLite, ChromaDB, auth)
- Pipeline EFD-Reinf integrado ao router_node dos Deep Agents
- `app_hf.py` v2 (demo pública refinada com KB 93)

---

## 🔒 Segurança e Compliance

### LGPD por design
- PII (CPF, CNPJ, NIS, dados EFD-Reinf) é mascarado **antes** de qualquer chamada ao LLM
- Opção de inferência 100% local via Ollama para dados ultra-sensíveis
- Sem armazenamento de dados pessoais identificáveis nos logs

### Por que HITL é decisão consciente (não limitação)
Em compliance trabalhista brasileiro, ações executadas automaticamente em sistemas como CNIS, RFB ou folha de pagamento podem causar:
- Inconsistências previdenciárias
- Autuações fiscais retroativas
- Passivos trabalhistas (FGTS, INSS, IR)

O EII **propõe** o diagnóstico e os passos de resolução. **Um analista humano** aprova e executa. Esse design é exigência de qualquer cliente sério em folha de pagamento.

---

## 📊 Observabilidade

Quando `LANGSMITH_API_KEY` está configurado:
- Cada execução do pipeline gera trace estruturado
- Metadata inclui: incident_id, tipo de evento, código de erro, versão da KB
- Retenção sugerida: 5 anos (alinhado com CLT art. 11)

---

## 🤝 Contribuições

Projeto open source MIT. Contribuições são bem-vindas, especialmente:
- Novos incidentes mapeados para a KB
- Suporte a novos eventos EFD-Reinf (R-1000, R-1070, R-2010, etc.)
- Melhorias no parser XML
- Casos de teste adicionais

Antes de contribuir, leia `WORKFLOW.md` para entender o fluxo de branches e commits.

---

## 📚 Referências

- [Leiaute eSocial S-1.3](https://www.gov.br/esocial/pt-br)
- [Manual EFD-Reinf 2.1.2](http://sped.rfb.gov.br/pasta/show/2225)
- [Anthropic Claude Documentation](https://docs.claude.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Groq API](https://console.groq.com/docs)

---

## 👤 Autor

**Edson Oliveira** — Senior IT Systems Analyst em transição para AI Agentic Engineering

- LinkedIn: [edson-pereira-oliveira](https://www.linkedin.com/in/edson-pereira-oliveira)
- GitHub: [edson-aiops](https://github.com/edson-aiops)
- HuggingFace: [EdsonPO](https://huggingface.co/EdsonPO)

12+ anos em HCM, folha de pagamento e ERP corporativo. Projeto de portfólio aplicado a perfis de Business Systems / Information Systems Analyst.

---

## 📄 Licença

[MIT License](LICENSE) — uso, modificação e redistribuição livres com atribuição.

---

**Última atualização do README:** 09/05/2026 (v3.1)
