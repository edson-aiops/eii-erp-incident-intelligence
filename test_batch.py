"""
Teste do Batch Processor com SmartRouter LGPD
"""

import os
from pathlib import Path
from batch_processor import process_batch, BatchProcessor

# Caminhos dos arquivos de teste
TEST_DIR = Path("tests/batch_samples")
xml_files = [
    str(TEST_DIR / "inc_001_public.xml"),
    str(TEST_DIR / "inc_002_pii.xml"),
    str(TEST_DIR / "inc_003_error.xml"),
]
incident_ids = ["TEST-PUB-001", "TEST-PII-002", "TEST-ERR-003"]

print("=" * 70)
print("📦 TESTE BATCH PROCESSOR + SMARTROUTER LGPD")
print("=" * 70)

# Callback simples para progresso
def progress_callback(completed: int, total: int, result):
    status = "✅" if result.success else "❌"
    route = result.route_used or "unknown"
    print(f"  [{completed}/{total}] {status} {result.incident_id:15} → {route:12} ({result.latency_ms:.0f}ms)")

# Executar batch
print("\n🚀 Processando lote...")
output = process_batch(
    xml_files=xml_files,
    incident_ids=incident_ids,
    max_workers=2,  # Poucos workers para teste
    mentor_mode=False,
    output_path="tests/batch_results.json",
    progress_callback=progress_callback
)

# Mostrar estatísticas
print("\n📊 Estatísticas do Batch:")
print("-" * 40)
stats = output["stats"]
summary = output["summary"]

print(f"✅ Sucesso: {summary['successful']}/{summary['total']} ({summary['successful']/summary['total']*100:.1f}%)")
print(f"🌐 Cloud calls: {stats['cloud_calls']} ({summary['cloud_ratio']}%)")
print(f"🛡️ Local calls: {stats['local_calls']} ({summary['local_ratio']}%)")
print(f"🔍 PII detectados: {stats['pii_detected']}")
print(f"📦 Cache hits: {stats['cache_hits']} ({stats['cache_hit_rate_percent']}%)")
print(f"⏱️  Latência média: {stats['avg_latency_ms']:.0f}ms")
print(f"🚀 Throughput: {stats['throughput_per_second']:.2f} itens/s")
print(f"🛡️  LGPD compliant: {summary['lgpd_compliant_count']} itens")

# Mostrar resultados individuais
print("\n📋 Resultados Individuais:")
print("-" * 40)
for r in output["results"]:
    print(f"{r['incident_id']}: {'✅' if r['success'] else '❌'} route={r['route_used']}, pii={r['pii_detected']}")

print("\n" + "=" * 70)
print("🎉 TESTE CONCLUÍDO!")
print("=" * 70)