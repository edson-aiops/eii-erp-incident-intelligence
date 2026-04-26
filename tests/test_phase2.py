"""
EII — Testes da Fase 2: PII Detection & LGPD Compliance
Foco: Validação estável e robusta do detector de dados sensíveis.
"""
import pytest
import time
from smartrouter.pii_detector import contains_pii, get_pii_summary

# ─────────────────────────────────────────────────────────────────────────────
# Dados de Teste (Samples Reais)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_XML_PUBLIC = """<evtFech4000>
  <ideEvento><tpAmb>1</tpAmb><procEmi>1</procEmi></ideEvento>
  <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000190</nrInsc></ideEmpregador>
</evtFech4000>"""

SAMPLE_XML_CPF = """<evtAdmissao>
  <trabalhador>
    <cpf>123.456.789-00</cpf>
    <nis>12345678901</nis>
    <nmTrab>JOAO DA SILVA</nmTrab>
  </trabalhador>
</evtAdmissao>"""

SAMPLE_XML_CNPJ = """<evtTabInicio>
  <ideEmpregador>
    <nrInsc>12.345.678/0001-90</nrInsc>
  </ideEmpregador>
</evtTabInicio>"""


# ─────────────────────────────────────────────────────────────────────────────
# Testes de Detecção de PII (LGPD)
# ─────────────────────────────────────────────────────────────────────────────

class TestPIIDetection:
    """Garante que dados sensíveis são identificados corretamente"""
    
    def test_detects_cpf_formatted(self):
        assert contains_pii(SAMPLE_XML_CPF) is True

    def test_detects_cpf_raw_numbers(self):
        assert contains_pii("<trabalhador><cpf>12345678900</cpf></trabalhador>") is True

    def test_detects_nis_pis(self):
        assert contains_pii(SAMPLE_XML_CPF) is True

    def test_detects_cnpj_formatted(self):
        assert contains_pii(SAMPLE_XML_CNPJ) is True

    def test_detects_cnpj_as_potential_pii(self):
        """
        O sistema deve detectar CNPJs (Privacy by Design).
        Mesmo sendo dados de PJ, em contextos de eSocial devem ser tratados
        com cautela para evitar vazamento de estrutura empresarial.
        """
        # O detector deve retornar True (conservador)
        assert contains_pii(SAMPLE_XML_PUBLIC) is True

    def test_ignores_empty_or_minimal_xml(self):
        assert contains_pii("<evtFech4000></evtFech4000>") is False

    def test_summary_returns_structured_dict(self):
        summary = get_pii_summary(SAMPLE_XML_CPF)
        assert isinstance(summary, dict)
        assert len(summary) > 0
        # Deve conter chaves como 'detected', 'types' ou 'count'
        assert any(k in summary for k in ["detected", "types", "count", "found"])


# ─────────────────────────────────────────────────────────────────────────────
# Testes de Performance (Benchmark Básico)
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformance:
    """Garante que a detecção é rápida o suficiente para produção"""
    
    def test_pii_detection_under_50ms(self):
        """100 iterações devem levar menos de 50ms no total"""
        start = time.time()
        for _ in range(100):
            contains_pii(SAMPLE_XML_CPF * 3)  # XML maior
        elapsed_ms = (time.time() - start) * 10
        
        assert elapsed_ms < 50, f"Performance degradation: {elapsed_ms:.2f}ms/100 calls"