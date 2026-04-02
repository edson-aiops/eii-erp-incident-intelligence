"""
EII — ERP Incident Intelligence
eSocial XML Diagnostic System with CRAG + Human-in-the-Loop
"""

import gradio as gr
import json
import os
import sqlite3
import threading
from datetime import datetime
from xml_parser import parse_esocial_xml, SAMPLE_XMLS
from crag_pipeline import build_vector_store, run_crag
from batch_processor import batch_analyze_streaming

# ─────────────────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────────────────

COLLECTION = build_vector_store()
_collection_lock = threading.RLock()   # guards concurrent access to COLLECTION

# ─────────────────────────────────────────────────────────────────────────────
# Persistence — SQLite
# DB_PATH: set to /data/eii_incidents.db in HuggingFace Spaces (persistent vol)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_DB = "eii_incidents.db"
_CONFIGURED_PATH = os.environ.get("DB_PATH", _DEFAULT_DB)

def _resolve_db_path() -> str:
    """Return a usable DB path, falling back to local if /data is not accessible."""
    path = _CONFIGURED_PATH
    if path.startswith("/data"):
        data_dir = os.path.dirname(path)
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError:
            return _DEFAULT_DB
    return path

DB_PATH = _resolve_db_path()


def _db_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _db_init() -> None:
    with _db_conn() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        con.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id             TEXT PRIMARY KEY,
                created_at     TEXT NOT NULL,
                diagnosis_json TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'PENDING',
                notes          TEXT,
                decided_at     TEXT
            )
        """)


_db_init()


def _db_save_pending(inc_id: str, diagnosis: dict, timestamp: str) -> None:
    with _db_conn() as con:
        con.execute(
            "INSERT INTO incidents (id, created_at, diagnosis_json, status) VALUES (?, ?, ?, 'PENDING')",
            (inc_id, timestamp, json.dumps(diagnosis, ensure_ascii=False)),
        )


def _db_fetch_pending(inc_id: str) -> dict | None:
    with _db_conn() as con:
        row = con.execute(
            "SELECT diagnosis_json FROM incidents WHERE id=? AND status='PENDING'",
            (inc_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def _db_decide(inc_id: str, status: str, notes: str) -> None:
    with _db_conn() as con:
        con.execute(
            "UPDATE incidents SET status=?, notes=?, decided_at=? WHERE id=?",
            (status, notes, datetime.now().isoformat(), inc_id),
        )


def _db_audit_log(limit: int = 20) -> list:
    with _db_conn() as con:
        rows = con.execute(
            "SELECT id, created_at, diagnosis_json, status, notes, decided_at "
            "FROM incidents WHERE status != 'PENDING' ORDER BY decided_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "diagnosis": json.loads(r[2]),
            "status":    r[3],
            "notes":     r[4] or "—",
            "decided_at": r[5] or "",
        }
        for r in rows
    ]


SEV = {
    "CRÍTICO": ("🔴", "#ff4444"),
    "ALTO":    ("🟠", "#ff8800"),
    "MÉDIO":   ("🟡", "#ffcc00"),
    "BAIXO":   ("🟢", "#44cc44"),
}
CONF = {"ALTA": "✅ ALTA", "MÉDIA": "⚠️ MÉDIA", "BAIXA": "❓ BAIXA"}


def new_incident_id() -> str:
    return f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

def load_sample(sample_name: str):
    return SAMPLE_XMLS.get(sample_name, "")


def analyze_xml(xml_input: str, mentor_mode: bool = False):
    """Parse XML → CRAG → return diagnosis markdown + hidden state."""
    if not xml_input or not xml_input.strip():
        return (
            render_placeholder(),
            "⚠️ Cole ou carregue um XML de retorno do eSocial.",
            "",
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )

    inc_id  = new_incident_id()
    parsed  = parse_esocial_xml(xml_input.strip())

    if parsed.erro:
        return (
            f"## ❌ Erro ao interpretar o XML\n\n```\n{parsed.erro}\n```\n\n"
            "Verifique se o XML é um retorno válido do webservice do eSocial.",
            "",
            "",
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
        )

    diagnosis = run_crag(COLLECTION, parsed, inc_id, mentor_mode=mentor_mode)

    _db_save_pending(inc_id, diagnosis, datetime.now().isoformat())

    diag_md  = render_diagnosis(diagnosis, parsed)
    parse_md = render_parsed_xml(parsed)

    return (
        diag_md,
        parse_md,
        inc_id,
        inc_id,
        gr.update(interactive=False),   # approve_btn: only enabled by HITL checklist
        gr.update(interactive=True),
    )


def approve_incident(inc_id: str, notes: str, analista_id: str = ""):
    return _decide(inc_id, notes, "APROVADO", analista_id)


def reject_incident(inc_id: str, notes: str, analista_id: str = ""):
    return _decide(inc_id, notes, "REJEITADO", analista_id)


def _decide(inc_id: str, notes: str, status: str, analista_id: str = ""):
    dx = _db_fetch_pending(inc_id) if inc_id else None
    if dx is None:
        return (
            "❌ ID não encontrado. Analise um XML primeiro na aba Diagnóstico.",
            render_audit_log(),
        )

    full_notes = (
        f"[analista: {analista_id}] {notes or '—'}" if analista_id else (notes or "—")
    )
    _db_decide(inc_id, status, full_notes)

    # Confidence-tier tracking: reward KB items that generated approved diagnoses
    if status == "APROVADO":
        kb_id = dx.get("fonte_kb_id", "")
        if kb_id:
            try:
                from qdrant_client import increment_validacao
                increment_validacao(kb_id)
            except Exception:
                pass  # non-critical — Qdrant may be unavailable in dev

    icon     = "✅" if status == "APROVADO" else "❌"
    sev_icon = SEV.get(dx.get("severidade", "MÉDIO"), ("⚪", "#888"))[0]

    result_md = f"""## {icon} Decisão Registrada

