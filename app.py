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
# Windows asyncio: usar SelectorEventLoop para evitar RuntimeError no cleanup
# ProactorEventLoop (default Win32) fecha handles antes do httpx terminar
# ─────────────────────────────────────────────────────────────────────────────
import asyncio as _asyncio_policy
if sys.platform == "win32":
    _asyncio_policy.set_event_loop_policy(_asyncio_policy.WindowsSelectorEventLoopPolicy())

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
# INTEL AGENT INTEGRATION (Fase 4 — IntelAgent proativo)
# ─────────────────────────────────────────────────────────────────────────────

INTEL_AGENT_AVAILABLE = False
try:
    from src.intel_agent.intel_agent import IntelAgent as _IntelAgent
    INTEL_AGENT_AVAILABLE = True
    print("✅ IntelAgent loaded successfully")
except Exception as _ie:
    print(f"⚠️ IntelAgent not available: {_ie}")

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


_PLACEHOLDER_VALUES = {
    "", "placeholder", "chave_key", "mude_esta_senha_urgente_123",
    "no-key-needed", "your-key-here", "sk-xxx",
}

def _inject_secrets_to_env():
    """Carrega API keys do Credential Manager para os.environ.

    Sempre sobrescreve — keyring tem prioridade sobre .env.
    Remove placeholders do os.environ para que SmartRouter pule
    providers não configurados (load_dotenv pode ter setado "placeholder").
    """
    _KEYS = ["GROQ_API_KEY", "GOOGLE_AI_API_KEY", "MISTRAL_API_KEY",
             "CEREBRAS_API_KEY", "QWEN_API_KEY", "LANGCHAIN_API_KEY"]
    for k in _KEYS:
        v = get_config_with_fallback(k)  # keyring → ctypes → .env → os.getenv
        if v and v not in _PLACEHOLDER_VALUES:
            os.environ[k] = v
            print(f"[SECRETS] {k} configurado")
        else:
            # Remove placeholder para SmartRouter nao tentar o provider
            if os.environ.get(k, "") in _PLACEHOLDER_VALUES:
                os.environ.pop(k, None)
                print(f"[SECRETS] {k} removido (placeholder)")

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
# Formatador IntelAgent — Insights Proativos
# ─────────────────────────────────────────────────────────────────────────────

def format_insights_md(insights: dict) -> str:
    """Formata ProactiveInsights dict como markdown para exibição no Gradio."""
    if not insights or insights.get("erro"):
        return ""

    risco = insights.get("risco_recorrencia", "DESCONHECIDO")
    risco_icon = {"ALTO": "🔴", "MEDIO": "🟡", "BAIXO": "🟢"}.get(risco, "⚪")

    padrao = insights.get("padrao_historico", {})
    total_90d = padrao.get("total_90d", 0)
    total_30d = padrao.get("total_30d", 0)
    taxa = padrao.get("taxa_aprovacao", 0.0)
    tempo = padrao.get("tempo_medio_resolucao_h")
    tendencia = padrao.get("tendencia", "ESTAVEL")
    tendencia_icon = {"CRESCENTE": "📈", "DECRESCENTE": "📉", "ESTAVEL": "➡️"}.get(tendencia, "")

    tempo_str = f"{tempo}h" if tempo is not None else "N/A"

    evento = insights.get("evento", "")
    codigo_erro = insights.get("codigo_erro", "")
    header = f"`{codigo_erro}`" if codigo_erro else ""
    if evento:
        header = f"`{evento}` / {header}" if header else f"`{evento}`"

    md = f"""---
### 🔍 Insights Proativos {risco_icon} Risco: **{risco}**
{f"**Padrão analisado:** {header}" if header else ""}

| Métrica | Valor |
|---------|-------|
| Ocorrências (90 dias) | {total_90d} |
| Ocorrências (30 dias) | {total_30d} {tendencia_icon} {tendencia} |
| Taxa de aprovação HITL | {int(taxa * 100)}% |
| Tempo médio de resolução | {tempo_str} |
"""

    alertas = insights.get("alertas", [])
    if alertas:
        md += "\n**⚠️ Alertas:**\n"
        for alerta in alertas:
            md += f"> {alerta}\n\n"

    relacionados = insights.get("incidentes_relacionados", [])
    if relacionados:
        md += "\n**🔗 Incidentes KB relacionados:**\n"
        for rel in relacionados:
            tags_str = ", ".join(rel.get("tags_comuns", []))
            md += (
                f"- **{rel['id']}** — {rel['titulo']} "
                f"(`{rel['evento']}` / `{rel['codigo_erro']}`) "
                f"| Impacto: {rel.get('impacto', 'N/A')} "
                f"| Tags em comum: _{tags_str}_\n"
            )

    return md.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Executor Deep Agents (sync wrapper para asyncio)
