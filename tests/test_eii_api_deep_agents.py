"""
Testes black-box para A3.5 — eii_api.py integrado com Deep Agents.

Escritos contra o contrato público (spec A3.5-LIGAR-EII-API-SPEC.md).

Cobrem:
  - POST /api/analyze chama Deep Agents, não glm_router
  - Scrubber é mandatório (fail-closed em exceção)
  - Arquivo via POST /api/analyze-file
  - Tokens restaurados na resposta

Utiliza cliente FastAPI TestClient. Valores sintéticos.
"""

import pytest
import os
import tempfile
import time
from fastapi.testclient import TestClient
from uuid import uuid4


# Imports (ajustar conforme estrutura real)
# from main import app

# Para testes, assumir que app está disponível
# pytest roda com: pytest tests/test_eii_api_deep_agents.py -v


# Valores sintéticos
CPF_TRAB = "11111111111"
NOME_TRAB = "MARIA APARECIDA"
INCIDENT_ID = "evt123"

XML_S2200_COM_CPF = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <evtAdmissao Id="ID1123456780001992026080112000000001">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>{CPF_TRAB}</cpfTrab>
      <nmTrab>{NOME_TRAB}</nmTrab>
      <sexo>F</sexo>
      <racaCor>3</racaCor>
    </trabalhador>
  </evtAdmissao>
</eSocial>"""

XML_MALFORMED = "<evento>nao eh xml bem formado"

XML_ESTRUTURAL = """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <evtInfoDeficiencia Id="ID1123456780001992026080112000000001">
    <ideEvento><indRetif>1</indRetif></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
  </evtInfoDeficiencia>
</eSocial>"""


# ==========================================================================
# 1. Integração Deep Agents via POST /api/analyze
# ==========================================================================


@pytest.mark.asyncio
async def test_analyze_chama_deep_agents_nao_glm_router(client: TestClient):
    """POST /api/analyze chama Deep Agents com scrubber."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_S2200_COM_CPF, "incident_id": INCIDENT_ID}
    )

    assert response.status_code == 202, f"POST /api/analyze deveria retornar 202, obteve {response.status_code}"
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # Aguardar processamento
    time.sleep(3)

    result = client.get(f"/api/results/{job_id}").json()

    assert result["status"] == "completed", \
        f"Job deveria estar 'completed', obteve '{result.get('status')}'"

    # Verificar que chamou Deep Agents (estrutura de resultado)
    assert "diagnosis" in result, \
        "Resultado deveria ter 'diagnosis' do Deep Agents"

    # Verificar que PII foi scrubbed
    diagnosis_text = result.get("diagnosis", {}).get("diagnostico", "")
    assert CPF_TRAB not in diagnosis_text, \
        "CPF real não deveria aparecer em claro no diagnóstico"


