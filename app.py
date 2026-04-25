"""
EII — ERP Incident Intelligence (SECURE VERSION)
Dashboard Gradio com Autenticação + Pipeline CRAG + Fallback Ollama
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
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Tuple
import gradio as gr
import hashlib
import os
import requests
import secrets
import time
import warnings

# ─────────────────────────────────────────────────────────────────────────────
# Configurações Globais
# ─────────────────────────────────────────────────────────────────────────────

# Arquivo .env para fallback
ENV_FILE = Path(__file__).parent / ".env"

# Silenciar warnings conhecidos
warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

# ─────────────────────────────────────────────────────────────────────────────
# Integração com Secure Secrets Manager (Credential Manager)
# ─────────────────────────────────────────────────────────────────────────────

def get_config_with_fallback(key: str, default: str = None) -> Optional[str]:
    """
    Recupera configuração com fallback: Credential Manager → .env → default
    
    Prioridade:
    1. Windows Credential Manager (via keyring)
    2. Arquivo .env (via dotenv)
    3. Valor default fornecido
    
    Args:
        key: Nome da variável de ambiente
        default: Valor fallback se não encontrado
        
    Returns:
        str | None: Valor configurado ou None
    """
    # Tenta Credential Manager primeiro
    try:
        import keyring
        value = keyring.get_password("EII_Project", key)
        if value:
            return value
    except ImportError:
        pass  # keyring não instalado, continua para fallback
    except Exception:
        pass  # Erro ao acessar credential manager, continua para fallback
    
    # Fallback para .env
    if ENV_FILE.exists():
        try:
            from dotenv import dotenv_values
            env_vars = dotenv_values(ENV_FILE)
            value = env_vars.get(key)
            if value and value not in ("", "placeholder", "chave_key", "mude_esta_senha_urgente_123"):
                return value
        except Exception:
            pass  # Erro ao ler .env, continua para fallback
    
    # Último fallback
    return default or os.getenv(key)

# ─────────────────────────────────────────────────────────────────────────────
# Imports do Projeto (após configurações)
# ─────────────────────────────────────────────────────────────────────────────

from crag_pipeline import diagnosticar_incidente

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE SEGURANÇA
# ─────────────────────────────────────────────────────────────────────────────

# Credenciais de administrador (usa Credential Manager com fallback para .env)
ADMIN_USERNAME = get_config_with_fallback("EII_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = hashlib.sha256(
    (get_config_with_fallback("EII_ADMIN_PASS", "mude_esta_senha_urgente_123")).encode()
).hexdigest()

# Rate limiting: 10 requisições por minuto por usuário
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # segundos

# Timeout de sessão: 30 minutos de inatividade
SESSION_TIMEOUT_MINUTES = 30

# Storage em memória (em produção, use Redis)
user_sessions: dict[str, dict] = {}
request_history: dict[str, list[float]] = defaultdict(list)


def verify_credentials(username: str, password: str) -> bool:
    """Verifica credenciais do usuário com hash SHA-256"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH


def generate_session_token() -> str:
    """Gera token de sessão criptograficamente seguro"""
    return secrets.token_urlsafe(32)


def is_session_valid(token: str) -> bool:
    """Verifica se a sessão é válida e não expirou"""
    if token not in user_sessions:
        return False
    
    session = user_sessions[token]
    last_activity = session.get("last_activity")
    
    # Verifica timeout
    if last_activity:
        if datetime.now() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            del user_sessions[token]
            return False
    
    # Atualiza last_activity
    session["last_activity"] = datetime.now()
    return True


def rate_limit_check(user_id: str) -> tuple[bool, int]:
    """
    Verifica rate limiting por usuário
    Returns: (allowed: bool, remaining_requests: int)
    """
    now = time.time()
    
    # Remove requisições antigas fora da janela
    request_history[user_id] = [
        req_time for req_time in request_history[user_id]
        if req_time > now - RATE_LIMIT_WINDOW
    ]
    
    remaining = RATE_LIMIT_REQUESTS - len(request_history[user_id])
    allowed = remaining > 0
    
    if allowed:
        request_history[user_id].append(now)
    
    return allowed, max(0, remaining)


