"""
Testes A6 — Endpoints da API de produção (eii_api.py).

A API já chamava o pipeline Deep Agents (A3.5, assíncrona com jobs);
o ciclo A6 adicionou aliases sem prefixo (/analyze, /health) para
compatibilidade com a spec. Estes 10 testes validam o contrato completo
via TestClient, com o worker mockado (zero chamadas reais a LLM).

Executar: pytest tests/test_eii_api.py -v
"""

import pytest
from unittest.mock import patch

import eii_api
from eii_api import app

from fastapi.testclient import TestClient

client = TestClient(app)

XML_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <evtAdmissao Id="ID1123456780001992026080112000000001">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>11111111112</cpfTrab>
      <nmTrab>JOAO SILVA</nmTrab>
    </trabalhador>
  </evtAdmissao>
</eSocial>"""


def _worker_completar(job_id, xml, incident_id, mentor_mode):
    """Worker fake: marca o job como completed com diagnóstico estruturado."""
    with eii_api.jobs_lock:
        eii_api.jobs[job_id] = {
            "status": "completed",
            "is_safe_for_remote": True,
            "diagnostico": "Causa raiz simulada para teste",
        }


@pytest.fixture(autouse=True)
def limpar_jobs():
    eii_api.jobs.clear()
    yield
    eii_api.jobs.clear()


# ==========================================================================
# Health
# ==========================================================================


def test_api_health_returns_ok():
    """GET /api/health responde status ok com engine deep_agents."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["engine"] == "deep_agents"


def test_api_health_alias_includes_version():
    """GET /health (alias A6) inclui versão da API."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "3.2"


# ==========================================================================
# Analyze
# ==========================================================================


def test_api_analyze_valid_xml_returns_job():
    """POST /api/analyze com XML válido retorna 202 + job_id."""
    with patch.object(eii_api, "run_analysis_deep_agents", _worker_completar):
        r = client.post("/api/analyze", json={"xml": XML_VALIDO, "incident_id": "evt_api_test"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "processing"
    assert body["job_id"]


def test_api_analyze_invalid_xml_returns_400():
    """XML vazio é rejeitado com 400 (nunca traceback)."""
    r = client.post("/api/analyze", json={"xml": "", "incident_id": "evt_vazio"})
    assert r.status_code == 400


def test_api_analyze_alias_matches_canonical():
    """POST /analyze (alias A6) tem o mesmo comportamento de /api/analyze."""
    with patch.object(eii_api, "run_analysis_deep_agents", _worker_completar):
        r1 = client.post("/api/analyze", json={"xml": XML_VALIDO, "incident_id": "evt_api_test"})
        r2 = client.post("/analyze", json={"xml": XML_VALIDO, "incident_id": "evt_api_test"})
    assert r1.status_code == r2.status_code == 202
    assert set(r1.json().keys()) == set(r2.json().keys())


# ==========================================================================
# Results (pipeline integration)
# ==========================================================================


def test_api_results_returns_completed_job():
    """Fluxo completo: analyze → polling → completed com diagnóstico."""
    with patch.object(eii_api, "run_analysis_deep_agents", _worker_completar):
        r = client.post("/api/analyze", json={"xml": XML_VALIDO, "incident_id": "evt_api_test"})
        job_id = r.json()["job_id"]
        r2 = client.get(f"/api/results/{job_id}")

    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "completed"
    assert "diagnostico" in body


def test_api_results_unknown_job_404():
    """Job inexistente retorna 404."""
    r = client.get("/api/results/nao-existe")
    assert r.status_code == 404


def test_api_lgpd_status_in_job():
    """Resultado do job expõe is_safe_for_remote (gate LGPD A3.5)."""
    with patch.object(eii_api, "run_analysis_deep_agents", _worker_completar):
        r = client.post("/api/analyze", json={"xml": XML_VALIDO, "incident_id": "evt_api_test"})
        job_id = r.json()["job_id"]
        body = client.get(f"/api/results/{job_id}").json()

    assert body["is_safe_for_remote"] is True


# ==========================================================================
# Analyze-file + robustez
# ==========================================================================


def test_api_analyze_file_not_found_404():
    """Arquivo inexistente retorna 404 com mensagem clara."""
    r = client.post("/api/analyze-file", json={"filepath": "C:/nao/existe.xml"})
    assert r.status_code == 404


def test_api_error_handling_never_500_on_bad_input():
    """Corpo malformado não gera 500 com traceback exposto."""
    r = client.post("/api/analyze", json={"xml_invalido": 123})
    assert r.status_code in (400, 422)
    assert "traceback" not in r.text.lower()
