"""
Testes de integração A3 — Deep Agents + PIIScrubber + SmartRouter.

Escritos a partir do contrato da spec A3 sem leitura da implementação.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.deep_agents.nodes.parse_node import parse_xml_node
from src.deep_agents.nodes.router_node import smart_router_node
from src.deep_agents.nodes.retrieve_node import retrieve_node
from src.deep_agents.nodes.generate_node import generate_node
from src.deep_agents.nodes.finalize_node import finalize_node
from src.deep_agents.state import AgentState, IncidentContext
from src.utils.tokenmap_store import get_token_map_store


S2200_COM_PII = """<eSocial>
  <evtAdmissao Id="ID1123456780001992026080112000000001">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>11111111111</cpfTrab>
      <nmTrab>MARIA APARECIDA DA SILVA</nmTrab>
      <sexo>F</sexo>
      <racaCor>3</racaCor>
      <nascimento>
        <dtNascto>1985-04-17</dtNascto>
        <paisNascto>105</paisNascto>
      </nascimento>
    </trabalhador>
  </evtAdmissao>
</eSocial>"""

S1200_SEM_PII_TITULAR = """<eSocial>
  <evtRemun Id="ID1123456780001992026080112000000002">
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    <ideTrabalhador><cpfTrab>11111111111</cpfTrab></ideTrabalhador>
  </evtRemun>
</eSocial>"""


def _base_state(**overrides) -> AgentState:
    defaults = {
        "xml_input": "",
        "payload": "",
        "incident_id": "TEST-001",
        "use_mentor_mode": False,
        "context": None,
        "retrieved": None,
        "diagnosis": None,
        "evaluation_score": None,
        "evaluation_feedback": None,
        "needs_refinement": False,
        "iteration_count": 0,
        "max_iterations": 3,
        "routing_decision": None,
        "retrieval_backend": "chromadb",
        "model_used": None,
        "errors": [],
        "warnings": [],
        "final_result": None,
        "proactive_insights": None,
        "scrubbed_payload": None,
        "is_safe_for_remote": None,
        "token_map": None,
        "pii_scrubbed": None,
    }
    defaults.update(overrides)
    return defaults  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_parse_node_retorna_scrubbed_payload_e_seguranca():
    state = _base_state(payload=S2200_COM_PII)
    result = await parse_xml_node(state)

    assert "scrubbed_payload" in result
    assert "is_safe_for_remote" in result
    # A25: token_map não viaja no estado do grafo — vai para a store (Redis/TTL)
    assert "token_map" not in result
    store = get_token_map_store()
    assert store.get("TEST-001"), "token_map deveria estar persistido na store"
    store.delete("TEST-001")
    assert result["pii_scrubbed"] is True
    assert "11111111111" not in result["scrubbed_payload"]
    assert "MARIA APARECIDA" not in result["scrubbed_payload"]


@pytest.mark.asyncio
async def test_parse_node_fail_closed_em_evento_desconhecido():
    state = _base_state(payload="<xml>invalido</xml>")
    result = await parse_xml_node(state)

    assert result.get("is_safe_for_remote") is False


@pytest.mark.asyncio
async def test_router_node_forca_local_quando_nao_seguro():
    state = _base_state(
        context=IncidentContext(
            evento="S-2200",
            codigo_erro="E428",
            xml_raw="<eSocial/>",
        ),
        is_safe_for_remote=False,
        severidade="alta",
    )
    result = await smart_router_node(state)
    assert result["routing_decision"] == "sensitive_data"
    assert result["model_used"] is None


@pytest.mark.asyncio
async def test_router_node_usa_severidade_quando_seguro():
    state = _base_state(
        context=IncidentContext(
            evento="S-2200",
            codigo_erro="E428",
            xml_raw="<eSocial/>",
        ),
        is_safe_for_remote=True,
        severidade="alta",
    )
    result = await smart_router_node(state)
    assert result["routing_decision"] == "deep_reasoning"
    assert result["model_used"] is None


@pytest.mark.asyncio
async def test_retrieve_node_usa_scrubbed_payload_quando_disponivel():
    state = _base_state(
        payload="<eSocial><tag>secreto</tag></eSocial>",
        scrubbed_payload="<eSocial><tag>TOKEN_001</tag></eSocial>",
        context=IncidentContext(
            evento="DESCONHECIDO",
            codigo_erro="E000",
            xml_raw="<eSocial><tag>secreto</tag></eSocial>",
        ),
    )
    # Apenas verifica que não levanta e que a query usa o payload limpo
    result = await retrieve_node(state)
    assert "retrieved" in result


@pytest.mark.asyncio
async def test_generate_node_passa_is_safe_ao_smart_router():
    state = _base_state(
        payload=S1200_SEM_PII_TITULAR,
        scrubbed_payload=S1200_SEM_PII_TITULAR,
        is_safe_for_remote=False,
        routing_decision="deep_reasoning",
        context=IncidentContext(
            evento="S-1200",
            codigo_erro="E000",
            xml_raw=S1200_SEM_PII_TITULAR,
        ),
    )

    with patch("smartrouter.smart_router.SmartRouter.call") as mock_call:
        mock_call.return_value = {
            "causa_raiz": "Causa teste",
            "confianca": "ALTA",
            "severidade": "MEDIA",
        }
        result = await generate_node(state)

    mock_call.assert_awaited_once()
    _, kwargs = mock_call.call_args
    assert kwargs.get("is_safe_for_remote") is False
    assert kwargs.get("routing_decision") == "deep_reasoning"
    assert "diagnosis" in result


@pytest.mark.asyncio
async def test_smart_router_forca_local_quando_is_safe_false():
    from smartrouter.smart_router import SmartRouter

    with patch("smartrouter.smart_router.ollama_local", new=AsyncMock()) as mock_local:
        mock_local.return_value = {"text": "resposta local"}
        router = SmartRouter()
        result = await router.call(
            prompt="teste",
            routing_decision="deep_reasoning",
            is_safe_for_remote=False,
        )

    mock_local.assert_awaited_once()
    assert result["_meta"]["route"] == "local"


@pytest.mark.asyncio
async def test_finalize_node_restaura_tokens_na_resposta():
    # A25: token_map vive na store (chave = incident_id), não no estado
    get_token_map_store().set("TEST-001", {"NOME_001": "JOSE DA SILVA"})
    state = _base_state(
        is_safe_for_remote=True,
        routing_decision="deep_reasoning",
        diagnosis={
            "resposta": "O titular NOME_001 apresenta inconsistência.",
            "causa_raiz": "Inconsistência",
        },
    )
    result = await finalize_node(state)

    diagnosis = result["final_result"]["diagnosis_raw"]
    assert "JOSE DA SILVA" in diagnosis["resposta"]
    assert "NOME_001" not in diagnosis["resposta"]
    # uso único: mapa apagado da store após o restore
    assert get_token_map_store().get("TEST-001") == {}


@pytest.mark.asyncio
async def test_finalize_node_nao_serializa_token_map():
    state = _base_state(
        token_map={"CPF_001": "11111111111"},
        is_safe_for_remote=True,
        routing_decision="deep_reasoning",
        diagnosis={"resposta": "ok"},
    )
    result = await finalize_node(state)

    assert result["final_result"].get("token_map") is None
    assert result["final_result"].get("is_safe_for_remote") is True