# ─────────────────────────────────────────────────────────────────────────────

def _diagnose_deep_agents(xml: str, inc_id: str, mentor: bool) -> tuple[str, str]:
    """Retorna (formatted_diagnosis, insights_md)."""
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
        "proactive_insights": None,
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
    insights = result_state.get("proactive_insights") or {}

    formatted = format_output_deep_agents(final_result, errors, warnings)
    insights_md = format_insights_md(insights)
    return formatted, insights_md


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
) -> tuple[str, str, str]:
    """Retorna (diagnosis_md, insights_md, error_msg)."""
    if not session_token or not is_session_valid(session_token):
        log_secure("unknown", "diagnose_attempt_failed", reason="invalid_session")
        return "", "", "❌ Sessão expirada ou inválida. Faça login novamente."

    user_info = user_sessions[session_token]
    user_id = user_info.get("username", "unknown")

    allowed, remaining = rate_limit_check(user_id)
    if not allowed:
        log_secure(user_id, "rate_limit_exceeded", incident_id=inc_id)
        return "", "", f"⚠️ Rate limit excedido. Aguarde {RATE_LIMIT_WINDOW} segundos."

    if not xml.strip():
        log_secure(user_id, "diagnose_attempt_failed", incident_id=inc_id, reason="empty_xml")
        return "", "", "⚠️ Por favor, cole o conteúdo do XML antes de diagnosticar."

    log_secure(user_id, "diagnose_started", incident_id=inc_id, extra={
        "force_local": force_local,
        "mentor_mode": mentor,
        "use_smartrouter": use_smartrouter,
        "use_deep_agents": use_deep_agents,
    })

    try:
        resultado, insights_md = _diagnose_internal(xml, inc_id, err_code, mentor, force_local, use_smartrouter, use_deep_agents)
        log_secure(user_id, "diagnose_completed", incident_id=inc_id, extra={"remaining_requests": remaining})
        return resultado, insights_md, ""
    except Exception as e:
        log_secure(user_id, "diagnose_error", incident_id=inc_id, extra={"error_type": type(e).__name__})
        return "", "", f"💥 Erro interno: {type(e).__name__}"

def _run_intel_agent(diagnosis: dict) -> str:
    """Executa IntelAgent sobre um diagnosis dict e retorna markdown formatado."""
    if not INTEL_AGENT_AVAILABLE:
        return ""
    try:
        agent = _IntelAgent()
        insights = agent.run(diagnosis)
        return format_insights_md(insights)
    except Exception as e:
        print(f"⚠️ [INTEL] IntelAgent falhou: {e}")
        return ""


@ls_trace("eii.diagnose_internal")
def _diagnose_internal(xml: str, inc_id: str, err_code: str, mentor: bool, force_local: bool, use_smartrouter: bool = False, use_deep_agents: bool = False) -> tuple[str, str]:
    """Retorna (formatted_diagnosis, insights_md)."""

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
                return formatted_output, _run_intel_agent(fallback_diag)
            return f"❌ Erro Ollama: {res['error']}", ""
        except Exception as e:
            return f"💥 Erro ao chamar Ollama: {str(e)}", ""

    # 2. Deep Agents pipeline (LangGraph — Fase 4)
    if use_deep_agents and DEEP_AGENTS_AVAILABLE:
        print(f"🤖 [DEBUG] Usando Deep Agents pipeline para {inc_id}...")
        try:
            result, insights_md = _diagnose_deep_agents(xml, inc_id, mentor)
            print(f"✅ [DEBUG] Deep Agents concluído para {inc_id}")
            return result, insights_md
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
            diagnosis = main_result.get("diagnosis", main_result)
            return formatted_output, _run_intel_agent(diagnosis)

        print(f"⚠️ [DEBUG] Pipeline falhou ({error_msg[:100]}...), tentando fallback Ollama...")

    except Exception as e:
        print(f"💥 [DEBUG] Exceção no pipeline principal: {e}")

    # 4. Fallback para Ollama
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
            return formatted_output, _run_intel_agent(fallback_diag)
    except Exception as e:
        print(f"💥 [DEBUG] Exceção no fallback: {e}")

    return "💥 Erro crítico: Nenhum pipeline respondeu. Verifique os logs.", ""

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


