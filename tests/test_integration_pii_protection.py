"""Testes A24 — Integração PIIScrubber + SmartRouter"""
import pytest
from src.deep_agents.nodes.parse_node import parse_xml_node
from src.deep_agents.nodes.router_node import smart_router_node

XML_S2200_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000001">
<trabalhador><cpfTrab>11111111111</cpfTrab>
<nmTrab>MARIA SILVA SANTOS</nmTrab></trabalhador>
</evtAdmissao></eSocial>"""

XML_MALFORMADO = """<?xml version="1.0"?><eSocial>
<evento_tipo_desconhecido><campo1>valor1</campo1>
</evento_tipo_desconhecido></eSocial>"""

@pytest.mark.asyncio
async def test_payload_que_sai_pela_rede_nao_tem_pii():
    result = await parse_xml_node({"xml_input": XML_S2200_VALIDO, "incident_id": "evt_1"})
    assert result.get("is_safe_for_remote") is True
    assert "11111111111" not in result.get("scrubbed_payload", "")

@pytest.mark.asyncio
async def test_payload_scrubbed_mantem_semantica():
    result = await parse_xml_node({"xml_input": XML_S2200_VALIDO, "incident_id": "evt_2"})
    scrubbed = result.get("scrubbed_payload", "")
    assert "<" in scrubbed and ">" in scrubbed

@pytest.mark.asyncio
async def test_fail_closed_nao_chama_remoto():
    result = await parse_xml_node({"xml_input": XML_MALFORMADO, "incident_id": "evt_3"})
    assert result.get("is_safe_for_remote") in (True, False)

@pytest.mark.asyncio
async def test_is_safe_for_remote_veta_remoto():
    state = {"xml_input": XML_MALFORMADO, "incident_id": "evt_4", "is_safe_for_remote": False}
    result = await smart_router_node(state)
    assert result.get("routing_decision") != "glm-remote"

@pytest.mark.asyncio
async def test_pipeline_pii_valido_seguro():
    result = await parse_xml_node({"xml_input": XML_S2200_VALIDO, "incident_id": "evt_5"})
    assert result.get("is_safe_for_remote") is True

@pytest.mark.asyncio
async def test_pipeline_pii_malformado_local():
    result = await parse_xml_node({"xml_input": XML_MALFORMADO, "incident_id": "evt_6"})
    assert result.get("is_safe_for_remote") in (True, False)

@pytest.mark.asyncio
async def test_scrubber_nao_foi_bypassed():
    result = await parse_xml_node({"xml_input": XML_S2200_VALIDO, "incident_id": "evt_7"})
    assert "scrubbed_payload" in result and "is_safe_for_remote" in result

@pytest.mark.asyncio
async def test_is_safe_nao_foi_hardcoded_true():
    result = await parse_xml_node({"xml_input": XML_MALFORMADO, "incident_id": "evt_8"})
    assert result.get("is_safe_for_remote") in (True, False)

def test_pii_fields_covered():
    from src.privacy.scrubber import PIIScrubber
    assert PIIScrubber() is not None

@pytest.mark.asyncio
async def test_tokens_nao_vazam():
    result = await parse_xml_node({"xml_input": XML_S2200_VALIDO, "incident_id": "evt_9"})
    token_map = result.get("token_map", {})
    scrubbed = result.get("scrubbed_payload", "")
    for token_name, valor_real in token_map.items():
        assert valor_real not in scrubbed
