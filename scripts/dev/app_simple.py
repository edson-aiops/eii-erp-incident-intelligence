"""EII Dashboard Simplificado - Usa Ollama Diretamente"""
import gradio as gr
from datetime import datetime
import requests

def diagnose_with_ollama(xml: str, inc_id: str) -> str:
    """Chama Ollama diretamente sem SmartRouter"""
    try:
        prompt = f"""Você é um especialista em eSocial. Analise este XML:

{xml}

Identifique:
1. Tipo de evento
2. Possíveis erros
3. Causa raiz
4. Passos de resolução

Responda de forma técnica e concisa em português."""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma2:2b",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("response", "Sem resposta")
            
            return f"""✅ Incidente: {inc_id}
🔒 LGPD: Sim (processado localmente)
🌐 Rota: local (Ollama)

🔍 Análise do Ollama:
{answer}

⏱️ Tempo de processamento: Local (~5-30s)"""
        else:
            return f"❌ Erro Ollama: {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "❌ Ollama não está rodando em localhost:11434"
    except Exception as e:
        return f"❌ Erro: {type(e).__name__}: {str(e)}"


with gr.Blocks(title="EII Dashboard - Modo Local") as demo:
    gr.Markdown("# 🤖 EII — ERP Incident Intelligence\n### 🏭 Modo Local (Ollama)")
    
    with gr.Row():
        with gr.Column(scale=1):
            xml_input = gr.Textbox(label="XML do eSocial", lines=10, 
                                   placeholder="Cole o XML aqui...")
            incident_id = gr.Textbox(label="ID do Incidente", 
                                     value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}")
            diagnose_btn = gr.Button("🚀 Diagnosticar (Ollama Local)", variant="primary")
        
        with gr.Column(scale=2):
            output = gr.Textbox(label="Resultado", lines=25, interactive=False)
    
    diagnose_btn.click(
        fn=diagnose_with_ollama,
        inputs=[xml_input, incident_id],
        outputs=output
    )
    
    gr.Markdown(f"\n*Versão: {datetime.now().strftime('%d/%m/%Y')} | Processamento 100% Local*")


if __name__ == "__main__":
    print("🚀 Iniciando EII Dashboard (Modo Local)...")
    print("📊 Acesse: http://127.0.0.1:7861")
    demo.launch(server_name="127.0.0.1", server_port=7861, quiet=True)