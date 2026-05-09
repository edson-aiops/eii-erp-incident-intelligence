"""
EII — Notifier
Envia alertas por e-mail quando um incidente fica PENDING aguardando decisão HITL.

Configuração (via keyring ou .env):
    EII_SMTP_HOST   — servidor SMTP  (ex: smtp.gmail.com)
    EII_SMTP_PORT   — porta SMTP     (ex: 587 para TLS, 465 para SSL)
    EII_SMTP_USER   — usuário SMTP   (ex: conta@gmail.com)
    EII_SMTP_PASS   — senha / app password
    EII_ALERT_EMAIL — destinatário(s), separados por vírgula

Configurar (uma vez):
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_SMTP_HOST', 'smtp.gmail.com')"
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_SMTP_PORT', '587')"
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_SMTP_USER', 'conta@gmail.com')"
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_SMTP_PASS', 'app-password')"
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_ALERT_EMAIL', 'analista@empresa.com')"

Sem nenhuma dependência além da stdlib — smtplib + email.mime.
"""

import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────

_SMTP_KEYS = ("EII_SMTP_HOST", "EII_SMTP_PORT", "EII_SMTP_USER", "EII_SMTP_PASS", "EII_ALERT_EMAIL")


def _get_secret(key: str) -> str | None:
    """Lê secret: keyring → os.environ."""
    try:
        import keyring
        val = keyring.get_password("EII_Project", key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key)


def _smtp_config() -> dict | None:
    """Retorna dict com configuração SMTP ou None se incompleta."""
    cfg = {k: _get_secret(k) for k in _SMTP_KEYS}
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        return None
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# E-mail builder
# ─────────────────────────────────────────────────────────────────────────────

_SEVERITY_COLOR = {
    "crítico": "#c0392b",
    "alto":    "#e67e22",
    "médio":   "#f39c12",
    "baixo":   "#27ae60",
}


