"""
Testes black-box da seção 3 v2 da PII-SCRUBBER-SPEC (A23).

Escritos a partir do contrato, sem leitura da implementação.
Cobrem:
  - dados sensíveis do S-2200 (art. 5º, II da LGPD): racaCor, infoDeficiencia,
    filiacaoSindical, incTrab de dependente
  - quasi-identificadores: sexo, estCiv, grauInstr, tpDep, paises
  - CPF do empregador embutido no atributo Id quando tpInsc != 1
  - rede de segurança v2 (eco de CPF em texto livre de retorno, run de dígitos)

Os XMLs são constantes no próprio módulo, e não arquivos em
tests/fixtures/pii/, porque as asserções dependem dos valores exatos. Manter o
dado ao lado da asserção elimina uma classe de falso verde (fixture editada,
teste continua passando). Todos os valores são sintéticos: os CPFs têm dígitos
repetidos, portanto são inválidos por DV e não correspondem a titular real.

Convenção de import: src é raiz de pacotes (ver EVIDENCE_PACK-scrubber.md).
"""

import re
import xml.etree.ElementTree as ET

import pytest

from src.privacy.scrubber import PIIScrubber

# --------------------------------------------------------------------------
# Valores sintéticos
# --------------------------------------------------------------------------

CPF_TRAB = "11111111111"
CPF_TRAB_FMT = "111.111.111-11"
CPF_DEP = "33333333333"
CPF_EMPR = "22222222222"
CAEPF_EMPR = "44444444444001"          # CPF (11) + 3 dígitos de estabelecimento
CNPJ_EMPR = "12345678000199"
CNPJ_SIND_TRAB = "98765432000155"
CNPJ_SIND_CATEG = "11222333000181"

NOME_TRAB = "MARIA APARECIDA DA SILVA"
NOME_MAE = "JOANA APARECIDA DA SILVA"
NOME_DEP = "PEDRO HENRIQUE DA SILVA"
EMAIL = "maria.silva@exemplo.com.br"
FONE = "11987654321"
MATRICULA = "EMP0001234"
SALARIO = "1543.27"
CEP = "01001000"
COD_MUNIC = "3550308"

TS = "20260801120000"
SEQ = "00001"

ID_TPINSC_1 = "ID1" + CNPJ_EMPR + TS + SEQ
ID_TPINSC_2 = "ID2" + CPF_EMPR + "000" + TS + SEQ
ID_TPINSC_3 = "ID3" + CAEPF_EMPR + TS + SEQ

CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")

# --------------------------------------------------------------------------
# Fixtures sintéticas
# --------------------------------------------------------------------------


def _s2200(raca_cor="3", pais_nascto="105", extra_trabalhador=""):
    return f"""<eSocial>
  <evtAdmissao Id="{ID_TPINSC_1}">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{CNPJ_EMPR}</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>{CPF_TRAB}</cpfTrab>
      <nmTrab>{NOME_TRAB}</nmTrab>
      <sexo>F</sexo>
      <racaCor>{raca_cor}</racaCor>
      <estCiv>2</estCiv>
      <grauInstr>07</grauInstr>
      <nascimento>
        <dtNascto>1985-04-17</dtNascto>
        <paisNascto>{pais_nascto}</paisNascto>
        <paisNac>{pais_nascto}</paisNac>
        <nmMae>{NOME_MAE}</nmMae>
      </nascimento>
      <endereco>
        <brasil>
          <tpLograd>R</tpLograd>
          <dscLograd>RUA DAS ACACIAS</dscLograd>
          <nrLograd>250</nrLograd>
          <bairro>CENTRO</bairro>
          <cep>{CEP}</cep>
          <codMunic>{COD_MUNIC}</codMunic>
          <uf>SP</uf>
        </brasil>
      </endereco>
      <infoDeficiencia>
        <defFisica>N</defFisica>
        <defVisual>S</defVisual>
        <defAuditiva>N</defAuditiva>
        <defMental>N</defMental>
        <defIntelectual>N</defIntelectual>
        <reabReadap>S</reabReadap>
        <infoCota>S</infoCota>
        <observacao>Laudo emitido em 2019, CID H54.</observacao>
      </infoDeficiencia>
      <dependente>
        <tpDep>03</tpDep>
        <nmDep>{NOME_DEP}</nmDep>
        <dtNascto>2015-09-02</dtNascto>
        <cpfDep>{CPF_DEP}</cpfDep>
        <incTrab>S</incTrab>
      </dependente>
      <contato>
        <fonePrinc>{FONE}</fonePrinc>
        <emailPrinc>{EMAIL}</emailPrinc>
      </contato>{extra_trabalhador}
    </trabalhador>
    <vinculo>
      <matricula>{MATRICULA}</matricula>
      <infoRegimeTrab>
        <infoCeletista>
          <dtAdm>2026-08-01</dtAdm>
          <cnpjSindCategProf>{CNPJ_SIND_CATEG}</cnpjSindCategProf>
        </infoCeletista>
      </infoRegimeTrab>
      <infoContrato>
        <codCateg>101</codCateg>
        <remuneracao>
          <vrSalFx>{SALARIO}</vrSalFx>
          <undSalFixo>5</undSalFixo>
        </remuneracao>
        <filiacaoSindical>
          <cnpjSindTrab>{CNPJ_SIND_TRAB}</cnpjSindTrab>
        </filiacaoSindical>
      </infoContrato>
    </vinculo>
  </evtAdmissao>
</eSocial>"""


