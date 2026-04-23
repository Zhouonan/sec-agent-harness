import ast
import operator
import sys


# 定义允许的操作符
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


def safe_eval(node):
    """
    安全地求值 AST 节点。
    只允许数学运算，禁止任何函数调用或属性访问。
    """
    if isinstance(node, ast.Expression):
        return safe_eval(node.body)
    
    elif isinstance(node, ast.BinOp):
        left = safe_eval(node.left)
        right = safe_eval(node.right)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](left, right)
        else:
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    
    elif isinstance(node, ast.UnaryOp):
        operand = safe_eval(node.operand)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](operand)
        else:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    
    elif isinstance(node, ast.Num):  # Python 3.7 及更早版本
        return node.n
    
    elif isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return node.value
        else:
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
    
    else:
        raise ValueError(f"Unsupported node type: {type(node).__name__}")


def calculate(expression):
    """
    安全地计算数学表达式。
    
    支持的操作：+、-、*、/、//、%、**（幂运算）、一元正负号
    
    参数:
        expression: 数学表达式字符串，如 "2 + 2"
    
    返回:
        计算结果，或 "Invalid input" 如果表达式不安全或无效
    """
    try:
        # 解析表达式为 AST
        tree = ast.parse(expression, mode='eval')
        
        # 安全求值
        result = safe_eval(tree)
        return result
    except (ValueError, SyntaxError, TypeError) as e:
        return "Invalid input"
    except Exception as e:
        return "Error"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        expression = sys.argv[1]
        result = calculate(expression)
        print(result)
    else:
        print("No expression provided")
