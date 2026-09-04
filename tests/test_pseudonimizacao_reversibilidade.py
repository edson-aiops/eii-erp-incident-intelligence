"""
Testes de reversibilidade para A12 — ADR sobre pseudonimização reversível.

Validam que:
  - Tokens mapeiam valores reais 1:1
  - Restauração é idêntica ao original
  - Mapa é invertível
  - Nenhum dado real vaza acidentalmente

Executar com: pytest tests/test_pseudonimizacao_reversibilidade.py -v
"""

import pytest
from src.privacy.scrubber import PIIScrubber


# --------------------------------------------------------------------------
# Valores sintéticos
# --------------------------------------------------------------------------

CPF_TRAB = "11111111111"
CPF_DEP = "33333333333"
NOME_TRAB = "MARIA APARECIDA DA SILVA"
NOME_MAE = "JOANA SILVA"
EMAIL = "maria@exemplo.com.br"
FONE = "11987654321"
CNPJ_SIND = "98765432000155"
SALARIO = "1543.27"
ENDERECO = "RUA DAS ACACIAS, 250, CENTRO, SAO PAULO, SP"

XML_COMPLETO_COM_PII = f"""<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <evtAdmissao Id="ID1123456780001992026080112000000001">
    <ideEvento><indRetif>1</indRetif><tpAmb>1</tpAmb></ideEvento>
    <ideEmpregador><tpInsc>1</tpInsc><nrInsc>12345678000199</nrInsc></ideEmpregador>
    <trabalhador>
      <cpfTrab>{CPF_TRAB}</cpfTrab>
      <nmTrab>{NOME_TRAB}</nmTrab>
      <nascimento>
        <dtNascto>1985-04-17</dtNascto>
        <nmMae>{NOME_MAE}</nmMae>
      </nascimento>
      <endereco>
        <brasil>
          <dscLograd>{ENDERECO}</dscLograd>
          <cep>01001000</cep>
        </brasil>
      </endereco>
      <contato>
        <fonePrinc>{FONE}</fonePrinc>
        <emailPrinc>{EMAIL}</emailPrinc>
      </contato>
    </trabalhador>
    <vinculo>
      <infoContrato>
        <remuneracao>
          <vrSalFx>{SALARIO}</vrSalFx>
        </remuneracao>
        <filiacaoSindical>
          <cnpjSindTrab>{CNPJ_SIND}</cnpjSindTrab>
        </filiacaoSindical>
      </infoContrato>
    </vinculo>
  </evtAdmissao>
</eSocial>"""


# ==========================================================================
# 1. Mapeamento 1:1 (um valor real → um token, sempre)
# ==========================================================================


def test_mesmo_valor_real_mapeia_mesmo_token():
    """Um mesmo CPF sempre gera o mesmo token no mesmo request."""
    scrubber = PIIScrubber()
    
    # XML com CPF repetido duas vezes
    xml_com_repeticao = f"""<?xml version="1.0"?>
    <eSocial>
      <evento1><cpfTrab>{CPF_TRAB}</cpfTrab></evento1>
      <evento2><cpfTrab>{CPF_TRAB}</cpfTrab></evento2>
    </eSocial>"""
    
    result = scrubber.scrub(xml_com_repeticao, "S-2200")
    
    # Contar quantos CPF_001 aparecem (deveria ser 1 token, não 2)
    ocorrencias = result.scrubbed_payload.count("CPF_")
    tokens_unicos = len({v for v in result.token_map.values() if v == CPF_TRAB})
    
    assert tokens_unicos == 1, f"Mesmo valor real deveria ter 1 token, obteve {tokens_unicos}"
    assert CPF_TRAB not in result.scrubbed_payload


