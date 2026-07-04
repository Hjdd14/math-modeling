#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mini contest benchmark 结构与 oracle 检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_CASE_FIELDS = ["id", "category", "prompt", "expected_outputs", "oracle"]
ORACLE_KEYS = {"expected_value", "known_case", "invariants", "verifier"}


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


def _has_oracle(oracle) -> bool:
    if not isinstance(oracle, dict):
        return False
    return any(key in oracle and oracle[key] not in (None, "", [], {}) for key in ORACLE_KEYS)


def check_benchmark(path: str, mode: str = "standard") -> dict:
    benchmark_path = Path(path)
    normalized_mode = mode.lower()
    issues: list[dict] = []
    checks: list[dict] = []

    if not benchmark_path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        return {
            "path": str(benchmark_path),
            "mode": normalized_mode,
            "passed": severity == "warning",
            "warning": severity == "warning",
            "cases_checked": 0,
            "case_summaries": [],
            "checks": [],
            "issues": [
                {
                    "code": "missing_mini_contest_benchmark",
                    "severity": severity,
                    "message": "缺少 mini contest benchmark。",
                }
            ],
        }

    try:
        payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "path": str(benchmark_path),
            "mode": normalized_mode,
            "passed": False,
            "warning": False,
            "cases_checked": 0,
            "case_summaries": [],
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        _add_issue(issues, "missing_cases", "benchmark 必须包含非空 cases 列表。")
        cases = []

    case_summaries = []
    categories = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            _add_issue(issues, "invalid_case", "benchmark case 必须是对象。", index=index)
            continue
        categories.add(case.get("category"))
        missing = [field for field in REQUIRED_CASE_FIELDS if field not in case]
        has_oracle = _has_oracle(case.get("oracle"))
        case_summaries.append(
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "has_oracle": has_oracle,
                "missing": missing,
            }
        )
        if missing:
            _add_issue(issues, "missing_case_field", "benchmark case 缺少必要字段。", index=index, missing=missing)
        if not has_oracle:
            _add_issue(issues, "missing_case_oracle", "benchmark case 必须有可核验目标值、known case、不变量或 verifier。", index=index)

    checks.append({"name": "case_count", "passed": len(cases) >= 6, "count": len(cases)})
    if len(cases) < 6:
        _add_issue(issues, "too_few_cases", "mini contest benchmark 至少应覆盖 6 个案例。")
    checks.append({"name": "category_coverage", "passed": len(categories) >= 6, "categories": sorted(str(item) for item in categories if item)})
    if len(categories) < 6:
        _add_issue(issues, "insufficient_category_coverage", "mini contest benchmark 至少应覆盖 6 类题型。")

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "path": str(benchmark_path),
        "mode": normalized_mode,
        "passed": passed,
        "warning": warning,
        "cases_checked": len(cases),
        "case_summaries": case_summaries,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 mini contest benchmark 是否包含可核验 oracle")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_benchmark(args.benchmark, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
