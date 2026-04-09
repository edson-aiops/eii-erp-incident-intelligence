"""
Teste Final da Integração Qwen - SmartRouter-EII
"""
import os
from dotenv import load_dotenv
from smartrouter import QwenAdapter

# 1. Carrega as variáveis do arquivo .env
print("🔄 Carregando variáveis de ambiente do .env...")
load_dotenv()

api_key = os.getenv("QWEN_API_KEY")
if not api_key or "substitua" in api_key:
    print("❌ Erro: A QWEN_API_KEY no arquivo .env parece inválida ou não foi alterada.")
    print("💡 Dica: Edite o arquivo .env e coloque sua chave real.")
    exit()

print("✅ QWEN_API_KEY carregada com sucesso.")

try:
    print("\n🚀 Inicializando QwenAdapter...")
    adapter = QwenAdapter()
    
    print("🧪 Enviando tarefa de teste (Supervisão)...")
    result = adapter.supervise_task(
        task="Criar um plano simples para diagnosticar um erro de login no sistema.",
        context={"project": "EII", "test": True}
    )
    
    print("\n🎉 SUCESSO! O Qwen respondeu:")
    print("-" * 50)
    print(f"Plano gerado com {len(result.get('plan', []))} etapas.")
    print(f"Regras de validação: {len(result.get('validation_rules', []))}")
    print("-" * 50)
    print("Resultado JSON:")
    print(result)
    
except Exception as e:
    print(f"\n❌ ERRO DURANTE O TESTE:")
    print(e)