| Campo | Valor |
|---|---|
| **ID** | `{inc_id}` |
| **Status** | **{status}** |
| **Evento** | {dx.get('evento', '—')} |
| **Severidade** | {sev_icon} {dx.get('severidade', '—')} |
| **Confiança IA** | {CONF.get(dx.get('confianca', 'BAIXA'), '—')} |
| **Analista** | {analista_id or '*(não informado)*'} |
| **Registrado em** | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} |

**Notas do analista:** {full_notes}

---
*Resolução arquivada no log de auditoria.*
"""
    return result_md, render_audit_log()


def render_audit_log() -> str:
    entries = _db_audit_log(20)
    if not entries:
        return "*Nenhuma resolução registrada ainda.*"

    md = f"## 📋 Log de Auditoria — {len(entries)} registro(s) (últimos 20)\n\n"
    for entry in entries:
        dx      = entry["diagnosis"]
        status  = entry["status"]
        icon    = "✅" if status == "APROVADO" else "❌"
        sev_icon = SEV.get(dx.get("severidade", "MÉDIO"), ("⚪", "#888"))[0]
        meta    = dx.get("_meta", {})

        eval_verdict   = meta.get("eval_final_verdict", "")
        eval_iters     = meta.get("eval_iterations", "")
        eval_badge     = ""
        if eval_verdict == "APPROVED":
            superscript = f"<sup>{eval_iters}</sup>" if eval_iters else ""
            eval_badge  = f" &nbsp;|&nbsp; **Avaliação:** ✅ APROVADO{superscript}"
        elif eval_verdict:
            eval_badge  = f" &nbsp;|&nbsp; **Avaliação:** ⚠️ MAX_ITER ({eval_iters}x)"

        logprob_sim = meta.get('logprob_sim')
        psim_str = f" *(P(SIM) = {logprob_sim:.3f})*" if isinstance(logprob_sim, float) else f" *(P={meta.get('logprob_sim', '—')})*"
        eval_section = _render_eval_section(meta, compact=True)

        md += (
            f"### {icon} `{dx['incident_id']}` — {status}\n"
            f"**Evento:** {dx.get('evento', '—')} &nbsp;|&nbsp; "
            f"**Erro:** `{dx.get('codigo_erro', '—')}` &nbsp;|&nbsp; "
            f"**Severidade:** {sev_icon} {dx.get('severidade', '—')}\n\n"
            f"**Confiança:** {CONF.get(dx.get('confianca','BAIXA'),'—')}"
            f"{psim_str}{eval_badge} &nbsp;|&nbsp; "
            f"**Fonte:** `{dx.get('fonte','—')}` &nbsp;|&nbsp; "
            f"**Docs KB:** {meta.get('candidates_relevant', 0)}/{meta.get('candidates_retrieved', 0)}\n\n"
            f"**Causa:** {dx.get('causa_raiz', '—')[:200]}...\n\n"
            f"{eval_section}\n"
            f"**Notas analista:** {entry.get('notes', '—')}\n\n"
            f"*Registrado: {entry.get('decided_at', '')[:16].replace('T', ' ')}*\n\n---\n\n"
        )
    return md


def render_parsed_xml(parsed) -> str:
    oc_lines = "\n".join([
        f"  - `[{o.tipo}]` **{o.codigo}** — {o.descricao}"
        + (f"\n    *Local:* `{o.localizacao}`" if o.localizacao else "")
        for o in parsed.ocorrencias
    ]) or "  *(nenhuma ocorrência extraída)*"

    return f"""### 📄 XML Interpretado

