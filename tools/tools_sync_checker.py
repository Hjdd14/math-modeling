#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双仓库工具漂移检查：比对主仓库与分支仓库的 `tools/*.py` 是否已同步。

背景
----
`math-modeling`（主仓库）与 `math-modeling-per-question`（按小问分别交付的变体）
各自维护一份 `tools/`。两边没有自动同步测试，主仓库新增或修改工具后，分支仓库
可能悄悄停在旧版本，表现为"同一个 skill 在两个仓库里行为不同"且无人发现。

判定口径
--------
按文件名取并集，逐个算 sha256，分五类：

- `identical`：两边哈希相同。
- `differs_expected`：内容不同，但该文件**本来就该不同**（在预期差异白名单里）。
  典型是 `doctor.py` / `pipeline_check.py` / `workflow_runner.py`：分支有自己的
  按小问交付逻辑，不能与主仓库逐字一致。双闸门改造后 `design_board*.py` 三件也
  属于这一类：主仓库是整题一块 B 板，分支是每问一块。
- `differs_unexpected`：不在白名单却内容不同 —— **这就是漂移**。
- `primary_only`：只存在于主仓库。
- `branch_only`：只存在于分支仓库（如 `question_queue.py`，分支独有能力）。

`passed` 判据：`differs_unexpected` 为空，且 `primary_only` 里的文件都在"设计闸门
新增文件"允许集合内（这些是主仓库先行、分支尚未同步时可接受的新增工具）。
`branch_only` 只作信息展示，不影响判定。

用法
----
    python tools/tools_sync_checker.py --primary . --branch ../math-modeling-per-question
    python tools/tools_sync_checker.py --primary . --branch ../math-modeling-per-question --mode strict

默认模式：发现漂移只在 stderr 警告，退出码 0，不阻断流程。
`--mode strict`：`passed` 为 False 时退出码 1，可挂到 CI 上当同步闸门。

零第三方依赖，只用标准库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# 预期差异白名单：这些文件在两边"理应不同"。
# `pipeline_check.py` 在两边都改了但改法不同（分支有 --stage question 等），
# 因此它出现在这里；`tools_sync_checker.py` 目前只有主仓库有，但为了以后
# 两边都放一份时不会误判成漂移，一并列入。
DEFAULT_EXPECTED_DIFFERENCES = frozenset(
    {
        "doctor.py",
        "pipeline_check.py",
        "workflow_runner.py",
        "tools_sync_checker.py",
        # 分小问分支的专属适配（见 docs/DESIGN_GATE_PLAN.md §21.2 / §21.3）：
        # - design_board_checker.py：时间线要扫 questions/qN/，交叉校验要按题读
        #   questions/qN/model_selection_audit.json，因此与主仓库**本就该不同**；
        # - migrate_workspace.py：有 question_queue.json 时要按题建板（每题一个 entry）。
        # 把这两个列进白名单是"声明差异"，不是"允许漂移"——一旦某天它们的差异变了，
        # 仍需人工确认是不是预期内的。
        "design_board_checker.py",
        "migrate_workspace.py",
        # 双闸门（A 框架闸门 / B 方案择定闸门）在分支是"每问一块 B 板"，主仓库是
        # "整题一块 B 板"，三件渲染/路由文件因此**本就该不同**（计划 v2 §4.1/4.1b）：
        # - design_board.py：路径常量按 gate 计算、--gate/--board 路由、B 板 ingest/confirm；
        # - design_board_html.py：B 板渲染（分数、pros/cons、多组数据对比表、确认码）；
        # - design_board_xlsx.py：选择表模板按 gate 输出（design_choices_gate_b.xlsx）。
        # 列进白名单是"声明差异"，不是"允许漂移"：差异一旦变化仍需人工确认。
        "design_board.py",
        "design_board_html.py",
        "design_board_xlsx.py",
    }
)

# 只存在于主仓库也可接受的文件：设计闸门（Phase 0.5）新增工具。
# 这些是主仓库先落地、分支尚未同步的工具；它们出现在 primary_only 里不算漂移。
DESIGN_GATE_NEW_FILES = frozenset(
    {
        "design_board.py",
        "design_board_checker.py",
        "design_board_html.py",
        "design_board_xlsx.py",
        "tools_sync_checker.py",
        # 双闸门新增工具（主仓库先行、分支随后同步）：只存在于主仓库时可接受。
        "model_advice_builder.py",
        "perspective_trial_runner.py",
    }
)

CATEGORY_FIELDS = (
    "identical",
    "differs_expected",
    "differs_unexpected",
    "primary_only",
    "branch_only",
)