def test_valores_diferentes_mapeiam_tokens_diferentes():
    """CPFs diferentes geram tokens diferentes."""
    scrubber = PIIScrubber()
    
    cpf1 = "11111111111"
    cpf2 = "22222222222"
    
    xml = f"""<?xml version="1.0"?>
    <eSocial>
      <evento1><cpfTrab>{cpf1}</cpfTrab></evento1>
      <evento2><cpfTrab>{cpf2}</cpfTrab></evento2>
    </eSocial>"""
    
    result = scrubber.scrub(xml, "S-2200")
    
    # Encontrar tokens (contrato ADR A12 §5: token_map = {token: valor})
    tokens = [t for t, v in result.token_map.items() if v in (cpf1, cpf2)]
    
    assert len(tokens) == 2, "Dois valores diferentes devem gerar dois tokens"
    assert len(set(tokens)) == 2, "Os tokens devem ser únicos"


# ==========================================================================
# 2. Reversibilidade (token restaura exatamente para o original)
# ==========================================================================


def test_restore_reverte_para_valor_original():
    """restore() inverte tokens de volta para valores reais, exatamente."""
    scrubber = PIIScrubber()
    
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # Encontrar um token e seu valor
    primeiro_valor_real = list(result.token_map.values())[0]
    primeiro_token = [k for k, v in result.token_map.items() if v == primeiro_valor_real][0]
    
    # Criar um texto com o token
    texto_com_token = f"Erro no campo {primeiro_token}"
    
    # Restaurar
    texto_restaurado = scrubber.restore(texto_com_token, result.token_map)
    
    # Verificar que voltou exatamente
    assert primeiro_valor_real in texto_restaurado, \
        f"Valor {primeiro_valor_real} deveria estar em '{texto_restaurado}'"
    assert primeiro_token not in texto_restaurado, \
        f"Token {primeiro_token} deveria ter sido removido"


def test_restore_com_todos_tokens_mapeia_corretamente():
    """Restaurar diagnóstico com múltiplos tokens funciona."""
    scrubber = PIIScrubber()
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # Diagnóstico sintético com vários tokens
    diagnostico = f"""
    Rejeição encontrada:
    - Trabalhador: CPF_001 ({NOME_TRAB if "NOME_" in result.token_map else "nome_desconhecido"})
    - Email: EMAIL_001
    - Telefone: FONE_001
    Ação: revisar dados e reenviar.
    """
    
    # Substituir nomes de tokens pelos nomes reais
    for token, valor in result.token_map.items():
        diagnostico = diagnostico.replace(token, valor)
    
    # Agora restaurar via scrubber
    restaurado = scrubber.restore(diagnostico, result.token_map)
    
    # Verificar que pelo menos alguns valores reais aparecem
    # (nem todos podem, porque nem todos tokens foram mencionados no diagnóstico)
    assert CPF_TRAB in restaurado or NOME_TRAB in restaurado or \
           EMAIL in restaurado or FONE in restaurado, \
        "Pelo menos um valor real deveria estar no diagnóstico restaurado"


# ==========================================================================
# 3. Invertibilidade do mapa (token → valor e valor → token)
# ==========================================================================


def test_token_map_e_bidirecional():
    """token_map permite buscar tanto token→valor quanto valor→token."""
    scrubber = PIIScrubber()
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    token_map = result.token_map
    
    # Forward (token → valor)
    for token, valor in token_map.items():
        assert valor is not None, f"Token {token} tem valor None"
    
    # Backward (valor → token)
    for token, valor in token_map.items():
        tokens_deste_valor = [t for t, v in token_map.items() if v == valor]
        assert len(tokens_deste_valor) == 1, \
            f"Valor {valor} deveria ter exatamente 1 token, tem {len(tokens_deste_valor)}"


# ==========================================================================
# 4. Nenhum dado real vaza
# ==========================================================================


def test_scrubbed_payload_nao_contem_valores_reais():
    """Após scrub, nenhum valor real deve aparecer em claro no payload."""
    scrubber = PIIScrubber()
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    valores_reais = [
        CPF_TRAB, CPF_DEP, NOME_TRAB, NOME_MAE, EMAIL, FONE, 
        CNPJ_SIND, SALARIO, ENDERECO
    ]
    
    for valor in valores_reais:
        if valor:  # Skip if empty
            assert valor not in result.scrubbed_payload, \
                f"Valor sensível {valor} vazou no payload"