| Campo | Valor |
|---|---|
| **Formato detectado** | `{parsed.formato}` |
| **Tipo de evento** | `{parsed.tipo_evento or '—'}` |
| **cdResposta** | `{parsed.cd_resposta}` |
| **Descrição governo** | {parsed.desc_resposta or '—'} |
| **CNPJ Empregador** | `{parsed.nr_inscricao or '—'}` |
| **Nr Recibo** | `{parsed.nr_recibo or '—'}` |
| **Ocorrências** | {len(parsed.ocorrencias)} |

**Ocorrências detalhadas:**
{oc_lines}
"""


def _render_eval_section(meta: dict, compact: bool = False) -> str:
    """Renders the EvaluatorAgent quality assessment section."""
    verdict    = meta.get("eval_final_verdict", "")
    iterations = meta.get("eval_iterations", 0)
    passed     = meta.get("eval_criteria_passed", [])
    failed     = meta.get("eval_criteria_failed", [])
    critique   = meta.get("eval_critique_last", "")

    if not verdict:
        return ""   # old records without eval data — render nothing

    total      = len(passed) + len(failed)
    n_approved = len(passed)
    verdict_badge = "✅ APROVADO" if verdict == "APPROVED" else "⚠️ NÃO APROVADO"
    iter_note = f"Gerado em {iterations} tentativa(s)"

    _LABELS = {
        "causal_coherence":        "Coerência causal",
        "resolution_actionability": "Acionabilidade dos passos",
        "kb_grounding":            "Aderência à KB",
        "schema_completeness":     "Completude do schema",
        "severity_calibration":    "Calibração de severidade",
    }

    criteria_rows = "\n".join(
        f"| {_LABELS.get(c, c)} | ✅ PASS |" for c in passed
    ) + "\n" + "\n".join(
        f"| {_LABELS.get(c, c)} | ❌ FAIL |" for c in failed
    )

    criteria_badge = (
        f"**`{n_approved}/{total} critérios aprovados`** &nbsp; {verdict_badge}"
    )

    critique_block = (
        f"\n> **Crítica do avaliador:** {critique}\n"
        if verdict != "APPROVED" and critique else ""
    )

    if compact:
        return (
            f"\n*{criteria_badge} — {iter_note}*\n\n"
            f"| Critério | Resultado |\n|---|---|\n{criteria_rows}\n"
            f"{critique_block}"
        )

    return f"""
---

### 🤖 Avaliação Automática de Qualidade

{criteria_badge}

*{iter_note}*

