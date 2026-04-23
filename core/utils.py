def render_plan(items):
    if not items:
        return "No plan items defined."
    
    lines = []
    for item in items:
        status = item.get("status", "pending")
        marker = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[x]",
        }.get(status, "[?]")
        
        content = item.get("content", "")
        if status == "in_progress" and item.get("activeForm"):
            line = f"{marker} {content} ({item['activeForm']})"
        else:
            line = f"{marker} {content}"
        lines.append(line)
    
    return "\n".join(lines)
