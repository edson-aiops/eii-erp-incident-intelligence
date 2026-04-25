# 🤖 EII — ERP Incident Intelligence

Sistema inteligente de diagnóstico de incidentes eSocial com IA e compliance LGPD.

## 🚀 Funcionalidades
- ✅ Diagnóstico automático de XMLs eSocial
- ✅ Roteamento inteligente: Cloud ↔ Local (Ollama)
- ✅ Compliance LGPD: Dados sensíveis processados localmente
- ✅ Interface web profissional (Gradio)
- ✅ Fallback automático se API cloud indisponível

## 🔧 Instalação Rápida
```bash
# Pré-requisitos: Python 3.13, Ollama com gemma2:2b
pip install -r requirements.txt
ollama pull gemma2:2b
python app.py
# Acesse: http://localhost:7860