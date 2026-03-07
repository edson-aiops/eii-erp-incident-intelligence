---
title: EII — ERP Incident Intelligence
emoji: ⚙️
colorFrom: orange
colorTo: red
sdk: docker
pinned: true
license: mit
short_description: Diagnóstico inteligente de falhas de integração eSocial com CRAG + Human-in-the-Loop
---

# ⚙️ EII — ERP Incident Intelligence

**Diagnóstico inteligente de falhas de integração com o governo brasileiro**  
eSocial · Webservice RFB · CRAG Pipeline · Human-in-the-Loop

---

## 🎯 O Problema

Quando um evento eSocial é rejeitado pelo governo, o analista recebe um XML com código de erro.
Diagnosticar a causa raiz e os passos corretos de resolução exige experiência específica em
legislação trabalhista, leiautes do eSocial e regras de negócio da RFB.

O EII transforma esse XML em um diagnóstico estruturado em segundos.

## 💡 Como Usar

1. **Acesse a aba 🚨 Diagnóstico**
2. Cole o XML de retorno do eSocial (ou carregue um exemplo)
3. Clique **🔍 Analisar XML**
4. Revise o diagnóstico gerado
5. Acesse **✋ Aprovação** para registrar sua decisão como analista

## 🏗️ Arquitetura

```
XML Upload → [Parser] → [CRAG: Retrieve → Grade → Generate] → [HITL] → [Audit Log]
```

**CRAG (Corrective RAG):** recupera documentos da KB → LLM avalia relevância → gera diagnóstico com contexto filtrado

## 📚 Base de Conhecimento

20 incidentes documentados do eSocial:

| Área | Eventos / Erros |
|---|---|
| Retificação | S-1200/E428, S-3000/E430 |
| Certificado digital | E214, E215 |
| Vínculo/admissão | S-2200/E469, S-2299/E312, S-2206/E422 |
| CPF trabalhador | S-2200/E460, S-1210/E301 |
| Afastamento | S-2230/E350, S-2230/E351 |
| Remuneração/folha | S-1200/E320, S-1299/E450 |
| Transmissão/lote | E500, E200, E403 |
| Tabelas | S-1000/E100, S-1070/E601 |
| CAT | S-2210/E380 |

## ⚙️ Configuração

Adicione a Secret no HuggingFace Space:

```
GROQ_API_KEY = sua_chave_aqui
```

Chave gratuita em: [console.groq.com](https://console.groq.com)

## 🔒 Human-in-the-Loop como Princípio de Design

> Nenhuma resolução é marcada como executada sem aprovação explícita de um analista humano.

Em contextos de eSocial, erros executados automaticamente podem causar inconsistências no CNIS,
autuações fiscais e passivos trabalhistas. O HITL é uma decisão intencional de design — não
uma limitação técnica.

## 🛠️ Stack

- **LLM:** Llama 3.3 70B via Groq API
- **Vector Store:** ChromaDB in-memory
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **UI:** Gradio 4.x
- **Deploy:** HuggingFace Spaces (Docker)

## 🚀 Roadmap

- [ ] Expansão da KB para 100+ incidentes
- [ ] Suporte a EFD-Reinf (R-xxxx)
- [ ] Upload de arquivo XML (além de paste)
- [ ] Dashboard de métricas (taxa de acerto, tempo médio, confiança)
- [ ] API REST para integração com ticketing (JIRA, ServiceNow)
- [ ] Notificação por e-mail quando incidente aguarda aprovação

---

*Desenvolvido por Edson · Senior IT Systems Analyst · 12+ anos em HCM/ERP*  
*Portfolio: IA aplicada a compliance e operações de RH no Brasil*

[![MIT License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
