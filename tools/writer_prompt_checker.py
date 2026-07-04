#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写作交接提示词质量检查工具"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from tools.figure_auditor import _parse_storyboard
except ImportError:
    from figure_auditor import _parse_storyboard


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
SECTION_GROUPS = {
    "problem": ["题目", "小问", "评分"],
    "model": ["模型", "方案", "主线"],
    "code_results": ["代码", "结果"],
    "figures": ["图表", "可视化"],
    "evidence": ["验证", "证据"],
    "compliance": ["合规", "匿名", "AI"],
    "submission_review": ["后续写作", "提交复核", "官方规则"],
}
REQUIRED_TERMS = [
    "problem_brief",
    "final_solution",
    "validation_summary",
    "figure",
    "judge_panel_review",
    "compliance_record",
    "reproducibility",
]
REQUIRED_CN_TERMS = ["风险", "合规"]
IDENTITY_PATTERNS = [
    r"\b\d{8,}\b",
    "某某大学",
    "队伍编号",
    "参赛队",
    "姓名",
    "学号",
]


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
        "path": str(root / "writer_prompt.md"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "sections_found": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_writer_prompt",
                "severity": severity,
                "message": "缺少 writer_prompt.md；excellence 模式必须输出写作交接提示词。",
            }
        ],
    }


def _has_section(text: str, aliases: list[str]) -> bool:
    headings = re.findall(r"^#{1,6}\s*(.+)$", text, flags=re.MULTILINE)
    return any(any(alias.lower() in heading.lower() for alias in aliases) for heading in headings)


def check_writer_prompt(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "writer_prompt.md"
    report_path = root / "writer_prompt_quality.json"
    if not path.exists():
        result = _missing_result(root, normalized_mode)
        if root.exists():
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    text = path.read_text(encoding="utf-8", errors="ignore")
    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []
    sections_found = 0

    missing_terms = [term for term in REQUIRED_TERMS if term not in text]
    missing_cn_terms = [term for term in REQUIRED_CN_TERMS if term not in text]
    mentions_boundary = "不生成正式写作正文" in text and ("写作交接" in text or "交接提示" in text)
    minimal_handoff_ok = not missing_terms and not missing_cn_terms and mentions_boundary

    for name, aliases in SECTION_GROUPS.items():
        found = _has_section(text, aliases)
        checks.append({"name": f"section_{name}", "passed": found, "aliases": aliases})
        if found:
            sections_found += 1
        else:
            _add_issue(
                issues,
                "missing_writer_prompt_section",
                f"writer_prompt.md 缺少 {aliases[0]} 相关交接章节。",
                severity="warning" if minimal_handoff_ok else severity,
                section=name,
            )

    checks.append({"name": "required_handoff_references", "passed": not missing_terms, "missing": missing_terms})
    for term in missing_terms:
        _add_issue(
            issues,
            "writer_prompt_missing_context",
            f"writer_prompt.md 缺少写作交接关键信息: {term}。",
            severity=severity,
            term=term,
        )

    checks.append({"name": "cn_risk_compliance_terms", "passed": not missing_cn_terms, "missing": missing_cn_terms})
    for term in missing_cn_terms:
        _add_issue(
            issues,
            "writer_prompt_missing_context",
            f"writer_prompt.md 缺少写作交接关键信息: {term}。",
            severity=severity,
            term=term,
        )

    checks.append({"name": "handoff_boundary", "passed": mentions_boundary})
    if not mentions_boundary:
        _add_issue(
            issues,
            "writer_prompt_missing_boundary",
            "writer_prompt.md 必须说明本 skill 不生成正式写作正文，只提供写作交接材料。",
            severity=severity,
        )

    has_submission_checklist = (
        "后续写作/提交复核清单" in text
        or ("提交复核" in text and "官方规则" in text)
        or ("submission checklist" in text.lower() and "official" in text.lower())
    )
    checklist_terms = ["匿名", "引用", "AI", "页数", "附件", "代码"]
    missing_checklist_terms = [term for term in checklist_terms if term not in text]
    checklist_ok = has_submission_checklist and not missing_checklist_terms
    checks.append(
        {
            "name": "submission_review_checklist",
            "passed": checklist_ok,
            "missing": missing_checklist_terms,
        }
    )
    if not checklist_ok:
        _add_issue(
            issues,
            "missing_submission_review_checklist",
            "writer_prompt.md 必须包含后续写作/提交复核清单，覆盖匿名、引用、AI 披露、页数、附件和代码提交。",
            severity=severity,
            missing=missing_checklist_terms,
        )

    storyboard_path = root / "figure_storyboard.md"
    if storyboard_path.exists():
        storyboard_entries = _parse_storyboard(storyboard_path.read_text(encoding="utf-8", errors="ignore"))
        missing_figure_handoffs = []
        for entry in storyboard_entries:
            file_name = entry.get("file", "")
            claim = entry.get("claim", "")
            if file_name and file_name not in text:
                missing_figure_handoffs.append({"file": file_name, "field": "file"})
            if claim and claim not in text:
                missing_figure_handoffs.append({"file": file_name, "field": "claim", "claim": claim})
        checks.append({"name": "figure_claim_handoff", "passed": not missing_figure_handoffs, "missing": missing_figure_handoffs})
        for missing in missing_figure_handoffs:
            _add_issue(
                issues,
                "missing_figure_claim_handoff",
                "writer_prompt.md 必须交接每张图支撑的结论。",
                severity=severity,
                **missing,
            )

    contains_body_request = "请直接写完整论文" in text or "正式成稿如下" in text
    checks.append({"name": "no_formal_body_request", "passed": not contains_body_request})
    if contains_body_request:
        _add_issue(
            issues,
            "writer_prompt_contains_formal_body_request",
            "writer_prompt.md 不应要求本 skill 直接生成完整正式论文正文。",
            severity=severity,
        )

    identity_hits = []
    for pattern in IDENTITY_PATTERNS:
        if re.search(pattern, text):
            identity_hits.append(pattern)
    checks.append({"name": "anonymity_screen", "passed": not identity_hits, "hits": identity_hits})
    for hit in identity_hits:
        _add_issue(issues, "identity_leak", "writer_prompt.md 疑似包含身份信息。", severity=severity, pattern=hit)

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    result = {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "quality_report_path": str(report_path),
        "passed": passed,
        "warning": warning,
        "sections_found": sections_found,
        "checks": checks,
        "issues": issues,
    }
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description="检查 writer_prompt.md 的写作交接质量")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_writer_prompt(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
