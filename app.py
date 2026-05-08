"""
EII — ERP Incident Intelligence (SECURE VERSION v2.2)
Dashboard Gradio com Autenticação + Pipeline CRAG + SmartRouter Opcional + Observability
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

if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "eii-erp-v2")
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

def ls_trace(name: str):
    """Decorador seguro: aplica @traceable apenas se LangSmith estiver configurado."""
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
        return func
    return decorator

# ─────────────────────────────────────────────────────────────────────────────
# SMARTROUTER INTEGRATION (Optional - Graceful Fallback)
# ─────────────────────────────────────────────────────────────────────────────

SMARTROUTER_AVAILABLE = False
try:
    # Importa apenas a função de diagnóstico do pipeline com SmartRouter
    from crag_pipeline_smartrouter import run_crag as diagnosticar_incidente_sr
    SMARTROUTER_AVAILABLE = True
    print("✅ SmartRouter v2 loaded successfully")
except ImportError as e:
    print(f"⚠️ SmartRouter not available: {e}. Using standard pipeline.")
    # Fallback: usa o pipeline padrão que já funciona
    from crag_pipeline import diagnosticar_incidente as diagnosticar_incidente_sr

# ─────────────────────────────────────────────────────────────────────────────
# DEEP AGENTS INTEGRATION (LangGraph pipeline — Fase 4)
# ─────────────────────────────────────────────────────────────────────────────

DEEP_AGENTS_AVAILABLE = False
try:
    import asyncio as _asyncio
    import concurrent.futures as _futures
    from src.deep_agents.graph import create_deep_agent_graph as _create_graph
    from src.deep_agents.state import AgentState as _AgentState
    _eii_agent_graph = _create_graph()
    DEEP_AGENTS_AVAILABLE = True
    print("✅ Deep Agents pipeline (LangGraph) loaded successfully")
except Exception as _e:
    print(f"⚠️ Deep Agents not available: {_e}")

# ─────────────────────────────────────────────────────────────────────────────
# Configurações Globais
# ─────────────────────────────────────────────────────────────────────────────

ENV_FILE = Path(__file__).parent / ".env"
warnings.filterwarnings("ignore", message=".*logfire-plugin.*")

# ─────────────────────────────────────────────────────────────────────────────
# Integração com Secure Secrets Manager (Credential Manager)
# ─────────────────────────────────────────────────────────────────────────────

def _read_wincred(service: str, username: str) -> Optional[str]:
    """Lê credencial do Windows Credential Manager via ctypes (compatível com cmdkey).

    O Python keyring usa WinVaultKeyring que às vezes não lê credenciais salvas
    via `cmdkey /add` porque o blob é UTF-16-LE e o lookup pode divergir.
    Esta função chama CredReadW diretamente, contornando essa incompatibilidade.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        CRED_TYPE_GENERIC = 1

        class _FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]

        class _CRED_ATTR(ctypes.Structure):
            _fields_ = [
                ("Keyword",   ctypes.c_wchar_p),
                ("Flags",     wt.DWORD),
                ("ValueSize", wt.DWORD),
                ("Value",     ctypes.POINTER(wt.BYTE)),
            ]

        class _CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags",              wt.DWORD),
                ("Type",               wt.DWORD),
                ("TargetName",         ctypes.c_wchar_p),
                ("Comment",            ctypes.c_wchar_p),
                ("LastWritten",        _FILETIME),
                ("CredentialBlobSize", wt.DWORD),
                ("CredentialBlob",     ctypes.POINTER(wt.BYTE)),
                ("Persist",            wt.DWORD),
                ("AttributeCount",     wt.DWORD),
                ("Attributes",         ctypes.POINTER(_CRED_ATTR)),
                ("TargetAlias",        ctypes.c_wchar_p),
                ("UserName",           ctypes.c_wchar_p),
            ]

        advapi32 = ctypes.windll.advapi32

        # Tenta GENERIC (1) — keyring/secure_secrets.py; depois DOMAIN_PASSWORD (2) — cmdkey
        # Nota: cmdkey armazena como DOMAIN_PASSWORD mas o blob fica vazio por design do Windows
        for cred_type in (1, 2):
            p_cred = ctypes.POINTER(_CREDENTIAL)()
            if advapi32.CredReadW(service, cred_type, 0, ctypes.byref(p_cred)):
                cred = p_cred.contents
                blob_size = cred.CredentialBlobSize
                if blob_size and cred.CredentialBlob and cred.UserName == username:
                    raw = bytes(cred.CredentialBlob[:blob_size])
                    advapi32.CredFree(p_cred)
                    return raw.decode("utf-16-le", errors="replace").rstrip("\x00")
                advapi32.CredFree(p_cred)
    except Exception:
        pass
    return None