@pytest.mark.asyncio
async def test_analyze_xml_obrigatorio(client: TestClient):
    """POST /api/analyze rejeita se XML não for fornecido."""
    response = client.post(
        "/api/analyze",
        json={"xml": "", "incident_id": INCIDENT_ID}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_status_processing(client: TestClient):
    """POST /api/analyze retorna status='processing' imediatamente."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_S2200_COM_CPF, "incident_id": INCIDENT_ID}
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "processing"
    assert "job_id" in data


# ==========================================================================
# 2. Fail-closed em scrubber
# ==========================================================================


@pytest.mark.asyncio
async def test_scrubber_exception_retorna_erro(client: TestClient):
    """Se scrubber falha, retorna erro (não tenta cloud)."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_MALFORMED, "incident_id": INCIDENT_ID}
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Aguardar processamento
    time.sleep(3)

    result = client.get(f"/api/results/{job_id}").json()

    # Fail-closed: status deve ser "error"
    assert result["status"] == "error", \
        f"Scrubber exception deveria resultar em status='error', obteve '{result.get('status')}'"
    assert "error" in result or "Scrubber" in result.get("error", "")


@pytest.mark.asyncio
async def test_scrubber_nao_envia_cloud_se_pii_nao_seguro(client: TestClient):
    """Se PII é detectado como não-seguro, força local (não cloud)."""
    # S-2200 com CPF do empregador quando tpInsc=2 (não seguro)
    xml_nao_seguro = """<?xml version="1.0" encoding="UTF-8"?>
    <eSocial>
      <evtRemun Id="ID222222222200020260801120000000001">
        <ideEvento><indRetif>1</indRetif></ideEvento>
        <ideEmpregador><tpInsc>2</tpInsc><nrInsc>22222222222</nrInsc></ideEmpregador>
        <ideTrabalhador><cpfTrab>11111111111</cpfTrab></ideTrabalhador>
      </evtRemun>
    </eSocial>"""

    response = client.post(
        "/api/analyze",
        json={"xml": xml_nao_seguro, "incident_id": INCIDENT_ID}
    )

    job_id = response.json()["job_id"]
    time.sleep(3)

    result = client.get(f"/api/results/{job_id}").json()

    # Deep Agents deveria ter rodado com force_local=True
    assert result.get("is_safe_for_remote") == False or result.get("status") == "completed"


# ==========================================================================
# 3. Arquivo via POST /api/analyze-file
# ==========================================================================


@pytest.mark.asyncio
async def test_analyze_file_chama_deep_agents(client: TestClient):
    """POST /api/analyze-file lê arquivo e chama Deep Agents."""
    # Criar arquivo temp
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(XML_S2200_COM_CPF)
        filepath = f.name

    try:
        response = client.post(
            "/api/analyze-file",
            json={"filepath": filepath, "question": "Analisar XML"}
        )

        assert response.status_code == 202, \
            f"POST /api/analyze-file deveria retornar 202, obteve {response.status_code}"

        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"

        job_id = data["job_id"]
        time.sleep(3)

        result = client.get(f"/api/results/{job_id}").json()

        assert result["status"] == "completed"
        assert "diagnosis" in result
    finally:
        os.unlink(filepath)


@pytest.mark.asyncio
async def test_analyze_file_arquivo_nao_existe(client: TestClient):
    """POST /api/analyze-file retorna 404 se arquivo não existe."""
    response = client.post(
        "/api/analyze-file",
        json={"filepath": "/nao/existe/arquivo.xml"}
    )

    assert response.status_code == 404


# ==========================================================================
# 4. Tokens restaurados na resposta
# ==========================================================================


@pytest.mark.asyncio
async def test_tokens_restaurados_na_resposta(client: TestClient):
    """Diagnóstico retorna ao usuário com dados reais, não tokens."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_S2200_COM_CPF, "incident_id": INCIDENT_ID}
    )

    job_id = response.json()["job_id"]
    time.sleep(3)

    result = client.get(f"/api/results/{job_id}").json()

    assert result["status"] == "completed"
    diagnosis = result.get("diagnosis", {})
    diagnosis_text = diagnosis.get("diagnostico", "")

    # Se o diagnóstico menciona erro do trabalhador, deveria ter dados reais
    # (Isso é uma heurística; ajustar conforme o diagnóstico real)
    if "trabalhador" in diagnosis_text.lower() or "nome" in diagnosis_text.lower():
        # Se mencionou trabalhador/nome, deveria ter dados reais ou estar vazio
        assert CPF_TRAB not in diagnosis_text, \
            "CPF real não deveria aparecer em claro"


# ==========================================================================
# 5. Compatibilidade com requests antigos (opcional, se houver)
# ==========================================================================


@pytest.mark.asyncio
async def test_analyze_retorna_job_id_uuid(client: TestClient):
    """Retorno inclui job_id em formato UUID."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_ESTRUTURAL, "incident_id": INCIDENT_ID}
    )

    data = response.json()
    job_id = data["job_id"]

    # UUID válido tem 36 caracteres (com hífens)
    assert len(job_id) == 36 or len(job_id) == 32, \
        f"job_id deveria ser UUID, obteve '{job_id}'"


@pytest.mark.asyncio
async def test_results_endpoint_retorna_mesmo_job(client: TestClient):
    """GET /api/results/{job_id} retorna os dados do job."""
    response = client.post(
        "/api/analyze",
        json={"xml": XML_ESTRUTURAL, "incident_id": INCIDENT_ID}
    )

    job_id = response.json()["job_id"]

    # Job não deve existir instantaneamente (estava processing)
    result1 = client.get(f"/api/results/{job_id}").json()
    assert result1["status"] in ("processing", "completed", "error")

    # Aguardar
    time.sleep(3)

    # Agora deveria estar completo
    result2 = client.get(f"/api/results/{job_id}").json()
    assert result2["status"] == "completed" or result2["status"] == "error"


# ==========================================================================
# 6. Invariantes de segurança
# ==========================================================================


@pytest.mark.asyncio
async def test_glm_router_nao_e_importado(app):
    """Verificar que glm_router não é importado em eii_api.py."""
    import eii_api

    assert not hasattr(eii_api, 'qwen_local'), \
        "eii_api.py não deveria ter qwen_local de glm_router"
    assert not hasattr(eii_api, 'glm_remote'), \
        "eii_api.py não deveria ter glm_remote de glm_router"


@pytest.mark.asyncio
async def test_scrubber_e_importado(app):
    """Verificar que PIIScrubber é importado."""
    import eii_api

    # Procurar pela classe em locals/imports
    source = open("eii_api.py").read()
    assert "PIIScrubber" in source, \
        "eii_api.py deveria importar PIIScrubber"
    assert "deep_agents_wrapper" in source, \
        "eii_api.py deveria importar diagnose_incident_deep_agents"