S2200_SENSIVEL = _s2200()
S2200_RACA_FORA_DOMINIO = _s2200(raca_cor="9")
S2200_ESTRANGEIRO = _s2200(pais_nascto="063")
S2200_PAIS_FORA_FORMATO = _s2200(pais_nascto="XX")
S2200_CAMPO_NOVO = _s2200(
    extra_trabalhador="\n      <nmSocialAnterior>FULANA DE TAL</nmSocialAnterior>"
)


def _s1200(id_attr, tp_insc, nr_insc):
    return f"""<eSocial>
  <evtRemun Id="{id_attr}">
    <ideEvento><indRetif>1</indRetif></ideEvento>
    <ideEmpregador><tpInsc>{tp_insc}</tpInsc><nrInsc>{nr_insc}</nrInsc></ideEmpregador>
    <ideTrabalhador><cpfTrab>{CPF_TRAB}</cpfTrab></ideTrabalhador>
  </evtRemun>
</eSocial>"""


S1200_TPINSC_1 = _s1200(ID_TPINSC_1, "1", CNPJ_EMPR)
S1200_TPINSC_2 = _s1200(ID_TPINSC_2, "2", CPF_EMPR)
S1200_TPINSC_3 = _s1200(ID_TPINSC_3, "3", CAEPF_EMPR)

S1200_RUN_LONGO_EM_CAMPO_DESCONHECIDO = f"""<eSocial>
  <evtRemun Id="{ID_TPINSC_1}">
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{CNPJ_EMPR}</nrInsc></ideEmpregador>
    <ideTrabalhador><cpfTrab>{CPF_TRAB}</cpfTrab></ideTrabalhador>
    <campoQueAindaNaoExiste>999999999999</campoQueAindaNaoExiste>
  </evtRemun>
</eSocial>"""

RETORNO_COM_ECO_DE_CPF = f"""<eSocial>
  <retornoEvento>
    <evtAdmissao Id="{ID_TPINSC_1}">
      <ideEmpregador><tpInsc>1</tpInsc><nrInsc>{CNPJ_EMPR}</nrInsc></ideEmpregador>
      <trabalhador>
        <cpfTrab>{CPF_TRAB}</cpfTrab>
        <nmTrab>{NOME_TRAB}</nmTrab>
      </trabalhador>
    </evtAdmissao>
    <processamento>
      <cdResposta>301</cdResposta>
      <descResposta>Erro nas assertivas de validacao</descResposta>
      <ocorrencias>
        <ocorrencia>
          <codigo>MS0424</codigo>
          <descricao>O CPF {CPF_TRAB_FMT} do trabalhador {NOME_TRAB} nao consta na base do CNIS.</descricao>
        </ocorrencia>
      </ocorrencias>
    </processamento>
  </retornoEvento>
</eSocial>"""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _nos(payload, tag):
    root = ET.fromstring(payload)
    return [el for el in root.iter() if el.tag.split("}")[-1] == tag]


def _texto(payload, tag):
    nos = _nos(payload, tag)
    assert nos, f"tag <{tag}> desapareceu do payload"
    return (nos[0].text or "").strip()


