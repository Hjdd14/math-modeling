#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""problem_brief.md 完成度检查工具"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
PLACEHOLDER_PATTERNS = [
    r"待\s*Agent\s*提取",
    r"待确认",
    r"待补充",
    r"待定",
    r"\bTODO\b",
    r"\bTBD\b",
]
SECTION_GROUPS = {
    "objectives": ["目标", "任务", "问题", "小问", "求解"],
    "constraints": ["约束", "限制", "条件", "假设"],
    "outputs": ["输出", "结果", "提交", "交付", "要求"],
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


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "problem_brief.md"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks_passed": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_problem_brief",
                "severity": severity,
                "message": "缺少 problem_brief.md；excellence 模式必须先完成题意审计。",
            }
        ],
    }


def _has_section(text: str, aliases: list[str]) -> bool:
    headings = re.findall(r"^#{1,6}\s*(.+)$", text, flags=re.MULTILINE)
    if any(any(alias.lower() in heading.lower() for alias in aliases) for heading in headings):
        return True
    return any(alias in text for alias in aliases)


def check_brief_completeness(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "problem_brief.md"
    if not path.exists():
        return _missing_result(root, normalized_mode)

    text = path.read_text(encoding="utf-8", errors="ignore")
    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []

    placeholder_hits = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            placeholder_hits.append(pattern)
            _add_issue(
                issues,
                "brief_placeholder",
                "problem_brief.md 仍残留待提取或待确认占位文本。",
                severity=severity,
                pattern=pattern,
            )
    checks.append({"name": "no_placeholders", "passed": not placeholder_hits, "hits": placeholder_hits})

    for name, aliases in SECTION_GROUPS.items():
        found = _has_section(text, aliases)
        checks.append({"name": f"section_{name}", "passed": found, "aliases": aliases})
        if not found:
            _add_issue(
                issues,
                "missing_brief_section",
                f"problem_brief.md 缺少 {aliases[0]} 相关内容。",
                severity=severity,
                section=name,
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 problem_brief.md 是否完成题意审计")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_brief_completeness(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
