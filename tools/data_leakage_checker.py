#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据泄漏检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
TIME_SERIES_TASKS = {"forecasting", "time_series", "prediction"}
TRAIN_ONLY = {"train", "training", "train_only", "fit_train_only"}


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
        "path": str(root / "data_validation.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks": [],
        "issues": [
            {
                "code": "missing_data_validation",
                "severity": severity,
                "message": "缺少 data_validation.json；预测/机器学习题在 excellence 模式必须排查数据泄漏。",
            }
        ],
    }


def check_data_leakage(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "data_validation.json"
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

    target = payload.get("target") if isinstance(payload, dict) else None
    features = payload.get("features", []) if isinstance(payload, dict) else []
    feature_set = set(features) if isinstance(features, list) else set()
    target_ok = bool(target) and target not in feature_set
    checks.append({"name": "target_not_in_features", "passed": target_ok})
    if target and target in feature_set:
        _add_issue(issues, "target_leakage", "目标字段进入特征列表，存在直接泄漏。", severity=severity, target=target)
    elif not target:
        _add_issue(issues, "missing_target", "data_validation.json 缺少 target 字段。", severity=severity)

    split = payload.get("split", {}) if isinstance(payload, dict) else {}
    task_type = str(payload.get("task_type", "")).lower() if isinstance(payload, dict) else ""
    split_type = str(split.get("type", "")).lower() if isinstance(split, dict) else ""
    split_ok = bool(split_type)
    if task_type in TIME_SERIES_TASKS and split_type not in {"time", "time_series", "chronological", "rolling"}:
        split_ok = False
        _add_issue(issues, "invalid_time_split", "时间序列/预测任务不得使用随机切分，应采用时间切分或滚动验证。", severity=severity, split=split_type)
    elif not split_ok:
        _add_issue(issues, "missing_holdout", "缺少 holdout/CV 数据切分记录。", severity=severity)
    checks.append({"name": "split_strategy", "passed": split_ok, "split_type": split_type})

    preprocessing = payload.get("preprocessing", []) if isinstance(payload, dict) else []
    preprocessing_ok = isinstance(preprocessing, list)
    if preprocessing_ok:
        for index, step in enumerate(preprocessing):
            fit_on = str(step.get("fit_on", "")).lower() if isinstance(step, dict) else ""
            if fit_on not in TRAIN_ONLY:
                preprocessing_ok = False
                _add_issue(
                    issues,
                    "preprocessing_leakage",
                    "标准化、填补、编码等预处理必须只在训练集拟合。",
                    severity=severity,
                    index=index,
                    fit_on=fit_on,
                )
    else:
        _add_issue(issues, "invalid_preprocessing_record", "preprocessing 必须是列表。", severity=severity)
    checks.append({"name": "preprocessing_train_only", "passed": preprocessing_ok})

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
    parser = argparse.ArgumentParser(description="检查 data_validation.json 中的数据泄漏风险")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_data_leakage(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
