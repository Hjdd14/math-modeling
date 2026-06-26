#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码与文档一致性检查工具"""

import argparse
import ast
import json
import keyword
import os
import re
import sys
import textwrap


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


MATH_OPERATORS = {
    "+", "-", "*", "/", "**", "//", "%",
    "sum", "prod", "mean", "std", "min", "max",
    "sqrt", "abs", "exp", "log", "sin", "cos", "tan",
    "dot", "cross", "norm", "inv", "det", "solve",
}

IGNORED_SYMBOLS = MATH_OPERATORS | {
    "leq", "geq", "neq", "cdot", "times", "frac", "sqrt", "text",
    "begin", "end", "cases", "aligned", "operatorname", "argmin", "argmax",
    "left", "right", "quad", "qquad", "mathbf", "mathrm", "mathbb",
    "mathcal", "boldsymbol", "np", "sp", "math",
    "List", "Tuple", "Dict", "Set", "Load", "Store", "Name", "Constant",
    "UnaryOp", "USub", "BinOp", "Add", "Sub", "Mult", "Div", "Pow",
    "Call", "Attribute", "keyword", "arg", "args", "elts", "ctx",
    "func", "id", "attr", "value", "operand", "op", "keywords",
    "None", "True", "False", "return", "_",
}
PYTHON_KEYWORDS = set(keyword.kwlist)


def extract_symbols(text: str) -> set:
    """提取可用于一致性比较的符号，过滤 LaTeX/Python 结构噪声"""
    symbols = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text))
    return {
        symbol for symbol in symbols
        if symbol not in IGNORED_SYMBOLS
        and symbol not in PYTHON_KEYWORDS
        and not symbol.startswith("__")
    }


def extract_numbers(text: str) -> set:
    """提取公式或表达式中的数字常量"""
    numbers = set()
    for match in re.finditer(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?", text):
        raw = match.group(0)
        value = abs(float(raw))
        if value.is_integer():
            numbers.add(str(int(value)))
        else:
            numbers.add(str(value))
    return numbers


def strip_simple_lhs(formula: str) -> str:
    """去掉 Z = ... 这类目标函数记号，避免把结果符号误判为必需代码变量"""
    return re.sub(r"^\s*[A-Z]\s*=", "", formula, count=1)


def is_likely_math_symbol(symbol: str) -> bool:
    """代码侧只报告接近数学记号的独有符号，避免容器/函数名噪声淹没结果"""
    return bool(re.fullmatch(r"[A-Za-z](?:\d+)?", symbol))


def extract_doc_formulas(doc_content: str) -> list:
    """从文档中提取公式"""
    formulas = []

    display_pattern = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
    for match in display_pattern.finditer(doc_content):
        formula = match.group(1).strip()
        formulas.append({
            "formula": formula,
            "line": doc_content[:match.start()].count("\n") + 1,
            "type": "display"
        })

    inline_pattern = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
    for match in inline_pattern.finditer(doc_content):
        formula = match.group(1).strip()
        if formula:
            formulas.append({
                "formula": formula,
                "line": doc_content[:match.start()].count("\n") + 1,
                "type": "inline"
            })

    return formulas


def _call_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _is_math_call(node: ast.Call) -> bool:
    name = _call_name(node.func)
    short_name = name.rsplit(".", 1)[-1]
    return short_name in MATH_OPERATORS or name.startswith(("np.", "sp.", "math."))


def _has_numeric_constant(node) -> bool:
    return any(
        isinstance(child, ast.Constant) and isinstance(child.value, (int, float))
        for child in ast.walk(node)
    )


def _is_literal_container(node) -> bool:
    return isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set))


def _numeric_constant_expression(node) -> str:
    numbers = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
            value = abs(float(child.value))
            numbers.append(str(int(value)) if value.is_integer() else str(value))
    return " ".join(numbers)


def _is_math_expression(node) -> bool:
    if _is_literal_container(node):
        return False
    for child in ast.walk(node):
        if isinstance(child, (ast.BinOp, ast.Compare)):
            return True
        if isinstance(child, ast.Call) and _is_math_call(child):
            return True
    return _has_numeric_constant(node)


