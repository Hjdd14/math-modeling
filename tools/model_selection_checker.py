#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型选择审计检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}


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
        "path": str(root / "model_selection_audit.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "candidates_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_model_selection_audit",
                "severity": severity,
                "message": "缺少 model_selection_audit.json；excellence 模式必须说明候选模型、评分、拒绝理由与最终选择证据。",
            }
        ],
    }


def check_model_selection(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "model_selection_audit.json"
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
            "candidates_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []
    candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    final_selection = payload.get("final_selection", {}) if isinstance(payload, dict) else {}

    candidates_ok = isinstance(candidates, list) and len(candidates) >= 2
    checks.append({"name": "candidate_models", "passed": candidates_ok, "count": len(candidates) if isinstance(candidates, list) else 0})
    if not candidates_ok:
        _add_issue(issues, "missing_model_selection_evidence", "模型选择审计至少应列出 2 个候选模型。", severity=severity)
        candidates = candidates if isinstance(candidates, list) else []

    selected_name = final_selection.get("name") if isinstance(final_selection, dict) else None
    rejected_count = 0
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            _add_issue(issues, "invalid_model_candidate", "候选模型必须是对象。", severity=severity, index=index)
            continue
        name = candidate.get("name")
        if not _present(name) or not _present(candidate.get("score")):
            _add_issue(issues, "missing_model_selection_evidence", "候选模型必须包含 name 和 score。", severity=severity, index=index)
        if name != selected_name:
            if not _present(candidate.get("rejection_reason")):
                _add_issue(issues, "missing_model_rejection_reason", "未入选候选模型必须记录拒绝理由。", severity=severity, index=index, name=name)
            else:
                rejected_count += 1

    final_ok = isinstance(final_selection, dict) and _present(final_selection.get("name")) and _present(final_selection.get("evidence"))
    checks.append({"name": "final_selection_evidence", "passed": final_ok})
    if not final_ok:
        _add_issue(issues, "missing_model_selection_evidence", "最终模型选择必须包含 name 和 evidence。", severity=severity)

    rejected_ok = rejected_count >= 1 or len(candidates) <= 1
    checks.append({"name": "rejection_reasons", "passed": rejected_ok, "rejected_count": rejected_count})

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "candidates_checked": len(candidates),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 model_selection_audit.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_model_selection(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
