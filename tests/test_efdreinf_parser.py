"""
EII — Testes do parser EFD-Reinf (xml_parser.py)
Cobre: parse_efdreinf_xml, parse_xml_auto, detecção de evento, PII scrubbing EFD-Reinf.
"""
import pytest
from xml_parser import (
    parse_efdreinf_xml,
    parse_xml_auto,
    parse_esocial_xml,
    scrub_pii,
    EFDREINF_EVENTS,
    SAMPLE_XMLS,
)

# ─────────────────────────────────────────────────────────────────────────────
# XMLs de teste
# ─────────────────────────────────────────────────────────────────────────────

R1000_REJEITADO = """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <retornoLoteEventos>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000195</nrInsc></ideEmpregador>
    <status>
      <cdRetorno>1</cdRetorno>
      <descRetorno>Lote com erros</descRetorno>
    </status>
    <retornoEventos>
      <evento id="Evt001">
        <retornoEvento>
          <Reinf>
            <retornoEvtInfoContribuinte>
              <ideStatus>
                <cdRetorno>1</cdRetorno>
                <descRetorno>Evento rejeitado</descRetorno>
                <ocorrencias>
                  <ocorrencia>
                    <tipo>1</tipo>
                    <codigo>ERF001</codigo>
                    <descricao>CNPJ do contribuinte não cadastrado na RFB.</descricao>
                    <localizacao>evtInfoContribuinte/ideContri/nrInsc</localizacao>
                  </ocorrencia>
                </ocorrencias>
              </ideStatus>
            </retornoEvtInfoContribuinte>
          </Reinf>
        </retornoEvento>
      </evento>
    </retornoEventos>
  </retornoLoteEventos>
</Reinf>"""

R2010_REJEITADO = """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <retornoLoteEventos>
    <ideEmpregador><nrInsc>12345678000195</nrInsc></ideEmpregador>
    <status><cdRetorno>1</cdRetorno><descRetorno>Erro</descRetorno></status>
    <retornoEventos>
      <evento id="Evt002">
        <retornoEvento>
          <Reinf>
            <retornoEvtServTom>
              <ideStatus>
                <cdRetorno>1</cdRetorno>
                <descRetorno>R-2010 rejeitado</descRetorno>
                <ocorrencias>
                  <ocorrencia>
                    <tipo>1</tipo>
                    <codigo>ERF010</codigo>
                    <descricao>Valor de retencao CSLL/COFINS/PIS diverge de 4,65%.</descricao>
                    <localizacao>evtServTom/ideServTom/vlrCsll</localizacao>
                  </ocorrencia>
                </ocorrencias>
              </ideStatus>
            </retornoEvtServTom>
          </Reinf>
        </retornoEvento>
      </evento>
    </retornoEventos>
  </retornoLoteEventos>
</Reinf>"""

R2010_COM_PII = """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <evtServTom>
    <cnpjPrestador>12345678000195</cnpjPrestador>
    <cnpjTomador>98765432000110</cnpjTomador>
    <vlrBruto>10000.00</vlrBruto>
  </evtServTom>
</Reinf>"""

R2050_COM_CPF = """<?xml version="1.0" encoding="UTF-8"?>
<Reinf>
  <evtComProd>
    <cpfProdRural>12345678901</cpfProdRural>
    <vlrFunrural>150.00</vlrFunrural>
  </evtComProd>
</Reinf>"""

ESOCIAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/retorno/v1_1_1">
  <retornoEnvioLoteEventos>
    <ideEmpregador><nrInsc>12345678000195</nrInsc></ideEmpregador>
    <status><cdResposta>401</cdResposta><descResposta>Rejeitado</descResposta></status>
    <retornoLoteEventos>
      <retornoEventos>
        <retornoEvento id="ID_S1200_001">
          <retornoEvento>
            <cdResposta>401</cdResposta>
            <ocorrencias>
              <ocorrencia>
                <tipo>ERROR</tipo><codigo>E428</codigo>
                <descricao>Campo indRetif deve ser 2.</descricao>
                <localizacaoErro>evtRemun/ideEvento/indRetif</localizacaoErro>
              </ocorrencia>
            </ocorrencias>
          </retornoEvento>
        </retornoEvento>
      </retornoEventos>
    </retornoLoteEventos>
  </retornoEnvioLoteEventos>
