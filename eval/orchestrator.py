import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime
from typing import List, Optional

from eval.schema import EvalCase, EvalCaseResult
from eval.datasets import DatasetProvider
from eval.runner import EvalRunner
from eval.reporter import Reporter


class RunOrchestrator:
    """Orchestrates multi-case evaluation runs with parallel execution."""

    def __init__(self, parallel: int = 1, per_case_timeout: int = 1200):
        self.parallel = max(1, parallel)
        self.per_case_timeout = per_case_timeout

    def run(self, dataset: DatasetProvider, cases: List[str],
            runner: EvalRunner = None) -> List[EvalCaseResult]:
        """Run multiple cases, optionally in parallel. Returns results for all cases."""
        if runner is None:
            runner = EvalRunner()

        run_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results: List[EvalCaseResult] = []
        total = len(cases)

        print(f"\n{'='*60}")
        print(f"Evaluation Run: {run_id}")
        print(f"Cases: {total}  |  Parallel: {self.parallel}  |  Timeout: {self.per_case_timeout}s")
        print(f"{'='*60}\n")

        if self.parallel == 1:
            for i, case_name in enumerate(cases):
                print(f"[{i+1}/{total}] Starting: {case_name}")
                try:
                    ecase = dataset.load_case(case_name)
                    ecase.metadata["dataset"] = dataset.__class__.__name__
                    result = runner.run_single(ecase, run_id=run_id)
                    results.append(result)
                    print(f"[{i+1}/{total}] Finished: {case_name} -> {result.final_state} "
                          f"(composite={result.composite_score:.2f})")
                except Exception as e:
                    logging.error(f"[{case_name}] CRASHED: {e}")
                    results.append(_error_result(case_name, run_id, str(e)))
        else:
            results = self._run_parallel(dataset, cases, runner, run_id, total)

        return results

    def _run_parallel(self, dataset: DatasetProvider, cases: List[str],
                      runner: EvalRunner, run_id: str, total: int) -> List[EvalCaseResult]:
        results_map: dict = {}

        def _run_one(case_name: str) -> EvalCaseResult:
            try:
                ecase = dataset.load_case(case_name)
                ecase.metadata["dataset"] = dataset.__class__.__name__
                return runner.run_single(ecase, run_id=run_id)
            except Exception as e:
                logging.error(f"[{case_name}] CRASHED: {e}")
                return _error_result(case_name, run_id, str(e))

        with ThreadPoolExecutor(max_workers=self.parallel) as executor:
            future_map = {
                executor.submit(_run_one, name): name
                for name in cases
            }

            completed = 0
            for future in as_completed(future_map):
                case_name = future_map[future]
                completed += 1
                try:
                    result = future.result(timeout=self.per_case_timeout)
                    results_map[case_name] = result
                    print(f"[{completed}/{total}] Finished: {case_name} -> {result.final_state} "
                          f"(composite={result.composite_score:.2f})")
                except TimeoutError:
                    logging.error(f"[{case_name}] TIMEOUT ({self.per_case_timeout}s)")
                    results_map[case_name] = _error_result(
                        case_name, run_id, f"Timeout after {self.per_case_timeout}s"
                    )
                except Exception as e:
                    logging.error(f"[{case_name}] FAILED: {e}")
                    results_map[case_name] = _error_result(case_name, run_id, str(e))

        # Preserve original order
        return [results_map[name] for name in cases if name in results_map]


def _error_result(case_name: str, run_id: str, error: str) -> EvalCaseResult:
    return EvalCaseResult(
        case_name=case_name,
        dataset="",
        run_id=run_id,
        timestamp=datetime.now().isoformat(),
        model="",
        final_state="ERROR",
        duration_seconds=0,
        total_turns=0,
        error_info=error,
    )
