#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选 Claude CLI eval runner，用于人工评审前生成样例输出"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PARALLEL_MARKERS = [
    "五视角建模 Agent",
    "并行生成方案",
    "并行批评",
    "并行修正",
    "文档 Agent 与代码 Agent 并行",
    "语法审查 Agent",
    "逻辑审查 Agent",
    "输出审查 Agent",
]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def load_evals(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["evals"]


def check_parallel_markers(text: str) -> dict:
    found = [marker for marker in PARALLEL_MARKERS if marker in text]
    return {
        "found": found,
        "missing": [marker for marker in PARALLEL_MARKERS if marker not in found],
        "passed": len(found) == len(PARALLEL_MARKERS),
    }


def run_eval(prompt: str, skill_path: str, output_dir: Path, dry_run: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        text = "\n".join(PARALLEL_MARKERS)
    else:
        claude = shutil.which("claude")
        if not claude:
            raise RuntimeError("未找到 claude CLI")
        full_prompt = f"Skill path: {skill_path}\n\nTask:\n{prompt}"
        completed = subprocess.run(
            [claude, "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        text = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
        if completed.returncode != 0:
            raise RuntimeError(f"claude CLI 失败: {completed.returncode}")

    (output_dir / "output.txt").write_text(text, encoding="utf-8")
    markers = check_parallel_markers(text)
    return {
        "output": str(output_dir / "output.txt"),
        "parallel_markers": markers,
    }


def main():
    parser = argparse.ArgumentParser(description="Claude CLI eval runner")
    parser.add_argument("--evals", required=True)
    parser.add_argument("--skill-path", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        evals = load_evals(args.evals)
        results = []
        for item in evals:
            out_dir = Path(args.workspace) / f"eval-{item['id']}"
            results.append({
                "id": item["id"],
                "result": run_eval(item["prompt"], args.skill_path, out_dir, args.dry_run),
            })
        output({"results": results})
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