| Critério | Resultado |
|---|---|
{criteria_rows}
{critique_block}"""


def render_diagnosis(dx: dict, parsed) -> str:
    sev   = dx.get("severidade", "MÉDIO")
    conf  = dx.get("confianca", "BAIXA")
    fonte = dx.get("fonte", "—")
    meta  = dx.get("_meta", {})
    sev_icon = SEV.get(sev, ("⚪", "#888"))[0]

    steps = "\n".join([
        f"{i}. {s}" for i, s in enumerate(dx.get("passos_resolucao", []), 1)
    ])

    refs = ", ".join(dx.get("referencias_kb", [])) or "—"
    hitl_alert = dx.get("alerta_hitl", "Revisar antes de executar.")

    logprob_sim = meta.get("logprob_sim")
    psim_display = f"&nbsp; *(P(SIM) = {logprob_sim:.3f})*" if isinstance(logprob_sim, float) else ""

    return f"""## {sev_icon} Diagnóstico — `{dx.get('incident_id', '—')}`

| | |
|---|---|
| **Evento** | `{dx.get('evento', '—')}` |
| **Código de Erro** | `{dx.get('codigo_erro', '—')}` |
| **Severidade** | {sev_icon} **{sev}** |
| **Confiança IA** | {CONF.get(conf, conf)}{psim_display} |
| **Fonte do diagnóstico** | `{fonte}` |
| **Docs KB consultados** | {meta.get('candidates_relevant', 0)} relevantes / {meta.get('candidates_retrieved', 0)} recuperados |
| **Tempo estimado** | {dx.get('tempo_estimado', '—')} |
| **Referências KB** | {refs} |

---

### 🔍 Causa Raiz Provável
{dx.get('causa_raiz', '—')}
{_render_eval_section(meta)}

---

### 📋 Passos de Resolução Propostos
{steps}

---

### ✅ Como Validar a Resolução
{dx.get('validacao', '—')}

---

### ⚠️ Alerta Human-in-the-Loop
> {hitl_alert}

**Acesse a aba ✋ Aprovação para registrar sua decisão antes de executar qualquer ação.**

---
*EII CRAG Pipeline — {datetime.now().strftime('%d/%m/%Y %H:%M')} — eSocial KB v1.0 | KB hash: {dx.get('versao_kb', '')[:8] or '—'}*
"""


def run_batch(xml_text, max_workers):
    """Generator: yields (log_str, dataframe_rows) as each XML completes."""
    if not xml_text or not xml_text.strip():
        yield "⚠️ Nenhum XML colado.", []
        return

    # Split on blank lines — each block is one XML document
    blocks = [b.strip() for b in xml_text.split("\n\n") if b.strip()]
    xml_list = [b for b in blocks if b.startswith("<")]

    if not xml_list:
        yield "⚠️ Nenhum XML encontrado. Separe os XMLs com uma linha em branco.", []
        return

    n = len(xml_list)
    workers = max(1, min(5, int(max_workers)))
    log_lines = [f"📦 {n} XML(s) identificados | Workers: {workers} | Iniciando...\n"]
    yield "\n".join(log_lines), []

    rows: list[list] = []
    for done, partial in batch_analyze_streaming(xml_list, max_workers=workers,
                                                 collection=COLLECTION):
        # partial has None for items not yet complete — find the one just finished
        completed_items = [r for r in partial if r is not None]
        last = completed_items[-1] if completed_items else {}
        icon = "✅" if last.get("status") == "OK" else "❌"
        log_lines.append(
            f"  {icon} [{done}/{n}] {last.get('incident_id','—')} "
            f"— {last.get('codigo_erro','—')} "
            f"— sev={last.get('severidade','—')} "
            f"— {last.get('status','—')}"
        )
        rows = [
            [
                r["incident_id"], r["evento"], r["codigo_erro"],
                r["severidade"], r["confianca"], r["fonte"],
                r["status"], r["elapsed_s"],
            ]
            for r in completed_items
        ]
        yield "\n".join(log_lines), rows

    ok  = sum(1 for r in rows if r[6] == "OK")
    err = n - ok
    log_lines.append(
        f"\n✅ Lote concluído — {ok} OK · {err} ERROR · total {n} XMLs"
    )
    yield "\n".join(log_lines), rows


def _update_approve_btn(chk1: bool, chk2: bool, chk3: bool):
    """Enable approve button only when all 3 HITL checkboxes are checked."""
    return gr.update(interactive=bool(chk1 and chk2 and chk3))


def render_placeholder() -> str:
    return """## ⚙️ EII — Aguardando XML