def _source_segment(code_content: str, node) -> str:
    segment = ast.get_source_segment(code_content, node)
    return segment.strip() if segment else ast.unparse(node)


def _append_expression(expressions: list, seen: set, expression: str, line: int, kind: str):
    expression = " ".join(expression.strip().split())
    if not expression or expression in seen:
        return
    seen.add(expression)
    expressions.append({
        "expression": expression[:200],
        "line": line,
        "type": kind,
    })


def extract_python_expressions(code_content: str) -> list:
    """从 Python 代码中提取数学表达式源码，避免比较 AST 内部结构词"""
    code_content = textwrap.dedent(code_content)
    expressions = []
    seen = set()
    try:
        tree = ast.parse(code_content)
        for node in ast.walk(tree):
            value = None
            kind = ""
            if isinstance(node, ast.Assign):
                value = node.value
                kind = "assignment"
            elif isinstance(node, ast.AnnAssign):
                value = node.value
                kind = "assignment"
            elif isinstance(node, ast.AugAssign):
                value = node.value
                kind = "assignment"
            elif isinstance(node, ast.Return):
                value = node.value
                kind = "return"
            elif isinstance(node, ast.Assert):
                value = node.test
                kind = "assertion"
            if value is not None and _is_math_expression(value):
                _append_expression(
                    expressions,
                    seen,
                    _source_segment(code_content, value),
                    getattr(node, "lineno", 0),
                    kind,
                )
            elif value is not None and _is_literal_container(value) and _has_numeric_constant(value):
                _append_expression(
                    expressions,
                    seen,
                    _numeric_constant_expression(value),
                    getattr(node, "lineno", 0),
                    "numeric_constants",
                )
            elif isinstance(node, ast.Call) and _is_math_call(node):
                _append_expression(
                    expressions,
                    seen,
                    _source_segment(code_content, node),
                    getattr(node, "lineno", 0),
                    "function_call",
                )
    except SyntaxError:
        for i, line in enumerate(code_content.split("\n"), 1):
            line = line.strip()
            if any(op in line for op in ["=", "+", "-", "*", "/", "np.", "math."]):
                if not line.startswith("#") and not line.startswith("import"):
                    _append_expression(expressions, seen, line, i, "raw_line")
    return expressions


def extract_matlab_expressions(code_content: str) -> list:
    """从 MATLAB 代码中提取数学表达式"""
    expressions = []
    for i, line in enumerate(code_content.split("\n"), 1):
        line = line.strip()
        if line.startswith("%") or not line:
            continue
        if re.search(r"[=+\-*/\^]", line) and not line.startswith("function"):
            expressions.append({
                "expression": line[:200],
                "line": i,
                "type": "assignment"
            })
    return expressions


