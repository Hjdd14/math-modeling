#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查难题建模可信度证据文件。

本工具只检查 `results/validation_summary.json` 的结构和显式通过状态，
不替代建模推理，也不声称证明数学结论正确。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
# 占位标记：模板默认产出这些值，代表"尚未真实验证"。
# 占位证据在任何模式下都不是合法证据，因此命中即判 error。
PLACEHOLDER_MARKERS = ("NOT_VALIDATED", "UNVALIDATED", "REPLACE_ME", "TODO", "FIXME")
NOT_APPLICABLE_STATUSES = {"not_applicable", "na", "n/a"}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _find_placeholders(value: Any, path: str = "") -> list[str]:
    """定位仍处于占位状态的证据字段。"""
    hits: list[str] = []
    if isinstance(value, dict):
        status = str(value.get("status", "")).strip().upper()
        if any(marker in status for marker in PLACEHOLDER_MARKERS):
            hits.append(path or "<root>")
        elif "passed" in value and value.get("passed") is None and status not in {
            s.upper() for s in NOT_APPLICABLE_STATUSES
        }:
            hits.append(f"{path or '<root>'}.passed=null")
        for key, child in value.items():
            hits.extend(_find_placeholders(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_find_placeholders(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        upper = value.strip().upper()
        if any(marker in upper for marker in PLACEHOLDER_MARKERS):
            hits.append(path or "<root>")
    return hits


def _placeholder_check(payload: Any) -> dict:
    hits = sorted(set(_find_placeholders(payload)))
    if hits:
        return {
            "name": "placeholder_evidence",
            "passed": False,
            "severity": "error",
            "detail": (
                "存在未替换的占位证据（模板默认值），不能作为验证结果: "
                + ", ".join(hits[:10])
                + (f" 等 {len(hits)} 处" if len(hits) > 10 else "")
            ),
            "fields": hits,
        }
    return {
        "name": "placeholder_evidence",
        "passed": True,
        "severity": "info",
        "detail": "ok",
        "fields": [],
    }


def _severity_for_missing(mode: str) -> str:
    return "error" if mode in STRICT_MODES else "warning"


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def _status_is_failure(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("passed") is False:
            return True
        status = str(value.get("status", "")).strip().lower()
        if status in {"fail", "failed", "error", "invalid"}:
            return True
        return any(_status_is_failure(child) for child in value.values())
    if isinstance(value, list):
        return any(_status_is_failure(item) for item in value)
    return False


def _has_positive_pass(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("passed") is True:
            return True
        status = str(value.get("status", "")).strip().lower()
        if status in {"pass", "passed", "ok", "success"}:
            return True
        return any(_has_positive_pass(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_positive_pass(item) for item in value)
    return False


def _section_check(name: str, value: Any, mode: str, require_positive_pass: bool = True) -> dict:
    if not _is_present(value):
        severity = _severity_for_missing(mode)
        return {
            "name": name,
            "passed": severity == "warning",
            "severity": severity,
            "detail": f"{name} missing or empty",
        }

    if _status_is_failure(value):
        return {
            "name": name,
            "passed": False,
            "severity": "error",
            "detail": f"{name} contains explicit failed status",
        }

    if require_positive_pass and not _has_positive_pass(value):
        severity = _severity_for_missing(mode)
        return {
            "name": name,
            "passed": severity == "warning",
            "severity": severity,
            "detail": f"{name} lacks explicit passed=true/status=passed evidence",
        }

    return {
        "name": name,
        "passed": True,
        "severity": "info",
        "detail": "ok",
    }


def _failure_modes_check(value: Any, mode: str) -> dict:
    if not _is_present(value):
        severity = _severity_for_missing(mode)
        return {
            "name": "failure_modes",
            "passed": severity == "warning",
            "severity": severity,
            "detail": "failure_modes missing or empty",
        }
    if not isinstance(value, list):
        return {
            "name": "failure_modes",
            "passed": False,
            "severity": "error",
            "detail": "failure_modes must be a list",
        }
    return {
        "name": "failure_modes",
        "passed": True,
        "severity": "info",
        "detail": "ok",
    }


def _issue_from_check(check: dict) -> dict:
    return {
        "check": check["name"],
        "severity": check["severity"],
        "detail": check["detail"],
    }


def _collect_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        for key in ("name", "baseline_name", "method", "holdout_metric"):
            item = value.get(key)
            if isinstance(item, str) and item:
                names.append(item)
        for child in value.values():
            names.extend(_collect_names(child))
    elif isinstance(value, list):
        for item in value:
            names.extend(_collect_names(item))
    return names


def check_evidence(workspace: str, mode: str = "standard") -> dict:
    """检查工作区中的 validation_summary.json。

    standard 模式向后兼容：缺少新证据文件或新结构时给 warning。
    strict/hard/complete/full/excellence 模式用于难题或完整验证：缺少证据即失败。
    未替换的模板占位证据在所有模式下都判失败。
    """
    normalized_mode = mode.lower()
    root = Path(workspace)
    path = root / "results" / "validation_summary.json"

    base_result = {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "exists": path.exists(),
        "passed": True,
        "warning": False,
        "checks": [],
        "issues": [],
    }

    if not path.exists():
        severity = _severity_for_missing(normalized_mode)
        issue = {
            "check": "validation_summary_json",
            "severity": severity,
            "detail": "results/validation_summary.json missing",
        }
        base_result["warning"] = severity == "warning"
        base_result["passed"] = severity == "warning"
        base_result["issues"].append(issue)
        return base_result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        base_result["passed"] = False
        base_result["issues"].append(
            {
                "check": "validation_summary_json",
                "severity": "error",
                "detail": f"invalid JSON: {exc}",
            }
        )
        return base_result

    if not isinstance(payload, dict):
        base_result["passed"] = False
        base_result["issues"].append(
            {
                "check": "validation_summary_json",
                "severity": "error",
                "detail": "validation_summary.json must contain a JSON object",
            }
        )
        return base_result

    oracle_value = payload.get("oracle_tests", payload.get("known_case_tests"))
    checks = [
        _placeholder_check(payload),
        _section_check("baseline_comparison", payload.get("baseline_comparison"), normalized_mode),
        _section_check("oracle_tests", oracle_value, normalized_mode),
        _section_check("solver_cross_checks", payload.get("solver_cross_checks"), normalized_mode),
        _section_check("sensitivity_analysis", payload.get("sensitivity_analysis"), normalized_mode),
        _section_check("invariants", payload.get("invariants"), normalized_mode),
        _failure_modes_check(payload.get("failure_modes"), normalized_mode),
    ]

    base_result["checks"] = checks
    base_result["evidence_items"] = {
        "baseline_comparison": _collect_names(payload.get("baseline_comparison")),
        "oracle_tests": _collect_names(oracle_value),
        "solver_cross_checks": _collect_names(payload.get("solver_cross_checks")),
        "sensitivity_analysis": _collect_names(payload.get("sensitivity_analysis")),
        "invariants": _collect_names(payload.get("invariants")),
        "failure_modes": _collect_names(payload.get("failure_modes")),
    }
    base_result["issues"] = [
        _issue_from_check(check)
        for check in checks
        if check["severity"] in {"warning", "error"}
    ]
    base_result["warning"] = any(issue["severity"] == "warning" for issue in base_result["issues"])
    base_result["passed"] = not any(check["passed"] is False for check in checks)
    return base_result


def main():
    parser = argparse.ArgumentParser(description="检查 validation_summary.json 可信度证据")
    parser.add_argument("--workspace", required=True, help="建模工作区")
    parser.add_argument(
        "--mode",
        default="standard",
        choices=["standard", "strict", "hard", "complete", "full", "excellence"],
        help="standard 向后兼容；strict/hard/complete/full/excellence 缺证据即失败",
    )
    args = parser.parse_args()

    result = check_evidence(args.workspace, args.mode)
    output(result)
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
