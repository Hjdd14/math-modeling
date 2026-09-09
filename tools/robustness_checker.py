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
# 占位标记：模板默认产出这些值，代表"尚未真实验证"，任何模式下都不算证据。
PLACEHOLDER_MARKERS = ("NOT_VALIDATED", "UNVALIDATED", "REPLACE_ME", "TODO", "FIXME")
NOT_APPLICABLE_STATUSES = {"not_applicable", "na", "n/a"}
# 确定性模型可对随机性相关条目声明不适用，但必须给出理由和替代验证方式。
NOT_APPLICABLE_ELIGIBLE = {
    "multi_start",
    "random_seed_stability",
    "bootstrap_confidence_interval",
    "perturbation_stability",
}


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


def _has_placeholder(value) -> bool:
    """判断证据条目是否仍是模板占位状态。"""
    if isinstance(value, dict):
        status = str(value.get("status", "")).strip().upper()
        if any(marker in status for marker in PLACEHOLDER_MARKERS):
            return True
        if "passed" in value and value.get("passed") is None and not _is_not_applicable(value):
            return True
        return any(_has_placeholder(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_placeholder(item) for item in value)
    if isinstance(value, str):
        return any(marker in value.strip().upper() for marker in PLACEHOLDER_MARKERS)
    return False


def _is_not_applicable(value) -> bool:
    if not isinstance(value, dict):
        return False
    return str(value.get("status", "")).strip().lower() in NOT_APPLICABLE_STATUSES


def _not_applicable_justified(value) -> tuple[bool, str]:
    """not_applicable 必须同时给出理由和替代验证方式，否则等同于跳过验证。"""
    rationale = value.get("rationale") or value.get("reason")
    alternative = value.get("alternative_validation") or value.get("alternative")
    if not (isinstance(rationale, str) and rationale.strip()):
        return False, "缺少 rationale：必须说明为什么该验证项不适用。"
    if not (isinstance(alternative, str) and alternative.strip()):
        return False, "缺少 alternative_validation：必须说明改用哪种验证方式替代。"
    return True, ""


def _as_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _numeric_threshold_issues(item: str, value) -> list[dict]:
    issues = []
    if not isinstance(value, dict):
        return issues

    if item == "constraint_residuals":
        actual = _as_float(value.get("max_abs"))
        tolerance = _as_float(value.get("tolerance"), 1e-6)
        if actual is not None and tolerance is not None and actual > tolerance:
            issues.append(
                {
                    "item": item,
                    "actual": actual,
                    "threshold": tolerance,
                    "message": f"约束最大残差 {actual} 超过阈值 {tolerance}。",
                }
            )

    if item == "optimality_gap":
        actual = _as_float(value.get("value"))
        tolerance = _as_float(value.get("tolerance"), 1e-4)
        if actual is not None and tolerance is not None and actual > tolerance:
            issues.append(
                {
                    "item": item,
                    "actual": actual,
                    "threshold": tolerance,
                    "message": f"最优性 gap {actual} 超过阈值 {tolerance}。",
                }
            )

    if item == "multi_start":
        runs = int(_as_float(value.get("runs"), 0) or 0)
        min_runs = int(_as_float(value.get("min_runs"), 3) or 3)
        if runs < min_runs:
            issues.append(
                {
                    "item": item,
                    "actual": runs,
                    "threshold": min_runs,
                    "message": f"多初值运行次数 {runs} 少于要求 {min_runs}。",
                }
            )

    if item == "random_seed_stability":
        seeds = value.get("seeds", [])
        if not isinstance(seeds, list) or len(seeds) < 3:
            issues.append(
                {
                    "item": item,
                    "actual": len(seeds) if isinstance(seeds, list) else 0,
                    "threshold": 3,
                    "message": "随机种子稳定性至少应记录 3 个种子。",
                }
            )

    if item == "bootstrap_confidence_interval":
        lower = _as_float(value.get("lower"))
        upper = _as_float(value.get("upper"))
        level = _as_float(value.get("level"), 0)
        if lower is not None and upper is not None and lower > upper:
            issues.append(
                {
                    "item": item,
                    "message": "置信区间 lower 大于 upper。",
                }
            )
        if level is not None and level < 0.95:
            issues.append(
                {
                    "item": item,
                    "actual": level,
                    "threshold": 0.95,
                    "message": "置信水平低于 0.95，不能支撑奖项级交付。",
                }
            )

    if item == "perturbation_stability" and value.get("ranking_changed") is True:
        issues.append(
            {
                "item": item,
                "message": "参数扰动后排序发生变化，需要解释或修正。",
            }
        )

    return issues


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

        # 占位证据优先判定：模板默认值不能当作验证结果，任何模式都判失败。
        if _has_placeholder(value):
            checks.append({"name": item, "passed": False, "placeholder": True})
            _add_issue(
                issues,
                "placeholder_evidence",
                f"{item} 仍是模板占位状态（NOT_VALIDATED/TODO/passed=null），必须用真实计算替换。",
                item=item,
            )
            continue

        # 确定性模型可显式声明不适用，但必须给出理由与替代验证。
        if _is_not_applicable(value):
            if item not in NOT_APPLICABLE_ELIGIBLE:
                checks.append({"name": item, "passed": False, "not_applicable": True})
                _add_issue(
                    issues,
                    "not_applicable_not_allowed",
                    f"{item} 不允许声明 not_applicable：约束残差与最优性 gap 对任何模型都可核验。",
                    item=item,
                )
                continue
            justified, reason = _not_applicable_justified(value)
            checks.append({"name": item, "passed": justified, "not_applicable": True})
            if not justified:
                _add_issue(
                    issues,
                    "not_applicable_without_justification",
                    f"{item} 声明 not_applicable 但{reason}",
                    item=item,
                )
            continue

        failed = _explicit_failure(value)
        threshold_issues = _numeric_threshold_issues(item, value) if mode in STRICT_MODES else []
        checks.append({"name": item, "passed": not failed and not threshold_issues})
        if failed:
            _add_issue(issues, "robustness_item_failed", f"{item} 显式标记为失败。", item=item)
        for threshold_issue in threshold_issues:
            _add_issue(
                issues,
                "robustness_threshold_failed",
                threshold_issue["message"],
                item=item,
                actual=threshold_issue.get("actual"),
                threshold=threshold_issue.get("threshold"),
            )

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
