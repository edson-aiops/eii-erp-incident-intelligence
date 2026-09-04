"""
Testes A7/A8 — Benchmark GLM-5.3 vs Qwen 14B.

Os testes validam o HARNESS do benchmark com um runner fake de latências
determinísticas (zero chamadas reais a LLM) e a integridade do dataset
sintético. Métricas reais só são produzidas pela execução do script em
ambiente com os provedores disponíveis — o relatório nunca fabrica números
(status "not_executed" quando indisponível).

Executar: pytest tests/test_benchmark.py -v
"""

import json
import pytest

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from fixtures.esocial_benchmark_dataset import dataset_completo, CATEGORIAS
import benchmark_motors as bm


# ==========================================================================
# Runner fake (latências determinísticas)
# ==========================================================================

def make_fake_runner(latency_by_motor=None, succeed=True):
    """Runner fake: latência fixa por motor, sucesso configurável."""
    latency_by_motor = latency_by_motor or {"glm": 4000.0, "qwen": 20000.0}
    calls = {"n": 0}

    async def runner(xml, motor_key):
        calls["n"] += 1
        if not succeed:
            return {"latency_ms": latency_by_motor.get(motor_key, 1000.0), "success": False}
        return {"latency_ms": latency_by_motor.get(motor_key, 1000.0), "success": True}

    return runner, calls


# ==========================================================================
# Dataset
# ==========================================================================

def test_benchmark_dataset_has_20_xmls():
    """Dataset completo tem 20 XMLs."""
    assert len(dataset_completo()) == 20


def test_benchmark_dataset_composition():
    """Composição: 10 válidos + 5 erros + 5 edge cases."""
    assert len(CATEGORIAS["valido"]) == 10
    assert len(CATEGORIAS["erro"]) == 5
    assert len(CATEGORIAS["edge"]) == 5


# ==========================================================================
# Estatísticas e targets
# ==========================================================================

def test_compute_stats_avg_and_p95():
    """compute_stats calcula média e p95 (nearest-rank) corretos."""
    lat = [1000.0] * 19 + [9000.0]  # p95 cai no valor máximo com n=20
    stats = bm.compute_stats(lat)

    assert stats["n"] == 20
    assert stats["avg_latency_ms"] == pytest.approx(1400.0)
    assert stats["p95_latency_ms"] == 9000.0


def test_evaluate_targets_glm_pass():
    """GLM com p95 < 5000ms atende o target."""
    assert bm.evaluate_targets({"p95_latency_ms": 4800.0}, 5000) is True


def test_evaluate_targets_qwen_pass():
    """Qwen com p95 < 21000ms atende o target."""
    assert bm.evaluate_targets({"p95_latency_ms": 20500.0}, 21000) is True


def test_evaluate_targets_fail_when_slow():
    """p95 acima do target não atende."""
    assert bm.evaluate_targets({"p95_latency_ms": 6000.0}, 5000) is False
    assert bm.evaluate_targets({"p95_latency_ms": None}, 5000) is False


# ==========================================================================
# Relatório do benchmark (com runner fake)
# ==========================================================================

@pytest.mark.asyncio
async def test_benchmark_report_completed_with_fake_runner(tmp_path):
    """Com motores disponíveis, relatório sai completed com resultados."""
    runner, _ = make_fake_runner({"glm": 4000.0, "qwen": 20000.0})
    report = await bm.run_benchmark(runner=runner, dataset=dataset_completo())

    assert report["status"] == "completed"
    assert report["dataset_size"] == 20
    assert report["results"]["glm"]["meets_target"] is True
    assert report["results"]["qwen"]["meets_target"] is True
    assert report["verdict"]["glm_meets_target"] is True
    assert report["verdict"]["qwen_meets_target"] is True


@pytest.mark.asyncio
async def test_benchmark_report_not_executed_when_unavailable(tmp_path):
    """Sem motores disponíveis, relatório é honesto: not_executed."""
    async def failing_runner(xml, motor_key):
        raise ConnectionError("provider offline")

    report = await bm.run_benchmark(runner=failing_runner, dataset=dataset_completo())

    assert report["status"] == "not_executed"
    assert "reason" in report
    assert "results" not in report  # nenhum número fabricado


def test_benchmark_report_file_created(tmp_path):
    """save_report grava JSON legível em disco."""
    out = tmp_path / "benchmark_result.json"
    bm.save_report({"status": "not_executed", "reason": "test"}, str(out))
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "not_executed"


def test_benchmark_report_valid_json(tmp_path):
    """Relatório completo é JSON válido com as chaves esperadas."""
    import asyncio as aio
    runner, _ = make_fake_runner({"glm": 4500.0, "qwen": 15000.0})
    report = aio.run(bm.run_benchmark(runner=runner, dataset=dataset_completo()))

    out = tmp_path / "r.json"
    bm.save_report(report, str(out))
    data = json.loads(out.read_text(encoding="utf-8"))

    for key in ["status", "generated_at", "dataset_size", "results", "verdict"]:
        assert key in data
    for key in ["motor", "avg_latency_ms", "p95_latency_ms", "success_rate_pct",
                "p95_target_ms", "meets_target"]:
        assert key in data["results"]["glm"]
