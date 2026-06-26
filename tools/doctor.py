#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地环境与仓库体验体检工具"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "references/workflow.md",
    "references/tools.md",
    "tools/pipeline_check.py",
    "tools/workflow_runner.py",
    "tools/state_manager.py",
    "examples/quickstart/problem.md",
    "examples/quickstart/production_data.csv",
]

RUNTIME_MODULES = {
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "numpy": "numpy",
    "Pillow": "PIL",
    "matplotlib": "matplotlib",
    "scipy": "scipy",
    "pypdf": "pypdf",
    "python-docx": "docx",
}

OPTIONAL_TOOLS = ["node", "matlab", "claude"]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def make_check(name: str, passed: bool, severity: str, detail: str, **extra) -> dict:
    check = {
        "name": name,
        "passed": passed,
        "severity": severity,
        "detail": detail,
    }
    check.update(extra)
    return check


def check_required_files(root: Path) -> dict:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return make_check(
        "required_files",
        not missing,
        "error",
        "必备文件齐全" if not missing else "缺少必备文件",
        missing=missing,
    )


def check_runtime_dependencies() -> dict:
    missing = [
        package
        for package, module_name in RUNTIME_MODULES.items()
        if importlib.util.find_spec(module_name) is None
    ]
    return make_check(
        "runtime_dependencies",
        not missing,
        "error",
        "运行依赖可导入" if not missing else "存在未安装的运行依赖",
        missing=missing,
    )


def check_optional_tools() -> dict:
    found = {tool: shutil.which(tool) is not None for tool in OPTIONAL_TOOLS}
    return make_check(
        "optional_tools",
        True,
        "info",
        "可选外部工具探测完成",
        tools=found,
    )


def check_git_repository(root: Path) -> dict:
    git_dir = root / ".git"
    if not git_dir.exists():
        return make_check("git_repository", False, "warning", "当前目录不是 Git 仓库")
    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", "status", "--short"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        clean = result.returncode == 0 and not result.stdout.strip()
        return make_check(
            "git_repository",
            result.returncode == 0,
            "warning",
            "Git 仓库可读取" if result.returncode == 0 else "Git 仓库状态读取失败",
            clean=clean,
            status=result.stdout.strip().splitlines(),
            stderr=result.stderr.strip(),
        )
    except Exception as exc:
        return make_check("git_repository", False, "warning", f"Git 检查失败: {exc}")


def check_quickstart_example(root: Path) -> dict:
    problem = root / "examples" / "quickstart" / "problem.md"
    data = root / "examples" / "quickstart" / "production_data.csv"
    passed = problem.exists() and data.exists()
    return make_check(
        "quickstart_example",
        passed,
        "warning",
        "公开 quickstart 示例可用" if passed else "缺少公开 quickstart 示例",
    )


def summarize(checks: list[dict]) -> dict:
    failed = [check for check in checks if not check["passed"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["passed"] and check["severity"] == "warning"]
    return {
        "total": len(checks),
        "failed": len(failed),
        "warnings": len(warnings),
        "passed": len(checks) - len(failed) - len(warnings),
    }


def run_doctor(workspace: str = ".") -> dict:
    root = Path(workspace).resolve()
    checks = [
        check_required_files(root),
        check_runtime_dependencies(),
        check_optional_tools(),
        check_git_repository(root),
        check_quickstart_example(root),
    ]
    return {
        "workspace": str(root),
        "python": sys.version.split()[0],
        "checks": checks,
        "summary": summarize(checks),
    }


def main():
    parser = argparse.ArgumentParser(description="检查 math-modeling 本地环境、依赖和仓库基础")
    parser.add_argument("--workspace", default=".", help="skill 仓库或工作目录")
    args = parser.parse_args()

    result = run_doctor(args.workspace)
    output(result)
    sys.exit(0 if result["summary"]["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