def get_config_with_fallback(key: str, default: str = None) -> Optional[str]:
    """Recupera configuração: Credential Manager (keyring) → Credential Manager (ctypes) → .env → default"""
    # 1. Tenta via keyring (caminho normal)
    try:
        import keyring
        value = keyring.get_password("EII_Project", key)
        if value:
            return value
    except (ImportError, Exception):
        pass

    # 2. Fallback: lê direto do Windows Credential Manager via ctypes
    #    Resolve incompatibilidade com credenciais salvas por `cmdkey /add`
    value = _read_wincred("EII_Project", key)
    if value:
        return value

    # 3. Fallback: arquivo .env local
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


def _inject_secrets_to_env():
    """Carrega API keys do Credential Manager para os.environ.

    Necessário porque crag_pipeline.py e smartrouter_v2 leem via os.environ.
    Sempre sobrescreve — keyring tem prioridade sobre valores de .env que
    podem estar desatualizados ou como placeholder.
    """
    _KEYS = ["GROQ_API_KEY", "GOOGLE_AI_API_KEY", "MISTRAL_API_KEY",
             "CEREBRAS_API_KEY", "QWEN_API_KEY", "LANGCHAIN_API_KEY"]
    for k in _KEYS:
        v = get_config_with_fallback(k)  # keyring → ctypes → .env → os.getenv
        if v:
            os.environ[k] = v
            print(f"[SECRETS] {k} configurado")

_inject_secrets_to_env()

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
        safe_keys = ["route", "backend", "force_local", "mentor_mode", "use_smartrouter"]
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
# Formatador Deep Agents
# ─────────────────────────────────────────────────────────────────────────────

def format_output_deep_agents(final_result: dict, errors: list, warnings: list) -> str:
    if not final_result:
        errs = "\n".join(errors) if errors else "Nenhum detalhe disponível."
        return f"❌ **Diagnóstico não gerado.**\n\n{errs}"

    meta = final_result.get("metadata", {})
    logprob = meta.get("logprob_sim")
    logprob_str = f"{logprob:.3f}" if logprob is not None else "N/A"
    routing = meta.get("routing_decision", "N/A")
    iteracoes = meta.get("iteracoes", 0)
    eval_score = meta.get("evaluation_score")
    eval_str = f"{eval_score:.0%}" if eval_score is not None else "N/A"

    passos_md = ""
    for i, step in enumerate(final_result.get("passos_resolucao", []), 1):
        passos_md += f"{i}. {step}\n"

    alerta = final_result.get("alerta_hitl", "")
    alerta_md = f"\n> ⚠️ **HITL:** {alerta}" if alerta else ""

    refs = final_result.get("referencias_kb", [])
    refs_md = f"\n**Referências KB:** {', '.join(refs)}" if refs else ""

    warn_md = ""
    if warnings:
        warn_md = "\n**Avisos:** " + " | ".join(warnings)

    err_md = ""
    if errors:
        err_md = "\n\n> ⚠️ " + "\n> ".join(errors)

    return f"""### 📋 Diagnóstico Deep Agents: `{final_result.get('incident_id', 'N/A')}`
**Pipeline:** LangGraph v2.3 | **Routing:** `{routing}` | **Iterações:** {iteracoes}

| Campo | Valor |
|-------|-------|
| **Severidade** | {final_result.get('severidade', 'N/A')} |
| **Confiança** | {final_result.get('confianca', 'N/A')} (logprob={logprob_str}) |
| **Fonte** | {final_result.get('fonte', 'N/A')} |
| **Avaliação** | {eval_str} |
| **Tempo estimado** | {final_result.get('tempo_estimado', 'N/A')} |

### 🔍 Causa Raiz
{final_result.get('diagnostico', 'N/A')}

### 🛠️ Passos de Resolução
{passos_md}
### ✅ Validação
{final_result.get('validacao', 'N/A')}
{alerta_md}{refs_md}{warn_md}{err_md}"""


