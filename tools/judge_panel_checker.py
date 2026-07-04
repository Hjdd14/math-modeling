#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多评委并行审查结果检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_ROLES = {
    "national_modeling_judge": "国赛建模评委",
    "comap_judge": "美赛评委",
    "code_reproducibility_judge": "代码复现评委",
    "figure_evidence_judge": "图表证据评委",
    "engineering_business_judge": "工程/业务解释评委",
}
RESOLVED_STATUSES = {"resolved", "fixed", "closed", "accepted", "done", "通过", "已解决"}


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
        "path": str(root / "judge_panel_review.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "roles_present": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_judge_panel_review",
                "severity": severity,
                "message": "缺少 judge_panel_review.json；excellence 模式必须有多评委并行审查记录。",
            }
        ],
    }


def _issue_is_unresolved_high(issue: dict) -> bool:
    severity = str(issue.get("severity", "")).lower()
    status = str(issue.get("status", "")).lower()
    if severity != "high":
        return False
    return status not in RESOLVED_STATUSES


def check_judge_panel(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "judge_panel_review.json"
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
            "roles_present": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    judges = payload.get("judges") if isinstance(payload, dict) else None
    if not isinstance(judges, list):
        judges = []
        _add_issue(issues, "invalid_judges", "judge_panel_review.json 必须包含 judges 列表。")

    roles = {str(item.get("judge_type", "")).strip() for item in judges if isinstance(item, dict)}
    missing_roles = [role for role in REQUIRED_ROLES if role not in roles]
    checks.append({"name": "required_judge_roles", "passed": not missing_roles, "missing": missing_roles})
    for role in missing_roles:
        _add_issue(issues, "missing_judge_role", f"缺少评委角色: {REQUIRED_ROLES[role]}。", role=role)

    for judge in judges:
        if not isinstance(judge, dict):
            continue
        for item in judge.get("issues", []) or []:
            if isinstance(item, dict) and _issue_is_unresolved_high(item):
                _add_issue(
                    issues,
                    "unresolved_high_severity_issue",
                    "评委组存在未解决 high severity 问题。",
                    judge_type=judge.get("judge_type"),
                    issue=item,
                )
        if judge.get("passed") is False:
            _add_issue(issues, "judge_marked_failed", "某评委显式标记未通过。", judge_type=judge.get("judge_type"))

    chair = payload.get("chair_summary") if isinstance(payload, dict) else None
    chair_ok = isinstance(chair, dict) and bool(chair.get("decision")) and "required_fixes" in chair
    checks.append({"name": "chair_summary", "passed": chair_ok})
    if not chair_ok:
        _add_issue(issues, "missing_chair_summary", "缺少 chair_summary.decision 或 required_fixes。")

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "roles_present": len(roles),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 judge_panel_review.json 的多评委审查记录")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_judge_panel(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
