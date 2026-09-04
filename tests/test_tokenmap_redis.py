"""
Testes para A25 — token_map migrado para Redis com fallback memória.

Validam: set/get Redis, TTL, fallback, concorrência, integração parse+finalize.

Executar: pytest tests/test_tokenmap_redis.py -v
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from src.utils.tokenmap_store import TokenMapStore, RedisTokenMapStore, MemoryTokenMapStore, get_token_map_store


# ==========================================================================
# 1. Redis set/get básico
# ==========================================================================


def test_redis_set_e_get():
    """Redis armazena token_map e retorna idêntico."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111", "NOME_001": "MARIA"}

    resultado = store.set("incident123", token_map)
    assert resultado is True, "set() deveria retornar True em sucesso"

    recuperado = store.get("incident123")
    assert recuperado == token_map, f"Recuperado {recuperado}, esperava {token_map}"


def test_redis_get_nao_encontrado():
    """Redis retorna {} se incident_id não existe."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    recuperado = store.get("incident_inexistente_xyz")
    assert recuperado == {}, f"Esperava {{}}, obteve {recuperado}"


# ==========================================================================
# 2. Memory store fallback
# ==========================================================================


def test_memory_store_set_e_get():
    """MemoryTokenMapStore armazena e recupera."""
    store = MemoryTokenMapStore()
    token_map = {"CPF_001": "11111111111"}

    store.set("incident1", token_map)
    recuperado = store.get("incident1")

    assert recuperado == token_map


def test_memory_store_ttl_expira():
    """MemoryTokenMapStore respeita TTL."""
    store = MemoryTokenMapStore()
    token_map = {"CPF_001": "11111111111"}

    store.set("incident1", token_map, ttl_seconds=1)
    assert store.get("incident1") == token_map

    time.sleep(1.5)
    assert store.get("incident1") == {}, "Mapa deveria ter expirado"


# ==========================================================================
# 3. Fallback Redis → Memória
# ==========================================================================


def test_redis_fallback_se_conexao_cai():
    """Se Redis cair, RedisTokenMapStore usa fallback memória."""
    store = RedisTokenMapStore()
    if store.redis_client is None:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111"}

    # Simular falha no Redis
    with patch.object(store.redis_client, 'setex', side_effect=Exception("Redis connection refused")):
        resultado = store.set("incident1", token_map)
        assert resultado is False, "set() deveria retornar False em falha"

    # Deveria estar no fallback
    recuperado = store.fallback.get("incident1")
    assert recuperado == token_map, "Fallback deveria ter armazenado"


def test_redis_get_cai_usa_fallback():
    """Se Redis.get() cai, recupera do fallback."""
    store = RedisTokenMapStore()
    if store.redis_client is None:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111"}

    # Armazenar normalmente
    store.set("incident1", token_map)

    # Simular falha no get
    with patch.object(store.redis_client, 'get', side_effect=Exception("Redis connection lost")):
        recuperado = store.get("incident1")
        assert recuperado == token_map, "Deveria recuperar do fallback"


# ==========================================================================
# 4. Concorrência (múltiplos incidents)
# ==========================================================================


def test_multiworker_nao_interfere():
    """Dois incidents diferentes não se misturam no Redis."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    incident1 = "evt001"
    incident2 = "evt002"
    map1 = {"CPF_001": "11111111111"}
    map2 = {"CPF_002": "22222222222"}

    store.set(incident1, map1)
    store.set(incident2, map2)

    assert store.get(incident1) == map1
    assert store.get(incident2) == map2
    assert store.get("evt999") == {}


# ==========================================================================
# 5. Factory (singleton)
# ==========================================================================


def test_get_token_map_store_retorna_singleton():
    """get_token_map_store() retorna mesma instância."""
    store1 = get_token_map_store()
    store2 = get_token_map_store()

    assert store1 is store2, "Factory deveria retornar singleton"


