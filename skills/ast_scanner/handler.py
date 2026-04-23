import json

def scan_python_file_handler(agent, state, file_path: str):
    print(f"[{state.current_state.name}] AST Scan: {file_path}")
    result = agent.ast_scanner.scan_file(file_path)
    return json.dumps(result, indent=2)

def find_definition_handler(agent, state, symbol_name: str):
    print(f"[{state.current_state.name}] AST Find: {symbol_name}")
    result = agent.ast_scanner.find_definitions(symbol_name)
    return json.dumps(result, indent=2)
