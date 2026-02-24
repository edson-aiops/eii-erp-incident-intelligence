#!/usr/bin/env python3
"""
EII — Validação da Fase 1: Fundação
====================================
Verifica se a estrutura do projeto está correta e pronta
para ser enviada ao HuggingFace Spaces.

Uso:
    python validate_phase1.py

Todos os checks devem estar ✅ antes de avançar para a Fase 2.
"""

import os
import sys
import ast
import subprocess

# ── Cores ────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = []
failed = []

def ok(check: str, detail: str = ""):
    msg = f"  ✅ {check}"
    if detail:
        msg += f" — {detail}"
    print(f"{GREEN}{msg}{RESET}")
    passed.append(check)

def fail(check: str, detail: str = ""):
    msg = f"  ❌ {check}"
    if detail:
        msg += f"\n     {YELLOW}→ {detail}{RESET}"
    print(f"{RED}{msg}{RESET}")
    failed.append(check)

def header(title: str):
    print(f"\n{BOLD}{'═' * 55}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'═' * 55}{RESET}")

def info(msg: str):
    print(f"  {BLUE}ℹ  {msg}{RESET}")

# ════════════════════════════════════════════════════════════════
# CHECK 1 — Estrutura de Arquivos
# ════════════════════════════════════════════════════════════════
def check_file_structure():
    header("CHECK 1 — Estrutura de Arquivos")

    required_files = [
        ("Dockerfile",           "Necessário para HuggingFace Spaces"),
        ("requirements.txt",     "Dependências Python"),
        ("README.md",            "Metadados do HuggingFace Spaces"),
        (".gitignore",           "Protege .env de ser commitado"),
        ("app/main.py",          "Aplicação principal Gradio"),
    ]

    required_dirs = [
        ("app/",   "Código da aplicação"),
        ("data/",  "Knowledge base (usada a partir da Fase 2)"),
    ]

    for path, desc in required_dirs:
        if os.path.isdir(path):
            ok(f"Diretório: {path}", desc)
        else:
            fail(f"Diretório ausente: {path}", f"Crie com: mkdir -p {path}")

    for path, desc in required_files:
        if os.path.isfile(path):
            ok(f"Arquivo: {path}", desc)
        else:
            fail(f"Arquivo ausente: {path}", desc)

# ════════════════════════════════════════════════════════════════
# CHECK 2 — README com Metadados HuggingFace
# ════════════════════════════════════════════════════════════════
def check_readme():
    header("CHECK 2 — README (Metadados HuggingFace Spaces)")

    if not os.path.isfile("README.md"):
        fail("README.md não encontrado")
        return

    with open("README.md") as f:
        content = f.read()

    required_fields = ["sdk: docker", "title:", "emoji:", "colorFrom:"]
    for field in required_fields:
        if field in content:
            ok(f"Campo HF: '{field}'")
        else:
            fail(f"Campo ausente: '{field}'", "Necessário no cabeçalho YAML do README.md")

# ════════════════════════════════════════════════════════════════
# CHECK 3 — Sintaxe Python
# ════════════════════════════════════════════════════════════════
def check_python_syntax():
    header("CHECK 3 — Sintaxe Python")

    py_files = []
    for root, _, files in os.walk("app"):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        fail("Nenhum arquivo .py encontrado em app/")
        return

    for py_file in py_files:
        try:
            with open(py_file) as f:
                source = f.read()
            ast.parse(source)
            ok(f"Sintaxe válida: {py_file}")
        except SyntaxError as e:
            fail(f"Erro de sintaxe: {py_file}", f"Linha {e.lineno}: {e.msg}")

# ════════════════════════════════════════════════════════════════
# CHECK 4 — Dockerfile
# ════════════════════════════════════════════════════════════════
def check_dockerfile():
    header("CHECK 4 — Dockerfile")

    if not os.path.isfile("Dockerfile"):
        fail("Dockerfile não encontrado")
        return

    with open("Dockerfile") as f:
        content = f.read()

    checks = {
        "FROM python:":         "Imagem base Python",
        "EXPOSE 7860":          "Porta obrigatória HuggingFace Spaces",
        "COPY requirements.txt": "Copia dependências",
        "pip install":          "Instala dependências",
        "CMD":                  "Comando de inicialização",
    }

    for pattern, desc in checks.items():
        if pattern in content:
            ok(f"Dockerfile: {desc}")
        else:
            fail(f"Dockerfile: ausente — {desc}", f"Adicione '{pattern}' ao Dockerfile")