**Como usar:**
1. Cole o XML de retorno do eSocial na caixa à esquerda, **ou**
2. Selecione um exemplo no menu abaixo e clique **Carregar Exemplo**
3. Clique **🔍 Analisar XML**
4. Revise o diagnóstico e acesse a aba **✋ Aprovação** para registrar sua decisão

---
*O EII analisa XMLs de retorno do webservice do eSocial — formatos de lote (retornoEnvioLoteEventos), processamento individual e retorno de evento.*
"""


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

* { box-sizing: border-box; }

body, .gradio-container {
    font-family: 'IBM Plex Sans', sans-serif !important;
    background: #F5F7FA !important;
    color: #1A1A2E !important;
}

.gradio-container { max-width: 1280px !important; margin: 0 auto !important; }

/* Header */
.eii-header {
    background: #FFFFFF;
    border: 1px solid #D1E7DD;
    border-left: 4px solid #1D9E75;
    border-radius: 8px;
    padding: 24px 32px;
    margin-bottom: 16px;
}
.eii-header h1 {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.6rem !important;
    font-weight: 600 !important;
    color: #1A1A2E !important;
    margin: 0 0 6px !important;
    letter-spacing: -0.5px;
}
.eii-header p {
    color: #6B7280 !important;
    font-size: 0.88rem !important;
    margin: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
.badge {
    display: inline-block;
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    color: #065F46;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-left: 8px;
    letter-spacing: 0.5px;
}
.badge.green { color: #065F46; border-color: #6EE7B7; background: #D1FAE5; }
.badge.amber { color: #854F0B; border-color: #FCD34D; background: #FFFBEB; }
.badge.red   { color: #A32D2D; border-color: #FECACA; background: #FEF2F2; }

/* Tabs */
.tab-nav { background: #FFFFFF !important; border-bottom: 1px solid #E5E7EB !important; }
.tab-nav button {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.85rem !important;
    color: #6B7280 !important;
    border: none !important;
    background: transparent !important;
    padding: 10px 20px !important;
    font-weight: 400 !important;
}
.tab-nav button.selected {
    color: #1D9E75 !important;
    border-bottom: 2px solid #1D9E75 !important;
    font-weight: 600 !important;
}

/* Inputs */
textarea, input[type="text"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    background: #FFFFFF !important;
    border: 1px solid #D1D5DB !important;
    color: #1A1A2E !important;
    border-radius: 6px !important;
}
textarea:focus, input:focus {
    border-color: #1D9E75 !important;
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(29, 158, 117, 0.12) !important;
}

/* Buttons */
.btn-primary button {
    background: #1D9E75 !important;
    color: #FFFFFF !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 10px 24px !important;
    letter-spacing: 0.3px !important;
    transition: all 0.15s ease !important;
}
.btn-primary button:hover { background: #17866200 !important; }

.btn-approve button {
    background: #1D9E75 !important;
    color: #FFFFFF !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 6px !important;
}
.btn-approve button:hover { background: #178662 !important; }

.btn-reject button {
    background: #FFFFFF !important;
    color: #A32D2D !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    border: 1px solid #A32D2D !important;
    border-radius: 6px !important;
}
.btn-reject button:hover { background: #FEF2F2 !important; }

/* Dropdowns */
.gr-dropdown select, select {
    background: #FFFFFF !important;
    border: 1px solid #D1D5DB !important;
    color: #1A1A2E !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
    border-radius: 6px !important;
}

/* Markdown output */
.markdown-body, .gr-markdown {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    padding: 20px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    color: #1A1A2E !important;
    min-height: 200px;
}
.markdown-body h2 {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #1A1A2E !important;
    border-bottom: 1px solid #E5E7EB !important;
    padding-bottom: 8px !important;
    font-size: 1.1rem !important;
}
.markdown-body h3 {
    color: #1D9E75 !important;
    font-size: 0.95rem !important;
    font-family: 'IBM Plex Mono', monospace !important;
    margin-top: 16px !important;
}
.markdown-body table {
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 0.85rem !important;
}
.markdown-body th {
    background: #F9FAFB !important;
    color: #6B7280 !important;
    padding: 8px 12px !important;
    text-align: left !important;
    font-weight: 600 !important;
    border-bottom: 1px solid #E5E7EB !important;
}
.markdown-body td {
    padding: 8px 12px !important;
    border-bottom: 1px solid #F3F4F6 !important;
}
.markdown-body code {
    background: #F3F4F6 !important;
    color: #1D9E75 !important;
    padding: 2px 6px !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.83em !important;
}
.markdown-body blockquote {
    border-left: 3px solid #1D9E75 !important;
    padding-left: 12px !important;
    color: #6B7280 !important;
    margin: 12px 0 !important;
    background: #F0FDF9 !important;
    border-radius: 0 4px 4px 0 !important;
}
.markdown-body ol li, .markdown-body ul li {
    margin: 6px 0 !important;
    line-height: 1.6 !important;
}

/* Labels */
label span {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: #6B7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

/* Panel backgrounds */
.gr-panel, .gr-box { background: #FFFFFF !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F5F7FA; }
::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #1D9E75; }

/* Separator */
hr { border-color: #E5E7EB !important; }

/* Footer kill */
footer { display: none !important; }
"""

