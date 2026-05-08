"""
EII — ERP Incident Intelligence (PUBLIC DEMO v2.3)
Versão para HuggingFace Spaces: CRAG Pipeline + PII Scrubbing + Groq Cloud
"""
import os
import re
import requests
import gradio as gr
from datetime import datetime
import warnings
import sys
from pathlib import Path

# Adicionar raiz do projeto ao sys.path para imports funcionarem
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

# ─────────────────────────────────────────────────────────────────────────────
# Import opcional: Deep Agents (fallback para Groq direto se falhar)
# crag_pipeline faz init pesado no module level — pode falhar no HF cold start
# ─────────────────────────────────────────────────────────────────────────────
_deep_agents_available = False
_diagnose_fn = None
_scrub_fn = None

try:
    from src.deep_agents_wrapper import diagnose_incident_sync as _diagnose_fn
    from src.utils.scrubber import scrub_pii as _scrub_fn
    _deep_agents_available = True
    print("[EII] Deep Agents pipeline carregado com sucesso")
except Exception as _e:
    print(f"[EII] Deep Agents indisponivel ({_e}), usando fallback Groq direto")


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: scrub PII simples (sem dependencias externas)
# ─────────────────────────────────────────────────────────────────────────────
def _scrub_pii_simple(text: str) -> tuple[str, dict]:
    """Remove CPF, CNPJ e NIS do texto sem deps externas."""
    counts = {"cpf": 0, "cnpj": 0, "nis": 0}
    text = re.sub(r'\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\.\s]?\d{2}\b',
                  lambda m: f"[CPF/****{m.group()[-2:]}]", text)
    counts["cpf"] = text.count("[CPF/")
    text = re.sub(r'\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\.\s]?\d{4}[-\.\s]?\d{2}\b',
                  lambda m: f"[CNPJ/****{m.group()[-2:]}]", text)
    counts["cnpj"] = text.count("[CNPJ/")
    text = re.sub(r'\b\d{11}\b', lambda m: f"[NIS/****{m.group()[-2:]}]", text)
    counts["nis"] = text.count("[NIS/")
    return text, counts


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: diagnóstico via Groq REST direto (sem langgraph/chromadb)
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

def _diagnose_groq_direct(xml: str, incident_id: str, mentor_mode: bool) -> dict:
    if not GROQ_API_KEY:
        return {
            "diagnostico": "### ⚠️ Configuração Pendente\n`GROQ_API_KEY` não encontrada nos Secrets do Space.",
            "metadata": "Fallback Groq | Sem API key"
        }
    prompt = f"""Você é o EII, especialista em eSocial e legislação trabalhista brasileira.
Analise o XML de incidente abaixo e gere um diagnóstico técnico estruturado em Markdown.

XML do incidente ({incident_id}):
{xml[:3000]}

Retorne APENAS Markdown com as seções:
### 📋 Diagnóstico: {incident_id}
### 🔍 Causa Raiz
### 🛠️ Passos de Resolução
### ✅ Validação
"""
    if mentor_mode:
        prompt += "\n🎓 **MODO MENTOR:** Explique como se fosse para um analista júnior. Inclua conceito técnico, motivo da rejeição e dica de prevenção."

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 1500},
            timeout=30
        )
        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"]
            return {"diagnostico": text, "metadata": f"Fallback Groq | {GROQ_MODEL}"}
        return {"diagnostico": f"### ❌ Erro Groq ({resp.status_code})\n{resp.text[:200]}",
                "metadata": "Fallback Groq | erro HTTP"}
    except Exception as e:
        return {"diagnostico": f"### ❌ Erro de conexão\n{e}", "metadata": "Fallback Groq | timeout"}


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES DA DEMO
# ─────────────────────────────────────────────────────────────────────────────

DEMO_WARNING = """
⚠️ **DEMO PÚBLICA — NÃO USE DADOS REAIS**
Esta é uma demonstração técnica para portfólio. Dados sensíveis (CPF/CNPJ/NIS) são **sanitizados automaticamente** antes do processamento.
🔗 [GitHub Repo](https://github.com/edson-aiops/eii-erp-incident-intelligence)
"""

def diagnose_public(xml_raw: str, incident_id: str, mentor_mode: bool) -> tuple[str, str]:
    """Handler da Demo Pública: PII scrubbing + Deep Agents ou Groq direto."""

    if not xml_raw or not xml_raw.strip().startswith("<"):
        return "### ❌ Erro\nXML inválido ou vazio. Cole um XML eSocial completo.", ""

    # Scrubbing de PII
    scrub = _scrub_fn if _scrub_fn else _scrub_pii_simple
    xml_clean, pii_counts = scrub(xml_raw)
    total_pii = sum(pii_counts.values())
    scrub_log = f"Scrubbing: {total_pii} dado(s) removido(s)" if total_pii > 0 else "Sem PII detectado"

    # Diagnóstico: Deep Agents se disponivel, senão Groq direto
    if _deep_agents_available and _diagnose_fn:
        try:
            result = _diagnose_fn(
                xml=xml_clean, incident_id=incident_id,
                mentor_mode=mentor_mode, force_local=False,
                retrieval_backend="chromadb"
            )
            engine = "Deep Agents v0.5"
        except Exception as e:
            result = _diagnose_groq_direct(xml_clean, incident_id, mentor_mode)
            engine = f"Fallback Groq (Deep Agents erro: {e})"
    else:
        result = _diagnose_groq_direct(xml_clean, incident_id, mentor_mode)
        engine = "Groq direto"

    diagnosis = result.get("diagnostico", "### ❌ Erro ao gerar diagnóstico.")
    meta = result.get("metadata", "")
    return diagnosis, f"{scrub_log} | {engine} | {meta}"

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
