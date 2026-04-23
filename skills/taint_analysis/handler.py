import json
import subprocess
import os

def _run_command(command: list) -> tuple[int, str, str]:
    """Helper to run shell commands safely."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=300)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out."
    except Exception as e:
        return -1, "", str(e)

def analyze_path_codeql_handler(agent, state, source: str = None, sink: str = None):
    """
    专门的 CodeQL 处理器。如果失败，仅返回错误及原始 stderr，
    不进行任何自动降级。具体的自愈引导由 Hook 完成。
    """
    print(f"[{state.current_state.name}] Executing DEEP CodeQL Analysis: {source} -> {sink}")
    workspace = agent.workspace_path
    codeql_db_path = os.path.join(workspace, ".codeql_db")
    
    rc, out, err = _run_command(["codeql", "database", "create", codeql_db_path, "--language=python", "--overwrite"])
    
    if rc != 0:
        return json.dumps({
            "engine": "CodeQL",
            "status": "error",
            "stderr": err,
            "message": "CodeQL analysis failed. Please refer to the system diagnosis (if any) or check environment."
        }, indent=2)

    return json.dumps({
        "engine": "CodeQL", 
        "status": "success", 
        "message": "Deep analysis complete (Database created)."
    }, indent=2)

def analyze_path_semgrep_handler(agent, state, source: str = None, sink: str = None):
    """
    专门的 Semgrep 处理器。作为轻量级匹配工具。
    """
    print(f"[{state.current_state.name}] Executing AGILE Semgrep Analysis: {source} -> {sink}")
    workspace = agent.workspace_path
    
    semgrep_config = {
        "rules": [{
            "id": "manual-agent-taint",
            "languages": ["python"],
            "message": f"Potential taint path from {source} to {sink}",
            "mode": "taint",
            "pattern-sources": [{"pattern": source}],
            "pattern-sinks": [{"pattern": sink}]
        }]
    }
    
    config_path = os.path.join(workspace, ".temp_semgrep.yaml")
    with open(config_path, "w") as f:
        import yaml
        yaml.dump(semgrep_config, f)
        
    rc, out, err = _run_command(["semgrep", "scan", "--config", config_path, "--json"])
    
    if rc == 0:
        return json.dumps({
            "engine": "Semgrep",
            "status": "success",
            "vulnerabilities": json.loads(out).get("results", [])
        }, indent=2)
        
    return json.dumps({"engine": "Semgrep", "status": "error", "stderr": err}, indent=2)