def load_xml_file(file) -> tuple[str, str]:
    """Lê arquivo XML enviado via gr.File e retorna (conteúdo, nome_arquivo).

    Gradio 5 entrega FileData (Pydantic) com .path e .orig_name, ou um dict
    equivalente. Retorna strings vazias se inválido ou ilegível.
    """
    if file is None:
        return "", ""
    try:
        # Gradio 5: FileData Pydantic ou dict
        if isinstance(file, dict):
            file_path = file.get("path") or file.get("name", "")
            orig_name = file.get("orig_name") or file.get("name", "")
        else:
            file_path = getattr(file, "path", None) or getattr(file, "name", str(file))
            orig_name = getattr(file, "orig_name", None) or getattr(file, "name", "")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        print(f"[XML_UPLOAD] Arquivo carregado: {orig_name} ({len(content)} chars)")
        return content, orig_name
    except Exception as e:
        print(f"[XML_UPLOAD] Erro ao ler arquivo: {e}")
        return "", ""

# ─────────────────────────────────────────────────────────────────────────────
# Admin Handlers
# ─────────────────────────────────────────────────────────────────────────────

def _require_session(session_token: str) -> Optional[str]:
    """Retorna username se sessão válida, None caso contrário."""
    if not session_token or not is_session_valid(session_token):
        return None
    return user_sessions[session_token].get("username", "unknown")


def admin_get_sessions(session_token: str) -> str:
    user = _require_session(session_token)
    if not user:
        return "❌ Sessão inválida."

    if not user_sessions:
        return "_Nenhuma sessão ativa._"

    now = datetime.now()
    rows = []
    for token, info in user_sessions.items():
        last = info.get("last_activity")
        login = info.get("login_time")
        expires_in = ""
        if last:
            remaining = timedelta(minutes=SESSION_TIMEOUT_MINUTES) - (now - last)
            minutes = max(0, int(remaining.total_seconds() / 60))
            expires_in = f"{minutes}min"
        is_current = "**← atual**" if token == session_token else ""
        rows.append(
            f"| {info.get('username','?')} "
            f"| {login.strftime('%H:%M:%S') if login else '?'} "
            f"| {last.strftime('%H:%M:%S') if last else '?'} "
            f"| {expires_in} "
            f"| {is_current} |"
        )

    header = (
        "| Usuário | Login | Última atividade | Expira em | |\n"
        "|---------|-------|------------------|-----------|---|"
    )
    return f"**{len(user_sessions)} sessão(ões) ativa(s)**\n\n{header}\n" + "\n".join(rows)


def admin_revoke_sessions(session_token: str) -> str:
    user = _require_session(session_token)
    if not user:
        return "❌ Sessão inválida."

    tokens_to_remove = [t for t in list(user_sessions.keys()) if t != session_token]
    for t in tokens_to_remove:
        del user_sessions[t]

    log_secure(user, "admin_revoke_sessions", extra={"revoked": len(tokens_to_remove)})
    return f"✅ {len(tokens_to_remove)} sessão(ões) revogada(s). Sua sessão atual permanece ativa."