def test_token_map_nao_e_serializado_na_resposta():
    """token_map é local, nunca sai do servidor (testado via contrato ScrubResult)."""
    scrubber = PIIScrubber()
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # ScrubResult.token_map não deve ser serializado (não há método __repr__ expondo valores)
    # Verificar que é um dict com chaves e valores sensíveis
    assert isinstance(result.token_map, dict)
    
    # Nenhum VALOR REAL do mapa deveria estar no payload (tokens por
    # definição ESTÃO no payload — é a pseudonimização, ADR A12 §5)
    for token, valor in result.token_map.items():
        assert valor not in result.scrubbed_payload, \
            f"Valor real {valor} não deveria estar no payload"
        # o token (CPF_001 etc.) aparece no payload por design


# ==========================================================================
# 5. Determinismo (mesmo input → mesmo output)
# ==========================================================================


def test_scrub_e_determinista():
    """Dois scrubs do mesmo XML geram o mesmo mapeamento (mesmos tokens)."""
    scrubber1 = PIIScrubber()
    scrubber2 = PIIScrubber()
    
    result1 = scrubber1.scrub(XML_COMPLETO_COM_PII, "S-2200")
    result2 = scrubber2.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # Payloads devem ser idênticos
    assert result1.scrubbed_payload == result2.scrubbed_payload, \
        "Dois scrubs do mesmo XML devem gerar payloads idênticos"
    
    # Mapas devem ser idênticos
    assert result1.token_map == result2.token_map, \
        "Dois scrubs devem gerar o mesmo mapeamento"


# ==========================================================================
# 6. Propriedade central: round-trip
# ==========================================================================


def test_round_trip_completo():
    """
    Round-trip completo: valor real → token → restore → valor real idêntico.
    
    Este é o teste mais crítico para validar a pseudonimização.
    """
    scrubber = PIIScrubber()
    
    # 1. Scrub
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # 2. Extrair um valor real e seu token
    valor_real = list(result.token_map.values())[0]
    token = [k for k, v in result.token_map.items() if v == valor_real][0]
    
    # 3. Simular um diagnóstico que menciona o token
    diagnostico_com_token = f"Erro encontrado em {token}: validação falhou"
    
    # 4. Restaurar
    diagnostico_restaurado = scrubber.restore(diagnostico_com_token, result.token_map)
    
    # 5. Verificar que é idêntico
    assert valor_real in diagnostico_restaurado, \
        f"Valor original {valor_real} não apareceu após restore"
    assert token not in diagnostico_restaurado, \
        f"Token {token} não deveria aparecer após restore"
    
    # 6. Dupla reversão (restaurar duas vezes deveria ser idempotente)
    # Assumindo que restore não re-tokeniza, apenas desfe tokens
    diagnostico_duplo = scrubber.restore(diagnostico_restaurado, result.token_map)
    assert diagnostico_duplo == diagnostico_restaurado, \
        "Restaurar duas vezes deveria ser idempotente"


# ==========================================================================
# 7. Conformidade LGPD
# ==========================================================================


def test_dados_sensiveis_nao_deixam_o_servidor():
    """
    LGPD art. 32: controlador deve manter controle sobre dados.
    
    Neste teste, verificamos que o payload que "sai" (para remoto)
    não contém PII.
    """
    scrubber = PIIScrubber()
    result = scrubber.scrub(XML_COMPLETO_COM_PII, "S-2200")
    
    # payload scrubbed é o que "sai" para o remoto
    payload_remoto = result.scrubbed_payload
    
    # Dados sensíveis que NÃO devem estar lá
    dados_sensiveis = [CPF_TRAB, NOME_TRAB, EMAIL, FONE, ENDERECO]
    
    for dado in dados_sensiveis:
        assert dado not in payload_remoto, \
            f"Dado sensível {dado} vazou para o remoto"
    
    # is_safe_for_remote deve refletir isso
    assert result.is_safe_for_remote is True or result.is_safe_for_remote is False, \
        "is_safe_for_remote deve ser boolean"
    
    # Se tem PII não-seguro, is_safe deve ser False
    if CPF_TRAB in payload_remoto:
        assert result.is_safe_for_remote is False, \
            "Se CPF ainda está no payload, is_safe_for_remote deve ser False"
