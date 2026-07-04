#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创新筛选登记检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_FIELDS = [
    "claim",
    "problem_pain_point",
    "baseline_gain",
    "implementation_cost",
    "interpretability",
    "verification_evidence",
    "failure_risk",
]
VAGUE_TERMS = ["高级", "先进", "智能算法", "复杂模型", "深度学习", "机器学习"]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _strict(mode: str) -> bool:
    return mode in STRICT_MODES


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "innovation_register.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "innovations_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_innovation_register",
                "severity": severity,
                "message": "缺少 innovation_register.json；excellence 模式必须记录创新筛选证据。",
            }
        ],
    }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _baseline_gain_has_evidence(value: Any) -> bool:
    if isinstance(value, dict):
        return _present(value.get("metric")) and (
            _present(value.get("delta")) or _present(value.get("evidence"))
        )
    return _present(value)


def _verification_has_evidence(value: Any) -> bool:
    if isinstance(value, list):
        return len([item for item in value if _present(item)]) > 0
    return _present(value)


def check_innovations(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    path = root / "innovation_register.json"
    normalized_mode = mode.lower()
    if not path.exists():
        return _missing_result(root, normalized_mode)

    checks: list[dict] = []
    issues: list[dict] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "passed": False,
            "warning": False,
            "innovations_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    innovations = payload.get("innovations", payload.get("items")) if isinstance(payload, dict) else None
    if not isinstance(innovations, list) or not innovations:
        _add_issue(
            issues,
            "missing_innovation_items",
            "innovation_register.json 必须包含非空 innovations 列表。",
            "error" if _strict(normalized_mode) else "warning",
        )
        innovations = []

    for index, item in enumerate(innovations):
        if not isinstance(item, dict):
            _add_issue(issues, "invalid_innovation_item", "创新项必须是对象。", index=index)
            continue

        missing_fields = [field for field in REQUIRED_FIELDS if not _present(item.get(field))]
        checks.append({"name": "innovation_required_fields", "index": index, "passed": not missing_fields, "missing": missing_fields})
        for field in missing_fields:
            _add_issue(
                issues,
                "missing_innovation_field",
                f"创新项缺少必要字段: {field}。",
                field=field,
                index=index,
            )

        has_gain = _baseline_gain_has_evidence(item.get("baseline_gain"))
        has_verification = _verification_has_evidence(item.get("verification_evidence"))
        checks.append(
            {
                "name": "innovation_evidence",
                "index": index,
                "passed": has_gain and has_verification,
            }
        )
        if not (has_gain and has_verification):
            _add_issue(
                issues,
                "missing_innovation_evidence",
                "创新点必须有 baseline 增益、消融或敏感性分析支撑，不能只写方法名。",
                index=index,
            )

        claim = str(item.get("claim", ""))
        vague = any(term in claim for term in VAGUE_TERMS)
        if vague and not (has_gain and has_verification):
            _add_issue(
                issues,
                "vague_innovation_claim",
                "创新表述过于空泛且缺少证据，疑似为了高级而高级。",
                index=index,
                claim=claim,
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "innovations_checked": len(innovations),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 innovation_register.json 的创新筛选证据")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_innovations(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
