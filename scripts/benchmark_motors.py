"""
A7/A8: Benchmark GLM-5.3 vs Qwen 14B

Mede latência (avg/p95) e taxa de sucesso dos dois motores sobre o dataset
sintético de 20 XMLs e compara com os design targets:

- GLM-5.3 (remoto): latência alvo < 5000ms p95
- Qwen 14B (local):  latência alvo < 21000ms p95

HONESTIDADE DE MEDIÇÃO: se os provedores não estão disponíveis no ambiente
(sem chave OpenRouter, sem Ollama local), o relatório sai com
status="not_executed" e o motivo — NUNCA com números fabricados.

O runner é injetável: os testes usam um runner fake com latências
determinísticas; a execução real usa o pipeline Deep Agents.

Executar (da raiz do repo):
    python scripts/benchmark_motors.py --output benchmark_result.json
"""

import os
import sys
import json
import time
import asyncio
import argparse
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests")))

from fixtures.esocial_benchmark_dataset import dataset_completo, CATEGORIAS

TARGETS = {
    "glm":  {"label": "GLM-5.3 (OpenRouter)", "p95_latency_ms": 5000},
    "qwen": {"label": "Qwen 14B (Ollama local)", "p95_latency_ms": 21000},
}


# ==========================================================================
# Estatísticas e avaliação de targets (funções puras — testáveis)
# ==========================================================================

def compute_stats(latencies_ms: list) -> dict:
    """avg e p95 de uma lista de latências. p95 por nearest-rank."""
    if not latencies_ms:
        return {"avg_latency_ms": None, "p95_latency_ms": None, "n": 0}
    ordered = sorted(latencies_ms)
    p95_idx = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "avg_latency_ms": round(sum(ordered) / len(ordered), 2),
        "p95_latency_ms": round(ordered[p95_idx], 2),
        "n": len(ordered),
    }


def evaluate_targets(stats: dict, target_ms: int) -> bool:
    """True se p95 dentro do target (ou sem dados -> False)."""
    return stats.get("p95_latency_ms") is not None and stats["p95_latency_ms"] < target_ms


# ==========================================================================
# Runner real (pipeline Deep Agents) — com detecção de indisponibilidade
# ==========================================================================

async def _real_runner(xml: str, motor_key: str) -> dict:
    """Executa um diagnóstico real e mede latência."""
    from src.deep_agents_wrapper import diagnose_incident_deep_agents

    force_local = motor_key == "qwen"
    incident_id = f"bench_{motor_key}_{int(time.time() * 1000)}"
    start = time.time()
    result = await diagnose_incident_deep_agents(
        xml=xml, incident_id=incident_id, force_local=force_local,
    )
    latency_ms = (time.time() - start) * 1000

    diagnostico = result.get("diagnostico", "")
    success = bool(diagnostico) and "Erro" not in diagnostico[:30]
    return {"latency_ms": latency_ms, "success": success}


async def check_availability(runner) -> dict:
    """Proba cada motor com um XML simples; retorna disponibilidade."""
    disponiveis = {}
    for key in TARGETS:
        try:
            probe = await runner(CATEGORIAS["valido"][0], key)
            disponiveis[key] = probe["success"]
        except Exception:
            disponiveis[key] = False
    return disponiveis


# ==========================================================================
# Benchmark
# ==========================================================================

async def run_benchmark(runner=None, dataset=None) -> dict:
    """Roda o benchmark completo. Runner injetável (testes usam fake)."""
    runner = runner or _real_runner
    dataset = dataset if dataset is not None else dataset_completo()

    availability = await check_availability(runner)
    if not any(availability.values()):
        return {
            "status": "not_executed",
            "generated_at": datetime.now().isoformat(),
            "dataset_size": len(dataset),
            "reason": "Nenhum motor disponível neste ambiente "
                      "(sem chave OpenRouter e/ou Ollama local). "
                      "Regenerar em ambiente com os provedores configurados.",
            "availability": {TARGETS[k]["label"]: v for k, v in availability.items()},
            "targets": {k: v["p95_latency_ms"] for k, v in TARGETS.items()},
        }

    per_motor = {k: {"latencies": [], "successes": 0, "executed": 0}
                 for k, v in availability.items() if v}

    for i, xml in enumerate(dataset):
        for key, avail in availability.items():
            if not avail:
                continue
            try:
                r = await runner(xml, key)
            except Exception:
                r = {"latency_ms": None, "success": False}
            if r.get("latency_ms") is not None:
                per_motor[key]["latencies"].append(r["latency_ms"])
                per_motor[key]["executed"] += 1
                per_motor[key]["successes"] += int(bool(r.get("success")))

    results = {}
    for key, agg in per_motor.items():
        stats = compute_stats(agg["latencies"])
        success_rate = (
            round(100.0 * agg["successes"] / agg["executed"], 2)
            if agg["executed"] else None
        )
        results[key] = {
            "motor": TARGETS[key]["label"],
            **stats,
            "success_rate_pct": success_rate,
            "p95_target_ms": TARGETS[key]["p95_latency_ms"],
            "meets_target": evaluate_targets(stats, TARGETS[key]["p95_latency_ms"]),
        }

    return {
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "dataset_size": len(dataset),
        "availability": {TARGETS[k]["label"]: v for k, v in availability.items()},
        "results": results,
        "verdict": {
            "glm_meets_target": results.get("glm", {}).get("meets_target", False),
            "qwen_meets_target": results.get("qwen", {}).get("meets_target", False),
        },
    }


def save_report(report: dict, output_file: str) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"✅ Relatório salvo: {output_file}")
    print(f"   status: {report['status']}")
    if report["status"] == "completed":
        for key, r in report.get("results", {}).items():
            print(f"   {r['motor']}: p95={r['p95_latency_ms']}ms "
                  f"(target <{r['p95_target_ms']}ms) -> "
                  f"{'✅' if r['meets_target'] else '❌'}")
    else:
        print(f"   motivo: {report['reason']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A7/A8: Benchmark GLM-5.3 vs Qwen 14B")
    parser.add_argument("--output", default="benchmark_result.json", help="Arquivo de saída (JSON)")
    args = parser.parse_args()

    report = asyncio.run(run_benchmark())
    save_report(report, args.output)
