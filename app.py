"""
EII — ERP Incident Intelligence (SECURE VERSION v2.1)
Dashboard Gradio com Autenticação + Pipeline CRAG + Fallback Ollama + Observability
"""

# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidade Windows: Forçar encoding UTF-8 para emojis no terminal
# ─────────────────────────────────────────────────────────────────────────────
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# ─────────────────────────────────────────────────────────────────────────────
# Imports Padrão
# ─────────────────────────────────────────────────────────────────────────────
import gradio as gr
import hashlib
import os
import requests
import secrets
import time
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# MODO MENTOR & HITL CHECKLIST
# ─────────────────────────────────────────────────────────────────────────────

MENTOR_PROMPT_ADDON = """
---
🎓 MODO MENTOR ATIVADO:
Explique a causa raiz como se estivesse treinando um analista júnior.
Inclua:
1. Conceito técnico envolvido
2. Por que o eSocial rejeita esse formato
3. Dica de prevenção para futuros envios
"""

HITL_CHECKLIST = [
    "✅ XML validado contra schema oficial eSocial",
    "✅ Campos obrigatórios preenchidos conforme manual",
    "✅ Testado em ambiente de produção limitada (staging)",
    "✅ Backup do arquivo original realizado",
    "✅ Responsável técnico ciente da alteração"
]

def apply_mentor_mode(diagnosis_text: str, mentor_enabled: bool) -> str:
    """Adiciona seção de mentor e checklist ao diagnóstico"""
    if not mentor_enabled:
        return diagnosis_text
    
    mentor_section = f"""
---
🎓 **Nota do Mentor (Modo Didático)**
{MENTOR_PROMPT_ADDON.strip()}

📋 **Checklist de Validação (HITL)**
Antes de prosseguir com o envio, confirme:
"""
    for item in HITL_CHECKLIST:
        mentor_section += f"- [ ] {item}\n"
    
    mentor_section += "\n💡 *Dica: Marque todos os itens antes de dar o incidente como resolvido.*"
    return diagnosis_text + mentor_section

# ─────────────────────────────────────────────────────────────────────────────
# LANGSMITH OBSERVABILITY (Graceful Integration)
# ─────────────────────────────────────────────────────────────────────────────

# Configura variáveis de ambiente para LangChain/LangSmith se ativado
if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "eii-erp-v2")
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

def ls_trace(name: str):
    """
    Decorador seguro: aplica @traceable apenas se LangSmith estiver configurado.
    Degrada gracefully se a biblioteca não estiver instalada ou sem chave.
    """
    def decorator(func):
        if os.getenv("LANGCHAIN_API_KEY"):
            try:
                from langsmith import traceable
                return traceable(name=name, run_type="chain")(func)
            except ImportError:
                print(f"⚠️ [LangSmith] Library not installed. Skipping trace for '{name}'.")
                return func
            except Exception as e:
                print(f"⚠️ [LangSmith] Error setting up trace for '{name}': {e}")
                return func
        return func  # Sem chave → sem tracing, app continua normal
    return decorator

# ─────────────────────────────────────────────────────────────────────────────
# Configurações Globais
# ─────────────────────────────────────────────────────────────────────────────

ENV_FILE = Path(__file__).parent / ".env"
warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

# ─────────────────────────────────────────────────────────────────────────────
# Integração com Secure Secrets Manager (Credential Manager)
# ─────────────────────────────────────────────────────────────────────────────

def get_config_with_fallback(key: str, default: str = None) -> Optional[str]:
    """Recupera configuração: Credential Manager → .env → default"""
    try:
        import keyring
        value = keyring.get_password("EII_Project", key)
        if value:
            return value
    except (ImportError, Exception):
        pass
    
    if ENV_FILE.exists():
        try:
            from dotenv import dotenv_values
            env_vars = dotenv_values(ENV_FILE)
            value = env_vars.get(key)
            if value and value not in ("", "placeholder", "chave_key", "mude_esta_senha_urgente_123"):
                return value
        except Exception:
            pass
    
    return default or os.getenv(key)

# ─────────────────────────────────────────────────────────────────────────────
# Imports do Projeto
# ─────────────────────────────────────────────────────────────────────────────

from crag_pipeline import diagnosticar_incidente

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE SEGURANÇA
# ─────────────────────────────────────────────────────────────────────────────

ADMIN_USERNAME = get_config_with_fallback("EII_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = hashlib.sha256(
    (get_config_with_fallback("EII_ADMIN_PASS", "mude_esta_senha_urgente_123")).encode()
).hexdigest()

RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60
SESSION_TIMEOUT_MINUTES = 30

user_sessions: dict[str, dict] = {}
request_history: dict[str, list[float]] = defaultdict(list)

def verify_credentials(username: str, password: str) -> bool:
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)

def is_session_valid(token: str) -> bool:
    if token not in user_sessions:
        return False
    session = user_sessions[token]
    last_activity = session.get("last_activity")
    if last_activity and datetime.now() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        del user_sessions[token]
        return False
    session["last_activity"] = datetime.now()
    return True

def rate_limit_check(user_id: str) -> tuple[bool, int]:
    now = time.time()
    request_history[user_id] = [t for t in request_history[user_id] if t > now - RATE_LIMIT_WINDOW]
    remaining = RATE_LIMIT_REQUESTS - len(request_history[user_id])
    allowed = remaining > 0
    if allowed:
        request_history[user_id].append(now)
    return allowed, max(0, remaining)

def log_secure(user_id: str, action: str, incident_id: Optional[str] = None, extra: Optional[dict] = None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_extra = ""
    if extra:
        safe_keys = ["route", "backend", "force_local", "mentor_mode"]
        safe_extra = " | ".join(f"{k}={extra[k]}" for k in safe_keys if k in extra)
    incident_safe = f" | incident={incident_id}" if incident_id else ""
    print(f"[{timestamp}] user={user_id} | action={action}{incident_safe}{f' | {safe_extra}' if safe_extra else ''}")

def cleanup_expired_sessions():
    now = datetime.now()
    expired = [t for t, s in user_sessions.items() if s.get("last_activity") and now - s["last_activity"] > timedelta(minutes=SESSION_TIMEOUT_MINUTES)]
    for t in expired:
        del user_sessions[t]
    if expired:
        print(f"[CLEANUP] Removed {len(expired)} expired sessions")

# ─────────────────────────────────────────────────────────────────────────────
# Fallback Local (Ollama)
# ─────────────────────────────────────────────────────────────────────────────

@ls_trace("eii.ollama_direct_call")
def call_ollama_direct(xml: str, inc_id: str) -> dict:
    start_time = time.time()
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

        print(f"⏱️ [OLLAMA] Enviando prompt ({len(prompt)} chars) para {inc_id}...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma2:2b", "prompt": prompt, "stream": False},
            timeout=300
        )
        elapsed = time.time() - start_time
        print(f"⏱️ [OLLAMA] Resposta em {elapsed:.1f}s | Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("response", "Sem resposta do modelo.")
            return {"success": True, "content": content, "route": "local_fallback", "latency_sec": round(elapsed, 1)}
        return {"success": False, "error": f"Ollama HTTP {response.status_code}: {response.text[:200]}"}
        
    except requests.exceptions.ConnectionError:
        print(f"⏱️ [OLLAMA] ConnectionError após {time.time()-start_time:.1f}s")
        return {"success": False, "error": "Ollama não está rodando em localhost:11434"}
    except requests.exceptions.ReadTimeout:
        print(f"⏱️ [OLLAMA] ReadTimeout após {time.time()-start_time:.1f}s")
        return {"success": False, "error": "Ollama demorou mais de 5 minutos. Tente novamente."}
    except Exception as e:
        print(f"⏱️ [OLLAMA] Exception {type(e).__name__} após {time.time()-start_time:.1f}s: {str(e)[:200]}")
        return {"success": False, "error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# Formatador de Saída
# ─────────────────────────────────────────────────────────────────────────────

def format_output(result: dict, route_used: str) -> str:
    if not result.get("success"):
        return f"❌ **Erro:** {result.get('error', 'Desconhecido')}"
    
    diagnosis = result.get("diagnosis", result)
    routing = result.get("_routing", {})
    meta = diagnosis.get("_meta", {})
    
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
# Handler Principal SEGURO
# ─────────────────────────────────────────────────────────────────────────────

@ls_trace("eii.diagnose_handler_secure")
def diagnose_handler_secure(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool, session_token: str) -> tuple[str, str]:
    if not session_token or not is_session_valid(session_token):
        log_secure("unknown", "diagnose_attempt_failed", reason="invalid_session")
        return "", "❌ Sessão expirada ou inválida. Faça login novamente."
    
    user_info = user_sessions[session_token]
    user_id = user_info.get("username", "unknown")
    
    allowed, remaining = rate_limit_check(user_id)
    if not allowed:
        log_secure(user_id, "rate_limit_exceeded", incident_id=inc_id)
        return "", f"⚠️ Rate limit excedido. Aguarde {RATE_LIMIT_WINDOW} segundos."
    
    if not xml.strip():
        log_secure(user_id, "diagnose_attempt_failed", incident_id=inc_id, reason="empty_xml")
        return "", "⚠️ Por favor, cole o conteúdo do XML antes de diagnosticar."
    
    log_secure(user_id, "diagnose_started", incident_id=inc_id, extra={"force_local": force_local, "mentor_mode": mentor})
    
    try:
        resultado = _diagnose_internal(xml, inc_id, err_code, mentor, force_local)
        log_secure(user_id, "diagnose_completed", incident_id=inc_id, extra={"remaining_requests": remaining})
        return resultado, ""
    except Exception as e:
        log_secure(user_id, "diagnose_error", incident_id=inc_id, extra={"error_type": type(e).__name__})
        return "", f"💥 Erro interno: {type(e).__name__}"

@ls_trace("eii.diagnose_internal")
def _diagnose_internal(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool) -> str:
    # 1. Forçar Local (Ollama)
    if force_local:
        print(f"🏭 [DEBUG] Forçando uso do Ollama local para {inc_id}...")
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
                formatted_output = format_output({"success": True, "diagnosis": fallback_diag}, "local")
                if mentor:
                    formatted_output = apply_mentor_mode(formatted_output, True)
                return formatted_output
            return f"❌ Erro Ollama: {res['error']}"
        except Exception as e:
            return f"💥 Erro ao chamar Ollama: {str(e)}"
    
    # 2. Pipeline CRAG (Cloud)
    print(f"☁️ [DEBUG] Tentando providers cloud primeiro para {inc_id}...")
    try:
        main_result = diagnosticar_incidente(xml_content=xml, incident_id=inc_id, error_code=err_code, mentor_mode=mentor)
        error_msg = str(main_result.get("error", "")).lower()
        is_api_error = any(x in error_msg for x in ["provedores falharam", "api key", "401", "invalid", "incorrect"])
        
        if main_result.get("success") and not is_api_error:
            route = main_result.get("_routing", {}).get("route_used", "auto")
            print(f"✅ [DEBUG] Pipeline principal funcionou! Rota: {route}")
            formatted_output = format_output(main_result, route)
            if mentor:
                formatted_output = apply_mentor_mode(formatted_output, True)
            return formatted_output
        
        print(f"⚠️ [DEBUG] Pipeline falhou ({error_msg[:100]}...), tentando Ollama local...")
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no pipeline principal: {e}")
    
    # 3. Fallback Ollama
    print(f"🏭 [DEBUG] Ativando fallback Ollama para {inc_id}...")
    try:
        fallback = call_ollama_direct(xml, inc_id)
        if fallback["success"]:
            fallback_diag = {
                "incident_id": inc_id,
                "evento": "Processamento Local (Fallback)",
                "severidade": "ANÁLISE",
                "confianca": "MÉDIA",
                "causa_raiz": fallback["content"],
                "passos_resolucao": ["1. Verificar estrutura do XML", "2. Validar dados obrigatórios", "3. Consultar documentação eSocial"],
                "validacao": "Validar no ambiente de produção",
                "_meta": {"retrieval_backend": "ollama-fallback"}
            }
            formatted_output = format_output({"success": True, "diagnosis": fallback_diag}, "local_fallback")
            if mentor:
                formatted_output = apply_mentor_mode(formatted_output, True)
            return formatted_output
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no fallback: {e}")
    
    return "💥 Erro crítico: Nem cloud nem Ollama local responderam. Verifique os logs."

# ─────────────────────────────────────────────────────────────────────────────
# Funções da Interface
# ─────────────────────────────────────────────────────────────────────────────

def login_page(username: str, password: str) -> tuple:
    cleanup_expired_sessions()
    if verify_credentials(username, password):
        session_token = generate_session_token()
        user_sessions[session_token] = {"username": username, "login_time": datetime.now(), "last_activity": datetime.now()}
        log_secure(username, "login_success")
        print(f"[LOGIN] {username} logged in at {datetime.now()}")
        return f"✅ Login bem-sucedido! Bem-vindo, {username}.", session_token, username, gr.update(visible=False), gr.update(visible=True)
    else:
        log_secure(username if username else "(empty)", "login_failed")
        return "❌ Credenciais inválidas. Tente novamente.", "", "", gr.update(visible=True), gr.update(visible=False)

def logout(session_token: str) -> tuple:
    if session_token and session_token in user_sessions:
        log_secure(user_sessions[session_token]["username"], "logout")
        del user_sessions[session_token]
    return gr.update(visible=True), gr.update(visible=False)

def get_user_display(username: str) -> str:
    return f"👤 Usuário: **{username}** | ⏱️ Sessão expira em {SESSION_TIMEOUT_MINUTES}min" if username else ""

# ─────────────────────────────────────────────────────────────────────────────
# Interface Gradio
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="EII — ERP Incident Intelligence", theme=gr.themes.Default(), css="""
    .login-container {max-width: 400px; margin: 80px auto; padding: 2rem; border: 1px solid #e5e7eb; border-radius: 8px;}
    .main-interface {max-width: 1200px; margin: 0 auto;}
    .error-box {border-left: 4px solid #ef4444; background: #fef2f2; padding: 0.5rem 1rem;}
""") as demo:
    
    session_token = gr.State("")
    current_user = gr.State("")
    
    with gr.Column(elem_classes=["login-container"]) as login_container:
        gr.Markdown("# 🔐 EII — ERP Incident Intelligence\n### Sistema de Diagnóstico Inteligente de Incidentes eSocial\n\n**Acesso Restrito — Requer Autenticação**")
        username_input = gr.Textbox(label="Usuário", placeholder="Digite seu usuário", value="admin")
        password_input = gr.Textbox(label="Senha", type="password", placeholder="Digite sua senha")
        login_btn = gr.Button("🔓 Entrar", variant="primary", size="lg")
        login_msg = gr.Markdown("")
        gr.Markdown("---\n*💡 Dica: Configure credenciais no `.env` ou use Credential Manager*")
    
    with gr.Column(elem_classes=["main-interface"], visible=False) as main_interface:
        with gr.Row():
            gr.Markdown("# 🤖 EII — ERP Incident Intelligence")
            user_info = gr.Markdown("")
            logout_btn = gr.Button("🚪 Sair", variant="stop", size="sm")
        
        gr.Markdown("### Diagnóstico inteligente de incidentes eSocial com IA e roteamento LGPD")
        
        with gr.Row():
            with gr.Column(scale=1):
                xml_input = gr.Textbox(label="XML do eSocial", lines=12, placeholder="Cole o conteúdo XML completo aqui...")
                incident_id = gr.Textbox(label="ID do Incidente", value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}", interactive=True)
                error_code = gr.Textbox(label="Código de Erro (opcional)")
                
                with gr.Row():
                    mentor_mode = gr.Checkbox(label="🎓 Modo Mentor + Checklist HITL", value=False)
                    force_local = gr.Checkbox(label="🏭 Forçar Local (Ollama)", value=False)
                
                diagnose_btn = gr.Button("🚀 Diagnosticar", variant="primary", size="lg")
            
            with gr.Column(scale=2):
                output = gr.Markdown(label="Resultado do Diagnóstico", show_copy_button=False)
                error_output = gr.Textbox(label="⚠️ Mensagens de Erro", visible=False, interactive=False, elem_classes=["error-box"])
        
        gr.Markdown(f"\n*Versão: {datetime.now().strftime('%d/%m/%Y')} | LGPD: Integrado | Python 3.13 Ready | 🔒 Autenticado*")
    
    # Event Handlers
    login_btn.click(fn=login_page, inputs=[username_input, password_input], outputs=[login_msg, session_token, current_user, login_container, main_interface]).then(fn=get_user_display, inputs=[current_user], outputs=[user_info])
    logout_btn.click(fn=logout, inputs=[session_token], outputs=[login_container, main_interface]).then(fn=lambda: ("", ""), outputs=[session_token, current_user])
    diagnose_btn.click(fn=diagnose_handler_secure, inputs=[xml_input, incident_id, error_code, mentor_mode, force_local, session_token], outputs=[output, error_output]).then(fn=lambda err: gr.update(visible=bool(err and err.strip())), inputs=[error_output], outputs=[error_output])
    demo.load(fn=get_user_display, inputs=[current_user], outputs=[user_info])

# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    print("🚀 Iniciando EII Dashboard v2.1 (Mentor + Observability)...")
    print(f"📊 Acesse: http://127.0.0.1:7860")
    print(f"🔐 Login: usa Credential Manager ou .env")
    print(f"🛡️ Segurança: Rate limit={RATE_LIMIT_REQUESTS}req/{RATE_LIMIT_WINDOW}s | Session timeout={SESSION_TIMEOUT_MINUTES}min")
    demo.launch(server_name="127.0.0.1", server_port=7860, quiet=True)