def _id_evento(payload):
    root = ET.fromstring(payload)
    for el in root.iter():
        if "Id" in el.attrib:
            return el.attrib["Id"]
    raise AssertionError("atributo Id ausente do payload")


def _scrub(xml, event_type="S-2200"):
    return PIIScrubber().scrub(xml, event_type)


# ==========================================================================
# 1. Dados sensíveis do S-2200 — art. 5º, II
# ==========================================================================


def test_raca_cor_e_classificada_e_nao_expoe_o_valor():
    """racaCor é dado sensível. Sai o valor, entra a classe de domínio."""
    r = _scrub(S2200_SENSIVEL)
    v = _texto(r.scrubbed_payload, "racaCor")
    assert v != "3"
    assert v.startswith("RACA_COR_VALIDO")


def test_raca_cor_fora_do_dominio_e_marcada_como_tal():
    """O erro de domínio continua diagnosticável sem o valor sair."""
    r = _scrub(S2200_RACA_FORA_DOMINIO)
    assert _texto(r.scrubbed_payload, "racaCor").startswith("RACA_COR_FORA_DOMINIO")


@pytest.mark.parametrize(
    "tag,valor_original,prefixo",
    [
        ("sexo", "F", "SEXO_VALIDO"),
        ("estCiv", "2", "EST_CIV_VALIDO"),
        ("grauInstr", "07", "GRAU_INSTR_VALIDO"),
    ],
)
def test_quasi_identificadores_de_dominio_fechado_sao_classificados(
    tag, valor_original, prefixo
):
    r = _scrub(S2200_SENSIVEL)
    v = _texto(r.scrubbed_payload, tag)
    assert v != valor_original
    assert v.startswith(prefixo)


def test_info_deficiencia_nao_revela_valores():
    """Dado de saúde. Presença e estrutura ficam; qual deficiência, não."""
    r = _scrub(S2200_SENSIVEL)
    for tag in (
        "defFisica",
        "defVisual",
        "defAuditiva",
        "defMental",
        "defIntelectual",
        "reabReadap",
        "infoCota",
    ):
        v = _texto(r.scrubbed_payload, tag)
        assert v not in ("S", "N"), f"<{tag}> manteve o valor original"
        assert "_VALIDO" in v or "_FORA_DOMINIO" in v


def test_observacao_de_deficiencia_e_tokenizada():
    """Texto livre dentro de bloco de saúde: pode conter CID, laudo, qualquer coisa."""
    r = _scrub(S2200_SENSIVEL)
    assert "CID" not in r.scrubbed_payload
    assert "H54" not in r.scrubbed_payload
    assert _texto(r.scrubbed_payload, "observacao").startswith("TEXTO_LIVRE_")


def test_filiacao_sindical_e_tokenizada_e_sindicato_da_categoria_e_preservado():
    """cnpjSindTrab revela filiação (art. 5º, II). cnpjSindCategProf é definido
    pelo CBO e não revela escolha do titular."""
    r = _scrub(S2200_SENSIVEL)
    assert CNPJ_SIND_TRAB not in r.scrubbed_payload
    assert _texto(r.scrubbed_payload, "cnpjSindTrab").startswith("CNPJ_SIND_")
    assert _texto(r.scrubbed_payload, "cnpjSindCategProf") == CNPJ_SIND_CATEG


def test_dependente_nao_sobrevive_ao_scrub():
    r = _scrub(S2200_SENSIVEL)
    assert NOME_DEP.upper() not in r.scrubbed_payload.upper()
    assert CPF_DEP not in r.scrubbed_payload
    assert _texto(r.scrubbed_payload, "incTrab") not in ("S", "N")
    assert _texto(r.scrubbed_payload, "tpDep") != "03"


def test_contato_nao_sobrevive_ao_scrub():
    r = _scrub(S2200_SENSIVEL)
    assert EMAIL not in r.scrubbed_payload
    assert FONE not in r.scrubbed_payload


@pytest.mark.parametrize(
    "xml,prefixo_esperado",
    [
        (S2200_SENSIVEL, "PAIS_BRASIL"),
        (S2200_ESTRANGEIRO, "PAIS_ESTRANGEIRO"),
    ],
)
def test_pais_preserva_apenas_o_bit_brasil_ou_estrangeiro(xml, prefixo_esperado):
    """Sem esse bit, a regra 'paisNascto != 105 exige trabEstrangeiro' fica
    indiagnosticável."""
    r = _scrub(xml)
    assert _texto(r.scrubbed_payload, "paisNascto").startswith(prefixo_esperado)