def sha256_of(path: Path) -> str:
    """流式计算文件 sha256，避免大文件一次性读入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_hashes(tools_dir: Path) -> dict[str, str]:
    """收集目录下 `*.py` 的 {文件名: sha256}；只取直接子文件，不递归。"""
    hashes: dict[str, str] = {}
    for entry in sorted(tools_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".py":
            hashes[entry.name] = sha256_of(entry)
    return hashes


def build_result(
    primary: str | Path,
    branch: str | Path,
    mode: str = "default",
    expected: frozenset[str] | set[str] | None = None,
    allowed_primary_only: frozenset[str] | set[str] | None = None,
) -> dict:
    """比对两个仓库的 `tools/*.py` 并返回结果字典（不打印、不退出）。

    `expected` 与 `allowed_primary_only` 允许上游覆盖默认白名单，便于测试或
    在别的仓库对上复用本工具。
    """
    expected_set = DEFAULT_EXPECTED_DIFFERENCES if expected is None else set(expected)
    allowed_set = DESIGN_GATE_NEW_FILES if allowed_primary_only is None else set(allowed_primary_only)

    primary_root = Path(primary).expanduser().resolve()
    branch_root = Path(branch).expanduser().resolve()
    primary_tools = primary_root / "tools"
    branch_tools = branch_root / "tools"

    for label, path in (("primary", primary_tools), ("branch", branch_tools)):
        if not path.is_dir():
            raise FileNotFoundError(f"{label} 的 tools 目录不存在：{path}")

    primary_hashes = collect_hashes(primary_tools)
    branch_hashes = collect_hashes(branch_tools)

    union = sorted(set(primary_hashes) | set(branch_hashes))
    categories: dict[str, list[str]] = {field: [] for field in CATEGORY_FIELDS}

    for name in union:
        in_primary = name in primary_hashes
        in_branch = name in branch_hashes
        if in_primary and in_branch:
            if primary_hashes[name] == branch_hashes[name]:
                categories["identical"].append(name)
            elif name in expected_set:
                categories["differs_expected"].append(name)
            else:
                categories["differs_unexpected"].append(name)
        elif in_primary:
            categories["primary_only"].append(name)
        else:
            categories["branch_only"].append(name)

    unexpected_primary_only = [
        name for name in categories["primary_only"] if name not in allowed_set
    ]
    passed = not categories["differs_unexpected"] and not unexpected_primary_only

    counts = {"union": len(union)}
    for field in CATEGORY_FIELDS:
        counts[field] = len(categories[field])

    return {
        "primary": str(primary_root),
        "branch": str(branch_root),
        "mode": mode,
        "passed": passed,
        "counts": counts,
        "identical": categories["identical"],
        "differs_expected": categories["differs_expected"],
        "differs_unexpected": categories["differs_unexpected"],
        "primary_only": categories["primary_only"],
        "branch_only": categories["branch_only"],
        # 便于排查的附加字段：被判为漂移时，两边的哈希对不上在哪里。
        "unexpected_primary_only": unexpected_primary_only,
        "expected_differences": sorted(expected_set),
        "allowed_primary_only": sorted(allowed_set),
    }


def exit_code_for(result: dict, mode: str) -> int:
    """默认模式永远 0（只警告）；strict 模式在未通过时返回 1。"""
    if mode == "strict" and not result.get("passed"):
        return 1
    return 0


def emit_warnings(result: dict) -> None:
    """把漂移信息写到 stderr，保证 stdout 只有可解析的 JSON。"""
    drifted = result["differs_unexpected"]
    unexpected_primary = result.get("unexpected_primary_only") or []
    if drifted:
        print(
            "[WARN] 检测到 %d 个预期外的工具差异（漂移）：%s"
            % (len(drifted), ", ".join(drifted)),
            file=sys.stderr,
        )
    if unexpected_primary:
        print(
            "[WARN] 以下工具只存在于主仓库且不在设计闸门允许集合内：%s"
            % ", ".join(unexpected_primary),
            file=sys.stderr,
        )
    branch_only = result["branch_only"]
    if branch_only:
        print(
            "[INFO] 分支独有（不影响判定）：%s" % ", ".join(branch_only),
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="比对主仓库与分支仓库的 tools/*.py，发现无人察觉的工具漂移。",
    )
    parser.add_argument(
        "--primary",
        default=".",
        help="主仓库根目录（默认当前目录 .）。",
    )
    parser.add_argument(
        "--branch",
        required=True,
        help="分支仓库根目录，例如 ../math-modeling-per-question。",
    )
    parser.add_argument(
        "--mode",
        default="default",
        choices=["default", "strict"],
        help="default：发现漂移只警告并退出 0；strict：未通过时退出 1。",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="可选：把结果 JSON 同时写入该路径（UTF-8，覆盖写）。",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="可选：不往 stderr 打印警告，仅输出 JSON。",
    )
    args = parser.parse_args(argv)

    try:
        result = build_result(args.primary, args.branch, mode=args.mode)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    print(payload)

    if args.json_out:
        out_path = Path(args.json_out).expanduser()
        if out_path.parent and str(out_path.parent) != "":
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if not args.quiet:
        emit_warnings(result)

    return exit_code_for(result, args.mode)


if __name__ == "__main__":
    sys.exit(main())
