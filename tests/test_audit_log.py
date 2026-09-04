"""
Testes para A26 — AuditLogStore: log de reversões de token_map em PostgreSQL.

Validam: insert, query, batch, fallback gracioso, integração finalize_node,
conformidade LGPD (metadados apenas — nunca o valor real do token).

Testes 1-8 usam mocks (não precisam de PostgreSQL).
Teste 9 é integração real: skipa se PostgreSQL indisponível.

Executar: pytest tests/test_audit_log.py -v
"""

import inspect
import pytest
from unittest.mock import patch, MagicMock

from src.utils.audit_log_store import AuditLogStore


def _make_store_with_mock_conn():
    """AuditLogStore com conexão mockada (sem PostgreSQL real)."""
    store = AuditLogStore.__new__(AuditLogStore)
    store.conn = MagicMock()
    return store


# ==========================================================================
# 1. Insert (log_restore)
# ==========================================================================


def test_log_restore_insere_metadados():
    """log_restore executa INSERT com metadados corretos."""
    store = _make_store_with_mock_conn()

    resultado = store.log_restore(
        incident_id="evt_abc123",
        token_name="CPF_001",
        token_value_length=11,
        result="success",
        job_id="job_1",
        source="finalize_node",
    )

    assert resultado is True, "log_restore deveria retornar True em sucesso"

    cursor = store.conn.cursor.return_value
    cursor.execute.assert_called_once()
    query, params = cursor.execute.call_args[0]
    assert "INSERT INTO tokenmap_audit" in query
    assert params[0] == "evt_abc123"
    assert params[2] == "CPF_001"
    assert params[3] == 11
    assert params[4] == "success"
    store.conn.commit.assert_called_once()


def test_log_restore_sem_postgres_fallback():
    """Sem conexão PostgreSQL, log_restore retorna False sem quebrar."""
    store = AuditLogStore.__new__(AuditLogStore)
    store.conn = None

    resultado = store.log_restore(
        incident_id="evt_x",
        token_name="CPF_001",
        token_value_length=11,
    )

    assert resultado is False, "Sem conexão deveria retornar False (fallback gracioso)"


def test_log_restore_registra_falha_com_error_msg():
    """Reversões com erro são registradas com result='failure' e error_msg."""
    store = _make_store_with_mock_conn()

    resultado = store.log_restore(
        incident_id="evt_abc123",
        token_name="NOME_001",
        token_value_length=5,
        result="failure",
        error_msg="token não encontrado no mapa",
    )

    assert resultado is True
    params = store.conn.cursor.return_value.execute.call_args[0][1]
    assert params[4] == "failure"
    assert params[5] == "token não encontrado no mapa"


# ==========================================================================
# 2. Batch (log_batch)
# ==========================================================================


def test_log_batch_multiplos_registros():
    """log_batch insere N registros em uma transação."""
    store = _make_store_with_mock_conn()

    records = [
        {"incident_id": "evt_1", "token_name": "CPF_001", "token_value_length": 11},
        {"incident_id": "evt_1", "token_name": "NOME_001", "token_value_length": 5},
        {"incident_id": "evt_1", "token_name": "NIS_001", "token_value_length": 11},
    ]

    with patch("src.utils.audit_log_store.execute_values") as mock_ev:
        count = store.log_batch(records)

    assert count == 3, f"Esperava 3 registros, obteve {count}"
    mock_ev.assert_called_once()
    values = mock_ev.call_args[0][2]
    assert len(values) == 3
    assert values[0][2] == "CPF_001"
    store.conn.commit.assert_called_once()


def test_log_batch_vazio_retorna_zero():
    """log_batch com lista vazia (ou sem conexão) retorna 0."""
    store = _make_store_with_mock_conn()
    assert store.log_batch([]) == 0

    store_sem_conn = AuditLogStore.__new__(AuditLogStore)
    store_sem_conn.conn = None
    assert store_sem_conn.log_batch([{"incident_id": "x"}]) == 0


# ==========================================================================
# 3. Query (query_by_incident)
# ==========================================================================


def test_query_by_incident_filtra_e_ordena():
    """query_by_incident busca por incident_id, mais recentes primeiro."""
    store = _make_store_with_mock_conn()
    store.conn.cursor.return_value.fetchall.return_value = [
        (2, "NOME_001", "success", "2026-09-04 10:01", None),
        (1, "CPF_001", "success", "2026-09-04 10:00", None),
    ]

    rows = store.query_by_incident("evt_abc123", limit=50)

    assert len(rows) == 2
    cursor = store.conn.cursor.return_value
    query, params = cursor.execute.call_args[0]
    assert "WHERE incident_id = %s" in query
    assert "ORDER BY timestamp DESC" in query
    assert params == ("evt_abc123", 50)


