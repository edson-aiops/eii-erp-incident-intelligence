"""
Teste simples de saúde do Ollama - Sem escaping complicado
"""
from dotenv import load_dotenv
import os

# Força recarregar o .env
load_dotenv(override=True)

print("📦 Variáveis do .env:")
print(f"OLLAMA_MODEL: {os.getenv('OLLAMA_MODEL')}")
print(f"OLLAMA_BASE_URL: {os.getenv('OLLAMA_BASE_URL')}")

from smartrouter.smart_router import SmartRouter

print("\n🔄 Criando SmartRouter...")
router = SmartRouter(lgpd_mode=True)

print(f"✅ Modelo no adapter: {router.local_adapter.model}")

health = router.local_adapter.check_health()
print(f"✅ Ollama disponível: {health}")

if health:
    print("\n🎉 SUCESSO! Ollama está pronto para uso LGPD!")
else:
    print(f"\n⚠️  Health check falhou, mas vamos testar uma chamada real...")
    # Tenta uma chamada real mesmo com health=False
    try:
        result = router.local_adapter.supervise_task("Teste", {})
        print("✅ Chamada real funcionou! Pode usar normalmente.")
    except Exception as e:
        print(f"❌ Chamada também falhou: {e}")