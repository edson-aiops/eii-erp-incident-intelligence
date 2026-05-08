import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState, IncidentContext

# Reutiliza o parser ja testado em producao em vez de duplicar regex
from xml_parser import parse_esocial_xml

logger = logging.getLogger(__name__)


async def parse_xml_node(state: AgentState) -> Dict[str, Any]:
    """Parseia o XML eSocial reutilizando xml_parser.py (PII scrub incluso)."""
    try:
        xml = state["xml_input"]
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

        pi_detected = []
        if parsed.nr_inscricao and "***" in parsed.nr_inscricao:
            pi_detected.append("CNPJ/CPF")

        codigo_erro = (
            parsed.ocorrencias[0].codigo if parsed.ocorrencias else parsed.cd_resposta or "N/A"
        )

        context = IncidentContext(
            evento=parsed.tipo_evento or parsed.formato or "DESCONHECIDO",
            codigo_erro=codigo_erro,
            xml_raw=xml[:1000],
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

        logger.info(f"Parsed: evento={context.evento}, erro={codigo_erro}, PII={pi_detected}")

        warnings = [f"PII detectado: {', '.join(pi_detected)}"] if pi_detected else []
        return {"context": context, "warnings": warnings}

    except Exception as e:
        logger.error(f"Erro no parse XML: {e}")
        return {
            "errors": [f"Erro no parse XML: {str(e)}"],
            "context": IncidentContext(
                evento="PARSE_ERROR",
                codigo_erro="E000",
                xml_raw=state["xml_input"][:500],
                metadata={"parse_success": False},
            ),
        }
