from typing import TypedDict, List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field

@dataclass
class IncidentContext:
    evento: str
    codigo_erro: str
    xml_raw: str
    pi_detected: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)  # era 'meta' no parse_node — corrigido

@dataclass
class RetrievedKnowledge:
    documents: List[Dict]
    relevance_scores: List[float]
    kb_version: str

@dataclass
class Diagnosis:
    incident_id: str
    root_cause: str
    resolution_steps: List[str]
    validation_steps: List[str]
    confidence: Literal["ALTA", "MEDIA", "BAIXA"]
    logprobs: float
    mentor_notes: Optional[str] = None
    hitl_checklist: List[Dict] = field(default_factory=list)

class AgentState(TypedDict):
    xml_input: str
    payload: Optional[str]                # alias opcional para xml_input (usado pelo scrubber)
    incident_id: str
    use_mentor_mode: bool
    context: Optional[IncidentContext]
    retrieved: Optional[RetrievedKnowledge]
    diagnosis: Optional[Dict[str, Any]]   # dict para compatibilidade com finalize_node
    evaluation_score: Optional[float]
    evaluation_feedback: Optional[str]
    needs_refinement: bool                # usado por should_reflexion — estava faltando
    iteration_count: int
    max_iterations: int
    routing_decision: Optional[str]
    retrieval_backend: str
    model_used: Optional[str]
    errors: List[str]
    warnings: List[str]
    final_result: Optional[Dict[str, Any]]
    proactive_insights: Optional[Dict[str, Any]]
    # Campos do PIIScrubber (A3)
    scrubbed_payload: Optional[str]
    is_safe_for_remote: Optional[bool]
    token_map: Optional[Dict[str, str]]
    pii_scrubbed: Optional[bool]