# ── Build UI ──────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="EII — ERP Incident Intelligence",
    css=CSS,
    theme=gr.themes.Base(
        primary_hue="orange",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("IBM Plex Sans"), "sans-serif"],
    ),
) as demo:

    # ── Header ───────────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="eii-header">
      <h1>⚙️ EII &mdash; ERP Incident Intelligence</h1>
      <p>
        Diagnóstico de falhas de integração com o governo &nbsp;·&nbsp;
        eSocial / Webservice RFB
        <span class="badge">CRAG Pipeline</span>
        <span class="badge green">Human-in-the-Loop</span>
      </p>
    </div>
    """)

    # ── Hidden state ─────────────────────────────────────────────────────────
    current_inc_id = gr.State("")

    with gr.Tabs():

        # ── TAB 1: DIAGNÓSTICO ────────────────────────────────────────────────
        with gr.Tab("🚨 Diagnóstico"):
            with gr.Row(equal_height=False):

                # Left column — input
                with gr.Column(scale=1, min_width=360):
                    gr.Markdown(
                        "### XML de Retorno eSocial\n"
                        "*Cole o XML recebido do webservice do governo*",
                    )
                    xml_box = gr.Textbox(
                        label="XML (retornoEnvioLoteEventos · retornoProcessamentoEvento · retornoEvento)",
                        placeholder='<?xml version="1.0" encoding="UTF-8"?>\n<eSocial>...',
                        lines=18,
                        max_lines=30,
                        show_copy_button=True,
                    )

                    with gr.Row():
                        sample_dd = gr.Dropdown(
                            label="Exemplos de XML",
                            choices=list(SAMPLE_XMLS.keys()),
                            value=None,
                            interactive=True,
                        )
                        load_btn = gr.Button("📂 Carregar", size="sm")

                    mentor_mode_cb = gr.Checkbox(
                        label="Modo Aprendiz",
                        value=False,
                        info="Entenda o porquê antes de decidir",
                    )

                    analyze_btn = gr.Button(
                        "🔍 Analisar XML",
                        variant="primary",
                        size="lg",
                        elem_classes=["btn-primary"],
                    )

                # Right column — output
                with gr.Column(scale=2):
                    diagnosis_md = gr.Markdown(render_placeholder())

                    with gr.Accordion("📄 Detalhes do XML Interpretado", open=True):
                        parsed_md = gr.Markdown("*Analise um XML para ver os detalhes.*")

            inc_id_display = gr.Textbox(
                label="ID do Incidente (use na aba Aprovação)",
                interactive=False,
                show_copy_button=True,
            )

        # ── TAB 2: APROVAÇÃO HITL ─────────────────────────────────────────────
        with gr.Tab("✋ Aprovação — Human-in-the-Loop"):
            gr.HTML("""
            <div style="
                background:#FFFBEB;border:1px solid #FCD34D;border-left:3px solid #854F0B;
                border-radius:8px;padding:16px 20px;margin-bottom:16px;
            ">
              <strong style="color:#854F0B;font-family:'IBM Plex Mono',monospace;">
                ⚠️ Revisão Humana Obrigatória
              </strong>
              <p style="color:#6B7280;margin:8px 0 0;font-size:0.85rem;line-height:1.6;">
                O EII gera diagnósticos baseados em IA e histórico de incidentes.<br>
                <strong style="color:#1A1A2E;">Toda resolução deve ser revisada por um analista antes de ser executada.</strong><br>
                Nenhuma ação é registrada como aprovada sem decisão explícita nesta tela.
              </p>
            </div>
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    hitl_inc_id = gr.Textbox(
                        label="ID do Incidente",
                        placeholder="INC-20250307-143022  (copiado da aba Diagnóstico)",
                    )
                    hitl_notes = gr.Textbox(
                        label="Notas do Analista",
                        placeholder=(
                            "Descreva sua análise:\n"
                            "- O diagnóstico da IA estava correto?\n"
                            "- Quais ajustes foram necessários?\n"
                            "- Ações executadas ou motivo da rejeição..."
                        ),
                        lines=5,
                    )
                    hitl_analista_id = gr.Textbox(
                        label="Analista ID",
                        placeholder="seu.nome@empresa.com",
                        lines=1,
                    )
                    chk_periodo = gr.Checkbox(
                        label="☑ Verifiquei o período de apuração",
                        value=False,
                    )
                    chk_vinculo = gr.Checkbox(
                        label="☑ Confirmei o vínculo do trabalhador",
                        value=False,
                    )
                    chk_legislacao = gr.Checkbox(
                        label="☑ Validei conforme legislação vigente",
                        value=False,
                    )
                    hitl_justificativa = gr.Textbox(
                        label="Justificativa (opcional)",
                        lines=2,
                    )
                    with gr.Row():
                        approve_btn = gr.Button(
                            "✅ Aprovar e Registrar",
                            variant="primary",
                            interactive=False,
                            elem_classes=["btn-approve"],
                        )
                        reject_btn = gr.Button(
                            "❌ Rejeitar e Escalar",
                            elem_classes=["btn-reject"],
                        )

                with gr.Column(scale=1):
                    decision_md = gr.Markdown("*Aguardando decisão do analista...*")

        # ── TAB 3: LOG DE AUDITORIA ───────────────────────────────────────────
        with gr.Tab("📋 Log de Auditoria"):
            refresh_btn = gr.Button("🔄 Atualizar Log", size="sm")
            audit_md = gr.Markdown("*Nenhuma resolução registrada ainda.*")

        # ── TAB 4: LOTE ───────────────────────────────────────────────────────
        with gr.Tab("📦 Lote"):
            gr.Markdown(
                "### Processamento em Lote\n"
                "*Analise múltiplos XMLs em paralelo. "
                "Cole os XMLs na caixa abaixo, separando cada um com uma linha em branco.*"
            )
            with gr.Row(equal_height=False):
                with gr.Column(scale=1, min_width=300):
                    batch_files = gr.Textbox(
                        label="XMLs para análise (cole um ou mais, separados por linha em branco)",
                        lines=10,
                        placeholder="<?xml version=\"1.0\"?>\n<eSocial>...</eSocial>\n\n<?xml version=\"1.0\"?>\n<eSocial>...</eSocial>",
                    )
                    batch_workers = gr.Slider(
                        minimum=1, maximum=5, value=3, step=1,
                        label="Workers paralelos",
                        interactive=True,
                    )
                    batch_btn = gr.Button(
                        "📦 Processar Lote",
                        variant="primary",
                        size="lg",
                        elem_classes=["btn-primary"],
                    )
                with gr.Column(scale=2):
                    batch_log = gr.Textbox(
                        label="Log de progresso",
                        lines=10,
                        interactive=False,
                        show_copy_button=True,
                    )
            batch_df = gr.Dataframe(
                headers=["ID", "Evento", "Código", "Severidade",
                         "Confiança", "Fonte", "Status", "Tempo(s)"],
                datatype=["str", "str", "str", "str", "str", "str", "str", "number"],
                label="Resultados do Lote",
                wrap=True,
            )

        # ── TAB 5: ARQUITETURA ────────────────────────────────────────────────
        with gr.Tab("🏗️ Arquitetura"):
            gr.Markdown("""
## EII — Arquitetura

### Pipeline CRAG

```
XML Upload (retorno webservice eSocial)
         │
    [xml_parser.py]
    Detecta formato · Extrai evento · Extrai ocorrências
         │
    [crag_pipeline.py — Step 1: Retrieve]
    ChromaDB query → Top-5 documentos KB
         │
    [crag_pipeline.py — Step 2: Grade]
    LLM avalia relevância de cada doc → filtra irrelevantes
         │
    [crag_pipeline.py — Step 3: Generate]
    LLM gera diagnóstico JSON com contexto filtrado
         │
    [PENDING queue] ← incidente retido aqui
         │
    [Human-in-the-Loop] ✋
    Analista revisa · Aprova ou Rejeita
         │
    [Audit Log] — registro imutável com notas
```

### Formatos XML Suportados

| Formato | Tag raiz | Descrição |
|---|---|---|
| `lote` | `retornoEnvioLoteEventos` | Resposta de transmissão em lote |
| `processamento` | `retornoProcessamentoEvento` | Retorno de processamento individual |
| `evento` | `retornoEvento` | Retorno simples de evento |
| `generico` | *qualquer* | Fallback com extração parcial |

### Base de Conhecimento — eSocial
20 incidentes documentados cobrindo:

- **Retificação:** E428, E430 (indRetif, nrRecEvt, S-3000)
- **Certificado/Assinatura:** E214, E215 (A1/A3, transmissor, procuração)
- **Vínculo:** E312, E422, E469, E460 (S-2200, S-2206, S-2299)
- **Remuneração:** E301, E320, E450 (S-1200, S-1210, S-1299)
- **Afastamento:** E350, E351 (S-2230 sobreposição, data)
- **Transmissão:** E200, E403, E500 (ambiente, leiaute, timeout, lote)
- **Tabelas:** E100, E601 (S-1000 duplicata, S-1070 data)
- **CAT:** E380 (S-2210 CID)

### Stack Técnica

| Componente | Tecnologia |
|---|---|
| LLM | Llama 3.3 70B (Groq API) |
| Vector Store | ChromaDB in-memory |
| Embeddings | sentence-transformers (all-MiniLM) |
| UI | Gradio 4.x |
| Deploy | HuggingFace Spaces (Docker) |

### Princípio de Design — Human-in-the-Loop

> Nenhuma resolução é registrada sem aprovação explícita de um analista humano.
> Isso garante rastreabilidade, conformidade e controle sobre ações de alto impacto em compliance.

Em contextos de eSocial e EFD-Reinf, erros executados automaticamente podem causar:
autuações fiscais, inconsistências no CNIS do trabalhador, e passivos trabalhistas.
O HITL é uma decisão de design — não uma limitação técnica.

---
*EII v1.0 · eSocial Brasil · Desenvolvido por Edson*
""")

    # ── Wiring ───────────────────────────────────────────────────────────────

    load_btn.click(
        fn=load_sample,
        inputs=[sample_dd],
        outputs=[xml_box],
    )

    analyze_btn.click(
        fn=analyze_xml,
        inputs=[xml_box, mentor_mode_cb],
        outputs=[diagnosis_md, parsed_md, inc_id_display, hitl_inc_id,
                 approve_btn, reject_btn],
    )

    for _chk in (chk_periodo, chk_vinculo, chk_legislacao):
        _chk.change(
            fn=_update_approve_btn,
            inputs=[chk_periodo, chk_vinculo, chk_legislacao],
            outputs=[approve_btn],
        )

    approve_btn.click(
        fn=approve_incident,
        inputs=[hitl_inc_id, hitl_justificativa, hitl_analista_id],
        outputs=[decision_md, audit_md],
    )

    reject_btn.click(
        fn=reject_incident,
        inputs=[hitl_inc_id, hitl_notes, hitl_analista_id],
        outputs=[decision_md, audit_md],
    )

    refresh_btn.click(fn=render_audit_log, outputs=[audit_md])

    batch_btn.click(
        fn=run_batch,
        inputs=[batch_files, batch_workers],
        outputs=[batch_log, batch_df],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
