import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

@dataclass
class ApiConfig:
    model: Optional[str] = field(default_factory=lambda: os.getenv("LLM_MODEL"))
    base_url: Optional[str] = field(default_factory=lambda: os.getenv("LLM_BASE_URL"))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("LLM_API_KEY"))

@dataclass
class LoopConfig:
    max_turns_per_state: int = 10
    total_max_turns: int = 40

@dataclass
class SandboxConfig:
    image: str = "python:3.10-slim"
    timeout: int = 60
    local_fallback: bool = False

@dataclass
class LoggingConfig:
    file_logging_enabled: bool = True
    console_prompt_enabled: bool = False

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        # Default values
        self.api = ApiConfig()
        self.loop = LoopConfig()
        self.sandbox = SandboxConfig()
        self.logging = LoggingConfig()

        # Load from file if exists
        abs_config_path = os.path.abspath(config_path)
        if os.path.exists(abs_config_path):
            with open(abs_config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self._merge_config(data)
        
        # Override with environment variables if present (optional, but good practice)
        env_key = os.getenv("MOONSHOT_API_KEY")
        if env_key:
            self.api.api_key = env_key
            
        env_fallback = os.getenv("LOCAL_EXECUTION_FALLBACK")
        if env_fallback:
            self.sandbox.local_fallback = env_fallback.lower() == "true"

    def _merge_config(self, data: Dict[str, Any]):
        if "api" in data:
            api_data = data["api"]
            if "model" in api_data:
                self.api.model = api_data["model"]
            if "base_url" in api_data:
                self.api.base_url = api_data["base_url"]
            if "api_key" in api_data:
                self.api.api_key = api_data["api_key"]
        
        if "loop" in data:
            loop_data = data["loop"]
            if "max_turns_per_state" in loop_data:
                self.loop.max_turns_per_state = loop_data["max_turns_per_state"]
            if "total_max_turns" in loop_data:
                self.loop.total_max_turns = loop_data["total_max_turns"]

        if "sandbox" in data:
            sb_data = data["sandbox"]
            if "image" in sb_data:
                self.sandbox.image = sb_data["image"]
            if "timeout" in sb_data:
                self.sandbox.timeout = sb_data["timeout"]
            if "local_fallback" in sb_data:
                self.sandbox.local_fallback = sb_data["local_fallback"]

        if "logging" in data:
            log_data = data["logging"]
            if "file_logging_enabled" in log_data:
                self.logging.file_logging_enabled = log_data["file_logging_enabled"]
            if "console_prompt_enabled" in log_data:
                self.logging.console_prompt_enabled = log_data["console_prompt_enabled"]

    @classmethod
    def load(cls, path: str = None):
        if path is None:
            # Try to find config.yaml in the project root
            # Assuming core/config.py is 2 levels deep
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(project_root, "config.yaml")
        return cls(path)

# Singleton instance
settings = Config.load()
