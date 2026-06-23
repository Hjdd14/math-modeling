#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码执行与错误捕获工具"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time


def snapshot_files(dir_path: str) -> dict:
    """记录工作目录下一层文件的大小和修改时间"""
    snapshot = {}
    if not os.path.isdir(dir_path):
        return snapshot

    for name in os.listdir(dir_path):
        path = os.path.join(dir_path, name)
        if os.path.isfile(path):
            stat = os.stat(path)
            snapshot[name] = {
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns
            }
    return snapshot


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def run_code(file_path: str, lang: str, timeout: int = 300, workdir: str = None) -> dict:
    """运行代码并捕获输出"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    abs_file = os.path.abspath(file_path)
    if workdir is None:
        workdir = os.path.dirname(abs_file) or "."
    workdir = os.path.abspath(workdir)

    before_snapshot = snapshot_files(workdir)
    before_files = set(before_snapshot)

    if lang == "python":
        cmd = [sys.executable, abs_file]
    elif lang == "matlab":
        script_name = os.path.splitext(os.path.basename(abs_file))[0]
        cmd = ["matlab", "-batch", f"cd('{workdir}'); {script_name}"]
    else:
        raise ValueError(f"不支持的语言: {lang}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"执行超时（超过 {timeout} 秒）"
    except FileNotFoundError as e:
        exit_code = -2
        stdout = ""
        stderr = f"命令未找到: {e}"

    execution_time = round(time.time() - start_time, 3)

    after_snapshot = snapshot_files(workdir)
    after_files = set(after_snapshot)

    new_files = after_files - before_files
    generated_files = [
        f for f in new_files
        if os.path.isfile(os.path.join(workdir, f))
    ]
    changed_files = [
        f for f in sorted(after_files)
        if f not in before_snapshot or after_snapshot[f] != before_snapshot[f]
    ]

    return {
        "exit_code": exit_code,
        "stdout": stdout[-5000:] if len(stdout) > 5000 else stdout,
        "stderr": stderr[-5000:] if len(stderr) > 5000 else stderr,
        "execution_time": execution_time,
        "generated_files": generated_files,
        "changed_files": changed_files,
        "success": exit_code == 0
    }


def main():
    parser = argparse.ArgumentParser(description="代码执行与错误捕获工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_run = subparsers.add_parser("run", help="运行代码")
    p_run.add_argument("--file", required=True, help="代码文件路径")
    p_run.add_argument("--lang", required=True, choices=["python", "matlab"], help="编程语言")
    p_run.add_argument("--timeout", type=int, default=300, help="超时秒数（默认300）")
    p_run.add_argument("--workdir", default=None, help="工作目录（默认为代码所在目录）")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "run":
            result = run_code(args.file, args.lang, args.timeout, args.workdir)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
