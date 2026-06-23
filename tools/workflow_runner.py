#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性工作流入口：只做文件、状态与验证编排"""

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.pipeline_check import run_checks
    from tools.state_manager import init_state, resume_state
except ImportError:
    from pipeline_check import run_checks
    from state_manager import init_state, resume_state


MEMORY_TEMPLATE = """# 数学建模过程记忆文档

## 基本信息
- 当前阶段：Phase 0
- 编程语言：{language}

## 更新日志
- 初始化工作区，等待并行 Agent 流程产生产物。
"""


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def scaffold_workspace(workspace: str, language: str = "python") -> dict:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(exist_ok=True)
    memory = root / "modeling_memory.md"
    if not memory.exists():
        memory.write_text(MEMORY_TEMPLATE.format(language=language), encoding="utf-8")
    state = init_state(workspace, language)
    return {
        "action": "scaffold",
        "state": state,
        "message": "工作区已初始化；并行 Agent 推理仍需由调用者执行。",
    }


def resume_workspace(workspace: str, language: str = "python") -> dict:
    state = resume_state(workspace, language)
    return {
        "action": "resume",
        "state": state,
        "message": "已根据现有文件恢复状态；workflow_runner 不替代并行 Agent。",
    }


def verify_workspace(workspace: str, language: str = "python") -> dict:
    return run_checks(workspace, language)


def main():
    parser = argparse.ArgumentParser(description="数学建模确定性工作流入口")
    subparsers = parser.add_subparsers(dest="action")

    for action in ["scaffold", "resume", "verify"]:
        sub = subparsers.add_parser(action)
        sub.add_argument("--workspace", required=True)
        sub.add_argument("--language", default="python", choices=["python", "matlab"])

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "scaffold":
            result = scaffold_workspace(args.workspace, args.language)
        elif args.action == "resume":
            result = resume_workspace(args.workspace, args.language)
        else:
            result = verify_workspace(args.workspace, args.language)
        output(result)
        sys.exit(0 if result.get("passed", True) else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
