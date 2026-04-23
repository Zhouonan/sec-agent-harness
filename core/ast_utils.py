import ast
import os
from typing import List, Dict, Any, Optional

class ASTScanner:
    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)

    def scan_file(self, file_path: str) -> Dict[str, Any]:
        full_path = os.path.join(self.root_path, file_path)
        if not os.path.exists(full_path):
            return {"error": f"File {file_path} not found."}
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            classes = []
            functions = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Top-level functions only if needed, but for now everything
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(f"{node.module}.{', '.join(n.name for n in node.names)}")

            return {
                "file": file_path,
                "classes": classes,
                "functions": functions,
                "imports": imports
            }
        except Exception as e:
            return {"error": f"Failed to parse {file_path}: {str(e)}"}

    def find_definitions(self, symbol_name: str) -> List[Dict[str, Any]]:
        results = []
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.endswith(".py"):
                    rel_path = os.path.relpath(os.path.join(root, file), self.root_path)
                    res = self.scan_file(rel_path)
                    if "error" in res:
                        continue
                    
                    found = False
                    for c in res["classes"]:
                        if c["name"] == symbol_name:
                            results.append({"type": "class", "file": rel_path, "line": c["line"]})
                            found = True
                    for f in res["functions"]:
                        if f["name"] == symbol_name:
                            results.append({"type": "function", "file": rel_path, "line": f["line"]})
                            found = True
        return results

if __name__ == "__main__":
    scanner = ASTScanner(root_path=".")
    print(scanner.scan_file("core/loop.py"))
