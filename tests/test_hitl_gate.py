# Testes black-box da SPEC-HITL-app_hf.md
# Escritos SEM ler a implementação. Fixtures como constantes no próprio módulo
# (convenção do projeto: arquivo editável + teste verde = falso verde silencioso).
#
# Contrato esperado:
#   from app_hf import hitl_gate  (ou módulo equivalente exposto pela demo)
#   hitl_gate(diagnostico: dict) -> tuple[str, list[str]]
#   retorna ("AUTO_RESOLVIDO", []) ou ("ESCALADO_HUMANO", [motivos...])
#
# Se o executor expor a função em outro módulo (ex.: hitl.py), ajustar APENAS
# o import abaixo — nunca os asserts.

import pytest

from app_hf import hitl_gate  # ajustar import se necessário; nada mais


# --- Fixtures (constantes) -------------------------------------------------

FIXTURE_LIMPA = {
    "evento": "S-2200",
    "severidade": "BAIXO",
    "confianca": 0.95,
    "fonte": "KB",
    "evento_nao_mapeado": False,
}

FIXTURE_AMBIGUA = {
    # O bug original: demo dizia "confiança Alta" para este caso.
    "evento": "S-2200",
    "severidade": "MEDIO",
    "confianca": 0.5,
    "fonte": "KB",
    "evento_nao_mapeado": False,
}

FIXTURE_CRITICA = {
    "evento": "S-1210",
    "severidade": "CRITICO",
    "confianca": 0.99,  # confiança alta NÃO salva severidade crítica
    "fonte": "KB",
    "evento_nao_mapeado": False,
}

FIXTURE_FALLBACK = {
    "evento": "S-2200",
    "severidade": "MEDIO",
    "confianca": 0.90,
    "fonte": "LLM_FALLBACK",
    "evento_nao_mapeado": False,
}

FIXTURE_NAO_MAPEADO = {
    "evento": "S-9999",
    "severidade": "BAIXO",
    "confianca": 0.92,
    "fonte": "KB",
    "evento_nao_mapeado": True,
}

FIXTURE_PARSE_QUEBRADO = {"lixo": "sem campos do contrato"}


# --- Regras do portão -------------------------------------------------------

def test_fixture_limpa_auto_resolve():
    status, motivos = hitl_gate(dict(FIXTURE_LIMPA))
    assert status == "AUTO_RESOLVIDO"
    assert motivos == []


def test_fixture_ambigua_escala():
    status, motivos = hitl_gate(dict(FIXTURE_AMBIGUA))
    assert status == "ESCALADO_HUMANO"
    assert any("CONFIANCA" in m.upper() for m in motivos)


def test_critico_escala_mesmo_com_confianca_alta():
    status, motivos = hitl_gate(dict(FIXTURE_CRITICA))
    assert status == "ESCALADO_HUMANO"
    assert any("CRITICO" in m.upper() for m in motivos)


def test_fallback_escala():
    status, motivos = hitl_gate(dict(FIXTURE_FALLBACK))
    assert status == "ESCALADO_HUMANO"
    assert any("FALLBACK" in m.upper() for m in motivos)


def test_evento_nao_mapeado_escala():
    status, motivos = hitl_gate(dict(FIXTURE_NAO_MAPEADO))
    assert status == "ESCALADO_HUMANO"
    assert any("MAPEADO" in m.upper() or "KB" in m.upper() for m in motivos)


def test_parse_falhou_fail_closed():
    status, motivos = hitl_gate(dict(FIXTURE_PARSE_QUEBRADO))
    assert status == "ESCALADO_HUMANO"
    assert any("PARSE" in m.upper() for m in motivos)


def test_limiar_confianca_exato():
    # 0.70 é o limiar: exatamente 0.70 NÃO escala por confiança
    d = dict(FIXTURE_LIMPA)
    d["confianca"] = 0.70
    status, _ = hitl_gate(d)
    assert status == "AUTO_RESOLVIDO"

    d["confianca"] = 0.69
    status, _ = hitl_gate(d)
    assert status == "ESCALADO_HUMANO"


def test_multiplos_motivos_acumulam():
    d = dict(FIXTURE_AMBIGUA)
    d["fonte"] = "LLM_FALLBACK"
    status, motivos = hitl_gate(d)
    assert status == "ESCALADO_HUMANO"
    assert len(motivos) >= 2


def test_proibido_heuristica_ocorrencias():
    # Regra rejeitada como maquiagem: contagem de ocorrências NÃO pode
    # influenciar o portão. Mesmo com 50 ocorrências, fixture limpa é auto.
    d = dict(FIXTURE_LIMPA)
    d["ocorrencias"] = 50
    status, _ = hitl_gate(d)
    assert status == "AUTO_RESOLVIDO"


def test_funcao_pura_sem_io():
    # Mesma entrada → mesma saída (determinístico, sem LLM/rede)
    r1 = hitl_gate(dict(FIXTURE_AMBIGUA))
    r2 = hitl_gate(dict(FIXTURE_AMBIGUA))
    assert r1 == r2
