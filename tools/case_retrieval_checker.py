#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题型案例检索结果与题目领域匹配检查工具"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
DOMAIN_RULES = [
    {
        "domain": "电力电工",
        "keywords": ["电力", "电网", "输电", "潮流", "电路", "电磁", "电机", "负荷"],
        "source_keywords": ["电工", "电机", "电力", "电气"],
        "problem_keywords": ["电力电工", "物理机理", "优化调度"],
    },
    {
        "domain": "统计调查",
        "keywords": ["问卷", "抽样", "调查", "统计推断", "社会经济", "置信区间", "回归"],
        "source_keywords": ["统计建模", "统计教育", "统计"],
        "problem_keywords": ["统计调查", "预测统计", "政策决策"],
    },
    {
        "domain": "行业大数据",
        "keywords": ["大数据", "平台用户", "用户行为", "商品画像", "行业数据", "日志", "业务指标"],
        "source_keywords": ["MathorCup", "大数据", "数据洞察"],
        "problem_keywords": ["机器学习混合", "预测统计", "优化调度"],
    },
]
REQUIRED_MATCH_FIELDS = {
    "source_competition",
    "year",
    "problem_id",
    "problem_type",
    "similarity_reason",
    "borrowable_methods",
    "cannot_copy_risks",
    "validation_needed",
}


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


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _mentions_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _top_match(payload: dict) -> dict:
    matches = payload.get("matched_cases", [])
    if not isinstance(matches, list) or not matches:
        return {}
    return matches[0] if isinstance(matches[0], dict) else {}


def check_case_retrieval(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "case_retrieval.json"
    brief_path = root / "problem_brief.md"
    issues: list[dict] = []
    checks: list[dict] = []

    if not path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        _add_issue(issues, "missing_case_retrieval", "缺少 case_retrieval.json；奖项级流程必须记录相似题型检索。", severity)
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "passed": severity != "error",
            "warning": severity == "warning",
            "top_match": {},
            "checks": checks,
            "issues": issues,
        }

    payload, load_error = _load_json(path)
    if load_error:
        _add_issue(issues, "invalid_case_retrieval_json", load_error)
        payload = {}

    top_match = _top_match(payload if isinstance(payload, dict) else {})
    matches = payload.get("matched_cases", []) if isinstance(payload, dict) else []
    checks.append({"name": "matched_cases_present", "passed": isinstance(matches, list) and len(matches) > 0, "count": len(matches) if isinstance(matches, list) else 0})
    if not isinstance(matches, list) or not matches:
        _add_issue(issues, "missing_matched_cases", "case_retrieval.json 缺少 matched_cases。")

    for index, match in enumerate(matches if isinstance(matches, list) else [], start=1):
        if not isinstance(match, dict):
            _add_issue(issues, "invalid_matched_case", "matched_cases 条目必须是对象。", index=index)
            continue
        missing = sorted(REQUIRED_MATCH_FIELDS - set(match))
        if missing:
            _add_issue(issues, "missing_case_field", "相似案例缺少必填字段。", index=index, missing=missing)
        for list_field in ["borrowable_methods", "cannot_copy_risks", "validation_needed"]:
            if not match.get(list_field):
                _add_issue(issues, "empty_case_evidence_field", f"相似案例 {list_field} 不能为空。", index=index, field=list_field)

    brief_text = brief_path.read_text(encoding="utf-8", errors="ignore") if brief_path.exists() else ""
    combined_text = " ".join([
        brief_text,
        str(payload.get("problem_domain", "")) if isinstance(payload, dict) else "",
        " ".join(payload.get("matched_problem_types", [])) if isinstance(payload, dict) and isinstance(payload.get("matched_problem_types"), list) else "",
    ])
    source = str(top_match.get("source_competition", ""))
    problem_type = str(top_match.get("problem_type", ""))

    for rule in DOMAIN_RULES:
        domain_detected = _mentions_any(combined_text, rule["keywords"])
        if not domain_detected:
            continue
        source_ok = _mentions_any(source, rule["source_keywords"])
        type_ok = _mentions_any(problem_type, rule["problem_keywords"])
        passed = source_ok and type_ok
        checks.append({
            "name": f"domain_source_match_{rule['domain']}",
            "passed": passed,
            "source": source,
            "problem_type": problem_type,
        })
        if not passed:
            _add_issue(
                issues,
                "domain_source_mismatch",
                f"题目含 {rule['domain']} 特征，但 top match 来源或题型不匹配。",
                domain=rule["domain"],
                source=source,
                problem_type=problem_type,
            )

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": any(issue.get("severity") == "warning" for issue in issues),
        "top_match": top_match,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 case_retrieval.json 是否与题目领域匹配")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_case_retrieval(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
