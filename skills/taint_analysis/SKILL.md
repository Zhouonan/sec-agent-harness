---
name: taint-analysis
description: Perform data-flow and taint analysis on the codebase to identify potential vulnerabilities.
tools:
  - name: analyze_path_codeql
    description: Performs deep, whole-program semantic analysis using GitHub CodeQL. Preferred for accurate vulnerability verification.
    parameters:
      type: object
      properties:
        source: {type: string, description: "The starting point of the taint (e.g., 'request.form', 'input()')."}
        sink: {type: string, description: "The sensitive function (e.g., 'os.system', 'eval')."}
      required: ["source", "sink"]
  - name: analyze_path_semgrep
    description: Performs agile, pattern-based taint analysis using Semgrep. Fallback if CodeQL is unavailable.
    parameters:
      type: object
      properties:
        source: {type: string, description: "The pattern to match as a source."}
        sink: {type: string, description: "The pattern to match as a sink."}
      required: ["source", "sink"]
---

# Taint Analysis Skill

This skill provides static analysis tools to trace data flows from sources (e.g., user input) to sinks (e.g., sensitive functions).

## Tools

### analyze_path_codeql
Performs deep, whole-program semantic analysis using GitHub CodeQL. This is the **preferred tool** for accurate vulnerability verification as it tracks flows across multiple files and functions.
- **parameters**:
  - `source`: The starting point of the taint (e.g., "request.form", "input()").
  - `sink`: The sensitive function that should not receive tainted data (e.g., "os.system", "eval").
- **states**: ["INITIAL_ANALYSIS", "VALIDATOR", "REVIEWER"]

### analyze_path_semgrep
Performs agile, pattern-based taint analysis using Semgrep. Use this as a **fallback** if CodeQL environment issues cannot be resolved, or for very simple local patterns.
- **parameters**:
  - `source`: The pattern to match as a source.
  - `sink`: The pattern to match as a sink.
- **states**: ["INITIAL_ANALYSIS", "VALIDATOR", "REVIEWER"]
