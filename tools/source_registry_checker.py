#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威竞赛来源库与方法卡可追溯性检查工具"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_SOURCE_FIELDS = {
    "name",
    "tier",
    "organizer",
    "official_url",
    "years_covered",
    "case_material_type",
    "trust_notes",
}
REQUIRED_CARD_LABELS = ["来源比赛", "年份", "题号", "适用条件", "误用风险", "推荐验证", "来源链接"]
REQUIRED_PROBLEM_TYPES = [
    "优化调度",
    "预测统计",
    "图网络",
    "随机仿真",
    "物理机理",
    "电力电工",
    "统计调查",
    "多目标鲁棒",
    "机器学习混合",
    "政策决策",
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


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _method_cards(playbook: str) -> list[str]:
    return re.findall(r"^#### 方法卡\s+.+?(?=^#### 方法卡\s+|^### |\Z)", playbook, flags=re.M | re.S)


def _label_present(card: str, label: str) -> bool:
    return f"- {label}：" in card or f"- {label}:" in card


def _source_names(registry: dict) -> list[str]:
    names = []
    for sources in registry.get("tiers", {}).values():
        if isinstance(sources, list):
            names.extend(str(source.get("name", "")) for source in sources if isinstance(source, dict))
    return [name for name in names if name]


def _source_known(card: str, names: list[str]) -> bool:
    if not names:
        return False
    match = re.search(r"- 来源比赛[：:]\s*(.+)", card)
    if not match:
        return False
    source = match.group(1).strip()
    return any(source in name or name in source for name in names)


def check_source_registry(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    registry_path = root / "references" / "competition_sources.json"
    playbook_path = root / "references" / "award_playbook.md"
    issues: list[dict] = []
    checks: list[dict] = []

    if not registry_path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        _add_issue(issues, "missing_source_registry", "缺少 references/competition_sources.json。", severity)
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "passed": severity != "error",
            "warning": severity == "warning",
            "registry_path": str(registry_path),
            "playbook_path": str(playbook_path),
            "tier_counts": {},
            "method_cards_checked": 0,
            "checks": checks,
            "issues": issues,
        }

    registry, load_error = _load_json(registry_path)
    if load_error:
        _add_issue(issues, "invalid_source_registry_json", load_error)
        registry = {}

    tiers = registry.get("tiers", {}) if isinstance(registry, dict) else {}
    tier_counts = {
        tier_name: len(sources) if isinstance(sources, list) else 0
        for tier_name, sources in tiers.items()
    }
    checks.append({"name": "tier_a_count", "passed": tier_counts.get("tier_a", 0) >= 7, "count": tier_counts.get("tier_a", 0)})
    checks.append({"name": "tier_b_count", "passed": tier_counts.get("tier_b", 0) >= 7, "count": tier_counts.get("tier_b", 0)})
    if tier_counts.get("tier_a", 0) < 7:
        _add_issue(issues, "insufficient_tier_a_sources", "tier_a 权威来源不足 7 个。")
    if tier_counts.get("tier_b", 0) < 7:
        _add_issue(issues, "insufficient_tier_b_sources", "tier_b 训练来源不足 7 个。")

    for tier_name, sources in tiers.items():
        if not isinstance(sources, list):
            _add_issue(issues, "invalid_tier_sources", f"{tier_name} 必须是列表。", tier=tier_name)
            continue
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                _add_issue(issues, "invalid_source_entry", "来源条目必须是对象。", tier=tier_name, index=index)
                continue
            missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
            if missing:
                _add_issue(issues, "missing_source_field", "来源条目缺少必填字段。", source=source.get("name"), missing=missing)
            if source.get("tier") != tier_name:
                _add_issue(issues, "source_tier_mismatch", "来源条目的 tier 与所在分层不一致。", source=source.get("name"), tier=tier_name)
            official_url = str(source.get("official_url", ""))
            if not official_url.startswith("http"):
                _add_issue(issues, "invalid_source_url", "official_url 必须是可核验 URL。", source=source.get("name"))

    if not playbook_path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        _add_issue(issues, "missing_award_playbook", "缺少 references/award_playbook.md。", severity)
        cards = []
        playbook = ""
    else:
        playbook = playbook_path.read_text(encoding="utf-8", errors="ignore")
        cards = _method_cards(playbook)

    for problem_type in REQUIRED_PROBLEM_TYPES:
        found = f"### {problem_type}" in playbook
        checks.append({"name": f"problem_type_{problem_type}", "passed": found})
        if not found:
            _add_issue(issues, "missing_problem_type_section", f"award_playbook.md 缺少题型章节：{problem_type}。", problem_type=problem_type)

    source_names = _source_names(registry if isinstance(registry, dict) else {})
    for idx, card in enumerate(cards, start=1):
        missing_labels = [label for label in REQUIRED_CARD_LABELS if not _label_present(card, label)]
        if missing_labels:
            code = "unsourced_method_card" if "来源链接" in missing_labels else "incomplete_method_card"
            _add_issue(issues, code, "方法卡缺少可追溯字段。", card_index=idx, missing=missing_labels)
        link_match = re.search(r"- 来源链接[：:]\s*(.+)", card)
        if link_match and not re.search(r"https?://", link_match.group(1)):
            _add_issue(issues, "unsourced_method_card", "方法卡来源链接不是 URL。", card_index=idx)
        if not _source_known(card, source_names):
            _add_issue(issues, "unknown_method_card_source", "方法卡来源比赛未登记在 competition_sources.json。", "warning", card_index=idx)

    checks.append({"name": "method_card_count", "passed": len(cards) >= 40, "count": len(cards)})
    if len(cards) < 40:
        _add_issue(issues, "insufficient_method_cards", "award_playbook.md 方法卡少于 40 张。", count=len(cards))

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "passed": passed,
        "warning": any(issue.get("severity") == "warning" for issue in issues),
        "registry_path": str(registry_path),
        "playbook_path": str(playbook_path),
        "tier_counts": tier_counts,
        "method_cards_checked": len(cards),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查竞赛来源库与 award_playbook 方法卡可追溯性")
    parser.add_argument("--workspace", default=None, help="skill 根目录；保留为兼容旧命令")
    parser.add_argument("--skill-root", default=None, help="skill 根目录")
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        root = args.skill_root or args.workspace
        if root is None:
            parser.error("the following arguments are required: --workspace or --skill-root")
        result = check_source_registry(root, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
