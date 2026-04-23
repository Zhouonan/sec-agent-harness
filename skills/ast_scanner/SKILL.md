---
name: ast-scanner
description: Extract code structures (classes, functions, imports) from Python source files.
tools:
  - name: scan_python_file
    description: Scan a Python file and return its classes, functions, and imports.
    parameters:
      type: object
      properties:
        file_path: {type: string, description: "Relative path to the Python file."}
      required: ["file_path"]
  - name: find_definition
    description: Search for the definition of a class or function by name.
    parameters:
      type: object
      properties:
        symbol_name: {type: string, description: "Name of the symbol (class/function) to find."}
      required: ["symbol_name"]
---
# AST Scanner Skill

This skill allows you to analyze the structure of the codebase without reading the entire file content. It is useful for mapping the project architecture and finding relevant code sections.

## Use Cases
- **Reconnaissance**: Quickly see what functions are available in a module.
- **Symbol Discovery**: Find where a specific class or function is defined across the repository.
- **Dependency Mapping**: Check what a module imports.

## Guidelines
- Use `scan_python_file` when you first encounter a new file.
- Use `find_definition` when you see a class/function being used but don't know where it's defined.
