from typing import Dict, Any


DEFAULT_WEIGHTS = {
    "correctness": 0.50,
    "process": 0.25,
    "efficiency": 0.25,
}

REQUIRED_STATES = {"INITIAL_ANALYSIS", "VALIDATOR", "FIXER", "REVIEWER"}


class Scorer:
    """Multi-dimension scoring for agent evaluation results."""

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def compute_process_score(self, state_path: list, blackboard: dict, final_state: str) -> float:
        """Score FSM process completeness (0-1)."""
        visited = set(state_path)

        # How many of the 4 required states were visited?
        coverage = len(visited & REQUIRED_STATES) / len(REQUIRED_STATES)

        # Did the agent reach DONE?
        done_bonus = 0.2 if final_state == "DONE" else 0.0

        # Blackboard has summaries?
        summary_count = sum(1 for k in blackboard if k.endswith("_summary"))
        summary_bonus = min(summary_count / len(REQUIRED_STATES), 1.0) * 0.2

        score = min(coverage + done_bonus + summary_bonus, 1.0)
        return round(score, 4)

    def compute_efficiency_score(self, total_turns: int, duration_seconds: float,
                                 max_turns: int = 40, max_duration: float = 600.0) -> float:
        """Score efficiency normalized against budget (0-1)."""
        turn_ratio = max(0, 1.0 - (total_turns / max_turns))
        time_ratio = max(0, 1.0 - (duration_seconds / max_duration))
        score = (turn_ratio * 0.5) + (time_ratio * 0.5)
        return round(max(0, min(1.0, score)), 4)

    def compute_composite(self, correctness: float, process: float, efficiency: float) -> float:
        """Weighted composite score."""
        return round(
            correctness * self.weights["correctness"]
            + process * self.weights["process"]
            + efficiency * self.weights["efficiency"],
            4,
        )