# ─────────────────────────────────────────────────────────────────────────────
# Executor Deep Agents (sync wrapper para asyncio)
# ─────────────────────────────────────────────────────────────────────────────

def _diagnose_deep_agents(xml: str, inc_id: str, mentor: bool) -> str:
    init_state: _AgentState = {
        "xml_input": xml,
        "incident_id": inc_id,
        "use_mentor_mode": mentor,
        "context": None,
        "retrieved": None,
        "diagnosis": None,
        "evaluation_score": None,
        "evaluation_feedback": None,
        "needs_refinement": False,
        "iteration_count": 0,
        "max_iterations": 2,
        "routing_decision": None,
        "retrieval_backend": os.environ.get("EII_RETRIEVAL_BACKEND", "chromadb"),
        "model_used": None,
        "errors": [],
        "warnings": [],
        "final_result": None,
    }

    # Executa o grafo async de forma segura — Gradio pode rodar em loop existente
    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with _futures.ThreadPoolExecutor(max_workers=1) as pool:
            result_state = pool.submit(_asyncio.run, _eii_agent_graph.ainvoke(init_state)).result()
    else:
        result_state = _asyncio.run(_eii_agent_graph.ainvoke(init_state))

    final_result = result_state.get("final_result")
    errors = result_state.get("errors", [])
    warnings = result_state.get("warnings", [])

    formatted = format_output_deep_agents(final_result, errors, warnings)
    return formatted


# ─────────────────────────────────────────────────────────────────────────────
# Handler Principal SEGURO
# ─────────────────────────────────────────────────────────────────────────────

@ls_trace("eii.diagnose_handler_secure")
def diagnose_handler_secure(
    xml: str,
    inc_id: str,
    err_code: str,
    mentor: bool,
    force_local: bool,
    session_token: str,
    use_smartrouter: bool = False,
    use_deep_agents: bool = False,
) -> tuple[str, str]:
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

    log_secure(user_id, "diagnose_started", incident_id=inc_id, extra={
        "force_local": force_local,
        "mentor_mode": mentor,
        "use_smartrouter": use_smartrouter,
        "use_deep_agents": use_deep_agents,
    })

    try:
        resultado = _diagnose_internal(xml, inc_id, err_code, mentor, force_local, use_smartrouter, use_deep_agents)
        log_secure(user_id, "diagnose_completed", incident_id=inc_id, extra={"remaining_requests": remaining})
        return resultado, ""
    except Exception as e:
        log_secure(user_id, "diagnose_error", incident_id=inc_id, extra={"error_type": type(e).__name__})
        return "", f"💥 Erro interno: {type(e).__name__}"

