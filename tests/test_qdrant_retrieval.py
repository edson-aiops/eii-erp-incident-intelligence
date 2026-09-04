"""
Testes A4 — Validação do retrieval Qdrant (integração já existente).

A integração Qdrant já está implementada e em produção:
  retrieve_node (state.retrieval_backend) → crag_pipeline.retrieve(backend=...)
  → qdrant_client.retrieve_qdrant() (Qdrant Cloud, fallback gracioso [])

Estes 10 testes validam o comportamento sem exigir rede nem QDRANT_API_KEY:
embeddings e HTTP são mockados; os testes de dispatch usam os próprios
módulos de produção.

Executar: pytest tests/test_qdrant_retrieval.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

import qdrant_client as qc_mod
from crag_pipeline import retrieve
from src.deep_agents.state import IncidentContext


QDRANT_HIT = {
    "id": 7,
    "score": 0.82,
    "payload": {
        "id": "KB007",
        "evento": "S-2200",
        "codigo_erro": "E428",
        "titulo": "CPF inválido na admissão",
        "descricao": "O CPF informado é inválido.",
        "causa_raiz": "Cadastro com CPF errado",
        "tags": ["S-2200", "E428"],
        "impacto": "Rejeição do evento",
        "passos_resolucao": ["Corrigir CPF"],
        "validacao": "Reenviar",
        "tempo_estimado": "5min",
        "confidence_tier": "gold",
    },
}


@pytest.fixture
def cloud_env(monkeypatch):
    """Ambiente com QDRANT_API_KEY e _embed mockado (sem carregar modelo)."""
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    monkeypatch.setattr(qc_mod, "_model", object())  # evita lazy-load real
    monkeypatch.setattr(qc_mod, "_embed", lambda text: [0.1] * 384)
    return monkeypatch


def _mock_response(status=200, hits=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"result": hits if hits is not None else [QDRANT_HIT]}
    return resp


# ==========================================================================
# 1. retrieve_qdrant — fallback gracioso
# ==========================================================================


def test_retrieve_qdrant_empty_without_api_key(monkeypatch):
    """Sem QDRANT_API_KEY retorna [] (nunca levanta exceção)."""
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    assert qc_mod.retrieve_qdrant("S-2200 admissão") == []


def test_retrieve_qdrant_empty_on_http_error(cloud_env):
    """HTTP != 200 retorna [] (fallback para LLM_FALLBACK no pipeline)."""
    with patch.object(qc_mod.requests, "post", return_value=_mock_response(status=503)):
        assert qc_mod.retrieve_qdrant("S-2200") == []


def test_retrieve_qdrant_empty_on_network_error(cloud_env):
    """Erro de rede/timeout retorna []."""
    import requests as req
    with patch.object(qc_mod.requests, "post", side_effect=req.ConnectionError("timeout")):
        assert qc_mod.retrieve_qdrant("S-2200") == []


# ==========================================================================
# 2. retrieve_qdrant — parsing da resposta
# ==========================================================================


def test_retrieve_qdrant_score_to_distance_conversion(cloud_env):
    """Score de similaridade é convertido em distance = 1 - score."""
    with patch.object(qc_mod.requests, "post", return_value=_mock_response()):
        results = qc_mod.retrieve_qdrant("S-2200", n=5)

    assert len(results) == 1
    assert results[0]["distance"] == round(1.0 - 0.82, 4)


def test_retrieve_qdrant_payload_fields(cloud_env):
    """Item reconstruído com os 11 campos KB + confidence_tier."""
    with patch.object(qc_mod.requests, "post", return_value=_mock_response()):
        results = qc_mod.retrieve_qdrant("S-2200", n=5)

    item = results[0]["item"]
    assert item["id"] == "KB007"
    assert item["evento"] == "S-2200"
    assert item["titulo"] == "CPF inválido na admissão"
    assert results[0]["document_name"] == item["titulo"]
    assert results[0]["confidence_tier"] == "gold"
    # distance em [0,1] → compatível com grade() do CRAG
    assert 0.0 <= results[0]["distance"] <= 1.0


def test_retrieve_qdrant_respects_top_n(cloud_env):
    """Limit n respeitado: com n=1 retorna no máximo 1 hit."""
    hits = [dict(QDRANT_HIT, id=i, score=0.9 - i * 0.01) for i in range(5)]
    with patch.object(qc_mod.requests, "post", return_value=_mock_response(hits=hits)) as post:
        results = qc_mod.retrieve_qdrant("eSocial", n=1)

    assert len(results) == 1
    assert post.call_args.kwargs["json"]["limit"] == 1


def test_retrieve_qdrant_gold_boost(cloud_env):
    """Items gold sobem na ordenação quando distances empatam."""
    std = dict(QDRANT_HIT, id=1, score=0.90,
               payload={**QDRANT_HIT["payload"], "id": "KB001", "confidence_tier": "standard"})
    gold = dict(QDRANT_HIT, id=2, score=0.90,
                payload={**QDRANT_HIT["payload"], "id": "KB002", "confidence_tier": "gold"})
    with patch.object(qc_mod.requests, "post",
                      return_value=_mock_response(hits=[std, gold])):
        results = qc_mod.retrieve_qdrant("eSocial", n=5)

    assert results[0]["confidence_tier"] == "gold"


# ==========================================================================
# 3. Dispatch no pipeline (crag_pipeline.retrieve)
# ==========================================================================


def test_retrieve_dispatches_to_qdrant_backend():
    """retrieve(backend='qdrant') chama qdrant_client.retrieve_qdrant."""
    with patch("qdrant_client.retrieve_qdrant", return_value=[{"id": "KB007"}]) as mock_q:
        out = retrieve(col=None, query="S-2200", n=5, backend="qdrant")

    mock_q.assert_called_once_with(query="S-2200", n=5)
    assert out == [{"id": "KB007"}]


def test_retrieve_env_var_backend_override(monkeypatch):
    """EII_RETRIEVAL_BACKEND=qdrant dispensa o argumento backend."""
    monkeypatch.setenv("EII_RETRIEVAL_BACKEND", "qdrant")
    with patch("qdrant_client.retrieve_qdrant", return_value=[]) as mock_q:
        retrieve(col=None, query="S-1200", n=3)

    mock_q.assert_called_once_with(query="S-1200", n=3)


# ==========================================================================
# 4. Integração retrieve_node
# ==========================================================================


@pytest.mark.asyncio
async def test_retrieve_node_uses_backend_from_state():
    """retrieve_node passa state.retrieval_backend para crag_pipeline.retrieve."""
    from src.deep_agents.nodes import retrieve_node as rn
    from importlib import import_module
    rn_mod = import_module("src.deep_agents.nodes.retrieve_node")

    state = {
        "retrieval_backend": "qdrant",
        "context": IncidentContext(
            evento="S-2200",
            codigo_erro="E428",
            xml_raw="",
            metadata={"ocorrencias": []},
        ),
    }

    with patch("crag_pipeline.build_vector_store", return_value=None), \
         patch("crag_pipeline.retrieve", return_value=[]) as mock_ret, \
         patch("crag_pipeline.grade", return_value=[]):
        result = await rn_mod.retrieve_node(state)

    assert mock_ret.call_args.kwargs.get("backend") == "qdrant" or \
           mock_ret.call_args[0][2] == "qdrant" or \
           mock_ret.call_args.kwargs.get("backend") == "qdrant"
    assert "retrieved" in result
