#!/usr/bin/env python3
"""
EII — Secure Secrets Manager
Gerencia API keys e credenciais sensíveis usando Windows Credential Manager

Uso:
    python secure_secrets.py set <KEY_NAME> <VALUE>
    python secure_secrets.py get <KEY_NAME>
    python secure_secrets.py list
    python secure_secrets.py delete <KEY_NAME>
    python secure_secrets.py migrate-env  # Migra do .env para Credential Manager

Exemplo:
    python secure_secrets.py set GROQ_API_KEY "gsk_abc123..."
    python secure_secrets.py get GROQ_API_KEY
"""

import sys
import os
import keyring
import argparse
from pathlib import Path
from dotenv import dotenv_values

# Configurações do EII
SERVICE_NAME = "EII_Project"
ENV_FILE = Path(__file__).parent / ".env"

# Keys que devem ser migradas/gerenciadas
EII_SECRETS = [
    "GROQ_API_KEY",
    "QWEN_API_KEY", 
    "CEREBRAS_API_KEY",
    "GOOGLE_AI_API_KEY",
    "MOONSHOT_API_KEY",
    "MISTRAL_API_KEY",
    "ANTHROPIC_API_KEY",
    "QDRANT_API_KEY",
    "LANGCHAIN_API_KEY",
    "EII_ADMIN_PASS",  # Senha da UI
]


