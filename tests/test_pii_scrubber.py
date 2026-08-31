import re
from pathlib import Path

import pytest

from src.privacy.scrubber import PIIScrubber, ScrubResult

# Regexes de segurança refinadas: negative lookbehind/ahead de dígitos
# evitam casar uma janela de 11 dígitos dentro de sequências maiores,
# como CNPJ de 14 dígitos ou Id do evento eSocial.
CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
PIS_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{5}\.?\d{2}-?\d(?!\d)")

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pii"


@pytest.fixture
def s1200_com_cpf() -> str:
    return (FIXTURES_DIR / "s1200_com_cpf.xml").read_text(encoding="utf-8")


@pytest.fixture
def s2200_com_nome() -> str:
    return (FIXTURES_DIR / "s2200_com_nome.xml").read_text(encoding="utf-8")


@pytest.fixture
def s1200_com_nis() -> str:
    return (FIXTURES_DIR / "s1200_com_nis.xml").read_text(encoding="utf-8")


@pytest.fixture
def s1200_padrao() -> str:
    return (FIXTURES_DIR / "s1200_padrao.xml").read_text(encoding="utf-8")


@pytest.fixture
def s1200_rejeitado() -> str:
    return (FIXTURES_DIR / "s1200_rejeitado.xml").read_text(encoding="utf-8")


@pytest.fixture
def s1200_com_rubrica() -> str:
    return (FIXTURES_DIR / "s1200_com_rubrica.xml").read_text(encoding="utf-8")


def test_cpf_nao_sobrevive_ao_scrub(s1200_com_cpf):
    r = PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert not CPF_PATTERN.search(r.scrubbed_payload)


def test_nome_nao_sobrevive_ao_scrub(s2200_com_nome):
    r = PIIScrubber().scrub(s2200_com_nome, "S-2200")
    assert "MARIA APARECIDA DA SILVA" not in r.scrubbed_payload.upper()


def test_pis_nao_sobrevive_ao_scrub(s1200_com_nis):
    r = PIIScrubber().scrub(s1200_com_nis, "S-1200")
    assert not PIS_PATTERN.search(r.scrubbed_payload)


def test_cnpj_empregador_e_preservado(s1200_padrao):
    r = PIIScrubber().scrub(s1200_padrao, "S-1200")
    assert "12345678000199" in r.scrubbed_payload.replace(".", "").replace("/", "")


def test_codigo_de_erro_sobrevive_ao_scrub(s1200_rejeitado):
    """O scrubbing não pode destruir o que é objeto do diagnóstico."""
    r = PIIScrubber().scrub(s1200_rejeitado, "S-1200")
    assert "MS0424" in r.scrubbed_payload


def test_restore_reverte_integralmente(s1200_com_cpf):
    sc = PIIScrubber()
    r = sc.scrub(s1200_com_cpf, "S-1200")
    token = next(iter(r.token_map))
    restored = sc.restore(f"Erro no trabalhador {token}.", r.token_map)
    assert r.token_map[token] in restored


def test_token_map_nunca_aparece_no_payload(s1200_com_cpf):
    r = PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    for valor_real in r.token_map.values():
        assert valor_real not in r.scrubbed_payload


def test_evento_desconhecido_e_fail_closed():
    r = PIIScrubber().scrub("<eSocial><evtDesconhecido/></eSocial>", "S-9999")
    assert r.is_safe_for_remote is False


def test_xml_malformado_e_fail_closed():
    r = PIIScrubber().scrub("<eSocial><quebrado", "S-1200")
    assert r.is_safe_for_remote is False


def test_scrub_nao_escreve_em_disco(s1200_com_cpf, tmp_path, monkeypatch):
    """Nenhum artefato criado durante o scrub."""
    monkeypatch.chdir(tmp_path)
    antes = set(tmp_path.rglob("*"))
    PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert set(tmp_path.rglob("*")) == antes


def test_scrub_nao_loga_conteudo_sensivel(s1200_com_cpf, caplog):
    PIIScrubber().scrub(s1200_com_cpf, "S-1200")
    assert not CPF_PATTERN.search(caplog.text)


def test_dois_requests_nao_compartilham_token_map(s1200_com_cpf, s2200_com_nome):
    sc = PIIScrubber()
    r1 = sc.scrub(s1200_com_cpf, "S-1200")
    r2 = sc.scrub(s2200_com_nome, "S-2200")
    assert r1.token_map is not r2.token_map


def test_valor_monetario_e_generalizado(s1200_com_rubrica):
    r = PIIScrubber().scrub(s1200_com_rubrica, "S-1200")
    assert "1543.27" not in r.scrubbed_payload
    assert "VALOR_FAIXA" in r.scrubbed_payload


def test_scrub_e_deterministico(s1200_com_cpf):
    """Mesmo input, mesmo payload — necessário para cache e reprodutibilidade."""
    sc = PIIScrubber()
    a = sc.scrub(s1200_com_cpf, "S-1200")
    b = sc.scrub(s1200_com_cpf, "S-1200")
    assert a.scrubbed_payload == b.scrubbed_payload


def test_cnpj_sem_formatacao_nao_dispara_falso_positivo(s1200_padrao):
    """CNPJ sem formatação contém substring que parece CPF/PIS —
    a rede de segurança não deve confundir as duas coisas."""
    r = PIIScrubber().scrub(s1200_padrao, "S-1200")
    assert r.is_safe_for_remote is True
