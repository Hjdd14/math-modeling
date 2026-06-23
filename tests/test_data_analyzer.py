#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_analyzer 工具测试"""

import json
import os
import subprocess
import sys
import time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "data_analyzer.py")
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_read_normal():
    """测试1：正常Excel文件"""
    result = run_tool("read", "--file", os.path.join(TEST_DATA, "data.xlsx"))
    assert result["file_type"] == "xlsx"
    assert result["sheets"][0]["rows"] == 100
    assert len(result["sheets"][0]["column_names"]) == 5


def test_read_csv():
    """测试2：CSV文件"""
    result = run_tool("read", "--file", os.path.join(TEST_DATA, "data.csv"))
    assert result["file_type"] == "csv"
    assert result["sheets"][0]["rows"] == 100


def test_stats_with_missing():
    """测试3：含缺失值的统计"""
    result = run_tool("stats", "--file", os.path.join(TEST_DATA, "data_missing.xlsx"))
    temp_col = next(c for c in result["columns"] if c["name"] == "温度")
    assert temp_col["missing"] == 2


def test_stats_outliers():
    """测试4：异常值检测"""
    result = run_tool("stats", "--file", os.path.join(TEST_DATA, "data_outliers.xlsx"))
    temp_col = next(c for c in result["columns"] if c["name"] == "温度")
    assert len(temp_col["outliers"]) > 0


def test_quality_score():
    """测试5：质量评分"""
    result = run_tool("quality", "--file", os.path.join(TEST_DATA, "data.xlsx"))
    assert 0 <= result["quality_score"] <= 100


def test_empty_file():
    """测试6：空文件处理"""
    result = run_tool("read", "--file", os.path.join(TEST_DATA, "empty.xlsx"))
    assert result["sheets"][0]["rows"] == 0


def test_large_file():
    """测试7：大文件性能"""
    start = time.time()
    result = run_tool("read", "--file", os.path.join(TEST_DATA, "large.xlsx"))
    elapsed = time.time() - start
    assert elapsed < 30, f"Too slow: {elapsed:.1f}s"
    assert result["sheets"][0]["rows"] == 10000


def test_invalid_file():
    """测试8：无效文件路径"""
    result = subprocess.run(
        [sys.executable, TOOL, "read", "--file", "nonexistent.xlsx"],
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode != 0


def test_specific_sheet():
    """测试9：指定工作表"""
    result = run_tool("stats", "--file", os.path.join(TEST_DATA, "multi_sheet.xlsx"), "--sheet", "Sheet2")
    assert result["columns"][0]["name"] is not None


def test_json_output_format():
    """测试10：输出格式为有效JSON"""
    result = run_tool("read", "--file", os.path.join(TEST_DATA, "data.xlsx"))
    assert isinstance(result, dict)
    assert "file_name" in result
    assert "sheets" in result
