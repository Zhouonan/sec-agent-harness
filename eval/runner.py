import os
import time
import shutil
from datetime import datetime
from typing import Optional

from core.loop import AgentLoop, AgentState
from eval.schema import EvalCase, EvalCaseResult
from eval.judge import LLMJudge
from eval.scorer import Scorer


class EvalRunner:
    """Runs a single evaluation case: forks workspace, executes agent, scores results."""

    def __init__(self, judge: LLMJudge = None, scorer: Scorer = None,
                 model: str = None, api_key: str = None, base_url: str = None):
        self.judge = judge or LLMJudge(model=model, api_key=api_key, base_url=base_url)
        self.scorer = scorer or Scorer()
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def run_single(self, case: EvalCase, prompt: str = None,
                   run_id: str = None) -> EvalCaseResult:
        """Execute a single case evaluation.

        1. Fork case to challenge/runs/
        2. Create AgentLoop in forked workspace
        3. Run agent loop
        4. Read results and score
        """
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = run_id or f"run_{timestamp_str}"

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        runs_root = os.path.join(project_root, "challenge", "runs")
        os.makedirs(runs_root, exist_ok=True)

        forked_dir = os.path.join(runs_root, f"{run_id}_{case.name}")
        if os.path.exists(forked_dir):
            shutil.rmtree(forked_dir)
        shutil.copytree(case.source_dir, forked_dir)

        prompt = prompt or (
            "Analyze and fix the vulnerability in 'vulnerable_code.c'.\n"
            "IMPORTANT: This is a C snippet. Create a wrapper with main() to compile.\n"
            "Follow the FSM: Analyze -> Validate -> Fix -> Review."
        )

        print(f"\n[{case.name}] Running evaluation in: {forked_dir}")

        loop = AgentLoop(
            workspace_path=forked_dir,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
        )

        start_time = time.time()
        try:
            final_state = loop.run(prompt)
        except Exception as e:
            # Agent crashed — build a minimal result
            duration = time.time() - start_time
            return EvalCaseResult(
                case_name=case.name,
                dataset=case.metadata.get("dataset", ""),
                run_id=run_id,
                timestamp=datetime.now().isoformat(),
                model=loop.model,
                final_state="ERROR",
                duration_seconds=round(duration, 2),
                total_turns=0,
                error_info=str(e),
                log_file=loop.log_file,
            )

        duration = time.time() - start_time

        # Read patched code from forked workspace
        patched_code = ""
        vulnerable_path = os.path.join(forked_dir, "vulnerable_code.c")
        if os.path.isfile(vulnerable_path):
            with open(vulnerable_path, "r", encoding="utf-8") as f:
                patched_code = f.read()

        # Count turns per state
        turns_per_state = {}
        for entry in final_state.turn_log:
            s = entry.get("state", "UNKNOWN")
            turns_per_state[s] = turns_per_state.get(s, 0) + 1

        # Judge scoring
        judge_result = self.judge.score(
            vulnerable_code=case.vulnerable_code,
            patched_code=patched_code,
            ground_truth=case.ground_truth,
            cwe_id=case.cwe_id,
        )

        # Process & efficiency scoring
        process_score = self.scorer.compute_process_score(
            state_path=final_state.state_path,
            blackboard=final_state.blackboard,
            final_state=final_state.current_state.name,
        )
        efficiency_score = self.scorer.compute_efficiency_score(
            total_turns=final_state.turn_count,
            duration_seconds=duration,
        )
        composite = self.scorer.compute_composite(
            correctness=judge_result["total_score"],
            process=process_score,
            efficiency=efficiency_score,
        )

        return EvalCaseResult(
            case_name=case.name,
            dataset=case.metadata.get("dataset", ""),
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            model=loop.model,
            final_state=final_state.current_state.name,
            duration_seconds=round(duration, 2),
            total_turns=final_state.turn_count,
            turns_per_state=turns_per_state,
            state_path=final_state.state_path,
            correctness_score=judge_result["total_score"],
            correctness_reasoning=judge_result["reasoning"],
            process_score=process_score,
            efficiency_score=efficiency_score,
            composite_score=composite,
            patched_code=patched_code,
            error_info=final_state.stop_reason,
            log_file=loop.log_file,
            turn_log=final_state.turn_log,
        )
