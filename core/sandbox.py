import docker
import os
import logging
import subprocess
from typing import Dict, Any, Optional, List

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SandboxTool")

class SandboxTool:
    """
    Isolated execution environment using Docker containers.
    Provides secure isolation for running potentially malicious PoCs or regression tests.
    If Docker is unavailable and local_fallback is enabled, it runs commands locally (WARNING: LESS SECURE).
    """
    def __init__(self, workspace_path: str, image: str = "python:3.10-slim", local_fallback: bool = False):
        self.workspace_path = os.path.abspath(workspace_path)
        self.image = image
        self.local_fallback = local_fallback
        self.client = None
        self._available = False
        
        try:
            # Check if docker is available
            self.client = docker.from_env()
            self.client.ping()
            self._available = True
            logger.info("Docker client initialized successfully.")
            self._ensure_image_exists()
        except Exception as e:
            error_msg = str(e)
            advice = ""
            if "FileNotFoundError" in error_msg or "Connection aborted" in error_msg:
                advice = " [ADVICE: Docker daemon not found. Is Docker Desktop running?]"
            elif "Permission denied" in error_msg:
                advice = " [ADVICE: Permission denied to docker.sock. Run 'sudo chmod 666 /var/run/docker.sock'?]"
            
            if self.local_fallback:
                logger.warning(f"Docker is not available. Using LOCAL FALLBACK (less secure): {error_msg}{advice}")
            else:
                logger.warning(f"Docker is not available. Sandbox execution will be disabled: {error_msg}{advice}")

    def _ensure_image_exists(self):
        """Checks if the required image exists locally, otherwise pulls it."""
        if not self._available:
            return
        try:
            self.client.images.get(self.image)
            logger.info(f"Using existing Docker image: {self.image}")
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling Docker image: {self.image}...")
            try:
                self.client.images.pull(self.image)
                logger.info(f"Successfully pulled Docker image: {self.image}")
            except Exception as pull_err:
                logger.error(f"Failed to pull image {self.image}: {pull_err}")
                self._available = False
        except Exception as e:
            logger.error(f"Error checking image {self.image}: {e}")
            self._available = False

    def execute(self, 
                command: str, 
                timeout: int = 60, 
                env_vars: Optional[Dict[str, str]] = None,
                user: str = "1000:1000",
                max_output_len: int = 5000) -> Dict[str, Any]:
        """
        Executes a command inside an isolated Docker container or locally as fallback.
        
        Args:
            command: The command to execute
            timeout: Maximum execution time in seconds
            env_vars: Dictionary of environment variables to pass
            user: UID:GID for the container user (only for Docker)
            max_output_len: Maximum length of the returned output
            
        Returns:
            Dict containing exit_code, output, and status.
        """
        if self._available:
            return self._execute_docker(command, timeout, env_vars, user, max_output_len)
        elif self.local_fallback:
            return self._execute_local(command, timeout, env_vars, max_output_len)
        else:
            return {
                "exit_code": -3,
                "output": "Docker is not available and local_fallback is disabled. Cannot execute command.",
                "status": "error"
            }

    def _execute_local(self, command: str, timeout: int, env_vars: Optional[Dict[str, str]], max_output_len: int) -> Dict[str, Any]:
        """Executes a command locally within the workspace directory."""
        logger.info(f"Executing locally: {command}")
        
        # Merge environment variables
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
            
        try:
            # Execute command using subprocess
            process = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = process.stdout + process.stderr
            if len(output) > max_output_len:
                output = output[:max_output_len] + "\n... [Output Truncated] ..."
                
            return {
                "exit_code": process.returncode,
                "output": output,
                "status": "success" if process.returncode == 0 else "failed",
                "mode": "local_fallback"
            }
        except subprocess.TimeoutExpired as e:
            output = (e.stdout.decode() if e.stdout else "") + (e.stderr.decode() if e.stderr else "")
            return {
                "exit_code": -2,
                "output": f"Timeout expired: {output}",
                "status": "timeout",
                "mode": "local_fallback"
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "output": f"Local execution error: {str(e)}",
                "status": "error",
                "mode": "local_fallback"
            }

    def _execute_docker(self, command: str, timeout: int, env_vars: Optional[Dict[str, str]], user: str, max_output_len: int) -> Dict[str, Any]:
        """Original Docker execution logic."""
        container = None
        try:
            # Prepare resource limits and isolation settings
            container = self.client.containers.run(
                self.image,
                command=["/bin/sh", "-c", command],
                volumes={self.workspace_path: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                environment=env_vars or {},
                user=user,
                detach=True,
                mem_limit="512m",
                cpu_quota=50000,   # 50% of one core
                network_disabled=True,
                remove=False,       # Manual removal after logs capture
                stderr=True,
                stdout=True
            )

            try:
                # Wait for execution with timeout
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", 1)
                
                # Fetch logs
                logs = container.logs().decode("utf-8", errors="replace")
                
                # Truncate logs if necessary
                if len(logs) > max_output_len:
                    logs = logs[:max_output_len] + "\n... [Output Truncated] ..."

                return {
                    "exit_code": exit_code,
                    "output": logs,
                    "status": "success" if exit_code == 0 else "failed",
                    "mode": "docker"
                }
            except Exception as wait_error:
                # Handle timeout or other wait errors
                logger.warning(f"Error during execution: {wait_error}")
                try:
                    container.kill()
                except:
                    pass
                return {
                    "exit_code": -2,
                    "output": f"Execution error: {str(wait_error)}",
                    "status": "timeout/error",
                    "mode": "docker"
                }

        except Exception as run_error:
            logger.error(f"Failed to start container: {run_error}")
            return {
                "exit_code": -1,
                "output": str(run_error),
                "status": "initialization_error",
                "mode": "docker"
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

if __name__ == "__main__":
    # Test script
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    sb = SandboxTool(workspace_path=workspace, local_fallback=True)
    print("Running in sandbox/local: echo 'Hello world'")
    res = sb.execute("echo 'Hello world'")
    print(f"Result: {res}")
