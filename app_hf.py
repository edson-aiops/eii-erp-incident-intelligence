"""
EII — ERP Incident Intelligence (PUBLIC DEMO v2.3)
Versão para HuggingFace Spaces: Deep Agents v0.5 + PII Scrubbing + Groq Cloud
"""
import os
import gradio as gr
from datetime import datetime
import warnings
import sys
from pathlib import Path

# Adicionar raiz do projeto ao sys.path para imports funcionarem
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# Supressão de avisos de plugin Pydantic
warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

from src.deep_agents_wrapper import diagnose_incident_sync
from src.utils.scrubber import scrub_pii

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES DA DEMO
# ─────────────────────────────────────────────────────────────────────────────

DEMO_WARNING = """
⚠️ **DEMO PÚBLICA — NÃO USE DADOS REAIS**
Esta é uma demonstração técnica para portfólio. Dados sensíveis (CPF/CNPJ/NIS) são **sanitizados automaticamente** antes do processamento.
Para uso em produção com conformidade LGPD total, clone o repositório e rode a versão local com Ollama.
🔗 [GitHub Repo](https://github.com/edson-aiops/eii-erp-incident-intelligence)
"""

def diagnose_public(xml_raw: str, incident_id: str, mentor_mode: bool) -> tuple[str, str]:
    """Handler da Demo Pública com Scrubbing + Deep Agents"""
    
    # 1. Validação básica
    if not xml_raw or not xml_raw.strip().startswith("<"):
        return "### ❌ Erro\nXML inválido ou vazio. Cole um XML eSocial completo.", ""
    
    # 2. Scrubbing de PII (LGPD)
    xml_clean, pii_counts = scrub_pii(xml_raw)
    total_pii = sum(pii_counts.values())
    
    scrub_log = f" Scrubbing: {total_pii} dado(s) sensível(eis) removido(s)" if total_pii > 0 else "✅ Sem PII detectado"
    
    # 3. Executar Deep Agents (via Groq Cloud no HF)
    try:
        result = diagnose_incident_sync(
            xml=xml_clean,
            incident_id=incident_id,
            mentor_mode=mentor_mode,
            force_local=False,  # Força cloud na demo
            retrieval_backend="chromadb"  # ChromaDB em memória para demo
        )
        
        diagnosis = result.get("diagnostico", "### ❌ Erro ao gerar diagnóstico.")
        metadata = result.get("metadata", "")
        
        # Adicionar log de scrubbing ao metadata
        full_metadata = f"{scrub_log} | {metadata}"
        return diagnosis, full_metadata
        
    except Exception as e:
        import logging
        logging.error(f"Erro na demo pública: {e}")
        return f"### ❌ Erro Interno\n{str(e)}", scrub_log

# ─────────────────────────────────────────────────────────────────────────────
# INTERFACE GRADIO
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="EII — Demo Pública", theme=gr.themes.Default()) as demo:
    gr.Markdown("# 🤖 EII — ERP Incident Intelligence")
    gr.Markdown("### Diagnóstico inteligente de incidentes eSocial com IA e roteamento LGPD")
    gr.Markdown(DEMO_WARNING)
    
    with gr.Row():
        with gr.Column(scale=1):
            xml_input = gr.Textbox(
                label="XML do eSocial",
                lines=10,
                placeholder="Cole o XML rejeitado aqui...",
                show_copy_button=True
            )
            incident_id = gr.Textbox(
                label="ID do Incidente",
                value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}"
            )
            mentor_mode = gr.Checkbox(label="🎓 Modo Mentor + Checklist HITL", value=False)
            diagnose_btn = gr.Button("🚀 Diagnosticar", variant="primary")
            
        with gr.Column(scale=2):
            output = gr.Markdown(label="Resultado do Diagnóstico")
            metadata_box = gr.Textbox(label="📊 Metadados & Logs", interactive=False, lines=2)
    
    gr.Markdown("---\n*Versão: 2.3 | Deep Agents v0.5 | LGPD: Scrubbing Ativo | 🔗 [GitHub](https://github.com/edson-aiops/eii-erp-incident-intelligence)*")
    
    diagnose_btn.click(
        fn=diagnose_public,
        inputs=[xml_input, incident_id, mentor_mode],
        outputs=[output, metadata_box]
    )

if __name__ == "__main__":
    print("🚀 Iniciando EII Demo Pública v2.3...")
    print("📊 Acesse: http://127.0.0.1:7860")
    print("🧼 PII Scrubbing: ATIVO | LLM: Groq Cloud")
    demo.launch(server_name="0.0.0.0", server_port=7860)
