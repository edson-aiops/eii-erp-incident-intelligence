"""
EII — ERP Incident Intelligence (Unificado)
Dashboard Gradio com Pipeline CRAG + Fallback Automático para Ollama Local
"""
# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidade Windows: Forçar encoding UTF-8 para emojis no terminal
# ─────────────────────────────────────────────────────────────────────────────
import sys
import io
# Forçar stdout/stderr para UTF-8 (evita UnicodeEncodeError no Windows)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
import gradio as gr
from datetime import datetime
import requests
import os
import warnings

# Silenciar warnings conhecidos (logfire-plugin incompatível com Python 3.13)
warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

# Importar pipeline principal
from crag_pipeline import diagnosticar_incidente


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Local (Garante resposta mesmo sem chaves de API cloud)
# ─────────────────────────────────────────────────────────────────────────────

def call_ollama_direct(xml: str, inc_id: str) -> dict:
    """Chama Ollama diretamente via API HTTP"""
    try:
        prompt = f"""Você é um especialista técnico em eSocial e legislação trabalhista brasileira.
Analise o XML abaixo e forneça um diagnóstico estruturado.

XML:
{xml}

Retorne APENAS:
1. Tipo de evento detectado
2. Possíveis códigos de erro ou inconsistências
3. Causa raiz técnica
4. Passos de resolução acionáveis
5. Como validar a correção"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma2:2b", "prompt": prompt, "stream": False},
            timeout=90
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "content": response.json().get("response", "Sem resposta do modelo."),
                "route": "local_fallback"
            }
        return {"success": False, "error": f"Ollama HTTP {response.status_code}: {response.text[:200]}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Ollama não está rodando em localhost:11434"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Formatador de Saída (Markdown limpo para Gradio)
# ─────────────────────────────────────────────────────────────────────────────

def format_output(result: dict, route_used: str) -> str:
    """Formata resultado em markdown legível"""
    if not result.get("success"):
        return f"❌ **Erro:** {result.get('error', 'Desconhecido')}"
    
    diagnosis = result.get("diagnosis", result)
    routing = result.get("_routing", {})
    meta = diagnosis.get("_meta", {})
    
    # Ícones de status
    route_icon = "☁️ Cloud" if "cloud" in route_used.lower() else "🏠 Local"
    lgpd_icon = "🔒 LGPD Ativo" if routing.get("pii_detected") else "🌐 Dados Públicos"
    
    md = f"""### 📋 Diagnóstico: `{diagnosis.get('incident_id', 'N/A')}`
**Rota:** {route_icon} | **Status:** {lgpd_icon}

| Campo | Valor |
|-------|-------|
| **Evento** | {diagnosis.get('evento', 'N/A')} |
| **Erro** | `{diagnosis.get('codigo_erro', 'N/A')}` |
| **Severidade** | {diagnosis.get('severidade', 'N/A')} |
| **Confiança** | {diagnosis.get('confianca', 'N/A')} |

### 🔍 Causa Raiz
{diagnosis.get('causa_raiz', 'N/A')}

### 🛠️ Passos de Resolução
"""
    for i, step in enumerate(diagnosis.get('passos_resolucao', []), 1):
        md += f"{i}. {step}\n"
    
    md += f"""
### ✅ Validação
{diagnosis.get('validacao', 'N/A')}

