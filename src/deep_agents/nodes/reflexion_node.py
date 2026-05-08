import logging
from typing import Dict, Any
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)


async def reflexion_node(state: AgentState) -> Dict[str, Any]:
    """Self-critique loop: calls crag_pipeline.reflect() to build a corrective hint.

    The reflection text is stored in evaluation_feedback so that generate_node
    picks it up as corrective_hint on the next iteration.
    Increments iteration_count to enforce the MAX_ITERATIONS guard in evaluate_node.
    """
    from crag_pipeline import reflect
    from xml_parser import parse_esocial_xml

    context = state.get("context")
    diagnosis = state.get("diagnosis")
    iteration_count = state.get("iteration_count", 0) + 1
    feedback = state.get("evaluation_feedback", "")

    logger.info(
        "reflexion_node: iteration=%d, feedback=%r", iteration_count, feedback[:80]
    )

    warnings = list(state.get("warnings", []))
    warnings.append(f"Reflexion aplicada na iteracao {iteration_count}")

    if context is None or diagnosis is None:
        return {
            "iteration_count": iteration_count,
            "evaluation_feedback": feedback,
            "warnings": warnings,
        }

    try:
        parsed_xml = parse_esocial_xml(context.xml_raw)
        eval_result = {
            "critique": feedback,
            "criteria_failed": [],
            "regeneration_hint": feedback,
        }
        reflection_text = reflect(parsed_xml, diagnosis, eval_result)
        logger.info(
            "reflexion_node: reflection produced %d chars", len(reflection_text)
        )
        return {
            "iteration_count": iteration_count,
            "evaluation_feedback": reflection_text,
            "warnings": warnings,
        }
    except Exception as e:
        logger.error("reflexion_node: reflect() failed: %s", e)
        return {
            "iteration_count": iteration_count,
            "evaluation_feedback": feedback,
            "warnings": warnings,
        }
