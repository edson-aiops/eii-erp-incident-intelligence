# 🤖 EII — ERP Incident Intelligence

[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-blue)](https://huggingface.co/spaces/EdsonPO/eii-erp-incident-intelligence)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![LGPD](https://img.shields.io/badge/LGPD-Privacy%20by%20Design-green)](docs/PRD.md)

---

> 🇧🇷 **Sistema inteligente de diagnóstico de incidentes eSocial com IA, roteamento automático e 100% compatível com a LGPD.**  
> 🇬🇧 **AI-powered diagnostic system for Brazilian eSocial incidents with intelligent routing and full LGPD compliance.**

---

## 📖 Índice / Table of Contents

- [🇧🇷 Versão em Português](#-versão-em-português)
  - [O Problema que Resolvemos](#-o-problema-que-resolvemos)
  - [Como Funciona na Prática](#-como-funciona-na-prática)
  - [Demo Pública](#-demo-pública)
  - [Arquitetura do Sistema](#-arquitetura-do-sistema)
  - [Como Rodar Localmente](#-como-rodar-localmente)
  - [Stack Tecnológica](#-stack-tecnológica)
  
- [🇬🇧 English Version](#-english-version)
  - [The Problem We Solve](#-the-problem-we-solve)
  - [How It Works in Practice](#-how-it-works-in-practice)
  - [Public Demo](#-public-demo)
  - [System Architecture](#-system-architecture)
  - [Running Locally](#-running-locally)
  - [Technology Stack](#-technology-stack)

---

# 🇧🇷 Versão em Português

## 🎯 O Problema que Resolvemos

### Contexto
Quando uma empresa envia um evento para o **eSocial** (sistema do governo federal brasileiro para obrigações trabalhistas), ela recebe um **XML de resposta** com:
- ✅ **Sucesso:** Evento processado corretamente
- ❌ **Erro:** Evento rejeitado com código de erro e descrição técnica

### O Desafio do Analista
Diagnosticar **por que** o evento foi rejeito exige:
1. 📚 Conhecimento profundo da legislação trabalhista brasileira
2. 🔍 Experiência com leiautes técnicos do eSocial (versões 1.0, 2.0, S-1.0, etc.)
3. 🧠 Familiaridade com centenas de códigos de erro da Receita Federal
4. ⏱️ Tempo de análise: **15-45 minutos por incidente** (em média)

### Nossa Solução
O **EII (ERP Incident Intelligence)** transforma um XML de erro em um **diagnóstico estruturado em segundos**:
- 🔍 **Causa Raiz:** Explicação técnica clara do problema
- 🛠️ **Passos de Resolução:** Ações específicas e acionáveis
- ✅ **Validação:** Como confirmar que o problema foi resolvido
- ⏱️ **Tempo Estimado:** Quanto tempo leva para corrigir

**Resultado:** Redução de **70% no tempo de análise** (de 30min para ~9min).

---

## 🚀 Como Funciona na Prática

### Fluxo Completo Passo a Passo
