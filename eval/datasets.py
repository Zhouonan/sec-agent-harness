import os
import re
from abc import ABC, abstractmethod
from typing import List

from eval.schema import EvalCase


class DatasetProvider(ABC):
    """Abstract base for dataset providers."""

    @abstractmethod
    def list_cases(self) -> List[str]:
        """Return list of case names in this dataset."""

    @abstractmethod
    def load_case(self, name: str) -> EvalCase:
        """Load a single case by name."""

    @abstractmethod
    def build_prompt(self, case: EvalCase) -> str:
        """Build the agent prompt for this case."""


class VulRepairDataset(DatasetProvider):
    """Loads cases from challenge/vuln_repair_eval/ case_* directories."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.join(project_root, "challenge", "vuln_repair_eval")
        self.root_dir = os.path.abspath(root_dir)

    def list_cases(self) -> List[str]:
        if not os.path.isdir(self.root_dir):
            return []
        return sorted([
            d for d in os.listdir(self.root_dir)
            if d.startswith("case_") and os.path.isdir(os.path.join(self.root_dir, d))
        ])

    def load_case(self, name: str) -> EvalCase:
        case_dir = os.path.join(self.root_dir, name)
        if not os.path.isdir(case_dir):
            raise FileNotFoundError(f"Case directory not found: {case_dir}")

        vulnerable_path = os.path.join(case_dir, "vulnerable_code.c")
        solution_path = os.path.join(case_dir, "solution.txt")
        readme_path = os.path.join(case_dir, "README.md")

        if not os.path.isfile(vulnerable_path):
            raise FileNotFoundError(f"Missing vulnerable_code.c in {case_dir}")
        if not os.path.isfile(solution_path):
            raise FileNotFoundError(f"Missing solution.txt in {case_dir}")

        with open(vulnerable_path, "r", encoding="utf-8") as f:
            vulnerable_code = f.read()

        with open(solution_path, "r", encoding="utf-8") as f:
            solution_content = f.read()

        # Parse solution.txt: metadata header followed by "--- Ground Truth Fix ---"
        parts = solution_content.split("--- Ground Truth Fix ---")
        metadata_text = parts[0].strip() if parts else ""
        ground_truth = parts[1].strip() if len(parts) > 1 else solution_content.strip()

        cwe_id = _extract_field(metadata_text, "CWE")
        cve_id = _extract_field(metadata_text, "CVE")

        # Fallback: parse CWE from directory name (e.g., case_01_CWE_119)
        if not cwe_id:
            m = re.search(r"CWE[_\-](\d+)", name)
            if m:
                cwe_id = f"CWE-{m.group(1)}"

        metadata = {"source_dir": case_dir}
        if os.path.isfile(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                metadata["readme"] = f.read()

        return EvalCase(
            name=name,
            source_dir=case_dir,
            vulnerable_code=vulnerable_code,
            ground_truth=ground_truth,
            cwe_id=cwe_id or "CWE-000",
            cve_id=cve_id or "",
            metadata=metadata,
        )

    def build_prompt(self, case: EvalCase) -> str:
        return (
            "Analyze and fix the vulnerability in 'vulnerable_code.c'.\n"
            "IMPORTANT GUIDELINES for this C snippet:\n"
            "1. This is a function snippet, not a full program. To compile it, you MUST create a wrapper (e.g., 'poc.c') with a 'main()' function.\n"
            "2. If you encounter missing types (e.g., structs, typedefs), define minimal MOCK versions in your wrapper to satisfy the compiler.\n"
            "3. Use 'execute_in_sandbox' to run your compilation and PoC tests.\n"
            "Follow the standard FSM procedure: Analyze -> Validate -> Fix -> Review."
        )


class SecBenchDataset(DatasetProvider):
    """Loads cases from challenge/secbench_trials/ directories."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.join(project_root, "challenge", "secbench_trials")
        self.root_dir = os.path.abspath(root_dir)

    def list_cases(self) -> List[str]:
        if not os.path.isdir(self.root_dir):
            return []
        return sorted([
            d for d in os.listdir(self.root_dir)
            if os.path.isdir(os.path.join(self.root_dir, d))
        ])

    def load_case(self, name: str) -> EvalCase:
        case_dir = os.path.join(self.root_dir, name)
        if not os.path.isdir(case_dir):
            raise FileNotFoundError(f"Case directory not found: {case_dir}")
        return EvalCase(
            name=name,
            source_dir=case_dir,
            vulnerable_code="",
            ground_truth="",
            cwe_id="CWE-000",
            cve_id="",
            metadata={"source_dir": case_dir},
        )

    def build_prompt(self, case: EvalCase) -> str:
        return (
            f"You are now tasked with fixing a real-world vulnerability in the '{case.name}' project.\n"
            "Use the sandbox for all compilation and test execution.\n"
            "Follow the FSM: Analyze -> Validate -> Fix -> Review."
        )


class CustomDataset(DatasetProvider):
    """Loads cases from a user-specified directory."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)

    def list_cases(self) -> List[str]:
        if not os.path.isdir(self.root_dir):
            return []
        return sorted([
            d for d in os.listdir(self.root_dir)
            if os.path.isdir(os.path.join(self.root_dir, d))
        ])

    def load_case(self, name: str) -> EvalCase:
        case_dir = os.path.join(self.root_dir, name)
        if not os.path.isdir(case_dir):
            raise FileNotFoundError(f"Case directory not found: {case_dir}")

        vulnerable_code = ""
        ground_truth = ""

        for fname in os.listdir(case_dir):
            if fname.endswith(".c") and "vuln" in fname.lower():
                with open(os.path.join(case_dir, fname), "r", encoding="utf-8") as f:
                    vulnerable_code = f.read()
            if fname == "solution.txt":
                with open(os.path.join(case_dir, fname), "r", encoding="utf-8") as f:
                    content = f.read()
                    parts = content.split("--- Ground Truth Fix ---")
                    ground_truth = parts[1].strip() if len(parts) > 1 else content.strip()

        return EvalCase(
            name=name,
            source_dir=case_dir,
            vulnerable_code=vulnerable_code,
            ground_truth=ground_truth,
            cwe_id="CWE-000",
            cve_id="",
            metadata={"source_dir": case_dir},
        )

    def build_prompt(self, case: EvalCase) -> str:
        return (
            f"Analyze and fix the vulnerability in the source code within '{case.name}'.\n"
            "Follow the FSM: Analyze -> Validate -> Fix -> Review."
        )


def _extract_field(text: str, prefix: str) -> str:
    m = re.search(rf"{prefix}:\s*(\S+)", text)
    return m.group(1) if m else ""
