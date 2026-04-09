import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("QWEN_API_KEY")
base_url = os.getenv("QWEN_BASE_URL", "https://api.aimlapi.com/v1")
model = os.getenv("QWEN_MODEL", "qwen-2.5-72b-instruct")

print(f"🔍 Testando conexão com:")
print(f"   URL: {base_url}")
print(f"   Model: {model}")
print(f"   API Key: {api_key[:10]}...")

try:
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # Teste 1: Listar modelos disponíveis (se a API suportar)
    print("\n📋 Tentando listar modelos...")
    try:
        models = client.models.list()
        model_names = [m.id for m in models.data[:10]]
        print(f"✅ Modelos disponíveis: {model_names}")
        if model not in model_names:
            print(f"⚠️  AVISO: Seu modelo '{model}' NÃO está na lista acima!")
    except Exception as e:
        print(f"ℹ️  Listagem de modelos não suportada: {e}")
    
    # Teste 2: Chamada simples de chat
    print(f"\n💬 Testando chamada de chat com modelo: {model}")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello, test!"}],
        max_tokens=50
    )
    
    print(f"✅ SUCESSO! Resposta: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"\n❌ ERRO:")
    print(f"   Tipo: {type(e).__name__}")
    print(f"   Mensagem: {e}")
    
    # Se for NotFoundError, dar dicas específicas
    if "NotFoundError" in str(type(e)):
        print(f"\n💡 DICAS para NotFoundError:")
        print(f"   1. Verifique se o nome do modelo está EXATO como na docs do provedor")
        print(f"   2. Tente: qwen-2.5-72b-instruct (AIMLAPI) ou Qwen/Qwen2.5-72B-Instruct (Together)")
        print(f"   3. Confirme se sua chave é do mesmo provedor da URL base")