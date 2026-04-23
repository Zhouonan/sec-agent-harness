import os
from core.utils import render_plan

def read_file_handler(agent, state, path: str):
    try:
        full_path = agent._safe_path(path)
        if not os.path.exists(full_path):
            return f"Error: File {path} not found."
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file_handler(agent, state, path: str, content: str):
    try:
        full_path = agent._safe_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_files_handler(agent, state, path: str = "."):
    try:
        full_path = agent._safe_path(path)
        if not os.path.isdir(full_path):
            return f"Error: {path} is not a directory."
        
        items = os.listdir(full_path)
        result = []
        for item in items:
            item_path = os.path.join(full_path, item)
            prefix = "[DIR] " if os.path.isdir(item_path) else "[FILE] "
            result.append(f"{prefix}{item}")
            
        return "\n".join(result) if result else "(Empty directory)"
    except Exception as e:
        return f"Error listing files: {str(e)}"

def update_plan_handler(agent, state, items: list):
    """
    Updates the session-level plan in the blackboard.
    Items should be a list of dictionaries with 'content' and 'status'.
    """
    in_progress_count = sum(1 for item in items if item.get("status") == "in_progress")
    if in_progress_count > 1:
        return "Error: Only one item can be 'in_progress' at a time."
    
    state.blackboard["plan"] = items
    state.rounds_since_todo_update = 0
    
    return "Plan updated successfully:\n" + render_plan(items)
