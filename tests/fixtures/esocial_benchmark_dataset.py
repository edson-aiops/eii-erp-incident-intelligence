"""
Dataset sintético A7/A8 — 20 XMLs eSocial para benchmark dos motores.

Composição:
- 10 XMLs válidos (S-1200, S-2200, S-2300, S-2299, S-2230, S-1210, S-2400, ...)
- 5 XMLs com erros comuns (CPF inválido, nrInsc divergente, evento sem
  trabalhador, data inválida, versão leiaute inexistente)
- 5 edge cases (XML vazio, malformado, evento desconhecido, payload apenas
  com PII, lote grande)

Todos os dados são sintéticos (CPFs/nomes fictícios) — seguros para CI.
"""

# ---------------------------------------------------------------------------
# 10 XMLs válidos
# ---------------------------------------------------------------------------

VALIDOS = [
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000001">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<trabalhador><cpfTrab>11111111112</cpfTrab><nmTrab>JOAO SILVA</nmTrab></trabalhador>
</evtAdmissao></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtRemun Id="ID1123456780001992026080112000000002">
<ideEvento><indRetif>1</indRetif><perApur>2026-08</perApur></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>22222222223</cpfTrab></ideTrabalhador>
</evtRemun></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtTSVInicio Id="ID1123456780001992026080112000000003">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<trabalhadorTSV><cpfTrab>33333333334</cpfTrab><nmTrab>ANA COSTA</nmTrab></trabalhadorTSV>
</evtTSVInicio></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtDeslig Id="ID1123456780001992026080112000000004">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>44444444445</cpfTrab></ideTrabalhador>
<infoDeslig><dtDeslig>2026-08-15</dtDeslig></infoDeslig>
</evtDeslig></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAfastTemp Id="ID1123456780001992026080112000000005">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>55555555556</cpfTrab></ideTrabalhador>
<infoAfastamento><dtIniAfast>2026-08-01</dtIniAfast><codMotAfast>01</codMotAfast></infoAfastamento>
</evtAfastTemp></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtPgtos Id="ID1123456780001992026080112000000006">
<ideEvento><indRetif>1</indRetif><perApur>2026-08</perApur></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideBenef><cpfBenef>66666666667</cpfBenef></ideBenef>
</evtPgtos></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtCadInicial Id="ID1123456780001992026080112000000007">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<infoEmpregador><nmRazao>EMPRESA TESTE LTDA</nmRazao></infoEmpregador>
</evtCadInicial></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtTabRubrica Id="ID1123456780001992026080112000000008">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb><versao>1.3</versao></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<infoRubrica><codRubr>001</codRubr><ideTabRubra>1</ideTabRubra></infoRubrica>
</evtTabRubrica></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtCAT Id="ID1123456780001992026080112000000009">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>77777777778</cpfTrab></ideTrabalhador>
<cat><dtAcid>2026-08-10</dtAcid></cat>
</evtCAT></eSocial>""",
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtExpRisco Id="ID1123456780001992026080112000000010">
<ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>88888888889</cpfTrab></ideTrabalhador>
<infoExpRisco><dtIniCondicao>2026-01-01</dtIniCondicao></infoExpRisco>
</evtExpRisco></eSocial>""",
]

# ---------------------------------------------------------------------------
# 5 XMLs com erros comuns
# ---------------------------------------------------------------------------

ERROS = [
    # CPF inválido (dígito verificador errado)
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000011">
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<trabalhador><cpfTrab>11111111111</cpfTrab><nmTrab>MARIA DOS SANTOS</nmTrab></trabalhador>
</evtAdmissao></eSocial>""",
    # nrInsc divergente do CNPJ de abertura
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000012">
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>99999999000199</nrInsc></ideEmpregador>
<trabalhador><cpfTrab>12345678901</cpfTrab><nmTrab>CARLOS PEREIRA</nmTrab></trabalhador>
</evtAdmissao></eSocial>""",
    # Evento S-1200 sem trabalhador
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtRemun Id="ID1123456780001992026080112000000013">
<ideEvento><perApur>2026-08</perApur></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
</evtRemun></eSocial>""",
    # Data de desligamento inválida
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtDeslig Id="ID1123456780001992026080112000000014">
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<ideTrabalhador><cpfTrab>44444444445</cpfTrab></ideTrabalhador>
<infoDeslig><dtDeslig>2026-13-45</dtDeslig></infoDeslig>
</evtDeslig></eSocial>""",
    # Retificação sem número do recibo
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000015">
<ideEvento><indRetif>2</indRetif><nrRecibo></nrRecibo></ideEvento>
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<trabalhador><cpfTrab>55555555556</cpfTrab><nmTrab>ANA COSTA</nmTrab></trabalhador>
</evtAdmissao></eSocial>""",
]

# ---------------------------------------------------------------------------
# 5 edge cases
# ---------------------------------------------------------------------------

EDGE_CASES = [
    # XML vazio
    "",
    # XML malformado
    """<?xml version="1.0"?>
<eSocial><evtAdmissao><trabalhador><cpfTrab>111""",
    # Evento desconhecido
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtEventoNovo Id="ID1123456780001992026080112000000018">
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
</evtEventoNovo></eSocial>""",
    # Payload apenas com PII (teste fail-closed)
    """<?xml version="1.0" encoding="UTF-8"?>
<eSocial><evtAdmissao Id="ID1123456780001992026080112000000019">
<ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
<trabalhador><cpfTrab>98765432100</cpfTrab><nmTrab>PIA ONLY DATA</nmTrab>
<contato><emailPrinc>pia@teste.com</emailPrinc><fonePrinc>11999999999</fonePrinc></contato>
</trabalhador></evtAdmissao></eSocial>""",
    # Lote grande (10 eventos repetidos)
    "<eSocial>" + "".join(
        f'<evtRemun Id="ID11234567800019920260801120000002{i:02d}">'
        f'<ideTrabalhador><cpfTrab>1111111111{i % 10}</cpfTrab></ideTrabalhador>'
        f'</evtRemun>'
        for i in range(10)
    ) + "</eSocial>",
]

# ---------------------------------------------------------------------------
# API pública do dataset
# ---------------------------------------------------------------------------

CATEGORIAS = {
    "valido": VALIDOS,
    "erro": ERROS,
    "edge": EDGE_CASES,
}


def dataset_completo() -> list:
    """Retorna os 20 XMLs na ordem: válidos, erros, edge cases."""
    return VALIDOS + ERROS + EDGE_CASES
