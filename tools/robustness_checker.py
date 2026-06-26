#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数值鲁棒性证据检查工具"""

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
ROBUSTNESS_ITEMS = [
    "constraint_residuals",
    "optimality_gap",
    "multi_start",
    "random_seed_stability",
    "bootstrap_confidence_interval",
    "perturbation_stability",
]


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
        "summary_path": str(root / "results" / "validation_summary.json"),
        "passed": not strict,
        "warning": not strict,
        "evidence_items_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_validation_summary",
                "severity": "error" if strict else "warning",
                "message": "缺少 results/validation_summary.json；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _explicit_failure(value) -> bool:
    if isinstance(value, dict):
        return value.get("passed") is False or value.get("status") in {"failed", "fail"}
    if isinstance(value, list):
        return any(_explicit_failure(item) for item in value)
    return False


def check_robustness(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    summary_path = root / "results" / "validation_summary.json"
    if not summary_path.exists():
        return _missing_result(root, mode)

    checks = []
    issues = []
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": mode,
            "summary_path": str(summary_path),
            "passed": False,
            "warning": False,
            "evidence_items_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    evidence_items_checked = 0
    missing = []
    for item in ROBUSTNESS_ITEMS:
        value = summary.get(item)
        if value is None:
            missing.append(item)
            severity = "error" if mode in STRICT_MODES else "warning"
            _add_issue(issues, "missing_robustness_item", f"缺少数值鲁棒性证据: {item}。", severity, item=item)
            continue
        evidence_items_checked += 1
        failed = _explicit_failure(value)
        checks.append({"name": item, "passed": not failed})
        if failed:
            _add_issue(issues, "robustness_item_failed", f"{item} 显式标记为失败。", item=item)

    checks.append({"name": "required_robustness_items", "passed": not missing, "missing": missing})
    passed = not any(issue.get("severity") == "error" for issue in issues)
    warning = any(issue.get("severity") == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": mode,
        "summary_path": str(summary_path),
        "passed": passed,
        "warning": warning,
        "evidence_items_checked": evidence_items_checked,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 validation_summary.json 中的数值鲁棒性证据")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_robustness(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
