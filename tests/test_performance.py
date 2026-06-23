#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""性能测试"""

import json
import os
import subprocess
import sys
import time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(SKILL_DIR, "tools")
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def run_tool(tool_name, *args):
    """运行指定工具并返回结果和耗时"""
    tool_path = os.path.join(TOOLS_DIR, tool_name)
    start = time.time()
    result = subprocess.run(
        [sys.executable, tool_path] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    elapsed = time.time() - start
    if result.returncode != 0:
        return {"error": result.stderr, "exit_code": result.returncode, "elapsed": elapsed}
    try:
        parsed = json.loads(result.stdout)
        parsed["_elapsed"] = elapsed
        return parsed
    except json.JSONDecodeError:
        return {"raw_output": result.stdout, "exit_code": 0, "_elapsed": elapsed}


def test_performance_data_analyzer_read():
    """测试1：data_analyzer read 性能"""
    result = run_tool("data_analyzer.py", "read", "--file", os.path.join(TEST_DATA, "large.xlsx"))
    assert result["_elapsed"] < 30, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_data_analyzer_stats():
    """测试2：data_analyzer stats 性能"""
    result = run_tool("data_analyzer.py", "stats", "--file", os.path.join(TEST_DATA, "large.xlsx"))
    assert result["_elapsed"] < 30, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_data_analyzer_quality():
    """测试3：data_analyzer quality 性能"""
    result = run_tool("data_analyzer.py", "quality", "--file", os.path.join(TEST_DATA, "large.xlsx"))
    assert result["_elapsed"] < 30, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_brief_validator():
    """测试4：brief_validator 性能"""
    result = run_tool("brief_validator.py", "extract",
                      "--brief", os.path.join(TEST_DATA, "problem_brief.md"))
    assert result["_elapsed"] < 10, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_figure_checker_batch():
    """测试5：figure_checker batch 性能"""
    result = run_tool("figure_checker.py", "batch",
                      "--dir", os.path.join(SKILL_DIR, "tests", "test_figures"), "--pattern", "*.png")
    assert result["_elapsed"] < 10, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_latex_validator():
    """测试6：latex_validator 性能"""
    result = run_tool("latex_validator.py", "validate",
                      "--file", os.path.join(SKILL_DIR, "tests", "test_docs", "mixed.md"))
    assert result["_elapsed"] < 10, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_consistency_checker():
    """测试7：consistency_checker 性能"""
    result = run_tool("consistency_checker.py", "formula",
                      "--doc", os.path.join(SKILL_DIR, "tests", "test_docs", "report.md"),
                      "--code", os.path.join(TEST_DATA, "solution.py"), "--lang", "python")
    assert result["_elapsed"] < 10, f"Too slow: {result['_elapsed']:.1f}s"


def test_performance_code_runner():
    """测试8：code_runner 性能"""
    result = run_tool("code_runner.py", "run",
                      "--file", os.path.join(TEST_DATA, "solution.py"), "--lang", "python", "--timeout", "30")
    assert result["_elapsed"] < 30, f"Too slow: {result['_elapsed']:.1f}s"