def check_formula_consistency(doc_path: str, code_path: str, lang: str) -> dict:
    """检查公式一致性"""
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"文档文件不存在: {doc_path}")
    if not os.path.exists(code_path):
        raise FileNotFoundError(f"代码文件不存在: {code_path}")

    with open(doc_path, "r", encoding="utf-8") as f:
        doc_content = f.read()
    with open(code_path, "r", encoding="utf-8") as f:
        code_content = f.read()

    doc_formulas = extract_doc_formulas(doc_content)
    if lang == "python":
        code_expressions = extract_python_expressions(code_content)
    elif lang == "matlab":
        code_expressions = extract_matlab_expressions(code_content)
    else:
        raise ValueError(f"不支持的语言: {lang}")

    matches = []
    mismatches = []

    doc_symbols = set()
    doc_numbers = set()
    for f in doc_formulas:
        comparable_formula = strip_simple_lhs(f["formula"])
        doc_symbols.update(extract_symbols(comparable_formula))
        doc_numbers.update(extract_numbers(f["formula"]))

    code_symbols = set()
    code_numbers = set()
    for expr in code_expressions:
        code_symbols.update(extract_symbols(expr["expression"]))
        code_numbers.update(extract_numbers(expr["expression"]))

    common = doc_symbols & code_symbols
    only_in_doc = doc_symbols - code_symbols
    only_in_code = {
        symbol for symbol in code_symbols - doc_symbols
        if is_likely_math_symbol(symbol)
    }
    doc_only_numbers = doc_numbers - code_numbers
    code_only_numbers = code_numbers - doc_numbers

    matches = sorted(common)
    for symbol in sorted(only_in_doc)[:20]:
        mismatches.append({
            "type": "doc_only_symbol",
            "symbol": symbol,
            "detail": "文档公式中出现，但代码表达式中未找到"
        })
    for symbol in sorted(only_in_code)[:20]:
        mismatches.append({
            "type": "code_only_symbol",
            "symbol": symbol,
            "detail": "代码表达式中出现，但文档公式中未找到"
        })
    if doc_only_numbers or code_only_numbers:
        mismatches.append({
            "type": "numeric_constant_mismatch",
            "doc_only": sorted(doc_only_numbers, key=float),
            "code_only": sorted(code_only_numbers, key=float),
            "detail": "文档公式与代码表达式中的数字常量不一致"
        })

    consistency_score = round(
        (len(common) / len(doc_symbols) * 100) if doc_symbols else 100, 2
    )
    passed = True
    if doc_formulas and doc_only_numbers and not common:
        passed = False

    return {
        "doc_formulas": [f["formula"][:100] for f in doc_formulas[:20]],
        "code_expressions": [e["expression"][:100] for e in code_expressions[:20]],
        "matches": matches,
        "mismatches": mismatches,
        "consistency_score": consistency_score,
        "passed": passed,
        "doc_symbols_count": len(doc_symbols),
        "code_symbols_count": len(code_symbols),
        "common_count": len(common)
    }


def check_variable_consistency(doc_path: str, code_path: str, lang: str) -> dict:
    """检查变量一致性"""
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"文档文件不存在: {doc_path}")
    if not os.path.exists(code_path):
        raise FileNotFoundError(f"代码文件不存在: {code_path}")

    with open(doc_path, "r", encoding="utf-8") as f:
        doc_content = f.read()
    with open(code_path, "r", encoding="utf-8") as f:
        code_content = f.read()

    doc_formulas = extract_doc_formulas(doc_content)
    doc_variables = set()
    for f in doc_formulas:
        vars_found = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", f["formula"])
        doc_variables.update(vars_found)

    code_variables = set()
    if lang == "python":
        try:
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    code_variables.add(node.id)
                elif isinstance(node, ast.FunctionDef):
                    code_variables.add(node.name)
        except SyntaxError:
            for line in code_content.split("\n"):
                line = line.strip()
                if not line.startswith("#") and not line.startswith("import"):
                    vars_found = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", line)
                    code_variables.update(vars_found)
    elif lang == "matlab":
        for line in code_content.split("\n"):
            line = line.strip()
            if not line.startswith("%"):
                vars_found = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", line)
                code_variables.update(vars_found)

    common = doc_variables & code_variables
    only_in_doc = doc_variables - code_variables
    only_in_code = code_variables - doc_variables

    return {
        "doc_variables": sorted(list(doc_variables))[:50],
        "code_variables": sorted(list(code_variables))[:50],
        "common": sorted(list(common))[:50],
        "only_in_doc": sorted(list(only_in_doc))[:50],
        "only_in_code": sorted(list(only_in_code))[:50]
    }


def main():
    parser = argparse.ArgumentParser(description="代码与文档一致性检查工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_formula = subparsers.add_parser("formula", help="检查公式一致性")
    p_formula.add_argument("--doc", required=True, help="文档文件路径")
    p_formula.add_argument("--code", required=True, help="代码文件路径")
    p_formula.add_argument("--lang", required=True, choices=["python", "matlab"], help="编程语言")

    p_variable = subparsers.add_parser("variable", help="检查变量一致性")
    p_variable.add_argument("--doc", required=True, help="文档文件路径")
    p_variable.add_argument("--code", required=True, help="代码文件路径")
    p_variable.add_argument("--lang", required=True, choices=["python", "matlab"], help="编程语言")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "formula":
            result = check_formula_consistency(args.doc, args.code, args.lang)
            output(result)
        elif args.action == "variable":
            result = check_variable_consistency(args.doc, args.code, args.lang)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
