#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不确定性预算检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_SOURCES = ["data", "parameter", "model", "random"]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _strict(mode: str) -> bool:
    return mode in STRICT_MODES


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "uncertainty_budget.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks": [],
        "issues": [
            {
                "code": "missing_uncertainty_budget",
                "severity": severity,
                "message": "缺少 uncertainty_budget.json；excellence 模式必须记录数据、参数、模型和随机误差预算。",
            }
        ],
    }


def check_uncertainty_budget(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "uncertainty_budget.json"
    if not path.exists():
        return _missing_result(root, normalized_mode)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "passed": False,
            "warning": False,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    checks: list[dict] = []
    issues: list[dict] = []

    for source in REQUIRED_SOURCES:
        item = payload.get(source) if isinstance(payload, dict) else None
        ok = isinstance(item, dict) and _present(item.get("impact"))
        checks.append({"name": f"source_{source}", "passed": ok})
        if not ok:
            _add_issue(
                issues,
                "missing_uncertainty_source",
                f"不确定性预算缺少 {source} 误差来源、影响或处理方式。",
                severity=severity,
                field=source,
            )
            continue
        if not (_present(item.get("mitigation")) or _present(item.get("sensitivity")) or _present(item.get("evidence"))):
            _add_issue(
                issues,
                "missing_uncertainty_mitigation",
                f"{source} 误差来源缺少 mitigation/sensitivity/evidence。",
                severity=severity,
                field=source,
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 uncertainty_budget.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_uncertainty_budget(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