def log_secure(user_id: str, action: str, incident_id: Optional[str] = None, extra: Optional[dict] = None):
    """
    Log seguro: NUNCA registra PII ou dados sensíveis
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_extra = ""
    if extra:
        # Filtra apenas chaves seguras para log
        safe_keys = ["route", "backend", "force_local", "mentor_mode"]
        safe_extra = " | ".join(f"{k}={extra[k]}" for k in safe_keys if k in extra)
    
    incident_safe = f" | incident={incident_id}" if incident_id else ""
    print(f"[{timestamp}] user={user_id} | action={action}{incident_safe}{f' | {safe_extra}' if safe_extra else ''}")


def cleanup_expired_sessions():
    """Remove sessões expiradas (chamar periodicamente)"""
    now = datetime.now()
    expired = [
        token for token, session in user_sessions.items()
        if session.get("last_activity") and 
           now - session["last_activity"] > timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    ]
    for token in expired:
        del user_sessions[token]
    if expired:
        print(f"[CLEANUP] Removed {len(expired)} expired sessions")


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Local (Garante resposta mesmo sem chaves de API cloud)
# ─────────────────────────────────────────────────────────────────────────────

def call_ollama_direct(xml: str, inc_id: str) -> dict:
    """Chama Ollama diretamente via API HTTP com logging de performance"""
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
        
        # Chamada correta: timeout como parâmetro, fecha parêntese ANTES do except
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma2:2b", "prompt": prompt, "stream": False},
            timeout=300  # ← 5 minutos para modelos locais
        )  # ← Fecha a chamada requests.post AQUI
        
        elapsed = time.time() - start_time
        print(f"⏱️ [OLLAMA] Resposta em {elapsed:.1f}s | Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("response", "Sem resposta do modelo.")
            print(f"⏱️ [OLLAMA] Content length: {len(content)} chars")
            
            return {
                "success": True,
                "content": content,
                "route": "local_fallback",
                "latency_sec": round(elapsed, 1)
            }
        return {"success": False, "error": f"Ollama HTTP {response.status_code}: {response.text[:200]}"}
        
    except requests.exceptions.ConnectionError:
        elapsed = time.time() - start_time
        print(f"⏱️ [OLLAMA] ConnectionError após {elapsed:.1f}s")
        return {"success": False, "error": "Ollama não está rodando em localhost:11434"}
        
    except requests.exceptions.ReadTimeout:
        elapsed = time.time() - start_time
        print(f"⏱️ [OLLAMA] ReadTimeout após {elapsed:.1f}s")
        return {"success": False, "error": f"Ollama demorou mais de 5 minutos (timeout). Tente novamente."}
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"⏱️ [OLLAMA] Exception {type(e).__name__} após {elapsed:.1f}s: {str(e)[:200]}")
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
# Handler Principal SEGURO (com autenticação e rate limiting)
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_handler_secure(
    xml: str, 
    inc_id: str, 
    err_code: str, 
    mentor: bool, 
    force_local: bool,
    session_token: str
) -> tuple[str, str]:
    """
    Handler seguro com autenticação e rate limiting
    Returns: (resultado: str, mensagem_erro: str)
    """
    # Verificar sessão
    if not session_token or not is_session_valid(session_token):
        log_secure("unknown", "diagnose_attempt_failed", reason="invalid_session")
        return "", "❌ Sessão expirada ou inválida. Faça login novamente."
    
    user_info = user_sessions[session_token]
    user_id = user_info.get("username", "unknown")
    
    # Verificar rate limiting
    allowed, remaining = rate_limit_check(user_id)
    if not allowed:
        log_secure(user_id, "rate_limit_exceeded", incident_id=inc_id)
        return "", f"⚠️ Rate limit excedido. Aguarde {RATE_LIMIT_WINDOW} segundos antes de tentar novamente."
    
    # Validar input básico
    if not xml.strip():
        log_secure(user_id, "diagnose_attempt_failed", incident_id=inc_id, reason="empty_xml")
        return "", "⚠️ Por favor, cole o conteúdo do XML antes de diagnosticar."
    
    # Log seguro do início do processamento (SEM PII)
    log_secure(
        user_id, 
        "diagnose_started", 
        incident_id=inc_id,
        extra={"force_local": force_local, "mentor_mode": mentor}
    )
    
    # Chamar lógica original de diagnóstico
    try:
        resultado = _diagnose_internal(xml, inc_id, err_code, mentor, force_local)
        
        # Log de sucesso (sem detalhes sensíveis)
        log_secure(user_id, "diagnose_completed", incident_id=inc_id, extra={"remaining_requests": remaining})
        return resultado, ""
        
    except Exception as e:
        # Log de erro seguro (sem stack trace completo)
        error_type = type(e).__name__
        log_secure(user_id, "diagnose_error", incident_id=inc_id, extra={"error_type": error_type})
        return "", f"💥 Erro interno: {error_type}"


def _diagnose_internal(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool) -> str:
    """
    Lógica interna de diagnóstico (sem segurança - chamada apenas por diagnose_handler_secure)
    """
    # 1. SE "Forçar Local" estiver marcado, usa Ollama DIRETAMENTE
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
                return format_output({"success": True, "diagnosis": fallback_diag}, "local")
            else:
                return f"❌ Erro Ollama: {res['error']}"
        except Exception as e:
            print(f"💥 [DEBUG] Exceção no call_ollama_direct: {e}")
            return f"💥 Erro ao chamar Ollama: {str(e)}"
    
    # 2. Tentar pipeline CRAG + SmartRouter (cloud primeiro)
    print(f"☁️ [DEBUG] Tentando providers cloud primeiro para {inc_id}...")
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
    print(f"🏭 [DEBUG] Ativando fallback Ollama para {inc_id}...")
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
# Funções da Interface (Login/Logout)
# ─────────────────────────────────────────────────────────────────────────────

def login_page(username: str, password: str) -> tuple:
    """
    Página de login
    Returns: (mensagem, session_token, username, login_visible, main_visible)
    """
    # Cleanup de sessões expiradas (a cada login)
    cleanup_expired_sessions()
    
    if verify_credentials(username, password):
        session_token = generate_session_token()
        user_sessions[session_token] = {
            "username": username,
            "login_time": datetime.now(),
            "last_activity": datetime.now()
        }
        
        msg = f"✅ Login bem-sucedido! Bem-vindo, {username}."
        log_secure(username, "login_success")
        print(f"[LOGIN] {username} logged in at {datetime.now()}")
        
        # Retorna: mensagem, token, username, esconder login, mostrar main
        return msg, session_token, username, gr.update(visible=False), gr.update(visible=True)
    else:
        attempted_user = username if username else "(empty)"
        log_secure(attempted_user, "login_failed")
        print(f"[FALHA LOGIN] Tentativa falha para user: {attempted_user}")
        return "❌ Credenciais inválidas. Tente novamente.", "", "", gr.update(visible=True), gr.update(visible=False)


def logout(session_token: str) -> tuple:
    """Logout do usuário"""
    if session_token and session_token in user_sessions:
        username = user_sessions[session_token]["username"]
        del user_sessions[session_token]
        log_secure(username, "logout")
        print(f"[LOGOUT] {username} logged out at {datetime.now()}")
    
    # Retorna: mostrar login, esconder main
    return gr.update(visible=True), gr.update(visible=False)


def get_user_display(username: str) -> str:
    """Retorna info do usuário para display"""
    if username:
        return f"👤 Usuário: **{username}** | ⏱️ Sessão expira em {SESSION_TIMEOUT_MINUTES}min"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Interface Gradio COM AUTENTICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="EII — ERP Incident Intelligence",
    theme=gr.themes.Default(),
    css="""
    .login-container {max-width: 400px; margin: 80px auto; padding: 2rem; border: 1px solid #e5e7eb; border-radius: 8px;}
    .main-interface {max-width: 1200px; margin: 0 auto;}
    .error-box {border-left: 4px solid #ef4444; background: #fef2f2; padding: 0.5rem 1rem;}
    """
) as demo:
    
    # Estado da sessão (não visível na UI)
    session_token = gr.State("")
    current_user = gr.State("")
    
    # ──────────────────────────────────────────────────────────────────────
    # TELA DE LOGIN
    # ──────────────────────────────────────────────────────────────────────
    with gr.Column(elem_classes=["login-container"]) as login_container:
        gr.Markdown("""
        # 🔐 EII — ERP Incident Intelligence
        ### Sistema de Diagnóstico Inteligente de Incidentes eSocial
        
        **Acesso Restrito — Requer Autenticação**
        """)
        
        username_input = gr.Textbox(
            label="Usuário",
            placeholder="Digite seu usuário",
            value="admin",
            elem_id="username-input"
        )
        password_input = gr.Textbox(
            label="Senha",
            type="password",
            placeholder="Digite sua senha",
            elem_id="password-input"
        )
        login_btn = gr.Button("🔓 Entrar", variant="primary", size="lg")
        login_msg = gr.Markdown("")
        
        gr.Markdown("""
        ---
        *💡 Dica: Configure as credenciais no arquivo `.env` ou use Credential Manager:*
        ```bash
        EII_ADMIN_USER=seu_usuario
        EII_ADMIN_PASS=sua_senha_forte_aqui
        # Ou: python secure_secrets.py set EII_ADMIN_PASS "sua_senha"
        ```
        """)
    
    # ──────────────────────────────────────────────────────────────────────
    # INTERFACE PRINCIPAL (Protegida - só aparece após login)
    # ──────────────────────────────────────────────────────────────────────
    with gr.Column(elem_classes=["main-interface"], visible=False) as main_interface:
        
        # Header com info do usuário e botão de logout
        with gr.Row():
            gr.Markdown("# 🤖 EII — ERP Incident Intelligence")
            user_info = gr.Markdown("")
            logout_btn = gr.Button("🚪 Sair", variant="stop", size="sm")
        
        gr.Markdown("### Diagnóstico inteligente de incidentes eSocial com IA e roteamento LGPD")
        
        with gr.Row():
            with gr.Column(scale=1):
                xml_input = gr.Textbox(
                    label="XML do eSocial",
                    lines=12,
                    placeholder="Cole o conteúdo XML completo aqui...",
                    elem_id="xml-input"
                )
                incident_id = gr.Textbox(
                    label="ID do Incidente",
                    value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}",
                    interactive=True
                )
                error_code = gr.Textbox(label="Código de Erro (opcional)")
                
                with gr.Row():
                    mentor_mode = gr.Checkbox(label="🎓 Modo Mentor", value=False)
                    force_local = gr.Checkbox(label="🏭 Forçar Local (Ollama)", value=False)
                
                diagnose_btn = gr.Button(
                    "🚀 Diagnosticar",
                    variant="primary",
                    size="lg",
                    elem_id="diagnose-btn"
                )
            
            with gr.Column(scale=2):
                output = gr.Markdown(label="Resultado do Diagnóstico", show_copy_button=False)
                error_output = gr.Textbox(
                    label="⚠️ Mensagens de Erro",
                    visible=False,
                    interactive=False,
                    elem_classes=["error-box"]
                )
        
        gr.Markdown(f"\n*Versão: {datetime.now().strftime('%d/%m/%Y')} | "
                   f"LGPD: Integrado | Python 3.13 Ready | 🔒 Autenticado*")
    
    # ──────────────────────────────────────────────────────────────────────
    # HANDLERS DE EVENTO
    # ──────────────────────────────────────────────────────────────────────
    
    # Login
    login_btn.click(
        fn=login_page,
        inputs=[username_input, password_input],
        outputs=[login_msg, session_token, current_user, login_container, main_interface]
    ).then(
        fn=get_user_display,
        inputs=[current_user],
        outputs=[user_info]
    )
    
    # Logout
    logout_btn.click(
        fn=logout,
        inputs=[session_token],
        outputs=[login_container, main_interface]
    ).then(
        fn=lambda: ("", ""),
        outputs=[session_token, current_user]
    )
    
    # Diagnóstico (com segurança)
    diagnose_btn.click(
        fn=diagnose_handler_secure,
        inputs=[xml_input, incident_id, error_code, mentor_mode, force_local, session_token],
        outputs=[output, error_output]
    ).then(
        fn=lambda err: gr.update(visible=bool(err and err.strip())),
        inputs=[error_output],
        outputs=[error_output]
    )
    
    # Atualizar info do usuário ao carregar a página
    demo.load(
        fn=get_user_display,
        inputs=[current_user],
        outputs=[user_info]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Desativar analytics via env var (compatível com Gradio 6.x)
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    
    print("🚀 Iniciando EII Dashboard (Modo SEGURO)...")
    print(f"📊 Acesse: http://127.0.0.1:7860")
    print(f"🔐 Login: usa Credential Manager ou .env (EII_ADMIN_USER/EII_ADMIN_PASS)")
    print(f"🛡️ Segurança: Rate limit={RATE_LIMIT_REQUESTS}req/{RATE_LIMIT_WINDOW}s | Session timeout={SESSION_TIMEOUT_MINUTES}min")
    
    demo.launch(
        server_name="127.0.0.1",  # Só localhost por segurança
        server_port=7860,
        quiet=True
    )