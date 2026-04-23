---
name: file-ops
description: Basic file operations and session-level planning.
tools:
  - name: read_file
    description: Read the content of a file from the workspace.
    parameters:
      type: object
      properties:
        path: {type: string, description: "Relative path to the file."}
      required: ["path"]
  - name: write_file
    description: Write content to a file in the workspace.
    parameters:
      type: object
      properties:
        path: {type: string, description: "Relative path to the file."}
        content: {type: string, description: "Content to write to the file."}
      required: ["path", "content"]
  - name: list_files
    description: List files in a directory within the workspace.
    parameters:
      type: object
      properties:
        path: {type: string, description: "Relative path to the directory (default is '.')."}
      required: []
  - name: update_plan
    description: Update the current session plan (TODO list).
    parameters:
      type: object
      properties:
        items:
          type: array
          items:
            type: object
            properties:
              content: {type: string, description: "Description of the task step."}
              status: {type: string, enum: ["pending", "in_progress", "completed"]}
              activeForm: {type: string, description: "Progress description (e.g. 'Scanning for vulnerabilities')."}
            required: ["content", "status"]
      required: ["items"]
---
# File Operations & Planning Skill

This skill gives you the ability to interact with the filesystem and manage your execution plan.

## Guidelines
- Use `read_file` to gather context.
- Use `write_file` to save your work.
- Use `update_plan` to keep your internal focus. A plan helps you avoid "drifting" and ensures multi-step tasks are completed systematically.

## Planning Rules
1. **Focus**: Only one item should be `in_progress` at any given time.
2. **Persistence**: Update your plan whenever a step is completed or when you need to pivot.
3. **Clarity**: Keep steps concise and actionable.
