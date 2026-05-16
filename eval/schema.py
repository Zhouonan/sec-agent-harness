from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class EvalCase:
    """Single evaluation case loaded from a dataset."""
    name: str
    source_dir: str
    vulnerable_code: str
    ground_truth: str
    cwe_id: str
    cve_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalCaseResult:
    """Result of running a single evaluation case."""
    case_name: str
    dataset: str
    run_id: str
    timestamp: str
    model: str
    final_state: str
    duration_seconds: float
    total_turns: int
    turns_per_state: Dict[str, int] = field(default_factory=dict)
    state_path: List[str] = field(default_factory=list)

    correctness_score: float = 0.0
    correctness_reasoning: str = ""
    process_score: float = 0.0
    efficiency_score: float = 0.0
    composite_score: float = 0.0

    patched_code: str = ""
    error_info: Optional[str] = None
    log_file: str = ""
    turn_log: List[Dict[str, Any]] = field(default_factory=list)
