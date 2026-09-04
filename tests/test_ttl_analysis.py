"""
Testes para A27 — TTL analysis + relatório LGPD.

Os testes usam conexão PostgreSQL mockada (não precisam de banco real).
Cenários cobertos: TTL, estatísticas de tokens, taxa de sucesso e geração
do relatório (seções obrigatórias, menção de violações).

Executar: pytest tests/test_ttl_analysis.py -v
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Importa o script (scripts/ não é pacote)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
import a27_ttl_analysis as a27


def _store_with_mock_conn():
    """AuditLogStore com conexão mockada (sem PostgreSQL real)."""
    store = MagicMock()
    store.conn = MagicMock()
    return store


# ==========================================================================
# 1. TTL validation
# ==========================================================================


def test_ttl_no_tokens_after_expiration():
    """Sem resultados 'expired', violations = 0 e status OK."""
    store = _store_with_mock_conn()
    # COUNT(*) FILTER (WHERE result='expired'), COUNT(*)
    store.conn.cursor.return_value.fetchall.return_value = [(0, 42)]

    result = a27.validate_ttl(store)

    assert result["ttl_violations"] == 0
    assert result["status"] == "✅ OK"
    assert result["total_restores"] == 42


def test_ttl_validator_runs_without_error():
    """Sem PostgreSQL, validator não quebra e marca indisponível."""
    store = MagicMock()
    store.conn = None

    result = a27.validate_ttl(store)

    assert result["ttl_violations"] is None
    assert "INDISPONÍVEL" in result["status"]


# ==========================================================================
# 2. Token stats
# ==========================================================================


def test_token_stats_returns_dict():
    """get_token_stats retorna dict token -> count."""
    store = _store_with_mock_conn()
    store.conn.cursor.return_value.fetchall.return_value = [
        ("CPF_001", 10),
        ("NOME_001", 8),
    ]

    stats = a27.get_token_stats(store)

    assert isinstance(stats, dict)
    assert stats == {"CPF_001": 10, "NOME_001": 8}


def test_token_stats_top_tokens_cpf_high():
    """CPF é tipicamente o token mais restaurado (ordenação DESC)."""
    store = _store_with_mock_conn()
    store.conn.cursor.return_value.fetchall.return_value = [
        ("CPF_001", 25),
        ("NOME_001", 12),
        ("NIS_001", 3),
    ]

    stats = a27.get_token_stats(store)
    top_token = max(stats, key=stats.get)

    assert top_token == "CPF_001", f"Esperava CPF_001 no topo, obteve {top_token}"


# ==========================================================================
# 3. Success rate
# ==========================================================================


def test_success_rate_above_95_percent():
    """Com dados saudáveis, sucesso >= 95%."""
    store = _store_with_mock_conn()
    store.conn.cursor.return_value.fetchall.return_value = [
        ("success", 199),
        ("failure", 1),
    ]

    rate = a27.get_success_rate(store)

    assert rate["success"] >= 95.0, f"Taxa de sucesso {rate['success']}% abaixo de 95%"


def test_success_rate_returns_percentages():
    """Percentuais somam ~100 e cobrem os resultados presentes."""
    store = _store_with_mock_conn()
    store.conn.cursor.return_value.fetchall.return_value = [
        ("success", 90),
        ("failure", 5),
        ("expired", 5),
    ]

    rate = a27.get_success_rate(store)

    assert set(rate.keys()) == {"success", "failure", "expired"}
    assert abs(sum(rate.values()) - 100.0) < 0.1


# ==========================================================================
# 4. Geração do relatório LGPD
# ==========================================================================


@pytest.fixture
def healthy_store():
    """Store mockada com dados saudáveis (0 violações, alto sucesso)."""
    store = _store_with_mock_conn()
    cursor = store.conn.cursor.return_value

    def execute(sql, params=()):
        sql_l = " ".join(sql.split()).lower()
        if "filter (where result = 'expired')" in sql_l:
            cursor.fetchall.return_value = [(0, 42)]
        elif "group by token_name" in sql_l:
            cursor.fetchall.return_value = [("CPF_001", 25), ("NOME_001", 12)]
        elif "group by result" in sql_l:
            cursor.fetchall.return_value = [("success", 42)]
        elif "min(timestamp)" in sql_l:
            cursor.fetchall.return_value = [("2026-09-01 08:00:00", "2026-09-04 18:00:00")]
        else:
            cursor.fetchall.return_value = []

    cursor.execute.side_effect = execute
    return store


def test_lgpd_report_generated_without_error(tmp_path, healthy_store):
    """Geração completa não lança exceção."""
    out = tmp_path / "relatorio.md"
    report = a27.generate_lgpd_report(healthy_store, output_file=str(out))
    assert isinstance(report, str)
    assert len(report) > 500


def test_lgpd_report_file_created(tmp_path, healthy_store):
    """Arquivo markdown é criado no disco."""
    out = tmp_path / "relatorio.md"
    a27.generate_lgpd_report(healthy_store, output_file=str(out))
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# Relatório de Conformidade LGPD")


def test_lgpd_report_contains_required_sections(tmp_path, healthy_store):
    """Relatório cobre art. 5º II, 12, 18, 32 e validação de TTL."""
    out = tmp_path / "relatorio.md"
    report = a27.generate_lgpd_report(healthy_store, output_file=str(out))

    for required in ["Art. 5º", "Art. 12", "Art. 18", "Art. 32",
                     "Validação de TTL", "Padrões de Uso", "Conclusão"]:
        assert required in report, f"Seção '{required}' ausente no relatório"


def test_lgpd_report_mentions_no_violations(tmp_path, healthy_store):
    """Com dados saudáveis, relatório declara zero violações."""
    out = tmp_path / "relatorio.md"
    report = a27.generate_lgpd_report(healthy_store, output_file=str(out))

    assert "Violações de TTL (7 dias): 0" in report
    assert "conformidade com LGPD" in report