def test_query_sem_postgres_retorna_lista_vazia():
    """Sem conexão, query_by_incident retorna [] (fallback gracioso)."""
    store = AuditLogStore.__new__(AuditLogStore)
    store.conn = None
    assert store.query_by_incident("evt_x") == []


# ==========================================================================
# 4. Conformidade LGPD — metadados apenas
# ==========================================================================


def test_lgpd_nunca_registra_valor_real():
    """API não aceita valor real do token; SQL nunca contém coluna de valor."""
    sig = inspect.signature(AuditLogStore.log_restore)
    assert "token_value" not in sig.parameters, \
        "log_restore não deve aceitar o valor real do token"

    store = _make_store_with_mock_conn()
    valor_real = "11111111111"
    store.log_restore(
        incident_id="evt_lgpd",
        token_name="CPF_001",
        token_value_length=len(valor_real),
    )

    query, params = store.conn.cursor.return_value.execute.call_args[0]
    assert "token_value_length" in query
    assert valor_real not in [str(p) for p in params], \
        "Valor real do token NUNCA pode ser persistido (LGPD art. 12)"


# ==========================================================================
# 5. Integração: finalize_node registra reversões
# ==========================================================================


@pytest.mark.asyncio
async def test_finalize_node_loga_reversoes():
    """finalize_node loga cada token restaurado no AuditLogStore."""
    from src.utils.tokenmap_store import MemoryTokenMapStore
    from importlib import import_module
    fn = import_module("src.deep_agents.nodes.finalize_node")

    store = MemoryTokenMapStore()
    incident_id = "evt_audit_001"
    store.set(incident_id, {"CPF_001": "11111111111", "NOME_001": "MARIA"})

    audit_mock = MagicMock()
    state = {
        "incident_id": incident_id,
        "job_id": "job_42",
        "context": None,
        "diagnosis": {"resposta": "Erro no CPF_001 do NOME_001"},
    }

    with patch.object(fn, "get_token_map_store", return_value=store), \
         patch.object(fn, "AuditLogStore", return_value=audit_mock):
        result = await fn.finalize_node(state)

    assert audit_mock.log_restore.call_count == 2, \
        "Deveria registrar um audit por token restaurado"

    for call in audit_mock.log_restore.call_args_list:
        kwargs = call.kwargs
        assert kwargs["incident_id"] == incident_id
        assert kwargs["source"] == "finalize_node"
        assert kwargs["result"] == "success"
        # LGPD: nenhum valor real passado ao audit
        assert "11111111111" not in [str(v) for v in kwargs.values()]
        assert "MARIA" not in [str(v) for v in kwargs.values()]

    audit_mock.close.assert_called_once()
    # Restore aconteceu (valores reais de volta na resposta ao usuário)
    assert "11111111111" in result["final_result"]["diagnosis_raw"]["resposta"]


# ==========================================================================
# 6. Integração real com PostgreSQL (skip se indisponível)
# ==========================================================================


def test_integracao_postgres_real():
    """Insert + query reais contra PostgreSQL (migration aplicada no teste)."""
    store = AuditLogStore()
    if store.conn is None:
        pytest.skip("PostgreSQL não disponível")

    import os
    migration = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "001_create_tokenmap_audit.sql"
    )
    with open(migration, encoding="utf-8") as f:
        sql = f.read()

    cursor = store.conn.cursor()
    cursor.execute(sql)
    store.conn.commit()
    cursor.close()

    incident_id = "evt_integracao_a26"
    ok = store.log_restore(
        incident_id=incident_id,
        token_name="CPF_001",
        token_value_length=11,
        source="test_integracao",
    )
    assert ok is True

    rows = store.query_by_incident(incident_id)
    assert len(rows) >= 1, "Audit recém-inserido deveria ser recuperável"
    assert rows[0][1] == "CPF_001"

    # Cleanup: remove registros do teste
    cursor = store.conn.cursor()
    cursor.execute("DELETE FROM tokenmap_audit WHERE incident_id = %s", (incident_id,))
    store.conn.commit()
    cursor.close()
    store.close()
