import logging
from typing import Dict, Any, Literal
from src.deep_agents.state import AgentState

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 2  # matches crag_pipeline.MAX_EVAL_ITERATIONS


async def evaluate_node(state: AgentState) -> Dict[str, Any]:
    """Evaluate diagnosis quality using crag_pipeline.evaluate_diagnosis().

    Sets needs_refinement=True when the verdict is REJECTED and we haven't
    hit max_iterations yet, triggering the reflexion loop in should_reflexion().
    """
    from crag_pipeline import evaluate_diagnosis
    from xml_parser import parse_esocial_xml

    context = state.get("context")
    diagnosis = state.get("diagnosis")
    retrieved = state.get("retrieved")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", MAX_ITERATIONS)

    # Hard stop: never loop more than max_iterations times
    if iteration_count >= max_iterations:
        logger.info(
            "evaluate_node: max_iterations=%d reached — forcing finalize", max_iterations
        )
        return {"evaluation_score": 0.5, "evaluation_feedback": "", "needs_refinement": False}

    if context is None or diagnosis is None:
        return {"evaluation_score": 0.0, "evaluation_feedback": "", "needs_refinement": False}

    try:
        parsed_xml = parse_esocial_xml(context.xml_raw)
    except Exception as e:
        logger.error("evaluate_node: re-parse failed: %s", e)
        return {"evaluation_score": 0.5, "evaluation_feedback": str(e), "needs_refinement": False}

    relevant = []
    if retrieved and retrieved.documents:
        for doc in retrieved.documents:
            relevant.append({"item": doc, "distance": 0.3, "id": doc.get("id", "")})

    try:
        eval_result = evaluate_diagnosis(parsed_xml, diagnosis, relevant, iteration_count)
    except Exception as e:
        logger.error("evaluate_node: evaluate_diagnosis() failed: %s", e)
        return {"evaluation_score": 0.5, "evaluation_feedback": str(e), "needs_refinement": False}

    passed = len(eval_result.get("criteria_passed", []))
    total = passed + len(eval_result.get("criteria_failed", []))
    score = passed / total if total > 0 else 0.5

    needs_refinement = eval_result.get("should_regenerate", False)
    feedback = eval_result.get("regeneration_hint") or eval_result.get("critique", "")

    logger.info(
        "evaluate_node: verdict=%s, score=%.2f, needs_refinement=%s",
        eval_result.get("verdict"), score, needs_refinement,
    )

    try:
        from observability import add_run_metadata
        add_run_metadata({
            "incident_id": state.get("incident_id"),
            "eval_verdict": eval_result.get("verdict"),
            "eval_score": round(score, 3),
            "eval_iteration": iteration_count,
            "needs_refinement": needs_refinement,
            "criteria_passed": eval_result.get("criteria_passed", []),
            "criteria_failed": eval_result.get("criteria_failed", []),
        })
    except Exception:
        pass

    return {
        "evaluation_score": score,
        "evaluation_feedback": feedback,
        "needs_refinement": needs_refinement,
    }


def should_reflexion(state: AgentState) -> Literal["reflexion", "finalize"]:
    """Conditional edge: go to reflexion if diagnosis needs refinement, else finalize."""
    return "reflexion" if state.get("needs_refinement", False) else "finalize"
