#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模交付物总控验证工具"""

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.brief_validator import validate_against_brief
    from tools.code_runner import run_code
    from tools.consistency_checker import check_formula_consistency
    from tools.figure_checker import batch_check
    from tools.latex_validator import validate_latex_file
except ImportError:
    from brief_validator import validate_against_brief
    from code_runner import run_code
    from consistency_checker import check_formula_consistency
    from figure_checker import batch_check
    from latex_validator import validate_latex_file


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _safe(name: str, checks: dict, func):
    try:
        checks[name] = func()
    except Exception as exc:
        checks[name] = {"passed": False, "error": str(exc)}
    return checks[name]


def run_checks(workspace: str, language: str = "python", timeout: int = 300) -> dict:
    root = Path(workspace)
    brief = root / "problem_brief.md"
    report = root / "modeling_report.md"
    code = root / ("solution.m" if language == "matlab" else "solution.py")
    results_dir = root / "results"

    required_paths = [brief, report, code, results_dir]
    missing = [str(path) for path in required_paths if not path.exists()]
    checks = {
        "required_files": {
            "passed": not missing,
            "missing": missing,
        }
    }

    if report.exists():
        def latex_step():
            result = validate_latex_file(str(report))
            result["passed"] = result["invalid"] == 0
            return result
        _safe("latex_validator", checks, latex_step)

    if code.exists():
        _safe("code_runner", checks, lambda: run_code(str(code), language, timeout, str(root)))

    if results_dir.exists():
        _safe("figure_checker", checks, lambda: batch_check(str(results_dir), "*.png"))

    if report.exists() and code.exists():
        def consistency_step():
            result = check_formula_consistency(str(report), str(code), language)
            result.setdefault("passed", "error" not in result)
            return result
        _safe("consistency_checker", checks, consistency_step)

    if brief.exists() and report.exists():
        _safe("brief_model", checks, lambda: validate_against_brief(str(brief), "model", str(report)))
    if brief.exists() and code.exists():
        _safe("brief_code", checks, lambda: validate_against_brief(str(brief), "code", str(code)))
    if brief.exists() and results_dir.exists():
        _safe("brief_output", checks, lambda: validate_against_brief(str(brief), "output", str(results_dir)))

    passed = checks["required_files"]["passed"]
    for name, result in checks.items():
        if name == "required_files":
            continue
        if result.get("success") is False or result.get("passed") is False:
            passed = False
        if name == "figure_checker" and (result.get("total", 0) == 0 or result.get("passed_all") is False):
            passed = False

    return {
        "workspace": str(root),
        "language": language,
        "passed": passed,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="数学建模交付物总控验证工具")
    parser.add_argument("--workspace", required=True, help="建模工作区")
    parser.add_argument("--language", default="python", choices=["python", "matlab"])
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    try:
        result = run_checks(args.workspace, args.language, args.timeout)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
