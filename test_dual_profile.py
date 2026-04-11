"""
Teste do SmartRouter Dual-Profile: Cloud vs Local (LGPD)
Versão robusta: protege contra erros de API e fallback
"""

import os
from dotenv import load_dotenv
from smartrouter.smart_router import SmartRouter
from smartrouter.pii_detector import contains_pii, get_pii_summary

load_dotenv()

print("=" * 60)
print("🔐 TESTE SMARTROUTER DUAL-PROFILE (LGPD + CLOUD)")
print("=" * 60)

router = SmartRouter(lgpd_mode=True, auto_detect_pii=True)

def safe_print_result(result: dict, test_name: str):
    """Imprime resultado com proteção contra erros"""
    print(f"\n{test_name}")
    print("-" * 40)
    
    if not result.get("success", True):
        print(f"❌ Erro: {result.get('error', 'Unknown error')}")
        print(f"🔄 Rota tentada: {result.get('_meta', {}).get('route', 'unknown')}")
        return False
    
    meta = result.get("_meta", {})
    print(f"✅ Rota usada: {meta.get('route', 'unknown')}")
    print(f"✅ PII detectado: {meta.get('pii_detected', 'N/A')}")
    print(f"⏱️  Latência: {meta.get('latency_ms', 0):.0f}ms")
    if meta.get('provider') or meta.get('llm'):
        print(f"📦 Provider/Model: {meta.get('provider') or meta.get('llm')}")
    return True

# Teste 1: Dado PÚBLICO (deve ir para Cloud/Groq)
print("\n🌐 Teste 1: Dado Público (sem PII)")
public_task = "Liste 3 etapas para analisar logs de erro do sistema."
try:
    result1 = router.call(public_task, context={"type": "log_analysis"})
    safe_print_result(result1, "Resultado:")
except Exception as e:
    print(f"❌ Exceção no teste 1: {e}")

# Teste 2: Dado SENSÍVEL (deve ir para Local/Ollama)
print("\n🛡️ Teste 2: Dado Sensível (com CPF/NIS)")
sensitive_task = "Analise o incidente do funcionário CPF 123.456.789-00 e NIS 98765432101."
try:
    result2 = router.call(sensitive_task, context={"employee": "sensível"})
    safe_print_result(result2, "Resultado:")
except Exception as e:
    print(f"❌ Exceção no teste 2: {e}")

# Teste 3: Forçar Cloud (mesmo com PII)
print("\n⚠️ Teste 3: Forçar Cloud (force_cloud=True)")
try:
    result3 = router.call(sensitive_task, context={}, force_cloud=True)
    safe_print_result(result3, "Resultado:")
except Exception as e:
    print(f"❌ Exceção no teste 3: {e}")

# Teste 4: Estatísticas Finais
print("\n📊 Teste 4: Estatísticas de Roteamento")
print("-" * 40)
try:
    stats = router.get_routing_stats()
    print(f"🌐 Cloud calls: {stats['routing']['cloud_calls']}")
    print(f"🛡️ Local calls: {stats['routing']['local_calls']}")
    print(f"🔍 PII detectados: {stats['routing']['pii_detected']}")
    print(f"🔄 Fallbacks: {stats['routing']['fallbacks']}")
    print(f"📦 Cache hit rate: {stats['cache']['metrics']['hit_rate_percent']}%")
except Exception as e:
    print(f"⚠️  Não foi possível obter stats: {e}")

# Teste 5: Verificar Ollama Health
print("\n🏥 Teste 5: Health Check Ollama")
print("-" * 40)
try:
    ollama_health = router.local_adapter.check_health()
    print(f"✅ Ollama rodando: {ollama_health}")
except Exception as e:
    print(f"❌ Health check falhou: {e}")

print("\n" + "=" * 60)
print("🎉 TESTES CONCLUÍDOS!")
print("=" * 60)
print("\n💡 Resumo:")
print("- Dados públicos → Cloud (Groq) ⚡")
print("- Dados com PII → Local (Ollama) 🛡️")
print("- Cache compartilhado entre ambos")
print("- Fallback automático se um provedor falhar")