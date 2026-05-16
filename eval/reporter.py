import json
import os
from datetime import datetime
from typing import List

from eval.schema import EvalCaseResult


SUCCESS_CORRECTNESS_THRESHOLD = 0.8


class Reporter:
    """Generates JSON and Markdown evaluation reports."""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(project_root, "eval_results")
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, results: List[EvalCaseResult], run_id: str = None) -> dict:
        """Generate both JSON and Markdown reports. Returns paths dict."""
        run_id = run_id or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = os.path.join(self.output_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        json_path = os.path.join(run_dir, "results.json")
        md_path = os.path.join(run_dir, "report.md")

        self._write_json(results, json_path)
        self._write_markdown(results, run_id, md_path)

        print(f"\nReport saved:")
        print(f"  JSON:     {json_path}")
        print(f"  Markdown: {md_path}")
        return {"json": json_path, "markdown": md_path}

    def _write_json(self, results: List[EvalCaseResult], path: str):
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_cases": len(results),
            "cases": [_result_to_dict(r) for r in results],
            "summary": _compute_summary(results),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_markdown(self, results: List[EvalCaseResult], run_id: str, path: str):
        lines = []
        lines.append(f"# Evaluation Report: {run_id}")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")

        summary = _compute_summary(results)
        lines.append("## Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Cases | {summary['total']} |")
        lines.append(f"| Completed (DONE) | {summary['done_count']} |")
        lines.append(f"| Errors | {summary['error_count']} |")
        lines.append(f"| Success Rate | {summary['success_rate']:.1%} |")
        lines.append(f"| Avg Composite Score | {summary['avg_composite']:.3f} |")
        lines.append(f"| Avg Correctness | {summary['avg_correctness']:.3f} |")
        lines.append(f"| Avg Process | {summary['avg_process']:.3f} |")
        lines.append(f"| Avg Efficiency | {summary['avg_efficiency']:.3f} |")
        lines.append(f"| Avg Duration (s) | {summary['avg_duration']:.1f} |")
        lines.append(f"| Avg Turns | {summary['avg_turns']:.1f} |")
        lines.append("")

        lines.append("## Dataset Breakdown")
        lines.append("")
        lines.append("| Dataset | Cases | Success | Success Rate | Avg Correctness | Avg Efficiency | Avg Duration (s) | Avg Turns |")
        lines.append("|---------|-------|---------|--------------|-----------------|----------------|------------------|-----------|")
        for dataset_name, stats in summary["by_dataset"].items():
            lines.append(
                f"| {dataset_name} | {stats['total']} | {stats['success_count']} | "
                f"{stats['success_rate']:.1%} | {stats['avg_correctness']:.3f} | "
                f"{stats['avg_efficiency']:.3f} | {stats['avg_duration']:.1f} | "
                f"{stats['avg_turns']:.1f} |"
            )
        lines.append("")

        lines.append("## Per-Case Results")
        lines.append("")
        lines.append("| Case | State | Turns | Duration | Correctness | Process | Efficiency | Composite |")
        lines.append("|------|-------|-------|----------|-------------|---------|------------|-----------|")
        for r in results:
            lines.append(
                f"| {r.case_name} | {r.final_state} | {r.total_turns} | "
                f"{r.duration_seconds:.1f}s | {r.correctness_score:.3f} | "
                f"{r.process_score:.3f} | {r.efficiency_score:.3f} | {r.composite_score:.3f} |"
            )
        lines.append("")

        # Failure mode analysis
        errors = [r for r in results if r.final_state == "ERROR"]
        if errors:
            lines.append("## Failures / Errors")
            lines.append("")
            for r in errors:
                lines.append(f"- **{r.case_name}**: {r.error_info or 'Unknown error'}")
            lines.append("")

        # Case details
        lines.append("## Case Details")
        lines.append("")
        for r in results:
            lines.append(f"### {r.case_name}")
            lines.append(f"- **Final State**: {r.final_state}")
            lines.append(f"- **State Path**: {' -> '.join(r.state_path) if r.state_path else 'N/A'}")
            lines.append(f"- **Turns**: {r.total_turns}")
            lines.append(f"- **Duration**: {r.duration_seconds:.1f}s")
            lines.append(f"- **Correctness**: {r.correctness_score:.3f}")
            lines.append(f"- **Process**: {r.process_score:.3f}")
            lines.append(f"- **Efficiency**: {r.efficiency_score:.3f}")
            lines.append(f"- **Composite**: {r.composite_score:.3f}")
            if r.correctness_reasoning:
                lines.append(f"- **Judge Reasoning**: {r.correctness_reasoning[:300]}")
            if r.error_info:
                lines.append(f"- **Error**: {r.error_info}")
            lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def _result_to_dict(r: EvalCaseResult) -> dict:
    return {
        "case_name": r.case_name,
        "dataset": r.dataset,
        "run_id": r.run_id,
        "timestamp": r.timestamp,
        "model": r.model,
        "final_state": r.final_state,
        "duration_seconds": r.duration_seconds,
        "total_turns": r.total_turns,
        "turns_per_state": r.turns_per_state,
        "state_path": r.state_path,
        "correctness_score": r.correctness_score,
        "correctness_reasoning": r.correctness_reasoning,
        "process_score": r.process_score,
        "efficiency_score": r.efficiency_score,
        "composite_score": r.composite_score,
        "patched_code": r.patched_code,
        "error_info": r.error_info,
        "log_file": r.log_file,
    }


def _compute_summary(results: List[EvalCaseResult]) -> dict:
    if not results:
        return {"total": 0, "by_dataset": {}}

    done = [r for r in results if r.final_state == "DONE"]
    errors = [r for r in results if r.final_state == "ERROR"]
    successes = [r for r in results if _is_success(r)]

    return {
        "total": len(results),
        "done_count": len(done),
        "error_count": len(errors),
        "success_count": len(successes),
        "success_rate": round(len(successes) / len(results), 4),
        "avg_composite": round(_avg(r.composite_score for r in results), 3),
        "avg_correctness": round(_avg(r.correctness_score for r in results), 3),
        "avg_process": round(_avg(r.process_score for r in results), 3),
        "avg_efficiency": round(_avg(r.efficiency_score for r in results), 3),
        "avg_duration": round(_avg(r.duration_seconds for r in results), 1),
        "avg_turns": round(_avg(r.total_turns for r in results), 1),
        "by_dataset": _compute_dataset_summary(results),
    }


def _avg(values) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0


def _is_success(result: EvalCaseResult) -> bool:
    return (
        result.final_state == "DONE"
        and result.correctness_score >= SUCCESS_CORRECTNESS_THRESHOLD
    )


def _compute_dataset_summary(results: List[EvalCaseResult]) -> dict:
    grouped = {}
    for result in results:
        dataset_name = result.dataset or "Unknown"
        grouped.setdefault(dataset_name, []).append(result)

    summary = {}
    for dataset_name in sorted(grouped):
        dataset_results = grouped[dataset_name]
        successes = [r for r in dataset_results if _is_success(r)]
        summary[dataset_name] = {
            "total": len(dataset_results),
            "done_count": sum(1 for r in dataset_results if r.final_state == "DONE"),
            "error_count": sum(1 for r in dataset_results if r.final_state == "ERROR"),
            "success_count": len(successes),
            "success_rate": round(len(successes) / len(dataset_results), 4),
            "avg_composite": round(_avg(r.composite_score for r in dataset_results), 3),
            "avg_correctness": round(_avg(r.correctness_score for r in dataset_results), 3),
            "avg_process": round(_avg(r.process_score for r in dataset_results), 3),
            "avg_efficiency": round(_avg(r.efficiency_score for r in dataset_results), 3),
            "avg_duration": round(_avg(r.duration_seconds for r in dataset_results), 1),
            "avg_turns": round(_avg(r.total_turns for r in dataset_results), 1),
        }
    return summary
