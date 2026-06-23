#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LaTeX 公式渲染验证工具"""

import argparse
import json
import os
import re
import sys


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


DISPLAY_PATTERN = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
INLINE_PATTERN = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")

OPEN_CLOSE_PAIRS = {
    "{": "}",
    "(": ")",
    "[": "]",
    "\\{": "\\}",
    "\\left(": "\\right)",
    "\\left[": "\\right]",
    "\\left\\{": "\\right\\}",
    "\\left|": "\\right|",
    "\\langle": "\\rangle",
    "\\lfloor": "\\rfloor",
    "\\lceil": "\\rceil",
}

LATEX_COMMANDS = [
    "frac", "sqrt", "sum", "prod", "int", "lim", "max", "min",
    "argmin", "argmax", "sin", "cos", "tan", "log", "ln", "exp", "sup", "inf",
    "begin", "end", "text", "operatorname", "mathbf", "mathrm", "mathbb",
    "mathcal", "boldsymbol",
    "partial", "nabla", "infty", "alpha", "beta", "gamma",
    "delta", "epsilon", "theta", "lambda", "mu", "sigma",
    "omega", "pi", "phi", "psi", "rho", "tau", "xi", "zeta",
    "cdot", "times", "div", "pm", "mp", "leq", "geq", "neq",
    "approx", "equiv", "subset", "supset", "cup", "cap",
    "forall", "exists", "in", "notin", "to", "rightarrow",
    "leftarrow", "Rightarrow", "Leftarrow", "overline", "underline",
    "hat", "bar", "vec", "dot", "ddot", "tilde",
    "cases", "aligned", "matrix", "pmatrix", "bmatrix", "vmatrix",
    "hspace", "vspace", "quad", "qquad", "left", "right",
]


def extract_formulas(content: str) -> list:
    """提取所有 LaTeX 公式"""
    formulas = []

    for match in DISPLAY_PATTERN.finditer(content):
        line_num = content[:match.start()].count("\n") + 1
        formulas.append({
            "formula": match.group(1).strip(),
            "line": line_num,
            "type": "display"
        })

    for match in INLINE_PATTERN.finditer(content):
        formula_text = match.group(1).strip()
        if not formula_text:
            continue
        line_num = content[:match.start()].count("\n") + 1
        formulas.append({
            "formula": formula_text,
            "line": line_num,
            "type": "inline"
        })

    return formulas


def validate_formula(formula: str) -> dict:
    """验证单个公式的语法"""
    issues = []

    env_stack = []
    env_pattern = re.compile(r"\\(begin|end)\s*\{([a-zA-Z*]+)\}")
    for env_match in env_pattern.finditer(formula):
        action, env_name = env_match.groups()
        if action == "begin":
            env_stack.append((env_name, env_match.start()))
        elif not env_stack:
            issues.append(f"未匹配的环境结束: \\end{{{env_name}}}")
        else:
            open_env, open_pos = env_stack[-1]
            if open_env == env_name:
                env_stack.pop()
            else:
                issues.append(
                    f"环境不匹配: 位置 {open_pos} 的 \\begin{{{open_env}}} "
                    f"对应到 \\end{{{env_name}}}"
                )

    for env_name, open_pos in env_stack:
        issues.append(f"未闭合的环境: \\begin{{{env_name}}} 位置 {open_pos}")

    open_stack = []
    i = 0
    while i < len(formula):
        ch = formula[i]

        if ch == "\\" and i + 1 < len(formula):
            next_ch = formula[i + 1]
            if next_ch == "{" or next_ch == "}":
                if next_ch == "{":
                    open_stack.append("{")
                else:
                    if open_stack and open_stack[-1] == "{":
                        open_stack.pop()
                    else:
                        issues.append(f"未匹配的闭合大括号 '}}' 位置 {i}")
                i += 2
                continue

        if ch == "{":
            open_stack.append("{")
        elif ch == "}":
            if open_stack and open_stack[-1] == "{":
                open_stack.pop()
            else:
                issues.append(f"未匹配的闭合大括号 '}}' 位置 {i}")

        i += 1

    if open_stack:
        issues.append(f"未闭合的大括号: {len(open_stack)} 个")

    cmd_pattern = re.compile(r"\\([a-zA-Z]+)")
    for cmd_match in cmd_pattern.finditer(formula):
        cmd = cmd_match.group(1)
        if cmd not in LATEX_COMMANDS and len(cmd) > 1:
            if not cmd.startswith("math"):
                issues.append(f"未知命令: \\{cmd}")

    frac_pattern = re.compile(r"\\frac(?!\{)")
    if frac_pattern.search(formula):
        issues.append("\\frac 命令后缺少花括号参数")

    sqrt_pattern = re.compile(r"\\sqrt(?!\{|\[)")
    if sqrt_pattern.search(formula):
        issues.append("\\sqrt 命令后缺少花括号参数")

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_latex_file(file_path: str) -> dict:
    """验证 Markdown 文件中的 LaTeX 公式"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    formulas = extract_formulas(content)
    total = len(formulas)
    valid = 0
    invalid = 0
    details = []

    for f_info in formulas:
        result = validate_formula(f_info["formula"])
        detail = {
            "formula": f_info["formula"][:100],
            "line": f_info["line"],
            "type": f_info["type"],
            "valid": result["valid"],
            "issues": result["issues"]
        }
        details.append(detail)
        if result["valid"]:
            valid += 1
        else:
            invalid += 1

    score = round((valid / total * 100) if total > 0 else 100, 2)

    return {
        "total_formulas": total,
        "valid": valid,
        "invalid": invalid,
        "details": details,
        "score": score
    }


def extract_formulas_from_file(file_path: str) -> dict:
    """提取文件中所有公式"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    formulas = extract_formulas(content)
    return {"formulas": formulas}


def main():
    parser = argparse.ArgumentParser(description="LaTeX 公式渲染验证工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_validate = subparsers.add_parser("validate", help="验证 Markdown 中的 LaTeX 公式")
    p_validate.add_argument("--file", required=True, help="Markdown 文件路径")

    p_extract = subparsers.add_parser("extract", help="提取所有公式")
    p_extract.add_argument("--file", required=True, help="Markdown 文件路径")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "validate":
            result = validate_latex_file(args.file)
            output(result)
        elif args.action == "extract":
            result = extract_formulas_from_file(args.file)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
