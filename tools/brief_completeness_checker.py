#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""problem_brief.md 完成度检查工具。

除了原有的"标题齐备 + 无占位文本"两类检查，本工具还负责**选型锁定扫描**：
``problem_brief.md``（根与每问 ``questions/qN/problem_brief.md``）里出现
"已锁定 / 不得更换 / 不得推翻 / user_locked=true / 主模型已由…闸门"这类措辞时，
说明闸门 A 又在偷偷替用户锁死模型选型 —— 真正的选型只能由 B 闸门
（``design_board_gate_b.json`` 的 ``user_choice``）决定。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}

# 选型锁定的措辞黑名单（契约 §2.1 与计划 v2 §4.6）。
# 命中即说明简报把"待探索范式集合"写成了"已定模型"，会在 Phase 1 被五视角照抄。
LOCKED_SELECTION_PATTERNS = (
    # 「不锁定选型」是正确写法，必须放过：只在没有否定前缀时才算命中。
    r"(?<![不未])锁定选型",
    r"已锁定",
    r"不得更换",
    r"不得推翻",
    r"user_locked\s*[=:：]\s*true",
    # 只抓"已由某道闸门锁定/定了"这种既成事实的措辞；单纯的
    # "由 B 闸门 user_choice 决定"不是锁定，不该误报。
    r"主模型已由[^\n]*闸门[^\n]*(?:锁定|确定|不得)",
)
LOCKED_SELECTION_CODE = "brief_contains_locked_selection"

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


def _brief_files(root: Path) -> list[Path]:
    """列出要扫描的简报：根 ``problem_brief.md`` + 每问 ``questions/qN/problem_brief.md``。

    只收真实存在的文件；顺序稳定（根在前，小问按目录名排序），便于报告对账。
    """
    files: list[Path] = []
    root_brief = root / "problem_brief.md"
    if root_brief.is_file():
        files.append(root_brief)
    questions_dir = root / "questions"
    if questions_dir.is_dir():
        for child in sorted(questions_dir.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            candidate = child / "problem_brief.md"
            if candidate.is_file():
                files.append(candidate)
    return files


def _locked_selection_hits(text: str) -> list[dict]:
    """返回选型锁定措辞的命中清单：{pattern, match, line}。"""
    hits: list[dict] = []
    for pattern in LOCKED_SELECTION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            hits.append(
                {
                    "pattern": pattern,
                    "match": match.group(0),
                    "line": text.count("\n", 0, match.start()) + 1,
                }
            )
    return hits


def _scan_locked_selection(
    root: Path, files: list[Path], severity: str
) -> tuple[list[dict], list[dict]]:
    """扫描全部简报里的选型锁定措辞，返回 (issues, checks)。

    这里不写死 severity：excellence 家族判 error（选型锁定是"闸门 A 越权"的硬错误），
    standard 只 warning（旧工作区仍能跑完，但要看到待办）。
    """
    issues: list[dict] = []
    checks: list[dict] = []
    for brief_path in files:
        try:
            text = brief_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # 读不到不是锁定问题，单独留痕
            issues.append(
                {
                    "code": "brief_unreadable",
                    "severity": "warning",
                    "message": f"{brief_path.name} 读取失败：{exc}",
                    "file": str(brief_path),
                }
            )
            continue
        try:
            label = brief_path.relative_to(root).as_posix()
        except ValueError:  # pragma: no cover - 防御性分支
            label = str(brief_path)
        hits = _locked_selection_hits(text)
        checks.append(
            {
                "name": "no_locked_selection",
                "file": label,
                "passed": not hits,
                "hits": hits,
            }
        )
        for hit in hits:
            issues.append(
                {
                    "code": LOCKED_SELECTION_CODE,
                    "severity": severity,
                    "message": (
                        f"{label} 第 {hit['line']} 行出现选型锁定措辞「{hit['match']}」；"
                        "闸门 A 只确认题意框架与待探索范式集合，模型选型必须留给 B 闸门的 "
                        "user_choice。请删掉该措辞，改为列出待探索的 paradigm_set / paradigm_selection。"
                    ),
                    "file": label,
                    "line": hit["line"],
                    "pattern": hit["pattern"],
                    "match": hit["match"],
                }
            )
    return issues, checks


def _has_section(text: str, aliases: list[str]) -> bool:
    headings = re.findall(r"^#{1,6}\s*(.+)$", text, flags=re.MULTILINE)
    if any(any(alias.lower() in heading.lower() for alias in aliases) for heading in headings):
        return True
    return any(alias in text for alias in aliases)


def check_brief_completeness(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "problem_brief.md"
    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"

    if not path.exists():
        result = _missing_result(root, normalized_mode)
        # 根简报缺失时，仍然扫一遍已存在的每问简报：锁定措辞不会因为根简报不在就消失。
        lock_issues, lock_checks = _scan_locked_selection(root, _brief_files(root), severity)
        if lock_checks:
            result["checks"].extend(lock_checks)
        if lock_issues:
            result["issues"].extend(lock_issues)
            result["passed"] = not any(issue["severity"] == "error" for issue in result["issues"])
            result["warning"] = any(issue["severity"] == "warning" for issue in result["issues"])
        return result

    text = path.read_text(encoding="utf-8", errors="ignore")
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

    # 选型锁定扫描：根简报 + 每问简报（questions/qN/problem_brief.md）。
    lock_issues, lock_checks = _scan_locked_selection(root, _brief_files(root), severity)
    issues.extend(lock_issues)
    checks.extend(lock_checks)

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
