#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学模型中间表示检查工具"""

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_SECTIONS = ["variables", "objective", "constraints", "parameters", "data_fields", "validation_plan"]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _missing_result(root: Path, mode: str) -> dict:
    strict = mode in STRICT_MODES
    return {
        "workspace": str(root),
        "mode": mode,
        "spec_path": str(root / "model_spec.json"),
        "passed": not strict,
        "warning": not strict,
        "checks": [],
        "issues": [
            {
                "code": "missing_model_spec",
                "severity": "error" if strict else "warning",
                "message": "缺少 model_spec.json；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _contains_word(text: str, token: str) -> bool:
    if not token:
        return False
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(str(token))}(?![A-Za-z0-9_])", text) is not None


def check_model_spec(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    spec_path = root / "model_spec.json"
    if not spec_path.exists():
        return _missing_result(root, mode)

    checks = []
    issues = []
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": mode,
            "spec_path": str(spec_path),
            "passed": False,
            "warning": False,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    missing_sections = []
    for section in REQUIRED_SECTIONS:
        value = spec.get(section)
        empty = value is None or value == [] or value == {}
        if empty:
            missing_sections.append(section)
            _add_issue(issues, "missing_model_spec_section", f"model_spec.json 缺少或留空 {section}。", section=section)

    checks.append({"name": "required_sections", "passed": not missing_sections, "missing": missing_sections})

    variables = _as_list(spec.get("variables"))
    constraints = _as_list(spec.get("constraints"))
    for variable in variables:
        if not isinstance(variable, dict):
            _add_issue(issues, "invalid_variable", "variables 中存在非对象项。")
            continue
        for field in ["name", "unit"]:
            if not variable.get(field):
                _add_issue(issues, "missing_variable_field", f"变量缺少 {field}。", variable=variable.get("name"))

    for constraint in constraints:
        if isinstance(constraint, dict) and not (constraint.get("expression") or constraint.get("formula")):
            _add_issue(issues, "missing_constraint_expression", "约束缺少 expression/formula。", constraint=constraint.get("name"))

    handoff_text = ""
    code_text = ""
    model_decision_path = root / "model_decision.md"
    writer_prompt_path = root / "writer_prompt.md"
    code_path = root / "solution.py"
    matlab_path = root / "solution.m"
    for doc_path in [model_decision_path, writer_prompt_path]:
        if doc_path.exists():
            handoff_text += "\n" + doc_path.read_text(encoding="utf-8", errors="ignore")
    if code_path.exists():
        code_text = code_path.read_text(encoding="utf-8", errors="ignore")
    elif matlab_path.exists():
        code_text = matlab_path.read_text(encoding="utf-8", errors="ignore")

    referenced = []
    unreferenced = []
    for variable in variables:
        if not isinstance(variable, dict):
            continue
        name = variable.get("name")
        code_name = variable.get("code_name") or name
        in_handoff = _contains_word(handoff_text, name) if handoff_text else True
        in_code = _contains_word(code_text, code_name) if code_text else True
        referenced.append({"name": name, "in_handoff": in_handoff, "in_code": in_code})
        if not in_handoff or not in_code:
            unreferenced.append(name)

    checks.append({"name": "variable_references", "passed": not unreferenced, "details": referenced})
    for name in unreferenced:
        _add_issue(
            issues,
            "model_spec_symbol_not_referenced",
            f"变量 {name} 未同时出现在写作交接材料和代码中。",
            "warning",
            variable=name,
        )

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": mode,
        "spec_path": str(spec_path),
        "passed": passed,
        "warning": False,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 model_spec.json 的完整性与可追踪性")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_model_spec(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