def set_secret(key_name: str, value: str) -> bool:
    """
    Armazena um secret no Windows Credential Manager
    
    Args:
        key_name: Nome da chave (ex: "GROQ_API_KEY")
        value: Valor do secret
        
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        keyring.set_password(SERVICE_NAME, key_name, value)
        print(f"✅ Secret '{key_name}' armazenado com sucesso no Windows Credential Manager!")
        return True
    except Exception as e:
        print(f"❌ Erro ao armazenar '{key_name}': {type(e).__name__}: {e}")
        return False


def get_secret(key_name: str, silent: bool = False) -> str | None:
    """
    Recupera um secret do Windows Credential Manager
    
    Args:
        key_name: Nome da chave
        silent: Se True, não imprime erros
        
    Returns:
        str | None: Valor do secret ou None se não encontrado
    """
    try:
        value = keyring.get_password(SERVICE_NAME, key_name)
        if value is None and not silent:
            print(f"⚠️  Secret '{key_name}' não encontrado no Credential Manager")
        return value
    except Exception as e:
        if not silent:
            print(f"❌ Erro ao recuperar '{key_name}': {type(e).__name__}: {e}")
        return None


def list_secrets() -> list[str]:
    """
    Lista todos os secrets do EII armazenados
    
    Returns:
        list[str]: Nomes das chaves encontradas
    """
    found = []
    print(f"🔍 Buscando secrets para o serviço: {SERVICE_NAME}")
    print("-" * 60)
    
    for key in EII_SECRETS:
        value = get_secret(key, silent=True)
        if value is not None:
            # Mostra apenas os primeiros 10 chars + ... para segurança
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"✅ {key}: {masked}")
            found.append(key)
        else:
            print(f"⚪ {key}: não configurado")
    
    print("-" * 60)
    print(f"📊 Total: {len(found)}/{len(EII_SECRETS)} secrets configurados")
    return found


def delete_secret(key_name: str) -> bool:
    """
    Remove um secret do Credential Manager
    
    Args:
        key_name: Nome da chave
        
    Returns:
        bool: True se sucesso
    """
    try:
        # keyring não tem método delete padrão, então definimos como None
        keyring.set_password(SERVICE_NAME, key_name, "")
        print(f"✅ Secret '{key_name}' removido com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao remover '{key_name}': {type(e).__name__}: {e}")
        return False


def migrate_from_env(dry_run: bool = False) -> dict:
    """
    Migra secrets do arquivo .env para o Credential Manager
    
    Args:
        dry_run: Se True, apenas mostra o que seria feito sem executar
        
    Returns:
        dict: Estatísticas da migração
    """
    if not ENV_FILE.exists():
        print(f"❌ Arquivo .env não encontrado em: {ENV_FILE}")
        return {"migrated": 0, "skipped": 0, "errors": 0}
    
    print(f"📦 Lendo secrets de: {ENV_FILE}")
    env_vars = dotenv_values(ENV_FILE)
    
    stats = {"migrated": 0, "skipped": 0, "errors": 0, "not_found": 0}
    
    for key in EII_SECRETS:
        value = env_vars.get(key)
        
        if not value or value in ("", "chave_key", "placeholder", "mude_esta_senha_urgente_123"):
            stats["not_found"] += 1
            print(f"⚪ {key}: não encontrado ou é placeholder no .env")
            continue
        
        if dry_run:
            print(f"🔍 [DRY RUN] Migraria: {key} = {value[:10]}...")
            stats["migrated"] += 1
            continue
        
        if set_secret(key, value):
            stats["migrated"] += 1
        else:
            stats["errors"] += 1
    
    return stats


def get_eii_llm_config() -> dict:
    """
    Helper para usar no app.py: carrega configs com fallback Credential Manager → .env
    
    Returns:
        dict: Configurações dos LLMs com secrets resolvidos
    """
    config = {}
    
    for key in EII_SECRETS:
        # Tenta Credential Manager primeiro
        value = get_secret(key, silent=True)
        
        # Fallback para .env se não encontrado
        if value is None and ENV_FILE.exists():
            env_vars = dotenv_values(ENV_FILE)
            value = env_vars.get(key)
        
        if value:
            config[key] = value
    
    return config


# ─────────────────────────────────────────────────────────────────────────────
# CLI Interface
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="EII Secure Secrets Manager — Windows Credential Manager Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s set GROQ_API_KEY "gsk_abc123..."
  %(prog)s get GROQ_API_KEY
  %(prog)s list
  %(prog)s migrate-env --dry-run
  %(prog)s delete GROQ_API_KEY
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")
    
    # set
    set_parser = subparsers.add_parser("set", help="Armazenar um secret")
    set_parser.add_argument("key", help="Nome da chave (ex: GROQ_API_KEY)")
    set_parser.add_argument("value", help="Valor do secret")
    
    # get
    get_parser = subparsers.add_parser("get", help="Recuperar um secret")
    get_parser.add_argument("key", help="Nome da chave")
    
    # list
    subparsers.add_parser("list", help="Listar todos os secrets configurados")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="Remover um secret")
    delete_parser.add_argument("key", help="Nome da chave")
    
    # migrate-env
    migrate_parser = subparsers.add_parser("migrate-env", help="Migrar secrets do .env para Credential Manager")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Apenas simular, não aplicar mudanças")
    
    args = parser.parse_args()
    
    if args.command == "set":
        success = set_secret(args.key, args.value)
        sys.exit(0 if success else 1)
        
    elif args.command == "get":
        value = get_secret(args.key)
        if value:
            print(value)  # Output limpo para uso em scripts
            sys.exit(0)
        else:
            sys.exit(1)
            
    elif args.command == "list":
        found = list_secrets()
        sys.exit(0 if found else 1)
        
    elif args.command == "delete":
        success = delete_secret(args.key)
        sys.exit(0 if success else 1)
        
    elif args.command == "migrate-env":
        print(f"{'[DRY RUN] ' if args.dry_run else ''}🔄 Migrando secrets do .env para Credential Manager...")
        print("=" * 70)
        
        stats = migrate_from_env(dry_run=args.dry_run)
        
        print("=" * 70)
        print(f"📊 Resultado: {stats['migrated']} migrados, {stats['not_found']} não encontrados, {stats['errors']} erros")
        
        if not args.dry_run and stats["migrated"] > 0:
            print("\n💡 Próximo passo: Remova as keys do .env para maior segurança:")
            print(f"   # Edite {ENV_FILE} e substitua valores por:")
            print(f"   GROQ_API_KEY=${{GROQ_API_KEY}}  # ou apenas comente a linha")
        
        sys.exit(0 if stats["errors"] == 0 else 1)
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()