⏱️ **Tempo Estimado:** {diagnosis.get('tempo_estimado', 'N/A')}
📦 **Backend:** {meta.get('retrieval_backend', 'N/A')}
"""
    return md


# ─────────────────────────────────────────────────────────────────────────────
# Handler Principal (Smart Routing com Fallback Automático)
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_handler(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool):
    """Tenta pipeline principal -> se falhar, usa Ollama local"""
    if not xml.strip():
        return "⚠️ Por favor, cole o conteúdo do XML antes de diagnosticar."
    
    # 1. SE "Forçar Local" estiver marcado, usa Ollama DIRETAMENTE
    if force_local:
        print("🏭 [DEBUG] Forçando uso do Ollama local...")
        try:
            res = call_ollama_direct(xml, inc_id)
            print(f"🏭 [DEBUG] Resposta do Ollama: success={res.get('success')}, error={res.get('error')}")
            
            if res["success"]:
                fallback_diag = {
                    "incident_id": inc_id,
                    "evento": "Processamento Local (Ollama)",
                    "severidade": "ANÁLISE",
                    "confianca": "MÉDIA",
                    "causa_raiz": res["content"],
                    "passos_resolucao": [
                        "1. Verificar estrutura do XML conforme schema eSocial",
                        "2. Validar dados obrigatórios",
                        "3. Consultar documentação oficial"
                    ],
                    "validacao": "Validar no ambiente de produção do eSocial",
                    "_meta": {"retrieval_backend": "ollama-local"}
                }
                return format_output({"success": True, "diagnosis": fallback_diag}, "local")
            else:
                return f"❌ Erro Ollama: {res['error']}"
        except Exception as e:
            print(f"💥 [DEBUG] Exceção no call_ollama_direct: {e}")
            return f"💥 Erro ao chamar Ollama: {str(e)}"
    
    # 2. Tentar pipeline CRAG + SmartRouter (cloud primeiro)
    print("☁️ [DEBUG] Tentando providers cloud primeiro...")
    try:
        main_result = diagnosticar_incidente(
            xml_content=xml,
            incident_id=inc_id,
            error_code=err_code,
            mentor_mode=mentor
        )
        
        # Verifica se foi sucesso real ou erro de API
        error_msg = str(main_result.get("error", "")).lower()
        is_api_error = any(x in error_msg for x in ["provedores falharam", "api key", "401", "invalid", "incorrect"])
        
        if main_result.get("success") and not is_api_error:
            # Sucesso real do pipeline principal
            route = main_result.get("_routing", {}).get("route_used", "auto")
            print(f"✅ [DEBUG] Pipeline principal funcionou! Rota: {route}")
            return format_output(main_result, route)
        
        # Pipeline falhou → tenta Ollama como fallback
        print(f"⚠️  [DEBUG] Pipeline falhou ({error_msg[:100]}...), tentando Ollama local...")
        
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no pipeline principal: {e}")
    
    # 3. Fallback para Ollama
    print("🏭 [DEBUG] Ativando fallback Ollama...")
    try:
        fallback = call_ollama_direct(xml, inc_id)
        print(f"🏭 [DEBUG] Fallback Ollama: success={fallback.get('success')}, error={fallback.get('error')}")
        
        if fallback["success"]:
            fallback_diag = {
                "incident_id": inc_id,
                "evento": "Processamento Local (Fallback)",
                "severidade": "ANÁLISE",
                "confianca": "MÉDIA",
                "causa_raiz": fallback["content"],
                "passos_resolucao": [
                    "1. Verificar estrutura do XML",
                    "2. Validar dados obrigatórios",
                    "3. Consultar documentação eSocial"
                ],
                "validacao": "Validar no ambiente de produção",
                "_meta": {"retrieval_backend": "ollama-fallback"}
            }
            return format_output({"success": True, "diagnosis": fallback_diag}, "local_fallback")
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no fallback: {e}")
    
    # 4. Tudo falhou
    return "💥 Erro crítico: Nem cloud nem Ollama local responderam. Verifique os logs acima."

# ─────────────────────────────────────────────────────────────────────────────
# Interface Gradio
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="EII — ERP Incident Intelligence") as demo:
    gr.Markdown("# 🤖 EII — ERP Incident Intelligence")
    gr.Markdown("### Diagnóstico inteligente de incidentes eSocial com IA e roteamento LGPD")
    
    with gr.Row():
        with gr.Column(scale=1):
            xml_input = gr.Textbox(label="XML do eSocial", lines=12, placeholder="Cole o conteúdo XML completo aqui...")
            incident_id = gr.Textbox(label="ID do Incidente", value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}")
            error_code = gr.Textbox(label="Código de Erro (opcional)")
            
            with gr.Row():
                mentor_mode = gr.Checkbox(label="🎓 Modo Mentor", value=False)
                force_local = gr.Checkbox(label="🏭 Forçar Local (Ollama)", value=False)
            
            diagnose_btn = gr.Button("🚀 Diagnosticar", variant="primary", size="lg")
        
        with gr.Column(scale=2):
            # ✅ Compatível com Gradio 6.x: sem show_copy_button
            output = gr.Markdown(label="Resultado do Diagnóstico")
    
    diagnose_btn.click(
        fn=diagnose_handler,
        inputs=[xml_input, incident_id, error_code, mentor_mode, force_local],
        outputs=output
    )
    
    gr.Markdown(f"\n*Versão: {datetime.now().strftime('%d/%m/%Y')} | LGPD: Integrado | Python 3.13 Ready*")


# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Desativar analytics via env var (compatível com Gradio 6.x)
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    
    print("🚀 Iniciando EII Dashboard (Modo Unificado)...")
    print("📊 Acesse: http://127.0.0.1:7860")
    print("💡 Dica: Marque 'Forçar Local' se quiser pular a nuvem e usar só Ollama")
    
    # ✅ Compatível com Gradio 6.x: sem enable_analytics
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        quiet=True
    )