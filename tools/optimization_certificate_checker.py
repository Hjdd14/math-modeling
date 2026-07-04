#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""优化证书检查工具"""

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


def _as_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "optimization_certificate.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks": [],
        "issues": [
            {
                "code": "missing_optimization_certificate",
                "severity": severity,
                "message": "缺少 optimization_certificate.json；优化题在 excellence 模式必须给出残差、上下界、gap 和 oracle/替代求解器证书。",
            }
        ],
    }


def check_optimization_certificate(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "optimization_certificate.json"
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

    residual = payload.get("feasibility_residual") or payload.get("feasibility_residuals")
    bounds = payload.get("bounds")
    gap = payload.get("optimality_gap") or payload.get("gap")
    oracle = payload.get("alternative_solver") or payload.get("enumeration_oracle") or payload.get("oracle")

    required = {
        "feasibility_residual": residual,
        "bounds": bounds,
        "optimality_gap": gap,
        "alternative_solver_or_oracle": oracle,
    }
    for field, value in required.items():
        ok = _present(value)
        checks.append({"name": f"field_{field}", "passed": ok})
        if not ok:
            _add_issue(issues, "missing_optimization_certificate_field", f"优化证书缺少 {field}。", severity=severity, field=field)

    if isinstance(residual, dict):
        max_abs = _as_float(residual.get("max_abs"))
        tolerance = _as_float(residual.get("tolerance"), 1e-6)
        if max_abs is not None and tolerance is not None and max_abs > tolerance:
            _add_issue(issues, "feasibility_residual_exceeds_tolerance", "可行性残差超过阈值。", actual=max_abs, threshold=tolerance)

    if isinstance(gap, dict):
        value = _as_float(gap.get("value"))
        tolerance = _as_float(gap.get("tolerance"), 1e-4)
    else:
        value = _as_float(gap)
        tolerance = 1e-4
    if value is not None and tolerance is not None and value > tolerance:
        _add_issue(issues, "optimality_gap_exceeds_tolerance", "最优性 gap 超过阈值。", actual=value, threshold=tolerance)

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
    parser = argparse.ArgumentParser(description="检查 optimization_certificate.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_optimization_certificate(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
