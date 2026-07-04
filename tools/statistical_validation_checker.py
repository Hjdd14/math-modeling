#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计验证检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_FIELDS = ["metrics", "residuals", "intervals", "robustness", "overfitting_risk"]


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
        "path": str(root / "statistical_validation.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks": [],
        "issues": [
            {
                "code": "missing_statistical_validation",
                "severity": severity,
                "message": "缺少 statistical_validation.json；excellence 模式必须记录指标、残差、区间、稳健性和过拟合风险。",
            }
        ],
    }


def check_statistical_validation(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "statistical_validation.json"
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
    issues: list[dict] = []
    checks: list[dict] = []

    has_holdout = _present(payload.get("holdout")) or _present(payload.get("cv"))
    checks.append({"name": "holdout_or_cv", "passed": has_holdout})
    if not has_holdout:
        _add_issue(issues, "missing_statistical_validation_field", "缺少 holdout 或 CV 验证记录。", severity=severity, field="holdout_or_cv")

    for field in REQUIRED_FIELDS:
        ok = _present(payload.get(field))
        checks.append({"name": f"field_{field}", "passed": ok})
        if not ok:
            _add_issue(issues, "missing_statistical_validation_field", f"统计验证缺少 {field}。", severity=severity, field=field)

    metrics = payload.get("metrics", {})
    if isinstance(metrics, dict) and metrics:
        metric_names = {str(name).upper() for name in metrics}
        has_core_metric = bool(metric_names & {"MAE", "RMSE", "MAPE", "R2", "ACCURACY", "AUC"})
        checks.append({"name": "core_metric_present", "passed": has_core_metric, "metrics": sorted(metric_names)})
        if not has_core_metric:
            _add_issue(issues, "missing_core_metric", "metrics 中缺少常用可解释指标。", severity=severity)

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
    parser = argparse.ArgumentParser(description="检查 statistical_validation.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_statistical_validation(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
