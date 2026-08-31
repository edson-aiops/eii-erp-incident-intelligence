#!/usr/bin/env bash
# ============================================================
# verify_faxina.sh — gate de aceite pós-execução do Kimi
# Rodar no Git Bash, na raiz do repo:
#   bash verify_faxina.sh
# Valida a task inteira de forma independente do relatório
# do executor. Saída: PASS/FAIL por item + veredito final.
# ============================================================
set -u
PASS=0; FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

check_absent_tracked() {  # arquivo NAO deve estar versionado
  if git ls-files --error-unmatch "$1" >/dev/null 2>&1; then
    bad "$1 ainda esta versionado"
  else
    ok "$1 fora do versionamento"
  fi
}

check_tracked() {         # arquivo DEVE estar versionado
  if git ls-files --error-unmatch "$1" >/dev/null 2>&1; then
    ok "$1 presente"
  else
    bad "$1 NAO encontrado no git"
  fi
}

echo "== 1. Branch correta =="
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = "chore/repo-hygiene-ci" ] \
  && ok "branch = $BRANCH" \
  || bad "branch atual e '$BRANCH' (esperado chore/repo-hygiene-ci)"

echo "== 2. Artefatos removidos =="
check_absent_tracked ".coverage"
check_absent_tracked "app.py.backup.v2.1"
check_absent_tracked "knowledge_base_v2.py"
check_absent_tracked ".dockerignore.txt"
check_absent_tracked "docker-compose..yml"
check_absent_tracked "smartrouter/tests/__init__.py.py"

echo "== 3. Renomes e movimentacoes =="
check_tracked ".dockerignore"
check_tracked "docker-compose.yml"
check_tracked "smartrouter/tests/__init__.py"
check_tracked "scripts/dev/test_final_qwen.py"
check_tracked "scripts/dev/debug_api.py"
check_tracked "docs/archive/README_EII_Completo.md"

echo "== 4. Arquivos novos =="
check_tracked "smartrouter/tests/conftest.py"
check_tracked "requirements-ci.txt"
check_tracked ".github/workflows/ci.yml"

echo "== 5. Guardrails de escopo =="
# llm_resilient.py da raiz nao podia ser tocado
if git diff main -- llm_resilient.py | grep -q .; then
  bad "llm_resilient.py (raiz) foi modificado — NAO deveria"
else
  ok "llm_resilient.py (raiz) intacto"
fi
# nenhum assert de teste alterado
if git diff main -- smartrouter/tests/test_smartrouter.py tests/ | grep -q .; then
  bad "arquivos de teste existentes foram modificados — revisar diff"
else
  ok "nenhum teste existente foi alterado"
fi

echo "== 6. BOM removido do requirements.txt =="
if head -c 3 requirements.txt | grep -q $'\xEF\xBB\xBF'; then
  bad "BOM ainda presente"
else
  ok "requirements.txt sem BOM"
fi

echo "== 7. Working tree limpa (tudo commitado) =="
if [ -z "$(git status --porcelain)" ]; then
  ok "git status limpo"
else
  bad "ha alteracoes nao commitadas:"; git status --short
fi

echo "== 8. Nenhum push feito =="
if git ls-remote --heads origin chore/repo-hygiene-ci | grep -q .; then
  bad "branch JA existe no origin — houve push"
else
  ok "branch existe apenas local"
fi

echo "== 9. Suite de testes (criterio: 120 passed) =="
RESULT=$(python -m pytest 2>&1 | tail -1)
echo "  pytest: $RESULT"
echo "$RESULT" | grep -q "120 passed" \
  && ok "120/120 testes verdes" \
  || bad "resultado diferente de 120 passed"

echo
echo "============================================"
echo " RESULTADO: $PASS pass / $FAIL fail"
if [ "$FAIL" -eq 0 ]; then
  echo " VEREDITO: APROVADO — pode fazer o push:"
  echo "   git push -u origin chore/repo-hygiene-ci"
else
  echo " VEREDITO: REPROVADO — revisar itens FAIL antes de push"
fi
echo "============================================"
exit "$FAIL"