# ════════════════════════════════════════════════════════════════
# CHECK 5 — requirements.txt
# ════════════════════════════════════════════════════════════════
def check_requirements():
    header("CHECK 5 — requirements.txt")

    if not os.path.isfile("requirements.txt"):
        fail("requirements.txt não encontrado")
        return

    with open("requirements.txt") as f:
        content = f.read()

    phase1_deps = ["gradio", "langchain", "langgraph", "chromadb", "langfuse", "ragas"]
    for dep in phase1_deps:
        if dep in content:
            ok(f"Dependência presente: {dep}")
        else:
            fail(f"Dependência ausente: {dep}", f"Adicione ao requirements.txt")

# ════════════════════════════════════════════════════════════════
# CHECK 6 — .gitignore protege .env
# ════════════════════════════════════════════════════════════════
def check_gitignore():
    header("CHECK 6 — Segurança (.gitignore)")

    if not os.path.isfile(".gitignore"):
        fail(".gitignore não encontrado", "Crie para proteger suas chaves de API")
        return

    with open(".gitignore") as f:
        content = f.read()

    if ".env" in content:
        ok(".env está no .gitignore", "Chaves de API protegidas")
    else:
        fail(".env não está no .gitignore", "RISCO: chaves de API podem ser expostas no git")

# ════════════════════════════════════════════════════════════════
# RESULTADO FINAL
# ════════════════════════════════════════════════════════════════
def print_summary():
    total  = len(passed) + len(failed)
    header("RESULTADO — Fase 1")

    print(f"\n  Checks executados: {total}")
    print(f"  {GREEN}✅ Aprovados: {len(passed)}{RESET}")
    print(f"  {RED}❌ Falhos:    {len(failed)}{RESET}")

    if not failed:
        print(f"""
{GREEN}{BOLD}  ╔══════════════════════════════════════════════╗
  ║   FASE 1 CONCLUÍDA — Pronto para o deploy!  ║
  ╚══════════════════════════════════════════════╝{RESET}
""")
        print("  📋 Próximos passos:\n")
        steps = [
            ("1", "Criar conta gratuita em groq.com", "Obter GROQ_API_KEY"),
            ("2", "Criar conta gratuita em cloud.langfuse.com", "Obter LANGFUSE_SECRET_KEY e PUBLIC_KEY"),
            ("3", "Criar repositório no huggingface.co/spaces", "Tipo: Docker"),
            ("4", "Configurar secrets no HuggingFace Spaces", "Settings → Variables and secrets"),
            ("5", "git push dos arquivos para o Space", "O deploy acontece automaticamente"),
            ("6", "Rodar validate_phase1.py no Space", "Confirmar URL pública funcionando"),
        ]
        for num, action, detail in steps:
            print(f"  {BLUE}{num}.{RESET} {action}")
            print(f"     {YELLOW}→ {detail}{RESET}")

        print(f"\n  Após concluir: avise para iniciar a {BOLD}Fase 2 — LLM + RAG{RESET}")

    else:
        print(f"\n{RED}{BOLD}  Corrija os erros acima antes de avançar.{RESET}")
        print(f"\n  Checks com falha:")
        for f in failed:
            print(f"  {RED}  • {f}{RESET}")

# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{BOLD}  EII — ERP Incident Intelligence{RESET}")
    print(f"  Validação: Fase 1 — Fundação\n")

    # Sobe para a raiz do projeto (um nível acima de tests/)
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

    check_file_structure()
    check_readme()
    check_python_syntax()
    check_dockerfile()
    check_requirements()
    check_gitignore()
    print_summary()

    sys.exit(0 if not failed else 1)
