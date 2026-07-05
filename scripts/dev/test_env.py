# test_env.py
from dotenv import load_dotenv
import os

load_dotenv()  # Carrega .env

print("🔍 Variáveis carregadas:")
print(f"EII_ADMIN_USER: {os.getenv('EII_ADMIN_USER', '❌ NÃO DEFINIDO')}")
print(f"EII_ADMIN_PASS: {'✅ DEFINIDO' if os.getenv('EII_ADMIN_PASS') else '❌ NÃO DEFINIDO'}")
print(f"GROQ_API_KEY: {'✅ DEFINIDO' if os.getenv('GROQ_API_KEY') else '❌ NÃO DEFINIDO'}")
print(f"OLLAMA_MODEL: {os.getenv('OLLAMA_MODEL', '❌ NÃO DEFINIDO')}")