def admin_get_stats(session_token: str) -> str:
    user = _require_session(session_token)
    if not user:
        return "❌ Sessão inválida."

    db_path = os.environ.get("DB_PATH", "eii_incidents.db")
    try:
        con = sqlite3.connect(db_path)
        con.execute("PRAGMA busy_timeout=3000")

        # Totais por status
        status_rows = con.execute(
            "SELECT status, COUNT(*) FROM incidents GROUP BY status ORDER BY COUNT(*) DESC"
        ).fetchall()

        # Total geral
        total = con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

        # Últimos 7 e 30 dias
        last_7d = con.execute(
            "SELECT COUNT(*) FROM incidents WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        last_30d = con.execute(
            "SELECT COUNT(*) FROM incidents WHERE created_at >= datetime('now', '-30 days')"
        ).fetchone()[0]

        # MTTR médio (horas)
        mttr_row = con.execute(
            "SELECT AVG((julianday(decided_at) - julianday(created_at)) * 24) "
            "FROM incidents WHERE decided_at IS NOT NULL AND created_at IS NOT NULL"
        ).fetchone()
        mttr = round(mttr_row[0], 1) if mttr_row and mttr_row[0] is not None else None

        # Mais recente
        last_inc = con.execute(
            "SELECT id, created_at, status FROM incidents ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        con.close()
    except Exception as e:
        return f"❌ Erro ao consultar banco: {e}"

    status_md = "\n".join(f"| {s} | {c} |" for s, c in status_rows) or "| — | 0 |"
    mttr_str = f"{mttr}h" if mttr is not None else "N/A"
    last_str = f"`{last_inc[0]}` — {last_inc[1][:16]} ({last_inc[2]})" if last_inc else "Nenhum"

    return f"""**Total de incidentes:** {total}

| Status | Quantidade |
|--------|-----------|
{status_md}

| Métrica | Valor |
|---------|-------|
| Últimos 7 dias | {last_7d} |
| Últimos 30 dias | {last_30d} |
| MTTR médio | {mttr_str} |

**Último incidente:** {last_str}"""


def admin_get_metrics(session_token: str):
    """Retorna (kpi_md, fig_status, fig_trend) para o dashboard de métricas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    user = _require_session(session_token)
    if not user:
        return "❌ Sessão inválida.", None, None

    db_path = os.environ.get("DB_PATH", "eii_incidents.db")
    try:
        con = sqlite3.connect(db_path)
        con.execute("PRAGMA busy_timeout=3000")

        status_rows = con.execute(
            "SELECT status, COUNT(*) FROM incidents GROUP BY status ORDER BY COUNT(*) DESC"
        ).fetchall()
        total = con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        mttr_val = con.execute(
            "SELECT AVG((julianday(decided_at)-julianday(created_at))*24) "
            "FROM incidents WHERE decided_at IS NOT NULL AND created_at IS NOT NULL"
        ).fetchone()[0]
        trend_rows = con.execute(
            "SELECT date(created_at) as d, COUNT(*) as n "
            "FROM incidents WHERE created_at >= datetime('now','-30 days') "
            "GROUP BY d ORDER BY d"
        ).fetchall()
        con.close()
    except Exception as e:
        return f"❌ Erro ao consultar banco: {e}", None, None

    status_dict = {s: c for s, c in status_rows}
    approved = status_dict.get("APPROVED", 0)
    rejected = status_dict.get("REJECTED", 0)
    pending  = status_dict.get("PENDING", 0)
    decided  = approved + rejected
    mttr_str = f"{round(mttr_val, 1)}h" if mttr_val else "N/A"
    taxa_ap  = f"{int(approved/decided*100)}%" if decided else "N/A"
    taxa_rej = f"{int(rejected/decided*100)}%" if decided else "N/A"
    escal    = f"{int(rejected/decided*100)}%" if decided else "N/A"

    kpi_md = f"""| Métrica | Valor |
|---------|-------|
| Total de incidentes | **{total}** |
| Aprovados (HITL) | {approved} ({taxa_ap}) |
| Rejeitados | {rejected} ({taxa_rej}) |
| Pendentes | {pending} |
| MTTR médio | **{mttr_str}** |
| Escalation rate | {escal} |"""

    # ── Gráfico 1: distribuição por status ───────────────────────────────────
    _STATUS_COLORS = {"APPROVED": "#22c55e", "REJECTED": "#ef4444", "PENDING": "#f59e0b"}
    labels = [s for s, _ in status_rows]
    values = [c for _, c in status_rows]
    bar_colors = [_STATUS_COLORS.get(l, "#6b7280") for l in labels]

    fig1, ax1 = plt.subplots(figsize=(5, 2.5))
    ax1.barh(labels, values, color=bar_colors, height=0.5)
    ax1.set_xlabel("Quantidade")
    ax1.set_title("Distribuição por Status")
    for i, v in enumerate(values):
        ax1.text(v + 0.1, i, str(v), va="center", fontsize=9)
    fig1.tight_layout()

    # ── Gráfico 2: tendência últimos 30 dias ─────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(7, 2.8))
    if trend_rows:
        dates  = [r[0] for r in trend_rows]
        counts = [r[1] for r in trend_rows]
        ax2.plot(dates, counts, marker="o", color="#3b82f6", linewidth=1.5, markersize=4)
        ax2.fill_between(dates, counts, alpha=0.1, color="#3b82f6")
        ax2.set_ylabel("Incidentes")
        plt.xticks(rotation=45, ha="right", fontsize=7)
    else:
        ax2.text(0.5, 0.5, "Sem dados nos últimos 30 dias",
                 ha="center", va="center", transform=ax2.transAxes, color="#6b7280")
    ax2.set_title("Incidentes por dia — últimos 30 dias")
    fig2.tight_layout()

    return kpi_md, fig1, fig2


def admin_change_password(session_token: str, new_pass: str, confirm_pass: str) -> str:
    global ADMIN_PASSWORD_HASH

    user = _require_session(session_token)
    if not user:
        return "❌ Sessão inválida."

    if not new_pass or not new_pass.strip():
        return "⚠️ A nova senha não pode ser vazia."
    if len(new_pass) < 8:
        return "⚠️ A senha deve ter pelo menos 8 caracteres."
    if new_pass != confirm_pass:
        return "⚠️ As senhas não coincidem."

    try:
        import keyring
        keyring.set_password("EII_Project", "EII_ADMIN_PASS", new_pass)
    except Exception as e:
        return f"❌ Erro ao salvar no Credential Manager: {e}"

    ADMIN_PASSWORD_HASH = hashlib.sha256(new_pass.encode()).hexdigest()
    log_secure(user, "admin_change_password")
    return "✅ Senha alterada com sucesso. O novo hash está ativo nesta sessão."


# ─────────────────────────────────────────────────────────────────────────────
# Interface Gradio
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
/* ── Reset e base ─────────────────────────────────────────── */
.gradio-container { font-family: 'IBM Plex Sans', 'Inter', system-ui, sans-serif !important; }

/* ── Login card ───────────────────────────────────────────── */
.login-card {
    max-width: 420px;
    margin: 80px auto;
    padding: 2.5rem;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    background: #ffffff;
}
.login-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.25rem;
}
.login-subtitle {
    font-size: 0.875rem;
    color: #64748b;
    margin-bottom: 1.5rem;
}

/* ── Header principal ─────────────────────────────────────── */
.app-header {
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.75rem;
    margin-bottom: 0.5rem;
}
.app-title {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    margin: 0 !important;
}
.user-badge {
    font-size: 0.8rem;
    color: #475569;
    padding: 4px 10px;
    background: #f1f5f9;
    border-radius: 20px;
    display: inline-block;
}

/* ── Painel de resultado ──────────────────────────────────── */
.output-panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.25rem;
    min-height: 420px;
}

/* ── Opções avançadas ─────────────────────────────────────── */
.advanced-opts label {
    font-size: 0.85rem !important;
    color: #475569 !important;
}

/* ── Erro ─────────────────────────────────────────────────── */
.error-box {
    border-left: 4px solid #ef4444;
    background: #fef2f2;
    padding: 0.5rem 1rem;
    border-radius: 0 6px 6px 0;
}

/* ── Footer ───────────────────────────────────────────────── */
.footer-note {
    font-size: 0.75rem;
    color: #94a3b8;
    text-align: right;
    margin-top: 0.5rem;
}
"""

with gr.Blocks(
    title="EII — ERP Incident Intelligence",
    theme=gr.themes.Monochrome(),
    css=_CSS,
) as demo:

    session_token = gr.State("")
    current_user  = gr.State("")

    # ── Login ──────────────────────────────────────────────────────────────
    with gr.Column(elem_classes=["login-card"]) as login_container:
        gr.Markdown("**EII — ERP Incident Intelligence**", elem_classes=["login-title"])
        gr.Markdown("Sistema de diagnóstico de incidentes eSocial · Acesso restrito", elem_classes=["login-subtitle"])
        username_input = gr.Textbox(label="Usuário", placeholder="seu.usuario")
        password_input = gr.Textbox(label="Senha", type="password", placeholder="••••••••")
        login_btn      = gr.Button("Entrar", variant="primary", size="lg")
        login_msg      = gr.Markdown("")
        gr.Markdown("_Credenciais via Windows Credential Manager ou `.env`_", elem_classes=["login-subtitle"])

    # ── App principal ──────────────────────────────────────────────────────
    with gr.Column(visible=False) as main_interface:

        # Header
        with gr.Row(elem_classes=["app-header"]):
            gr.Markdown("**EII — ERP Incident Intelligence**", elem_classes=["app-title"])
            user_info  = gr.Markdown("", elem_classes=["user-badge"])
            logout_btn = gr.Button("Sair", variant="secondary", size="sm")

        with gr.Tabs():

            # ── Aba Diagnóstico ───────────────────────────────────────────
            with gr.Tab("Diagnóstico"):

                with gr.Row():

                    # Coluna input (menor)
                    with gr.Column(scale=2):
                        xml_upload = gr.File(
                            label="Carregar arquivo XML",
                            file_types=[".xml"],
                            file_count="single",
                        )
                        upload_status = gr.Markdown(visible=False)
                        xml_input = gr.Textbox(
                            label="XML eSocial / EFD-Reinf",
                            lines=14,
                            placeholder="Cole o conteúdo XML completo aqui\nou carregue um arquivo acima...",
                        )
                        with gr.Row():
                            incident_id = gr.Textbox(
                                label="ID do Incidente",
                                value=f"INC-{datetime.now().strftime('%Y%m%d-%H%M')}",
                                scale=2,
                            )
                            error_code = gr.Textbox(label="Código de Erro", scale=1)

                        mentor_mode = gr.Checkbox(
                            label="Modo Mentor — explicação didática para analistas juniores",
                            value=False,
                        )

                        with gr.Accordion("Opções avançadas", open=False, elem_classes=["advanced-opts"]):
                            force_local = gr.Checkbox(label="Forçar Ollama local (LGPD total)", value=False)
                            if SMARTROUTER_AVAILABLE:
                                use_smartrouter = gr.Checkbox(
                                    label="SmartRouter — roteamento multi-LLM com fallback",
                                    value=False,
                                )
                            else:
                                use_smartrouter = gr.State(False)
                            if DEEP_AGENTS_AVAILABLE:
                                use_deep_agents = gr.Checkbox(
                                    label="Deep Agents — pipeline LangGraph (parse → route → generate → evaluate → reflexion)",
                                    value=False,
                                )
                            else:
                                use_deep_agents = gr.State(False)

                        diagnose_btn = gr.Button("Diagnosticar", variant="primary", size="lg")

                    # Coluna output (maior)
                    with gr.Column(scale=3):
                        output = gr.Markdown(
                            value=(
                                "### Como usar\n\n"
                                "1. Cole o XML rejeitado no campo ao lado\n"
                                "2. Clique em **Diagnosticar**\n"
                                "3. Revise causa raiz e passos de resolução\n"
                                "4. Aprove ou rejeite na aba de Aprovação HITL\n\n"
                                "---\n"
                                "_Pipeline CRAG com Knowledge Base de 93 incidentes documentados "
                                "(eSocial + EFD-Reinf) e PII Scrubbing automático (LGPD)._"
                            ),
                            elem_classes=["output-panel"],
                        )
                        insights_output = gr.Markdown(visible=False)
                        error_output    = gr.Textbox(
                            label="Erros",
                            visible=False,
                            interactive=False,
                            elem_classes=["error-box"],
                        )

                gr.Markdown(
                    f"v3.0 · {datetime.now().strftime('%d/%m/%Y')} · LGPD ativo · KB: 93 incidentes",
                    elem_classes=["footer-note"],
                )

            # ── Aba Admin ─────────────────────────────────────────────────
            with gr.Tab("Admin"):

                with gr.Tabs():

                    with gr.Tab("Sessões Ativas"):
                        sessions_output = gr.Markdown("_Clique em Atualizar para carregar._")
                        with gr.Row():
                            sessions_refresh_btn = gr.Button("Atualizar", size="sm")
                            sessions_revoke_btn  = gr.Button("Revogar todas (exceto atual)", variant="stop", size="sm")
                        sessions_action_msg = gr.Markdown("")

                    with gr.Tab("Métricas"):
                        metrics_kpi = gr.Markdown("_Clique em Atualizar para carregar._")
                        with gr.Row():
                            metrics_status_chart = gr.Plot(label="Status")
                            metrics_trend_chart  = gr.Plot(label="Tendência 30d")
                        metrics_refresh_btn = gr.Button("Atualizar", size="sm")

                    with gr.Tab("Alterar Senha"):
                        gr.Markdown("A senha é salva no Windows Credential Manager e o hash é atualizado na sessão atual.")
                        new_pass_input     = gr.Textbox(label="Nova senha", type="password", placeholder="Mínimo 8 caracteres")
                        confirm_pass_input = gr.Textbox(label="Confirmar nova senha", type="password")
                        change_pass_btn    = gr.Button("Alterar senha", variant="primary")
                        change_pass_msg    = gr.Markdown("")
    
    # Event Handlers
    login_btn.click(fn=login_page, inputs=[username_input, password_input], outputs=[login_msg, session_token, current_user, login_container, main_interface]).then(fn=get_user_display, inputs=[current_user], outputs=[user_info])
    logout_btn.click(fn=logout, inputs=[session_token], outputs=[login_container, main_interface]).then(fn=lambda: ("", ""), outputs=[session_token, current_user])
    diagnose_btn.click(
        fn=diagnose_handler_secure,
        inputs=[xml_input, incident_id, error_code, mentor_mode, force_local, session_token, use_smartrouter, use_deep_agents],
        outputs=[output, insights_output, error_output]
    ).then(
        fn=lambda ins, err: (
            gr.update(visible=bool(ins and ins.strip())),
            gr.update(visible=bool(err and err.strip())),
        ),
        inputs=[insights_output, error_output],
        outputs=[insights_output, error_output],
    )
    xml_upload.change(
        fn=load_xml_file,
        inputs=[xml_upload],
        outputs=[xml_input, upload_status],
    ).then(
        fn=lambda name: gr.update(
            visible=bool(name),
            value=f"_Arquivo carregado: **{name}**_" if name else "",
        ),
        inputs=[upload_status],
        outputs=[upload_status],
    )

    # Admin — Sessões
    sessions_refresh_btn.click(fn=admin_get_sessions, inputs=[session_token], outputs=[sessions_output])
    sessions_revoke_btn.click(fn=admin_revoke_sessions, inputs=[session_token], outputs=[sessions_action_msg]).then(
        fn=admin_get_sessions, inputs=[session_token], outputs=[sessions_output]
    )

    # Admin — Métricas
    metrics_refresh_btn.click(
        fn=admin_get_metrics,
        inputs=[session_token],
        outputs=[metrics_kpi, metrics_status_chart, metrics_trend_chart],
    )

    # Admin — Alterar Senha
    change_pass_btn.click(
        fn=admin_change_password,
        inputs=[session_token, new_pass_input, confirm_pass_input],
        outputs=[change_pass_msg],
    ).then(
        fn=lambda: ("", ""),
        outputs=[new_pass_input, confirm_pass_input],
    )

    demo.load(fn=get_user_display, inputs=[current_user], outputs=[user_info])

# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
    print("EII — ERP Incident Intelligence v3.0")
    print("Acesse: http://127.0.0.1:7860")
    print(f"Rate limit: {RATE_LIMIT_REQUESTS}req/{RATE_LIMIT_WINDOW}s | Timeout sessao: {SESSION_TIMEOUT_MINUTES}min")
    print(f"SmartRouter: {'disponivel' if SMARTROUTER_AVAILABLE else 'indisponivel'}")
    print(f"Deep Agents: {'disponivel' if DEEP_AGENTS_AVAILABLE else 'indisponivel'}")
    demo.launch(server_name="127.0.0.1", server_port=7860, quiet=True)