def _build_email(cfg: dict, incident: dict) -> MIMEMultipart:
    inc_id    = incident.get("incident_id", "—")
    evento    = incident.get("evento", "—")
    erro      = incident.get("codigo_erro", "—")
    sev       = incident.get("severidade", "—").lower()
    confianca = incident.get("confianca", "—")
    alerta    = incident.get("alerta_hitl", "")
    causa     = incident.get("causa_raiz", "—")

    sev_color = _SEVERITY_COLOR.get(sev, "#7f8c8d")
    passos = incident.get("passos_resolucao", [])
    passos_html = "".join(f"<li>{p}</li>" for p in passos) if passos else "<li>—</li>"

    subject = f"[EII] Incidente PENDING — {inc_id} | {evento} {erro} | severidade {sev.upper()}"

    html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family: 'IBM Plex Sans', Arial, sans-serif; background:#0f0f0f; color:#e0e0e0; padding:24px;">
  <div style="max-width:640px; margin:0 auto; background:#1a1a1a; border-radius:8px; overflow:hidden;">

    <!-- header -->
    <div style="background:#161616; padding:20px 24px; border-bottom:3px solid {sev_color};">
      <h2 style="margin:0; color:#ffffff; font-size:18px;">
        EII — Incidente aguardando aprovacao HITL
      </h2>
      <p style="margin:4px 0 0; color:#a8a8a8; font-size:13px;">
        Acao necessaria: revisar e aprovar ou rejeitar no dashboard EII
      </p>
    </div>

    <!-- body -->
    <div style="padding:24px;">

      <!-- badge severidade -->
      <div style="display:inline-block; background:{sev_color}; color:#fff;
                  padding:4px 12px; border-radius:4px; font-size:12px;
                  font-weight:bold; margin-bottom:16px; text-transform:uppercase;">
        SEVERIDADE {sev}
      </div>

      <!-- campos principais -->
      <table style="width:100%; border-collapse:collapse; margin-bottom:20px; font-size:14px;">
        <tr><td style="padding:8px; color:#a8a8a8; width:140px;">Incident ID</td>
            <td style="padding:8px; color:#f4f4f4; font-family:monospace;">{inc_id}</td></tr>
        <tr style="background:#222;"><td style="padding:8px; color:#a8a8a8;">Evento</td>
            <td style="padding:8px; color:#f4f4f4;">{evento}</td></tr>
        <tr><td style="padding:8px; color:#a8a8a8;">Codigo de Erro</td>
            <td style="padding:8px; color:#f4f4f4; font-family:monospace;">{erro}</td></tr>
        <tr style="background:#222;"><td style="padding:8px; color:#a8a8a8;">Confianca IA</td>
            <td style="padding:8px; color:#f4f4f4;">{confianca}</td></tr>
      </table>

      <!-- causa raiz -->
      <h3 style="color:#a8a8a8; font-size:13px; text-transform:uppercase;
                 letter-spacing:1px; margin:0 0 8px;">Causa Raiz</h3>
      <p style="background:#222; padding:12px; border-radius:4px;
                font-size:13px; color:#e0e0e0; margin:0 0 20px; line-height:1.5;">
        {causa}
      </p>

      <!-- passos -->
      <h3 style="color:#a8a8a8; font-size:13px; text-transform:uppercase;
                 letter-spacing:1px; margin:0 0 8px;">Passos de Resolucao</h3>
      <ol style="background:#222; padding:12px 12px 12px 28px; border-radius:4px;
                 font-size:13px; color:#e0e0e0; margin:0 0 20px; line-height:1.8;">
        {passos_html}
      </ol>

      <!-- alerta hitl (se houver) -->
      {"" if not alerta else f'''
      <div style="background:#2d2000; border-left:4px solid #f39c12;
                  padding:12px 16px; border-radius:0 4px 4px 0; margin-bottom:20px;">
        <p style="margin:0; font-size:13px; color:#f39c12; font-weight:bold;">Alerta HITL</p>
        <p style="margin:4px 0 0; font-size:13px; color:#e0e0e0;">{alerta}</p>
      </div>'''}

      <!-- CTA -->
      <div style="text-align:center; margin-top:24px;">
        <a href="http://127.0.0.1:7860"
           style="background:#0f62fe; color:#fff; padding:12px 32px;
                  border-radius:4px; text-decoration:none; font-size:14px;
                  font-weight:bold; display:inline-block;">
          Abrir Dashboard EII
        </a>
      </div>

    </div>

    <!-- footer -->
    <div style="background:#161616; padding:12px 24px; border-top:1px solid #262626;">
      <p style="margin:0; font-size:11px; color:#525252;">
        EII — ERP Incident Intelligence &nbsp;|&nbsp;
        Este e-mail foi gerado automaticamente. Nao responda.
      </p>
    </div>

  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["EII_SMTP_USER"]
    msg["To"]      = cfg["EII_ALERT_EMAIL"]
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# SMTP send
# ─────────────────────────────────────────────────────────────────────────────

def _send_sync(cfg: dict, msg: MIMEMultipart) -> None:
    port = int(cfg["EII_SMTP_PORT"])
    host = cfg["EII_SMTP_HOST"]
    user = cfg["EII_SMTP_USER"]
    pwd  = cfg["EII_SMTP_PASS"]
    to   = [addr.strip() for addr in cfg["EII_ALERT_EMAIL"].split(",")]

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            server.login(user, pwd)
            server.sendmail(user, to, msg.as_bytes())
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, pwd)
            server.sendmail(user, to, msg.as_bytes())

    logger.info("notifier: alerta HITL enviado para %s", cfg["EII_ALERT_EMAIL"])


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_hitl_alert(incident: dict) -> None:
    """
    Envia e-mail de alerta HITL em background thread (nao bloqueia o pipeline).

    Args:
        incident: dict retornado por query_incident() — precisa de ao menos
                  incident_id, evento, codigo_erro, severidade.

    Se SMTP nao estiver configurado, loga aviso e retorna silenciosamente.
    """
    cfg = _smtp_config()
    if cfg is None:
        logger.debug("notifier: SMTP nao configurado — alerta HITL ignorado")
        return

    try:
        msg = _build_email(cfg, incident)
    except Exception as exc:
        logger.warning("notifier: falha ao montar e-mail: %s", exc)
        return

    def _worker():
        try:
            _send_sync(cfg, msg)
        except Exception as exc:
            logger.warning("notifier: falha ao enviar e-mail: %s", exc)

    t = threading.Thread(target=_worker, daemon=True, name="eii-notifier")
    t.start()
