import os
from dotenv import load_dotenv
from smartrouter import QwenAdapter

load_dotenv()

print("🚀 Teste MÍNIMO de conexão...")
adapter = QwenAdapter()

# Prompt SUPER simples - apenas para validar que funciona
result = adapter.supervise_task(
    task="Diga olá em JSON.",
    context={},
    output_format="json"
)

print("✅ Funcionou!")
print(result)