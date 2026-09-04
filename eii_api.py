"""
EII — eii_api v2 (Deep Agents)
Expoe o pipeline Deep Agents (A3) com PIIScrubber obrigatório (A23) via HTTP.

Motor unico de producao: nenhuma chamada a LLM sem scrub antes (fail-closed).

Rodar:
    uvicorn eii_api:app --host 0.0.0.0 --port 8001 --reload

Endpoints:
    GET  /api/health
    POST /api/analyze
    POST /api/analyze-file
    GET  /api/results/{job_id}

Limitacoes (spec A3.5, secao 7):
    - event_type hardcoded como "S-2200" (detector futuro)
    - jobs em memoria (usar DB em producao)
"""

import asyncio
import logging
import os
import threading
import uuid
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from src.privacy.scrubber import PIIScrubber
from src.deep_agents_wrapper import diagnose_incident_deep_agents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EII — ERP Incident Intelligence (Deep Agents)",
    description="Diagnostico de incidentes eSocial via Deep Agents + PIIScrubber",
    version="2.0.0",
)

# Jobs em memoria (ver spec A3.5 secao 7: usar DB em producao)
jobs: Dict[str, dict] = {}
jobs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class DiagnoseRequest(BaseModel):
    xml: str
    incident_id: str
    mentor_mode: bool = False


class FileRequest(BaseModel):
    filepath: str
    question: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_analysis_deep_agents(
    job_id: str,
    xml: str,
    incident_id: str,
    mentor_mode: bool = False,
):
    """
    Executa Deep Agents com scrubber obrigatorio.

    Fail-closed: se scrubber levanta excecao (ou entra em fail-closed
    estrutural — XML malformado/evento nao mapeado, detectado por
    token_map vazio), retorna erro (nao tenta cloud).
    """
    try:
        # 1. Scrubber obrigatorio
        scrubber = PIIScrubber()
        try:
            scrub_result = scrubber.scrub(xml, event_type="S-2200")  # detectar tipo depois
            is_safe = scrub_result.is_safe_for_remote
            scrubbed_xml = scrub_result.scrubbed_payload
            token_map = scrub_result.token_map
        except Exception as e:
            # Fail-closed: PII nao seguro, nao tenta diagnostico
            logger.error(f"Scrubber exception no job {job_id}: {e}")
            with jobs_lock:
                jobs[job_id] = {
                    "status": "error",
                    "error": f"Scrubber exception: {e}",
                    "is_safe_for_remote": False,
                }
            return

        # Fail-closed estrutural: scrubber recusou o payload (XML malformado,
        # evento nao mapeado ou Id invalido) — token_map vazio e payload intacto
        if not is_safe and not token_map:
            logger.error(f"Scrubber fail-closed no job {job_id}: XML malformado ou evento nao suportado")
            with jobs_lock:
                jobs[job_id] = {
                    "status": "error",
                    "error": "Scrubber fail-closed: XML malformado ou evento nao suportado",
                    "is_safe_for_remote": False,
                }
            return

        # 2. Chamar Deep Agents (payload scrubbed; PII nao seguro forca local)
        result = await diagnose_incident_deep_agents(
            xml=scrubbed_xml,
            incident_id=incident_id,
            mentor_mode=mentor_mode,
            force_local=not is_safe,
        )

        # 3. Restaurar tokens na resposta (token_map fica local, nunca serializa)
        if token_map and result.get("diagnostico"):
            restaurado = scrubber.restore(result["diagnostico"], token_map)
            result["diagnostico"] = restaurado

        # 4. Salvar resultado
        with jobs_lock:
            jobs[job_id] = {
                "status": "completed",
                "diagnosis": result,
                "is_safe_for_remote": is_safe,
            }
    except Exception as e:
        logger.error(f"Erro no job {job_id}: {e}", exc_info=True)
        with jobs_lock:
            jobs[job_id] = {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "engine": "deep_agents"}


# ---------------------------------------------------------------------------
# Aliases sem o prefixo /api (compatibilidade com clientes da spec A6)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_alias():
    """Alias de /api/health — expõe também a versão da API."""
    return {"status": "ok", "engine": "deep_agents", "version": "3.2"}


@app.post("/api/analyze", status_code=202)
async def analyze(background_tasks: BackgroundTasks, body: DiagnoseRequest):
    """Analisa XML do eSocial via Deep Agents."""
    try:
        if not body.xml:
            raise HTTPException(status_code=400, detail="XML obrigatorio")

        job_id = str(uuid.uuid4())
        with jobs_lock:
            jobs[job_id] = {"status": "processing"}

        background_tasks.add_task(
            run_analysis_deep_agents,
            job_id,
            body.xml,
            body.incident_id,
            body.mentor_mode,
        )
        return {"job_id": job_id, "status": "processing"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-file", status_code=202)
async def analyze_file(background_tasks: BackgroundTasks, body: FileRequest):
    """Analisa arquivo XML via Deep Agents."""
    try:
        if not os.path.isfile(body.filepath):
            raise HTTPException(status_code=404, detail=f"Arquivo nao encontrado: {body.filepath}")

        with open(body.filepath, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        incident_id = str(uuid.uuid4())

        job_id = str(uuid.uuid4())
        with jobs_lock:
            jobs[job_id] = {"status": "processing"}

        background_tasks.add_task(
            run_analysis_deep_agents,
            job_id,
            xml_content,
            incident_id,
            False,  # mentor_mode
        )
        return {"job_id": job_id, "status": "processing", "filepath": body.filepath}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/{job_id}")
async def get_result(job_id: str):
    """Retorna resultado do job."""
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job nao encontrado")
        return jobs[job_id]


@app.post("/analyze", status_code=202)
async def analyze_alias(background_tasks: BackgroundTasks, body: DiagnoseRequest):
    """Alias de /api/analyze — mesmo contrato (202 + job_id + polling em /api/results)."""
    return await analyze(background_tasks, body)
