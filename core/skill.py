import os
import yaml
import importlib.util
from typing import Dict, Any, List, Optional

class SkillRegistry:
    """
    Registry for security skills. 
    Loads skills from directories containing a SKILL.md file with YAML frontmatter.
    """
    def __init__(self, skills_dir: str):
        self.skills_dir = os.path.abspath(skills_dir)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.discover_skills()

    def discover_skills(self):
        """Scans the skills directory for SKILL.md manifests."""
        if not os.path.exists(self.skills_dir):
            return
        
        for skill_name in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, skill_name)
            if os.path.isdir(skill_path):
                manifest_path = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(manifest_path):
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                frontmatter = parts[1]
                                body = parts[2]
                                meta = yaml.safe_load(frontmatter)
                                
                                handler_module = None
                                handler_path = os.path.join(skill_path, "handler.py")
                                if os.path.exists(handler_path):
                                    spec = importlib.util.spec_from_file_location(f"skill_{meta['name']}_handler", handler_path)
                                    if spec and spec.loader:
                                        handler_module = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(handler_module)
                                
                                skill_data = {
                                    "meta": meta,
                                    "body": body.strip(),
                                    "path": skill_path,
                                    "tools": meta.get("tools", []),
                                    "handler_module": handler_module
                                }
                                self.skills[meta["name"]] = skill_data

    def get_skill_catalog(self) -> str:
        """Returns a string description of all available skills for the system prompt."""
        if not self.skills:
            return "No specialized security skills available."
        
        catalog = "### Available Specialized Skills\n"
        for name, data in self.skills.items():
            desc = data['meta'].get('description', 'No description')
            catalog += f"- **{name}**: {desc}\n"
        return catalog

    def get_skill_content(self, name: str) -> Optional[str]:
        """Returns the full body of a skill."""
        if name in self.skills:
            return self.skills[name]["body"]
        return None

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Returns all tool definitions from all skills (OpenAI format)."""
        all_tools = []
        for skill in self.skills.values():
            for tool in skill.get("tools", []):
                # Ensure it's in OpenAI tool format
                if "type" not in tool:
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool.get("parameters", {
                                "type": "object",
                                "properties": {},
                                "required": []
                            })
                        }
                    }
                    all_tools.append(tool_def)
                else:
                    all_tools.append(tool)
        return all_tools
