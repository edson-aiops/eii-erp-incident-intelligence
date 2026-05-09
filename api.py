"""
EII — REST API v1
Expoe EII como servico HTTP para integracao com sistemas ERP/HCM.

Rodar (separado do Gradio):
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload

Configurar API key (uma vez):
    python -c "import keyring; keyring.set_password('EII_Project', 'EII_API_KEY', 'sua-chave-segura')"

Endpoints:
    GET  /health
    POST /v1/diagnose
    GET  /v1/incidents
    GET  /v1/incidents/{incident_id}
    POST /v1/incidents/{incident_id}/approve
    POST /v1/incidents/{incident_id}/reject
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, field_validator

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# API Key auth
# ─────────────────────────────────────────────────────────────────────────────

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_expected_key() -> Optional[str]:
    """Lê EII_API_KEY: keyring → os.environ."""
    try:
        import keyring
        val = keyring.get_password("EII_Project", "EII_API_KEY")
        if val:
            return val
    except Exception:
        pass
    return os.environ.get("EII_API_KEY")


async def require_api_key(api_key: str = Security(_API_KEY_HEADER)) -> str:
    expected = _get_expected_key()
    if not expected:
        raise HTTPException(status_code=500, detail="EII_API_KEY not configured on server.")
    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")
    return api_key


# ─────────────────────────────────────────────────────────────────────────────
# SQLite helpers (lista de incidentes — eii_handlers nao expoe isso)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_DB = "eii_incidents.db"


def _db_path() -> str:
    path = os.environ.get("DB_PATH", _DEFAULT_DB)
    if path.startswith("/data"):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError:
            return _DEFAULT_DB
    return path


def _db_conn() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.execute("PRAGMA busy_timeout=5000")
    con.row_factory = sqlite3.Row
    return con


def _parse_diag(diag_json: str) -> dict:
    try:
        return json.loads(diag_json)
    except Exception:
        return {}


def _row_to_summary(row: sqlite3.Row) -> dict:
    diag = _parse_diag(row["diagnosis_json"])
    return {
        "incident_id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "decided_at": row["decided_at"],
        "evento": diag.get("evento", ""),
        "codigo_erro": diag.get("codigo_erro", ""),
        "severidade": diag.get("severidade", ""),
        "confianca": diag.get("confianca", ""),
    }


def _db_list_incidents(
    status: Optional[str],
    page: int,
    page_size: int,
) -> tuple[int, list[dict]]:
    filters = []
    params: list = []
    if status:
        filters.append("status = ?")
        params.append(status.upper())

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    offset = (page - 1) * page_size

    with _db_conn() as con:
        total = con.execute(f"SELECT COUNT(*) FROM incidents {where}", params).fetchone()[0]
        rows = con.execute(
            f"SELECT id, created_at, diagnosis_json, status, decided_at "
            f"FROM incidents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return total, [_row_to_summary(r) for r in rows]


def _db_get_incident(incident_id: str) -> Optional[dict]:
    with _db_conn() as con:
        row = con.execute(
            "SELECT id, created_at, diagnosis_json, status, notes, decided_at "
            "FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
    if not row:
        return None
    diag = _parse_diag(row["diagnosis_json"])
    return {
        "incident_id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "notes": row["notes"],
        "decided_at": row["decided_at"],
        "diagnosis": diag,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class DiagnoseRequest(BaseModel):
    xml: str
    erp_reference: Optional[str] = None  # ID do ticket no ERP — devolvido no response para correlacao

    @field_validator("xml")
    @classmethod
    def xml_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("xml must not be empty")
        return v.strip()


class DiagnoseResponse(BaseModel):
    incident_id: str
    erp_reference: Optional[str]   # espelhado do request para correlacao no ERP
    evento: str
    codigo_erro: str
    severidade: str
    confianca: str
    causa_raiz: str
    passos_resolucao: list[str]
    validacao: str
    alerta_hitl: str
    status: str
    created_at: str


class DecideRequest(BaseModel):
    notes: str = ""


class DecideResponse(BaseModel):
    incident_id: str
    status: str
    decided_at: str
    message: str


class IncidentSummary(BaseModel):
    incident_id: str
    created_at: str
    status: str
    decided_at: Optional[str]
    evento: str
    codigo_erro: str
    severidade: str
    confianca: str


class IncidentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    incidents: list[IncidentSummary]


class IncidentDetailResponse(BaseModel):
    incident_id: str
    created_at: str
    status: str
    notes: Optional[str]
    decided_at: Optional[str]
    diagnosis: dict


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    db_reachable: bool


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EII — ERP Incident Intelligence API",
    description=(
        "REST API para integracao com sistemas ERP/HCM. "
        "Diagnostica incidentes eSocial via pipeline CRAG e expoe HITL para aprovacao."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Sistema"])
def health():
    """Verifica disponibilidade da API e do banco de dados."""
    db_ok = False
    try:
        with _db_conn() as con:
            con.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
        db_reachable=db_ok,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /v1/diagnose
# ─────────────────────────────────────────────────────────────────────────────

def _traced_diagnose(xml: str, erp_reference: Optional[str]) -> dict:
    """Wrapper para tracing LangSmith do endpoint diagnose."""
    from eii_handlers import query_incident
    return query_incident(xml)


try:
    from observability import traceable as _obs_traceable
    _traced_diagnose = _obs_traceable(
        name="EII.API.diagnose",
        run_type="chain",
        metadata={"component": "rest_api", "version": "v1"},
    )(_traced_diagnose)
except Exception:
    pass


@app.post(
    "/v1/diagnose",
    response_model=DiagnoseResponse,
    status_code=201,
    tags=["Diagnóstico"],
    dependencies=[Depends(require_api_key)],
)
def diagnose(body: DiagnoseRequest):
    """
    Analisa um XML eSocial e retorna o diagnóstico estruturado.

    O incidente é persistido com status PENDING aguardando aprovacao HITL.
    Use os endpoints /approve ou /reject para fechar o ciclo.
    """
    try:
        result = _traced_diagnose(body.xml, body.erp_reference)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("diagnose error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {type(e).__name__}")

    return DiagnoseResponse(
        incident_id=result.get("incident_id", ""),
        erp_reference=body.erp_reference,
        evento=result.get("evento", ""),
        codigo_erro=result.get("codigo_erro", ""),
        severidade=result.get("severidade", ""),
        confianca=result.get("confianca", ""),
        causa_raiz=result.get("causa_raiz", ""),
        passos_resolucao=result.get("passos_resolucao", []),
        validacao=result.get("validacao", ""),
        alerta_hitl=result.get("alerta_hitl", ""),
        status="PENDING",
        created_at=datetime.utcnow().isoformat() + "Z",
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /v1/incidents
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/v1/incidents",
    response_model=IncidentListResponse,
    tags=["Incidentes"],
    dependencies=[Depends(require_api_key)],
)
def list_incidents(
    status: Optional[str] = Query(None, description="Filtrar por status: PENDING, APPROVED, REJECTED"),
    page: int = Query(1, ge=1, description="Página (começa em 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página (max 100)"),
):
    """Lista incidentes com paginação e filtro opcional por status."""
    total, incidents = _db_list_incidents(status, page, page_size)
    return IncidentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        incidents=[IncidentSummary(**i) for i in incidents],
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /v1/incidents/{incident_id}
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/v1/incidents/{incident_id}",
    response_model=IncidentDetailResponse,
    tags=["Incidentes"],
    dependencies=[Depends(require_api_key)],
)
def get_incident(incident_id: str):
    """Retorna o diagnóstico completo e status de um incidente."""
    row = _db_get_incident(incident_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return IncidentDetailResponse(**row)


# ─────────────────────────────────────────────────────────────────────────────
# POST /v1/incidents/{incident_id}/approve
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/v1/incidents/{incident_id}/approve",
    response_model=DecideResponse,
    tags=["HITL"],
    dependencies=[Depends(require_api_key)],
)
def approve_incident(incident_id: str, body: DecideRequest):
    """Aprova um incidente PENDING (decisão HITL via ERP)."""
    try:
        from eii_handlers import escalate_incident
        result = escalate_incident(incident_id, "APROVADO", body.notes)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("approve error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {type(e).__name__}")

    return DecideResponse(**result)


# ─────────────────────────────────────────────────────────────────────────────
# POST /v1/incidents/{incident_id}/reject
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/v1/incidents/{incident_id}/reject",
    response_model=DecideResponse,
    tags=["HITL"],
    dependencies=[Depends(require_api_key)],
)
def reject_incident(incident_id: str, body: DecideRequest):
    """Rejeita um incidente PENDING com notas do analista."""
    try:
        from eii_handlers import escalate_incident
        result = escalate_incident(incident_id, "REJEITADO", body.notes)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("reject error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {type(e).__name__}")

    return DecideResponse(**result)
