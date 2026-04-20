"""
Teste do Sistema de Cache - SmartRouter
Valida: Hit/Miss, TTL, Métricas, Eviction LRU
"""

import os
import time
from dotenv import load_dotenv
from smartrouter import QwenAdapter
from smartrouter.cache import get_cache, TTLCache, CacheMetrics

load_dotenv()

print("=" * 60)
print("🧪 TESTE DO SISTEMA DE CACHE")
print("=" * 60)

# Teste 1: Cache básico de tarefas
print("\n📦 Teste 1: Cache Hit/Miss")
print("-" * 40)

adapter = QwenAdapter()

# Primeira chamada (cache miss)
print("\n1️⃣ Primeira chamada (deve ser MISS):")
start = time.time()
result1 = adapter.supervise_task(
    task="Liste 3 passos para diagnosticar erro de login",
    context={"test": True}
)
elapsed1 = time.time() - start
print(f"   ⏱️  Tempo: {elapsed1:.2f}s")
print(f"   📊 Cache hit: {result1.get('_meta', {}).get('cache_hit', 'N/A')}")

# Mesma chamada (deve ser HIT)
print("\n2️⃣ Mesma chamada (deve ser HIT - instantâneo):")
start = time.time()
result2 = adapter.supervise_task(
    task="Liste 3 passos para diagnosticar erro de login",
    context={"test": True}
)
elapsed2 = time.time() - start
print(f"   ⏱️  Tempo: {elapsed2:.2f}s")
print(f"   📊 Cache hit: {result2.get('_meta', {}).get('cache_hit', 'N/A')}")

speedup = elapsed1 / elapsed2 if elapsed2 > 0 else 0
print(f"   🚀 Speedup: {speedup:.1f}x mais rápido!")

# Teste 2: Diferentes contextos (cache miss)
print("\n3️⃣ Contexto diferente (deve ser MISS):")
start = time.time()
result3 = adapter.supervise_task(
    task="Liste 3 passos para diagnosticar erro de login",
    context={"test": False, "error_code": "E428"}  # Contexto diferente!
)
elapsed3 = time.time() - start
print(f"   ⏱️  Tempo: {elapsed3:.2f}s")
print(f"   📊 Cache hit: {result3.get('_meta', {}).get('cache_hit', 'N/A')}")

# Teste 3: Métricas do cache
print("\n📈 Teste 2: Métricas do Cache")
print("-" * 40)

stats = adapter.supervise_task.cache_stats()
print(f"   📦 Tamanho do cache: {stats['size']} items")
print(f"   🎯 Taxa de acerto: {stats['metrics']['hit_rate_percent']}%")
print(f"   ✅ Hits: {stats['metrics']['hits']}")
print(f"   ❌ Misses: {stats['metrics']['misses']}")
print(f"   🔄 Evictions: {stats['metrics']['evictions']}")

# Teste 4: Cache singleton global
print("\n🌐 Teste 3: Cache Global Singleton")
print("-" * 40)

cache1 = get_cache()
cache2 = get_cache()

print(f"   🔑 Mesma instância? {cache1 is cache2}")
print(f"   📊 Stats globais: {cache1.get_stats()}")

# Teste 5: TTL (Time-To-Live)
print("\n⏰ Teste 4: TTL (Time-To-Live)")
print("-" * 40)

print("   Criando cache com TTL de 2 segundos para teste...")
short_cache = TTLCache(max_size=100, ttl_seconds=2)

key = short_cache._make_key("test_ttl")
short_cache.set(key, {"data": "temporary"})

print("   ✅ Item armazenado")
print(f"   📥 Get imediato: {short_cache.get(key) is not None}")

print("   ⏳ Aguardando 3 segundos (TTL = 2s)...")
time.sleep(3)

print(f"   📥 Get após TTL: {short_cache.get(key) is not None} (deve ser False)")

# Teste 6: Eviction LRU
print("\n🗑️ Teste 5: LRU Eviction")
print("-" * 40)

small_cache = TTLCache(max_size=3, ttl_seconds=3600)

print("   Adicionando 3 items (max_size=3)...")
small_cache.set("key1", "value1")
small_cache.set("key2", "value2")
small_cache.set("key3", "value3")
print(f"   📦 Tamanho: {len(small_cache._cache)}")

print("   Adicionando 4º item (deve evictar 'key1')...")
small_cache.set("key4", "value4")
print(f"   📦 Tamanho: {len(small_cache._cache)}")
print(f"   ✅ 'key1' removido: {'key1' not in small_cache._cache}")
print(f"   ✅ 'key2' ainda existe: {'key2' in small_cache._cache}")

# Teste 7: Limpar cache
print("\n🧹 Teste 6: Limpar Cache")
print("-" * 40)

print(f"   Tamanho antes: {len(small_cache._cache)}")
small_cache.clear()
print(f"   Tamanho após clear: {len(small_cache._cache)}")

# Resumo final
print("\n" + "=" * 60)
print(" RESUMO DOS TESTES")
print("=" * 60)

final_stats = adapter.supervise_task.cache_stats()
print(f"✅ Cache funcional: {'✓' if final_stats['size'] > 0 else '✗'}")
print(f"✅ Hit rate: {final_stats['metrics']['hit_rate_percent']}%")
print(f"✅ Speedup médio: {speedup:.1f}x")
print(f"✅ TTL funcional: {'✓' if short_cache.get(key) is None else '✗'}")
print(f"✅ LRU eviction: {'✓' if 'key1' not in small_cache._cache else '✗'}")

print("\n💡 Dica: Use estas métricas em produção para monitorar eficiência!")
print("   adapter.supervise_task.cache_stats() retorna stats completos")