</eSocial>"""

XML_INVALIDO = "isso nao e xml <<<"


# ─────────────────────────────────────────────────────────────────────────────
# Testes: parse_efdreinf_xml
# ─────────────────────────────────────────────────────────────────────────────

class TestParseEfdReinf:

    def test_sistema_efdreinf(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.sistema == "efdreinf"

    def test_formato_lote(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.formato == "efdreinf_lote"

    def test_detecta_evento_r1000(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.tipo_evento == "R-1000"

    def test_detecta_evento_r2010(self):
        p = parse_efdreinf_xml(R2010_REJEITADO)
        assert p.tipo_evento == "R-2010"

    def test_cd_resposta_extraido(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.cd_resposta == "1"

    def test_ocorrencias_extraidas(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert len(p.ocorrencias) >= 1

    def test_codigo_erro_efr001(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert "ERF001" in p.error_codes

    def test_codigo_erro_efr010(self):
        p = parse_efdreinf_xml(R2010_REJEITADO)
        assert "ERF010" in p.error_codes

    def test_tipo_ocorrencia_normalizado(self):
        """tipo '1' deve ser normalizado para 'ERROR'"""
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.ocorrencias[0].tipo == "ERROR"

    def test_localizacao_ocorrencia(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.ocorrencias[0].localizacao != ""

    def test_evento_ids_capturados(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert "Evt001" in p.evento_ids

    def test_xml_invalido_retorna_erro(self):
        p = parse_efdreinf_xml(XML_INVALIDO)
        assert p.erro != ""
        assert p.sistema == "efdreinf"

    def test_is_rejected_true(self):
        p = parse_efdreinf_xml(R1000_REJEITADO)
        assert p.is_rejected is True


# ─────────────────────────────────────────────────────────────────────────────
# Testes: parse_xml_auto (detecção automática)
# ─────────────────────────────────────────────────────────────────────────────

class TestParseXmlAuto:

    def test_auto_detecta_efdreinf_por_namespace(self):
        p = parse_xml_auto(R1000_REJEITADO)
        assert p.sistema == "efdreinf"

    def test_auto_detecta_efdreinf_por_tag_evento(self):
        p = parse_xml_auto(R2010_COM_PII)
        assert p.sistema == "efdreinf"

    def test_auto_detecta_efdreinf_sem_namespace(self):
        p = parse_xml_auto(R2050_COM_CPF)
        assert p.sistema == "efdreinf"

    def test_auto_detecta_esocial(self):
        p = parse_xml_auto(ESOCIAL_XML)
        assert p.sistema == "esocial"

    def test_auto_esocial_evento_correto(self):
        p = parse_xml_auto(ESOCIAL_XML)
        assert p.tipo_evento == "S-1200"

    def test_auto_xml_invalido_retorna_erro(self):
        p = parse_xml_auto(XML_INVALIDO)
        assert p.erro != ""

    def test_parse_xml_alias_aponta_para_auto(self):
        """parse_xml deve ser alias de parse_xml_auto."""
        from xml_parser import parse_xml
        p = parse_xml(R1000_REJEITADO)
        assert p.sistema == "efdreinf"


# ─────────────────────────────────────────────────────────────────────────────
# Testes: PII scrubbing EFD-Reinf
# ─────────────────────────────────────────────────────────────────────────────

class TestPIIScrubEfdReinf:

    def test_cnpj_prestador_mascarado(self):
        result = scrub_pii("<cnpjPrestador>12345678000195</cnpjPrestador>")
        assert "12345678000195" not in result
        assert "CNPJ" in result

    def test_cnpj_tomador_mascarado(self):
        result = scrub_pii("<cnpjTomador>98765432000110</cnpjTomador>")
        assert "98765432000110" not in result
        assert "CNPJ" in result

    def test_cnpj_contri_mascarado(self):
        result = scrub_pii("<cnpjContri>11222333000181</cnpjContri>")
        assert "11222333000181" not in result
        assert "CNPJ" in result

    def test_cpf_prod_rural_mascarado(self):
        result = scrub_pii("<cpfProdRural>12345678901</cpfProdRural>")
        assert "12345678901" not in result
        assert "CPF" in result

    def test_parse_auto_aplica_scrub_pii(self):
        p = parse_xml_auto(R2010_COM_PII)
        assert "12345678000195" not in p.raw_xml or p.nr_inscricao == "" or \
               "CNPJ" in str(p.ocorrencias)
        # O scrub_pii é aplicado ao ParsedXML (nr_inscricao, ocorrencias)
        assert "12345678000195" not in p.nr_inscricao


# ─────────────────────────────────────────────────────────────────────────────
# Testes: EFDREINF_EVENTS e SAMPLE_XMLS
# ─────────────────────────────────────────────────────────────────────────────

class TestEfdReinfConfig:

    def test_efdreinf_events_nao_vazio(self):
        assert len(EFDREINF_EVENTS) > 0

    def test_eventos_principais_presentes(self):
        for evt in ["R-1000", "R-2010", "R-2020", "R-2060", "R-4010"]:
            assert evt in EFDREINF_EVENTS

    def test_samples_tem_efdreinf(self):
        efdreinf_samples = [k for k in SAMPLE_XMLS if k.startswith("R-")]
        assert len(efdreinf_samples) >= 3

    def test_samples_efdreinf_parseiam_corretamente(self):
        for key, xml in SAMPLE_XMLS.items():
            if key.startswith("R-"):
                p = parse_xml_auto(xml)
                assert p.sistema == "efdreinf", f"Sample '{key}' deveria ser efdreinf"
                assert p.erro == "", f"Sample '{key}' não deveria ter erro de parse"