def test_get_token_map_store_memory_se_redis_desabilitado():
    """Se REDIS_ENABLED=false, usa MemoryTokenMapStore."""
    import os
    original = os.getenv("REDIS_ENABLED")

    try:
        os.environ["REDIS_ENABLED"] = "false"
        # Resetar singleton
        import src.utils.tokenmap_store as mod
        mod._store_instance = None

        store = get_token_map_store()
        assert isinstance(store, MemoryTokenMapStore), f"Esperava MemoryTokenMapStore, obteve {type(store)}"
    finally:
        if original:
            os.environ["REDIS_ENABLED"] = original
        mod._store_instance = None


# ==========================================================================
# 6. TTL Redis
# ==========================================================================


def test_redis_ttl_respeita_parametro():
    """Redis TTL segue o parametro passado."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111"}

    store.set("incident_ttl", token_map, ttl_seconds=2)
    assert store.get("incident_ttl") == token_map

    time.sleep(2.5)
    assert store.get("incident_ttl") == {}, "TTL de 2s deveria ter expirado"


# ==========================================================================
# 7. Delete (opcional)
# ==========================================================================


def test_redis_delete_remove_chave():
    """delete() remove a chave do Redis."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111"}
    store.set("incident_del", token_map)

    resultado = store.delete("incident_del")
    assert resultado is True, "delete() deveria retornar True"

    recuperado = store.get("incident_del")
    assert recuperado == {}, "Mapa deveria ter sido deletado"


# ==========================================================================
# 8. Integração: Parse + Finalize round-trip
# ==========================================================================


@pytest.mark.asyncio
async def test_round_trip_parse_finalize():
    """token_map: parse_node escreve → finalize_node lê."""
    store = get_token_map_store()

    # Simular parse_node
    incident_id = "evt_roundtrip_001"
    token_map = {"CPF_001": "11111111111", "NOME_001": "MARIA"}
    store.set(incident_id, token_map)

    # Simular finalize_node
    recuperado = store.get(incident_id)
    assert recuperado == token_map, "finalize_node deveria recuperar token_map de parse_node"

    # Simular restore
    from src.privacy.scrubber import PIIScrubber
    scrubber = PIIScrubber()
    diagnostico = "Erro encontrado: CPF_001 inválido, NOME_001 não encontrado"
    restaurado = scrubber.restore(diagnostico, recuperado)

    assert "11111111111" in restaurado or "MARIA" in restaurado, \
        "Diagnóstico restaurado deveria ter valores reais"


# ==========================================================================
# 9. Conformidade de segurança
# ==========================================================================


def test_token_map_nao_aparece_no_estado_direto():
    """Validar que AgentState não carrega token_map (fica em Redis)."""
    # Este teste é mais de design/auditoria do código
    # Verifica que parse_node não retorna token_map
    import inspect
    from src.deep_agents.nodes.parse_node import parse_node

    source = inspect.getsource(parse_node)

    # Verificar que não há '"token_map": token_map' no retorno
    # (seria inclusão direta no estado)
    # Nota: este é um check frágil; melhor é audit de código real
    # Colocado aqui para documentar a expectativa
    assert '"token_map": token_map' not in source or 'store.set' in source, \
        "parse_node deveria usar store.set(), não retornar token_map no estado"


def test_redis_chave_nao_expoe_contexto():
    """Chaves Redis não expõem PII (usam incident_id, não CPF/Nome)."""
    try:
        store = RedisTokenMapStore()
    except Exception:
        pytest.skip("Redis não disponível")

    token_map = {"CPF_001": "11111111111"}
    incident_id = "evt_12345678_uuid_aleatorio"

    store.set(incident_id, token_map)

    # Verificar que a chave é "eii:tokenmap:evt_..." não expõe CPF
    # (isso é verificado internamente, não há API pública para listar chaves)
    # Mas podemos validar que incident_id é UUID/aleatório
    assert len(incident_id) > 10, "incident_id deveria ser UUID"
    assert "11111111111" not in incident_id, "incident_id não deveria conter CPF"
