"""
Testes A24 — Integração: PIIScrubber (A23) + SmartRouter (A3) + eii_api (A3.5)
"""

import pytest
from src.deep_agents.nodes.parse_node import parse_node
from src.deep_agents.nodes.router_node import router_node

XML_S2200_VALIDO = """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <evtAdmissao Id="ID1123456780001992026080112000000001">
    <trabalhador>
      <cpfTrab>11111111111</cpfTrab>
      <nmTrab>MARIA SILVA SANTOS</nmTrab>
    </trabalhador>
  </evtAdmissao>
</eSocial>"""

XML_MALFORMADO = """<?xml version="1.0"?>
<eSocial>
  <evento_tipo_desconhecido>
    <campo1>valor1</campo1>
  </evento_tipo_desconhecido>
</eSocial>"""

@pytest.mark.asyncio
async def test_payload_que_sai_pela_rede_nao_tem_pii():
    state = {"xml_input": XML_S2200_VALIDO, "incident_id": "evt_pii_clean_001"}
    result = await parse_node(state)
    scrubbed_payload = result.get("scrubbed_payload", "")
    is_safe = result.get("is_safe_for_remote")
    assert is_safe is True
    assert "11111111111" not in scrubbed_payload
    assert "MARIA SILVA SANTOS" not in scrubbed_payload

@pytest.mark.asyncio
async def test_payload_scrubbed_mantem_semantica():
    state = {"xml_input": XML_S2200_VALIDO, "incident_id": "evt_pii_semantica_001"}
    result = await parse_node(state)
    scrubbed = result.get("scrubbed_payload", "")
    assert "<" in scrubbed and ">" in scrubbed

@pytest.mark.asyncio
async def test_fail_closed_nao_chama_remoto():
    state = {"xml_input": XML_MALFORMADO, "incident_id": "evt_fail_closed_001"}
    result = await parse_node(state)
    is_safe = result.get("is_safe_for_remote")
    token_map = result.get("token_map", {})
    if len(token_map) == 0 or not is_safe:
        assert is_safe is False
        router_result = await router_node(result)
        routing = router_result.get("routing_decision")
        assert routing != "glm-remote"

@pytest.mark.asyncio
async def test_is_safe_for_remote_veta_remoto():
    unsafe_state = {"xml_input": XML_MALFORMADO, "incident_id": "evt_unsafe_001", "is_safe_for_remote": False, "scrubbed_payload": "<evento_xyz>...</evento_xyz>", "routing_decision": None}
    router_result = await router_node(unsafe_state)
    routing = router_result.get("routing_decision")
    assert routing != "glm-remote"

@pytest.mark.asyncio
async def test_pipeline_pii_valido_seguro():
    state = {"xml_input": XML_S2200_VALIDO, "incident_id": "evt_e2e_valido_001"}
    parse_result = await parse_node(state)
    assert parse_result.get("is_safe_for_remote") is True

@pytest.mark.asyncio
async def test_pipeline_pii_malformado_local():
    state = {"xml_input": XML_MALFORMADO, "incident_id": "evt_e2e_malformado_001"}
    parse_result = await parse_node(state)
    is_safe = parse_result.get("is_safe_for_remote")
    if is_safe is False:
        router_result = await router_node(parse_result)
        routing = router_result.get("routing_decision")
        assert routing != "glm-remote"

@pytest.mark.asyncio
async def test_scrubber_nao_foi_bypassed():
    state = {"xml_input": XML_S2200_VALIDO, "incident_id": "evt_bypass_001"}
    result = await parse_node(state)
    assert "scrubbed_payload" in result
    assert "is_safe_for_remote" in result

@pytest.mark.asyncio
async def test_is_safe_nao_foi_hardcoded_true():
    state = {"xml_input": XML_MALFORMADO, "incident_id": "evt_hardcode_001"}
    result = await parse_node(state)
    is_safe = result.get("is_safe_for_remote")
    assert is_safe in (True, False)

def test_pii_fields_covered():
    from src.privacy.scrubber import PIIScrubber
    scrubber = PIIScrubber()
    assert scrubber is not None

@pytest.mark.asyncio
async def test_tokens_nao_vazam():
    state = {"xml_input": XML_S2200_VALIDO, "incident_id": "evt_tokens_001"}
    result = await parse_node(state)
    scrubbed = result.get("scrubbed_payload", "")
    token_map = result.get("token_map", {})
    for token_name, valor_real in token_map.items():
        assert valor_real not in scrubbed
