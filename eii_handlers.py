"""
EII Handlers — pure Python, no Gradio dependency.

Extracted logic for query_incident() and escalate_incident(),
suitable for MCP, REST, or any headless consumer.

DB layer mirrors app.py exactly (same DB_PATH env var, same schema)
so both share the same SQLite file without conflict.
"""

import json
import os
import sqlite3
from datetime import datetime

from xml_parser import parse_esocial_xml
from crag_pipeline import build_vector_store, run_crag

# ── DB — mirrors app.py (same env var, same schema) ──────────────────────────

_DEFAULT_DB = "eii_incidents.db"
_CONFIGURED_PATH = os.environ.get("DB_PATH", _DEFAULT_DB)


def _resolve_db_path() -> str:
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
    return sqlite3.connect(DB_PATH)


def _db_init() -> None:
    with _db_conn() as con:
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


# ── Collection (lazy init — avoids loading ChromaDB at import time) ───────────

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = build_vector_store()
    return _collection


def _new_incident_id() -> str:
    return f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


# ── Public handlers ───────────────────────────────────────────────────────────

_VALID_STATUSES = {"APROVADO", "REJEITADO"}


def query_incident(xml_input: str) -> dict:
    """
    Parse an eSocial XML return and run the CRAG diagnostic pipeline.

    Persists the result as PENDING in SQLite (awaiting analyst review via
    escalate_incident). Returns a subset of the diagnosis dict suitable for
    display or further processing.

    Args:
        xml_input: Raw eSocial XML string (retornoEnvioLoteEventos,
                   retornoProcessamentoEvento, or retornoEvento format).

    Returns:
        dict with keys: incident_id, evento, codigo_erro, severidade,
        confianca, fonte, causa_raiz, passos_resolucao, alerta_hitl, _meta.

    Raises:
        ValueError: If xml_input is empty or XML cannot be parsed.
    """
    if not xml_input or not xml_input.strip():
        raise ValueError("xml_input is empty")

    inc_id = _new_incident_id()
    parsed = parse_esocial_xml(xml_input.strip())

    if parsed.erro:
        raise ValueError(f"XML parse error: {parsed.erro}")

    diagnosis = run_crag(_get_collection(), parsed, inc_id)
    _db_save_pending(inc_id, diagnosis, datetime.now().isoformat())

    return {
        "incident_id":      diagnosis.get("incident_id", inc_id),
        "evento":           diagnosis.get("evento", "—"),
        "codigo_erro":      diagnosis.get("codigo_erro", "—"),
        "severidade":       diagnosis.get("severidade", "—"),
        "confianca":        diagnosis.get("confianca", "—"),
        "fonte":            diagnosis.get("fonte", "—"),
        "causa_raiz":       diagnosis.get("causa_raiz", "—"),
        "passos_resolucao": diagnosis.get("passos_resolucao", []),
        "alerta_hitl":      diagnosis.get("alerta_hitl", "—"),
        "_meta":            diagnosis.get("_meta", {}),
    }


def escalate_incident(incident_id: str, status: str, notes: str = "") -> dict:
    """
    Record an analyst decision for a PENDING incident (Human-in-the-Loop).

    Args:
        incident_id: Incident ID from query_incident (e.g., INC-20250307-143022).
        status:      "APROVADO" or "REJEITADO".
        notes:       Analyst notes (optional but recommended for audit trail).

    Returns:
        dict with keys: incident_id, status, decided_at, message.

    Raises:
        ValueError:   If status is not "APROVADO" or "REJEITADO".
        LookupError:  If incident_id not found or already decided.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"status must be 'APROVADO' or 'REJEITADO', got: {status!r}"
        )

    dx = _db_fetch_pending(incident_id) if incident_id else None
    if dx is None:
        raise LookupError(
            f"Incident {incident_id!r} not found or already decided"
        )

    _db_decide(incident_id, status, notes or "—")
    decided_at = datetime.now().isoformat()

    return {
        "incident_id": incident_id,
        "status":      status,
        "decided_at":  decided_at,
        "message":     f"Incident {incident_id} marked as {status}.",
    }
