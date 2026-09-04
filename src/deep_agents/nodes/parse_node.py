import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState, IncidentContext

# Reutiliza o parser ja testado em producao em vez de duplicar regex
from xml_parser import parse_esocial_xml
from src.privacy.scrubber import PIIScrubber
from src.utils.tokenmap_store import get_token_map_store

logger = logging.getLogger(__name__)


def detect_severity(xml_raw: str) -> str:
    """Heurística simples de severidade baseada em palavras-chave do XML."""
    text = (xml_raw or "").upper()
    if any(code in text for code in ("E500", "E001", "E002", "E003", "E428")):
        return "critica"
    if any(code in text for code in ("E469", "E214", "E312", "E401")):
        return "alta"
    if any(evt in text for evt in ("S-1200", "S-2200", "S-2400", "S-2300", "S-5001", "S-5002", "S-5011", "S-5012")):
        return "alta"
    if any(evt in text for evt in ("S-2230", "S-2299", "S-3000", "S-5003")):
        return "media"
    return "baixa"


def extract_ids(xml_raw: str) -> tuple[str, str]:
    """Extrai evento_id e tipo_evento do XML bruto."""
    import re
    tipo_evento = "DESCONHECIDO"
    evento_id = ""
    # Tenta extrair tipo do atributo Id (ex.: ID1... => evento derivado do conteúdo)
    id_match = re.search(r'Id="([^"]+)"', xml_raw)
    if id_match:
        evento_id = id_match.group(1)
        # eSocial Id começa com ID + tpInsc (1 pos) + nrInsc (14 pos) + timestamp + seq
        # Não carrega tipo de evento; inferimos pela tag raiz do evento.
    tag_match = re.search(r'<(evt[A-Za-z0-9]+)', xml_raw)
    if tag_match:
        tag = tag_match.group(1)
        # Mapeamento comum de tag para tipo de evento
        tag_to_evento = {
            "evtAdmissao": "S-2200",
            "evtRemun": "S-1200",
            "evtTSVInicio": "S-2300",
            "evtTSVTermino": "S-2399",
            "evtDeslig": "S-2299",
            "evtAfastTemp": "S-2230",
            "evtCAT": "S-2210",
            "evtExpRisco": "S-2240",
            "evtInfoComplPer": "S-1207",
            "evtPgtos": "S-1210",
            "evtIrrf": "S-3000",
        }
        tipo_evento = tag_to_evento.get(tag, "DESCONHECIDO")
    return evento_id, tipo_evento


async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
    """Parseia o XML eSocial e aplica PIIScrubber obrigatório."""
    xml = state.get("payload") or state.get("xml_input", "")

    try:
        parsed = parse_esocial_xml(xml)

        if parsed.erro:
            logger.warning(f"Parse error: {parsed.erro}")
            return {
                "errors": [f"Erro no parse XML: {parsed.erro}"],
                "context": IncidentContext(
                    evento="PARSE_ERROR",
                    codigo_erro="E000",
                    xml_raw=xml[:500],
                    metadata={"parse_success": False},
                ),
            }

        evento_id, tipo_evento = extract_ids(xml)

        # Chamar scrubber v2
        scrubber = PIIScrubber()
        try:
            scrub_result = scrubber.scrub(xml, tipo_evento)
            is_safe = scrub_result.is_safe_for_remote
            scrubbed_payload = scrub_result.scrubbed_payload
            token_map = scrub_result.token_map
        except Exception as e:
            logger.error(f"Scrubber exception: {e}")
            scrubbed_payload = xml
            is_safe = False
            token_map = {}

        # A25: token_map sai do estado do grafo e vai para a store (Redis/TTL)
        incident_id = state.get("incident_id", "")
        if token_map and incident_id:
            try:
                get_token_map_store().set(incident_id, token_map)
            except Exception as e:
                logger.warning(f"parse_node: falha ao persistir token_map: {e}")

        pi_detected = []
        if parsed.nr_inscricao and "***" in parsed.nr_inscricao:
            pi_detected.append("CNPJ/CPF")

        codigo_erro = (
            parsed.ocorrencias[0].codigo if parsed.ocorrencias else parsed.cd_resposta or "N/A"
        )

        context = IncidentContext(
            evento=parsed.tipo_evento or tipo_evento or parsed.formato or "DESCONHECIDO",
            codigo_erro=codigo_erro,
            xml_raw=scrubbed_payload[:1000],
            pi_detected=pi_detected,
            metadata={
                "parse_success": True,
                "formato": parsed.formato,
                "cd_resposta": parsed.cd_resposta,
                "nr_recibo": parsed.nr_recibo,
                "ocorrencias_count": len(parsed.ocorrencias),
                "ocorrencias": [
                    {"codigo": o.codigo, "descricao": o.descricao}
                    for o in parsed.ocorrencias[:5]
                ],
            },
        )

        logger.info(
            f"Parsed: evento={context.evento}, erro={codigo_erro}, "
            f"PII={pi_detected}, is_safe_for_remote={is_safe}"
        )

        warnings = [f"PII detectado: {', '.join(pi_detected)}"] if pi_detected else []
        return {
            "context": context,
            "warnings": warnings,
            "scrubbed_payload": scrubbed_payload,
            "is_safe_for_remote": is_safe,
            # A25: token_map NÃO viaja no estado — fica na store (Redis/TTL)
            "pii_scrubbed": True,
            "evento_id": evento_id,
            "tipo_evento": tipo_evento,
            "severidade": detect_severity(scrubbed_payload),
        }

    except Exception as e:
        logger.error(f"Erro no parse XML: {e}")
        return {
            "errors": [f"Erro no parse XML: {str(e)}"],
            "context": IncidentContext(
                evento="PARSE_ERROR",
                codigo_erro="E000",
                xml_raw=state.get("xml_input", "")[:500],
                metadata={"parse_success": False},
            ),
            "is_safe_for_remote": False,
            "pii_scrubbed": False,
        }


# Alias de compatibilidade com o contrato A25 (testes referenciam parse_node)
parse_node = parse_xml_node