def test_pais_fora_do_formato_nao_e_tratado_como_estrangeiro_valido():
    """Seção 3.3.2: validação de FORMATO (3 dígitos), não contra tabela."""
    r = _scrub(S2200_PAIS_FORA_FORMATO)
    pais = _texto(r.scrubbed_payload, "paisNascto")
    assert pais.startswith("PAIS_FORA_DOMINIO")


# ==========================================================================
# 2. Valores, endereço e allowlist
# ==========================================================================


def test_salario_fixo_e_generalizado():
    r = _scrub(S2200_SENSIVEL)
    assert SALARIO not in r.scrubbed_payload
    assert "VALOR_FAIXA" in _texto(r.scrubbed_payload, "vrSalFx")


def test_cep_e_classificado_por_formato():
    r = _scrub(S2200_SENSIVEL)
    v = _texto(r.scrubbed_payload, "cep")
    assert v != CEP
    assert v.startswith("CEP_VALIDO")


def test_endereco_preserva_municipio_uf_e_tipo_de_logradouro():
    """Allowlist: quasi-identificadores fracos, objeto frequente de erro."""
    r = _scrub(S2200_SENSIVEL)
    assert _texto(r.scrubbed_payload, "codMunic") == COD_MUNIC
    assert _texto(r.scrubbed_payload, "uf") == "SP"
    assert _texto(r.scrubbed_payload, "tpLograd") == "R"
    assert "RUA DAS ACACIAS" not in r.scrubbed_payload


def test_data_contratual_e_preservada_e_data_de_nascimento_nao():
    r = _scrub(S2200_SENSIVEL)
    assert _texto(r.scrubbed_payload, "dtAdm") == "2026-08-01"
    assert _texto(r.scrubbed_payload, "dtNascto").startswith("DATA_NASC_")


def test_campo_novo_em_bloco_de_titular_e_tokenizado_por_padrao():
    """Allowlist: tag desconhecida dentro de <trabalhador> não passa em claro."""
    r = _scrub(S2200_CAMPO_NOVO)
    assert "FULANA DE TAL" not in r.scrubbed_payload.upper()
    assert _texto(r.scrubbed_payload, "nmSocialAnterior").startswith("CAMPO_TITULAR_")


def test_evento_com_dados_sensiveis_tratados_continua_seguro_para_remoto():
    r = _scrub(S2200_SENSIVEL)
    assert r.is_safe_for_remote is True


# ==========================================================================
# 3. Atributo Id e nrInsc do empregador
# ==========================================================================


def test_id_e_cnpj_intactos_quando_tp_insc_1():
    """Regressão: o caso pessoa jurídica não pode mudar."""
    r = _scrub(S1200_TPINSC_1, "S-1200")
    assert _id_evento(r.scrubbed_payload) == ID_TPINSC_1
    assert _texto(r.scrubbed_payload, "nrInsc") == CNPJ_EMPR
    assert r.is_safe_for_remote is True


def test_cpf_do_empregador_nao_sobrevive_quando_tp_insc_2():
    r = _scrub(S1200_TPINSC_2, "S-1200")
    assert CPF_EMPR not in r.scrubbed_payload
    assert not CPF_PATTERN.search(r.scrubbed_payload)


def test_id_preserva_36_posicoes_quando_tp_insc_2():
    """Erro de formato de Id é classe real de rejeição: a largura tem de sobreviver."""
    r = _scrub(S1200_TPINSC_2, "S-1200")
    novo_id = _id_evento(r.scrubbed_payload)
    assert len(novo_id) == 36
    assert novo_id.startswith("ID2")
    assert novo_id.endswith(TS + SEQ)


def test_token_do_empregador_e_coerente_entre_id_e_ide_empregador():
    """A validação cruzada Id.nrInsc == ideEmpregador/nrInsc tem de sobreviver."""
    r = _scrub(S1200_TPINSC_2, "S-1200")
    token = _texto(r.scrubbed_payload, "nrInsc")
    segmento_id = _id_evento(r.scrubbed_payload)[3:17]
    assert len(token) == 11
    assert segmento_id.startswith(token)
    assert r.token_map[token] == CPF_EMPR


