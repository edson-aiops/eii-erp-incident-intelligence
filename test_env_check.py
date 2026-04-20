"""
Teste simples de variáveis de ambiente - Sem escaping complicado
"""
from dotenv import load_dotenv
import os

# Força recarregar o .env
load_dotenv(override=True)

print("🔍 Verificando variáveis do .env:")
print("-" * 40)

# Verifica QWEN_* (suas variáveis originais)
qwen_key = os.getenv("QWEN_API_KEY")
print(f"QWEN_API_KEY: {'✅' if qwen_key else '❌'}")

# Verifica GROQ_* (aliases para compatibilidade)
groq_key = os.getenv("GROQ_API_KEY")
print(f"GROQ_API_KEY: {'✅' if groq_key else '❌'}")

# Verifica Ollama
ollama_model = os.getenv("OLLAMA_MODEL")
print(f"OLLAMA_MODEL: {ollama_model}")

# Verifica LGPD
lgpd_mode = os.getenv("LGPD_MODE")
print(f"LGPD_MODE: {lgpd_mode}")

print("-" * 40)
if groq_key and ollama_model:
    print("🎉 Configuração OK! Cloud + Local prontos.")
else:
    print("⚠️  Alguma variável faltando - revise o .env")