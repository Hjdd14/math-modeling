#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""code_runner 工具测试"""

import json
import os
import subprocess
import sys
import time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "code_runner.py")
TEST_CODE = os.path.join(SKILL_DIR, "tests", "test_code")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_python_hello():
    """测试1：Python正常执行"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "hello.py"), "--lang", "python")
    assert result["success"] is True
    assert "Hello" in result["stdout"]


def test_python_syntax_error():
    """测试2：Python语法错误"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "syntax_error.py"), "--lang", "python")
    assert result["success"] is False
    assert result["exit_code"] != 0
    assert result["stderr"] != ""


def test_timeout():
    """测试3：超时处理"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "infinite_loop.py"),
                      "--lang", "python", "--timeout", "3")
    assert result["success"] is False


def test_generated_files():
    """测试4：生成文件检测"""
    workdir = os.path.join(SKILL_DIR, "tests", "test_code")
    plot_file = os.path.join(workdir, "test_output.png")
    if os.path.exists(plot_file):
        os.remove(plot_file)
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "generate_plot.py"),
                      "--lang", "python", "--workdir", workdir)
    assert result["success"] is True
    assert any(f.endswith(".png") for f in result["generated_files"])
    # cleanup
    if os.path.exists(plot_file):
        os.remove(plot_file)


def test_changed_files_detects_overwritten_outputs():
    """测试：重复运行覆盖已有图表时 changed_files 必须记录该文件"""
    workdir = os.path.join(SKILL_DIR, "tests", "test_code")
    plot_file = os.path.join(workdir, "test_output.png")
    if os.path.exists(plot_file):
        os.remove(plot_file)

    first = run_tool("run", "--file", os.path.join(TEST_CODE, "generate_plot.py"),
                     "--lang", "python", "--workdir", workdir)
    time.sleep(1.1)
    second = run_tool("run", "--file", os.path.join(TEST_CODE, "generate_plot.py"),
                      "--lang", "python", "--workdir", workdir)

    assert first["success"] is True
    assert second["success"] is True
    assert "test_output.png" in first["generated_files"]
    assert second["generated_files"] == []
    assert "test_output.png" in second["changed_files"]

    if os.path.exists(plot_file):
        os.remove(plot_file)


def test_working_directory():
    """测试5：工作目录"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "check_cwd.py"),
                      "--lang", "python", "--workdir", TEST_CODE)
    assert "test_code" in result["stdout"].replace("\\", "/")


def test_execution_time():
    """测试6：执行时间记录"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "sleep_1s.py"), "--lang", "python")
    assert result["execution_time"] >= 0.9


def test_stdout_capture():
    """测试7：stdout捕获"""
    result = run_tool("run", "--file", os.path.join(TEST_CODE, "multi_print.py"), "--lang", "python")
    assert "line1" in result["stdout"]
    assert "line2" in result["stdout"]


def test_nonexistent_file():
    """测试8：不存在的文件"""
    result = subprocess.run(
        [sys.executable, TOOL, "run", "--file", "nonexistent.py", "--lang", "python"],
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode != 0
