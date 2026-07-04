#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奖项级交付上限产物检查工具"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_ARTIFACTS = [
    "ambiguity_register.json",
    "assumption_ledger.md",
    "scoring_strategy.md",
    "ablation_study.json",
    "decision_insights.md",
    "defense_questions.md",
]
RESOLVED_STATUSES = {
    "resolved",
    "fixed",
    "closed",
    "clarified",
    "accepted",
    "accepted_assumption",
    "not_applicable",
    "none",
}
UNRESOLVED_STATUSES = {"pending", "unresolved", "open", "todo", "待确认", "待解决", "未解决"}


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


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _read_json(path: Path, issues: list[dict]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _add_issue(issues, "invalid_json", f"{path.name} 不是合法 JSON。", file=path.name, detail=str(exc))
        return None


def _text_has_all(text: str, terms: list[str]) -> tuple[bool, list[str]]:
    missing = [term for term in terms if term.lower() not in text.lower()]
    return not missing, missing


def _check_ambiguity_register(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "ambiguity_register.json"
    payload = _read_json(path, issues)
    if not isinstance(payload, dict):
        checks.append({"name": "ambiguity_register_schema", "passed": False})
        return

    items = payload.get("items")
    ok_items = isinstance(items, list)
    checks.append({"name": "ambiguity_items_list", "passed": ok_items, "count": len(items) if ok_items else 0})
    if not ok_items:
        _add_issue(issues, "invalid_ambiguity_register", "ambiguity_register.json 必须包含 items 列表。")
        return

    required = ["id", "severity", "source", "issue", "impact", "resolution", "assumption_if_unresolved"]
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            _add_issue(issues, "invalid_ambiguity_item", "歧义项必须是对象。", index=index)
            continue
        missing = [field for field in required if not _present(item.get(field))]
        checks.append({"name": "ambiguity_item_fields", "index": index, "passed": not missing, "missing": missing})
        for field in missing:
            _add_issue(issues, "missing_ambiguity_field", f"歧义项缺少字段: {field}。", index=index, field=field)

        severity = str(item.get("severity", "")).lower()
        resolution = str(item.get("resolution", "")).lower()
        if severity == "high" and (resolution in UNRESOLVED_STATUSES or resolution not in RESOLVED_STATUSES):
            _add_issue(
                issues,
                "unresolved_high_ambiguity",
                "high severity 题意歧义不能在 excellence 模式下未解决进入建模。",
                index=index,
                resolution=item.get("resolution"),
            )


def _check_assumption_ledger(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "assumption_ledger.md"
    text = path.read_text(encoding="utf-8", errors="ignore")
    ok, missing = _text_has_all(text, ["来源", "影响", "验证", "状态"])
    checks.append({"name": "assumption_ledger_columns", "passed": ok, "missing": missing})
    if not ok:
        _add_issue(
            issues,
            "incomplete_assumption_ledger",
            "assumption_ledger.md 必须记录假设来源、影响、验证方式和状态。",
            missing=missing,
        )


def _check_scoring_strategy(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "scoring_strategy.md"
    text = path.read_text(encoding="utf-8", errors="ignore")
    ok, missing = _text_has_all(text, ["评分", "必答", "图表"])
    has_question_signal = any(term in text for term in ["小问", "问题", "任务"])
    checks.append({"name": "scoring_strategy_content", "passed": ok and has_question_signal, "missing": missing})
    if not (ok and has_question_signal):
        _add_issue(
            issues,
            "incomplete_scoring_strategy",
            "scoring_strategy.md 必须列出小问/任务、必答结果、评分重点和图表支撑。",
            missing=missing,
        )


def _check_ablation_study(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "ablation_study.json"
    payload = _read_json(path, issues)
    if not isinstance(payload, dict):
        checks.append({"name": "ablation_schema", "passed": False})
        return
    experiments = payload.get("experiments")
    ok_list = isinstance(experiments, list) and bool(experiments)
    checks.append({"name": "ablation_experiments_present", "passed": ok_list, "count": len(experiments) if isinstance(experiments, list) else 0})
    if not ok_list:
        _add_issue(issues, "missing_ablation_experiments", "ablation_study.json 必须包含非空 experiments 列表。")
        return

    required = ["name", "changed_component", "metric_delta", "interpretation", "passed"]
    for index, item in enumerate(experiments):
        if not isinstance(item, dict):
            _add_issue(issues, "invalid_ablation_experiment", "消融实验项必须是对象。", index=index)
            continue
        missing = [field for field in required if not _present(item.get(field))]
        checks.append({"name": "ablation_experiment_fields", "index": index, "passed": not missing, "missing": missing})
        for field in missing:
            _add_issue(issues, "missing_ablation_field", f"消融实验缺少字段: {field}。", index=index, field=field)
        if item.get("passed") is False:
            _add_issue(issues, "failed_ablation_experiment", "消融实验显式失败，必须回溯修正或解释。", index=index)


def _check_decision_insights(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "decision_insights.md"
    text = path.read_text(encoding="utf-8", errors="ignore")
    ok, missing = _text_has_all(text, ["关键结论", "风险", "策略"])
    has_meaning = "工程含义" in text or "业务" in text or "管理" in text or "决策" in text
    checks.append({"name": "decision_insights_content", "passed": ok and has_meaning, "missing": missing})
    if not (ok and has_meaning):
        _add_issue(
            issues,
            "incomplete_decision_insights",
            "decision_insights.md 必须包含关键结论、工程/业务/决策含义、风险提示和可执行策略。",
            missing=missing,
        )


def _check_defense_questions(root: Path, checks: list[dict], issues: list[dict]):
    path = root / "defense_questions.md"
    text = path.read_text(encoding="utf-8", errors="ignore")
    question_count = text.count("？") + text.count("?")
    answer_signal = any(term in text for term in ["回答", "要点", "修正", "证据"])
    checks.append({"name": "defense_questions_content", "passed": question_count >= 2 and answer_signal, "question_count": question_count})
    if question_count < 2 or not answer_signal:
        _add_issue(
            issues,
            "incomplete_defense_questions",
            "defense_questions.md 至少应包含两个评委可能追问的问题及回答要点/修正建议。",
            question_count=question_count,
        )


def check_award_readiness(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    severity = "error" if _strict(normalized_mode) else "warning"
    checks: list[dict] = []
    issues: list[dict] = []

    missing = [name for name in REQUIRED_ARTIFACTS if not (root / name).exists()]
    checks.append({"name": "required_award_artifacts", "passed": not missing, "missing": missing})
    for name in missing:
        _add_issue(
            issues,
            "missing_award_artifact",
            "缺少奖项级上限产物；excellence 模式必须补齐题意、评分、消融、决策解释和质询材料。",
            severity=severity,
            file=name,
        )

    if missing:
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "passed": severity == "warning",
            "warning": True,
            "checks": checks,
            "issues": issues,
        }

    _check_ambiguity_register(root, checks, issues)
    _check_assumption_ledger(root, checks, issues)
    _check_scoring_strategy(root, checks, issues)
    _check_ablation_study(root, checks, issues)
    _check_decision_insights(root, checks, issues)
    _check_defense_questions(root, checks, issues)

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "passed": passed,
        "warning": warning,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查奖项级上限产物是否完整可复核")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_award_readiness(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