def test_cpf_dentro_do_caepf_nao_sobrevive_quando_tp_insc_3():
    """CAEPF = CPF (11) + 3 dígitos de estabelecimento."""
    r = _scrub(S1200_TPINSC_3, "S-1200")
    assert CAEPF_EMPR[:11] not in r.scrubbed_payload
    nr_insc = _texto(r.scrubbed_payload, "nrInsc")
    assert len(nr_insc) == 14
    assert nr_insc.endswith("001")


def test_restore_reverte_o_cpf_do_empregador():
    sc = PIIScrubber()
    r = sc.scrub(S1200_TPINSC_2, "S-1200")
    token = _texto(r.scrubbed_payload, "nrInsc")
    restaurado = sc.restore(f"Inscricao {token} rejeitada.", r.token_map)
    assert CPF_EMPR in restaurado


def test_campos_classificados_sao_reversiveis():
    sc = PIIScrubber()
    r = sc.scrub(S2200_SENSIVEL, "S-2200")
    token = _texto(r.scrubbed_payload, "racaCor")
    assert sc.restore(f"Campo {token} invalido.", r.token_map) == "Campo 3 invalido."


@pytest.mark.parametrize(
    "id_invalido",
    [
        "XX1" + CNPJ_EMPR + TS + SEQ,      # prefixo errado
        "ID1" + CNPJ_EMPR + TS,            # largura menor que 36
        "ID9" + CNPJ_EMPR + TS + SEQ,      # tpInsc fora do domínio
        "ID1" + "1234567800019A" + TS + SEQ,  # segmento não numérico
    ],
)
def test_id_malformado_e_fail_closed(id_invalido):
    """Não adivinhar estrutura. Sem parse confiável, não sai da máquina."""
    r = _scrub(_s1200(id_invalido, "1", CNPJ_EMPR), "S-1200")
    assert r.is_safe_for_remote is False


# ==========================================================================
# 4. Rede de segurança v2
# ==========================================================================


def test_cpf_ecoado_na_ocorrencia_de_retorno_nao_sobrevive():
    """O webservice devolve o valor rejeitado na descrição do erro.
    Vazamento fora de qualquer bloco de titular."""
    r = _scrub(RETORNO_COM_ECO_DE_CPF, "S-2200")
    assert CPF_TRAB not in r.scrubbed_payload
    assert CPF_TRAB_FMT not in r.scrubbed_payload
    assert NOME_TRAB.upper() not in r.scrubbed_payload.upper()
    assert "MS0424" in r.scrubbed_payload
    assert r.is_safe_for_remote is True


def test_run_longo_em_campo_desconhecido_dispara_fail_closed():
    """12 dígitos: não casa com a regex de CPF/PIS. Só a camada 3 pega."""
    r = _scrub(S1200_RUN_LONGO_EM_CAMPO_DESCONHECIDO, "S-1200")
    assert r.is_safe_for_remote is False


def test_scrub_com_dados_sensiveis_e_deterministico():
    sc = PIIScrubber()
    a = sc.scrub(S2200_SENSIVEL, "S-2200")
    b = sc.scrub(S2200_SENSIVEL, "S-2200")
    assert a.scrubbed_payload == b.scrubbed_payload


@pytest.mark.parametrize(
    "valor_sensivel",
    [
        CPF_TRAB,
        CPF_DEP,
        NOME_TRAB,
        NOME_MAE,
        NOME_DEP,
        EMAIL,
        FONE,
        MATRICULA,
        SALARIO,
        CEP,
        CNPJ_SIND_TRAB,
        "RUA DAS ACACIAS",
        "1985-04-17",
        "2015-09-02",
        "Laudo emitido em 2019, CID H54.",
    ],
)
def test_identificador_direto_nao_sobrevive_no_payload(valor_sensivel):
    """Substitui a varredura sobre token_map.values().

    A varredura genérica media coincidência de alfabeto, não vazamento: os
    valores de campos CLASSIFICADOS têm 1 ou 2 caracteres (F, S, N, 07) e
    aparecem por acaso dentro de qualquer token semântico. O invariante que
    importa é este: nenhum identificador direto do evento sobrevive no payload.
    Os campos classificados são verificados um a um nos testes da seção 1.
    """
    r = _scrub(S2200_SENSIVEL)
    assert valor_sensivel not in r.scrubbed_payload
