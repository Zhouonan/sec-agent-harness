import os
import csv
import re
from collections import Counter

# Paths
VULREPAIR_PATH = "/Users/nnzz/Documents/agent/VulRepair/data/fine_tune_data/test.csv"
CHALLENGE_ROOT = "/Users/nnzz/Documents/agent/sec-agent-harness/challenge/vuln_repair_eval"

def clean_code(code_str, tags_to_remove):
    """Remove specific tags and metadata from the code string."""
    cleaned = code_str
    for tag in tags_to_remove:
        cleaned = cleaned.replace(tag, "")
    
    # Remove CWE prefix if it exists at the start (e.g., "CWE-119 ")
    cleaned = re.sub(r'^CWE-\d+\s+', '', cleaned)
    
    # Remove leading/trailing quotes if any (from CSV reading)
    cleaned = cleaned.strip('"')
    return cleaned

def prepare_cases(num_per_cwe=1):
    if not os.path.exists(VULREPAIR_PATH):
        print(f"Error: Dataset not found at {VULREPAIR_PATH}")
        return

    os.makedirs(CHALLENGE_ROOT, exist_ok=True)

    cases = []
    with open(VULREPAIR_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)

    # Find Top 10 CWEs
    cwe_counts = Counter(row['cwe_id'] for row in cases)
    top_10_cwes = [cwe for cwe, _ in cwe_counts.most_common(10)]
    print(f"Top 10 CWEs identified: {top_10_cwes}")

    selected_cases = []
    for cwe in top_10_cwes:
        cwe_cases = [row for row in cases if row['cwe_id'] == cwe]
        # Just take the first few for each for calibration
        selected_cases.extend(cwe_cases[:num_per_cwe])

    print(f"Sampling {len(selected_cases)} cases...")

    for i, case in enumerate(selected_cases):
        cwe_id = case['cwe_id']
        case_dir = os.path.join(CHALLENGE_ROOT, f"case_{i+1:02d}_{cwe_id.replace('-', '_')}")
        os.makedirs(case_dir, exist_ok=True)

        # 1. Cleaned Source for the Agent
        # Strip bug markers for the agent's view to see if it can find it
        source_cleaned = clean_code(case['source'], ["<S2SV_StartBug>", "<S2SV_EndBug>"])
        
        # 2. Source with Bug Markers (as a hint/reference for us)
        source_with_markers = case['source']
        
        # 3. Target (Ground Truth Fix)
        # Note: VulRepair targets often only show the modified part or have markers
        target_cleaned = clean_code(case['target'], ["<S2SV_ModStart>", "<S2SV_ModEnd>"])

        # Write vulnerable_code.c
        with open(os.path.join(case_dir, "vulnerable_code.c"), 'w') as f:
            f.write(source_cleaned)

        # Write metadata for verification
        with open(os.path.join(case_dir, "solution.txt"), 'w') as f:
            f.write(f"CWE: {cwe_id}\n")
            f.write(f"CVE: {case.get('cve_id', 'N/A')}\n")
            f.write(f"Project: {case.get('project_and_commit_id', 'N/A')}\n")
            f.write("\n--- Ground Truth Fix ---\n")
            f.write(target_cleaned)

        # Create README
        with open(os.path.join(case_dir, "README.md"), 'w') as f:
            f.write(f"# Vulnerability Repair Challenge: {cwe_id}\n")
            f.write(f"**Case ID**: {i+1:02d}\n\n")
            f.write("## Task\n")
            f.write("Identify and repair the vulnerability in `vulnerable_code.c`. ")
            f.write("Use the FSM-driven harness to analyze, validate, fix, and review the code.\n\n")
            f.write("## Metadata\n")
            f.write(f"- CWE: {cwe_id}\n")
            f.write(f"- CVE: {case.get('cve_id', 'N/A')}\n")

        print(f"  [+] Prepared {case_dir}")

    print("\nPreparation complete. You can now run the agent on these cases.")

if __name__ == "__main__":
    prepare_cases(num_per_cwe=1)
