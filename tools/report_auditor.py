#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞赛论文结构审计工具"""

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
SECTION_GROUPS = {
    "abstract": ["摘要"],
    "problem": ["问题重述", "问题描述", "问题分析"],
    "assumptions": ["模型假设", "假设"],
    "symbols": ["符号说明", "符号表"],
    "model": ["模型建立", "模型构建", "模型"],
    "solution": ["模型求解", "求解"],
    "validation": ["模型验证", "结果验证", "检验"],
    "sensitivity": ["敏感性分析", "鲁棒性分析"],
    "evaluation": ["模型评价", "优缺点", "改进"],
    "conclusion": ["结论", "决策建议"],
}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    strict = mode in STRICT_MODES
    return {
        "workspace": str(root),
        "mode": mode,
        "report_path": str(root / "modeling_report.md"),
        "passed": not strict,
        "warning": not strict,
        "sections_found": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_modeling_report",
                "severity": "error" if strict else "warning",
                "message": "缺少 modeling_report.md；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def _has_section(text: str, aliases: list[str]) -> bool:
    headings = re.findall(r"^#{1,6}\s*(.+)$", text, flags=re.MULTILINE)
    for heading in headings:
        if any(alias in heading for alias in aliases):
            return True
    return False


def audit_report(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    report_path = root / "modeling_report.md"
    if not report_path.exists():
        return _missing_result(root, mode)

    text = report_path.read_text(encoding="utf-8", errors="ignore")
    checks = []
    issues = []
    sections_found = 0
    missing_sections = []

    for key, aliases in SECTION_GROUPS.items():
        found = _has_section(text, aliases)
        checks.append({"name": f"section_{key}", "passed": found, "aliases": aliases})
        if found:
            sections_found += 1
        else:
            missing_sections.append(key)
            severity = "error" if mode in STRICT_MODES else "warning"
            _add_issue(issues, "missing_report_section", f"报告缺少 {aliases[0]} 相关章节。", severity, section=key)

    figure_refs = len(re.findall(r"!\[.*?\]\(.*?\)|图\s*\d+|\.png|\.svg|\.pdf", text, flags=re.IGNORECASE))
    checks.append({"name": "figure_references", "passed": figure_refs > 0, "count": figure_refs})
    if figure_refs == 0:
        _add_issue(
            issues,
            "missing_figure_reference",
            "报告正文没有可识别的图表引用。",
            "error" if mode in STRICT_MODES else "warning",
        )

    result_terms = ["结果", "最优", "误差", "指标", "利润", "成本", "准确率", "置信区间"]
    abstract_match = re.search(r"^#*\s*摘要[\s\S]*?(?=^#{1,6}\s|\Z)", text, flags=re.MULTILINE)
    abstract_text = abstract_match.group(0) if abstract_match else ""
    has_result_in_abstract = any(term in abstract_text for term in result_terms)
    checks.append({"name": "abstract_has_results", "passed": has_result_in_abstract})
    if abstract_match and not has_result_in_abstract:
        _add_issue(
            issues,
            "abstract_missing_results",
            "摘要缺少可识别的结果或指标表达。",
            "warning",
        )

    overclaim_terms = ["绝对最优", "完全解决", "必然", "没有任何误差"]
    overclaims = [term for term in overclaim_terms if term in text]
    checks.append({"name": "overclaim_terms", "passed": not overclaims, "terms": overclaims})
    for term in overclaims:
        _add_issue(issues, "overclaim", f"报告包含可能过度承诺的表述: {term}。", "warning", term=term)

    passed = not any(issue.get("severity") == "error" for issue in issues)
    warning = any(issue.get("severity") == "warning" for issue in issues)
    result = {
        "workspace": str(root),
        "mode": mode,
        "report_path": str(report_path),
        "passed": passed,
        "warning": warning,
        "sections_found": sections_found,
        "checks": checks,
        "issues": issues,
    }
    (root / "report_quality_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description="审计 modeling_report.md 的竞赛论文结构")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = audit_report(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