@ls_trace("eii.diagnose_internal")
def _diagnose_internal(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool, use_smartrouter: bool = False, use_deep_agents: bool = False) -> str:
    # 1. Forçar Local (Ollama) - prioridade máxima para LGPD
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
    
    # 2. Deep Agents pipeline (LangGraph — Fase 4)
    if use_deep_agents and DEEP_AGENTS_AVAILABLE:
        print(f"🤖 [DEBUG] Usando Deep Agents pipeline para {inc_id}...")
        try:
            result = _diagnose_deep_agents(xml, inc_id, mentor)
            print(f"✅ [DEBUG] Deep Agents concluído para {inc_id}")
            return result
        except Exception as e:
            print(f"💥 [DEBUG] Deep Agents falhou: {e} — caindo para pipeline padrão")

    # 3. Pipeline principal (SmartRouter ou padrão)
    pipeline_name = "SmartRouter" if (use_smartrouter and SMARTROUTER_AVAILABLE) else "padrão"
    print(f"☁️ [DEBUG] Usando pipeline {pipeline_name} para {inc_id}...")
    
    try:
        main_result = diagnosticar_incidente_sr(
            xml_content=xml,
            incident_id=inc_id,
            error_code=err_code,
            mentor_mode=mentor,
            force_local=False  # Já tratamos force_local acima
        )
        
        # Verificar se foi sucesso real
        error_msg = str(main_result.get("error", "")).lower()
        is_api_error = any(x in error_msg for x in ["provedores falharam", "api key", "401", "invalid", "incorrect"])
        
        if main_result.get("success") and not is_api_error:
            route = main_result.get("_routing", {}).get("route_used", "auto")
            route_label = f"smartrouter:{route}" if (use_smartrouter and SMARTROUTER_AVAILABLE) else route
            print(f"✅ [DEBUG] Pipeline funcionou! Rota: {route_label}")
            formatted_output = format_output(main_result, route_label)
            if mentor:
                formatted_output = apply_mentor_mode(formatted_output, True)
            return formatted_output
        
        print(f"⚠️ [DEBUG] Pipeline falhou ({error_msg[:100]}...), tentando fallback Ollama...")
        
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no pipeline principal: {e}")
    
    # 3. Fallback para Ollama
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
    
    return "💥 Erro crítico: Nenhum pipeline respondeu. Verifique os logs."

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
                    if SMARTROUTER_AVAILABLE:
                        use_smartrouter = gr.Checkbox(
                            label="🧠 SmartRouter (multi-LLM)",
                            value=False,
                            info="Roteamento inteligente multi-LLM com fallback resiliente"
                        )
                    else:
                        use_smartrouter = gr.State(False)
                    if DEEP_AGENTS_AVAILABLE:
                        use_deep_agents = gr.Checkbox(
                            label="🤖 Deep Agents (LangGraph v2.3)",
                            value=False,
                            info="Pipeline multi-agente: parse → route → retrieve → generate → evaluate → reflexion"
                        )
                    else:
                        use_deep_agents = gr.State(False)
                
                diagnose_btn = gr.Button("🚀 Diagnosticar", variant="primary", size="lg")
            
            with gr.Column(scale=2):
                output = gr.Markdown(label="Resultado do Diagnóstico")
                error_output = gr.Textbox(label="⚠️ Mensagens de Erro", visible=False, interactive=False, elem_classes=["error-box"])
        
        gr.Markdown(f"\n*Versão: {datetime.now().strftime('%d/%m/%Y')} | LGPD: Integrado | Python 3.13 Ready | 🔒 Autenticado*")
    
    # Event Handlers
    login_btn.click(fn=login_page, inputs=[username_input, password_input], outputs=[login_msg, session_token, current_user, login_container, main_interface]).then(fn=get_user_display, inputs=[current_user], outputs=[user_info])
    logout_btn.click(fn=logout, inputs=[session_token], outputs=[login_container, main_interface]).then(fn=lambda: ("", ""), outputs=[session_token, current_user])
    diagnose_btn.click(
        fn=diagnose_handler_secure,
        inputs=[xml_input, incident_id, error_code, mentor_mode, force_local, session_token, use_smartrouter, use_deep_agents],
        outputs=[output, error_output]
    ).then(fn=lambda err: gr.update(visible=bool(err and err.strip())), inputs=[error_output], outputs=[error_output])
    demo.load(fn=get_user_display, inputs=[current_user], outputs=[user_info])

# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    print("🚀 Iniciando EII Dashboard v2.3 (Mentor + SmartRouter + Deep Agents + Observability)...")
    print(f"📊 Acesse: http://127.0.0.1:7860")
    print(f"🔐 Login: usa Credential Manager ou .env")
    print(f"🛡️ Segurança: Rate limit={RATE_LIMIT_REQUESTS}req/{RATE_LIMIT_WINDOW}s | Session timeout={SESSION_TIMEOUT_MINUTES}min")
    if SMARTROUTER_AVAILABLE:
        print("🧠 SmartRouter: Disponível (marque o checkbox para usar)")
    else:
        print("⚠️ SmartRouter: Não disponível (usando pipeline padrão)")
    if DEEP_AGENTS_AVAILABLE:
        print("🤖 Deep Agents (LangGraph): Disponível (marque o checkbox para usar)")
    else:
        print("⚠️ Deep Agents: Não disponível")
    demo.launch(server_name="127.0.0.1", server_port=7860, quiet=True)
