"""
EII — ERP Incident Intelligence (HF Spaces Demo)
Versão otimizada para Gradio 5 + Python 3.13
"""
import os
import gradio as gr
import requests
from datetime import datetime

# Configuração Groq (Tier Grátis: 30 req/min, ~1000 req/dia)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"  # ✅ Modelo atualizado

def call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "⚠️ Configuração pendente: GROQ_API_KEY não encontrada nos Secrets do Space."
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1500
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return f"❌ Erro Groq ({response.status_code}): {response.text[:200]}"
    except Exception as e:
        return f"❌ Erro de conexão: {str(e)}"

def diagnose_eii(xml: str, incident_id: str, mentor_mode: bool) -> str:
    if not xml.strip():
        return "⚠️ Por favor, cole um XML válido."

    prompt_base = f"""Você é o EII (ERP Incident Intelligence), especialista em eSocial e legislação trabalhista brasileira.
Analise o seguinte XML de incidente e gere um diagnóstico técnico estruturado.

XML:
{xml[:3000]}

Retorne APENAS em Markdown, com as seções:
### 📋 Diagnóstico: {incident_id}
**Rota:** ☁️ Cloud Demo (Groq/Llama 3) | **Status:** 🌐 Dados Públicos
### 🔍 Causa Raiz
[Explicação técnica]
### 🛠️ Passos de Resolução
1. ...
2. ...
### ✅ Validação
[Como testar]
"""

    if mentor_mode:
        prompt_base += "\n\n🎓 **MODO MENTOR ATIVADO:** Explique como se estivesse treinando um analista júnior. Inclua conceito técnico, por que o eSocial rejeita esse formato, e dica de prevenção."

    result = call_groq(prompt_base)

    footer = """
---
> 💡 *Esta é uma **demo pública** para fins de portfolio. Dados sensíveis (CPF/CNPJ) NÃO devem ser usados aqui.*
> 🔐 Para uso com **LGPD compliance** e processamento local, acesse o repositório completo:
> 🔗 https://github.com/edson-aiops/eii-erp-incident-intelligence
"""
    return result + footer

# ─────────────────────────────────────────────────────────────────────────────
# Interface Gradio (Compatível com Gradio 5 + HF Spaces)
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="EII — ERP Incident Intelligence", theme=gr.themes.Default()) as demo:
    gr.Markdown("""
    # 🤖 EII — ERP Incident Intelligence
    ### Diagnóstico Inteligente de Incidentes eSocial (Demo Pública)
    """)

    with gr.Row():
        with gr.Column(scale=1):
            xml_input = gr.Textbox(
                label="XML do eSocial", 
                lines=10, 
                placeholder="Cole o XML aqui...", 
                value="<evtFech4000>\n  <ideEvento>\n    <tpAmb>1</tpAmb>\n  </ideEvento>\n</evtFech4000>"
            )
            incident_id = gr.Textbox(
                label="ID do Incidente", 
                value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}", 
                interactive=True
            )
            mentor_mode = gr.Checkbox(label="🎓 Modo Mentor + Checklist HITL", value=False)
            btn = gr.Button("🚀 Diagnosticar", variant="primary")

        with gr.Column(scale=2):
            output = gr.Markdown(label="Resultado do Diagnóstico")

    gr.Markdown("---\n*Versão: v2.2 | LGPD: Integrado (Local) | 🔗 [GitHub Repo](https://github.com/edson-aiops/eii-erp-incident-intelligence)*")

    btn.click(fn=diagnose_eii, inputs=[xml_input, incident_id, mentor_mode], outputs=[output])

if __name__ == "__main__":
    # Gradio 5 detecta automaticamente o ambiente HF Spaces
    demo.launch(server_name="0.0.0.0", server_port=7860)
