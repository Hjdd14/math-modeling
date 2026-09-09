#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题型专属 validation profile 检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
PROFILE_ALIASES = {
    "optimization": "optimization",
    "forecasting": "forecasting",
    "prediction": "forecasting",
    "machine_learning": "forecasting",
    "graph": "graph_network",
    "graph_path": "graph_network",
    "graph_network": "graph_network",
    "network": "graph_network",
    "simulation": "stochastic_simulation",
    "stochastic_simulation": "stochastic_simulation",
    "physical": "physical_mechanism",
    "mechanism": "physical_mechanism",
    "physical_mechanism": "physical_mechanism",
    "policy": "policy_decision",
    "decision": "policy_decision",
    "policy_decision": "policy_decision",
}
PROFILE_REQUIREMENTS = {
    "optimization": ["baseline", "oracle", "gap", "residuals", "sensitivity"],
    "forecasting": ["holdout", "cv", "metrics.MAE", "metrics.RMSE", "metrics.MAPE", "residuals", "interval_coverage"],
    "graph_network": ["path_validity", "edge_existence", "connectivity", "cost_recalculation"],
    "stochastic_simulation": ["multi_seed", "confidence_interval", "convergence_or_variance"],
    "physical_mechanism": ["units", "conservation", "boundary_conditions", "known_special_case"],
    "policy_decision": ["weights_sum_to_one", "ranking_stability", "scenario_explanation"],
}
# 题型天然不涉及某项验证时可显式声明不适用，但必须同时提供 rationale 与 alternative_validation。
NOT_APPLICABLE_STATUSES = {"not_applicable", "na", "n/a"}


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


def _is_not_applicable(value) -> bool:
    if not isinstance(value, dict):
        return False
    return str(value.get("status", "")).strip().lower() in NOT_APPLICABLE_STATUSES


def _not_applicable_justified(value) -> tuple[bool, str]:
    """not_applicable 必须同时给出理由和替代验证方式。"""
    rationale = value.get("rationale") or value.get("reason")
    alternative = value.get("alternative_validation") or value.get("alternative")
    if not (isinstance(rationale, str) and rationale.strip()):
        return False, "缺少 rationale：必须说明为什么该验证项不适用。"
    if not (isinstance(alternative, str) and alternative.strip()):
        return False, "缺少 alternative_validation：必须说明改用哪种验证方式替代。"
    return True, ""


def _get_path(payload: dict, dotted: str):
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "validation_profile.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "profile": None,
        "checks": [],
        "issues": [
            {
                "code": "missing_validation_profile",
                "severity": severity,
                "message": "缺少 validation_profile.json；excellence 模式必须给出题型专属验证证据。",
            }
        ],
    }


def check_validation_profile(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "validation_profile.json"
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
            "profile": None,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []

    raw_profile = str(payload.get("profile", "")).lower() if isinstance(payload, dict) else ""
    profile = PROFILE_ALIASES.get(raw_profile)
    if profile is None:
        _add_issue(issues, "unknown_validation_profile", "validation_profile.json 中的 profile 不在支持列表内。", severity=severity, profile=raw_profile)
        requirements = []
    else:
        requirements = PROFILE_REQUIREMENTS[profile]

    evidence = payload.get("evidence", {}) if isinstance(payload, dict) else {}
    if not isinstance(evidence, dict):
        evidence = {}
        _add_issue(issues, "invalid_validation_evidence", "validation_profile.evidence 必须是对象。", severity=severity)

    for field in requirements:
        value = _get_path(evidence, field)
        ok = _present(value)
        not_applicable = _is_not_applicable(value)
        if not_applicable:
            # 题型天然不涉及该验证时可显式声明，但必须给出理由和替代验证方式，
            # 否则 not_applicable 就等于无成本地跳过验证。
            justified, reason = _not_applicable_justified(value)
            checks.append({"name": f"field_{field}", "passed": justified, "not_applicable": True})
            if not justified:
                _add_issue(
                    issues,
                    "not_applicable_without_justification",
                    f"{profile} 的 {field} 声明 not_applicable 但{reason}",
                    severity=severity,
                    field=field,
                    profile=profile,
                )
            continue
        if isinstance(value, dict) and value.get("passed") is False:
            ok = False
        checks.append({"name": f"field_{field}", "passed": ok})
        if not ok:
            _add_issue(
                issues,
                "missing_validation_profile_field",
                f"{profile} 验证 profile 缺少或未通过字段: {field}。",
                severity=severity,
                field=field,
                profile=profile,
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "profile": profile,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 validation_profile.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_validation_profile(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
