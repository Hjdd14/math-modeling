#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure_checker 工具测试"""

import json
import os
import subprocess
import sys

from PIL import Image

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "figure_checker.py")
TEST_FIGURES = os.path.join(SKILL_DIR, "tests", "test_figures")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_normal_figure():
    """测试1：正常图表"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "normal.png"))
    assert result["exists"] is True
    assert result["is_blank"] is False
    assert result["quality_score"] > 50


def test_blank_figure():
    """测试2：空白图表"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "blank.png"))
    assert result["exists"] is True
    assert result["is_blank"] is True
    assert result["quality_score"] < 60


def test_low_dpi():
    """测试3：低分辨率"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "low_dpi.png"))
    assert result["dpi"][0] < 300
    assert any("DPI" in issue or "dpi" in issue.lower() for issue in result["issues"])


def test_batch_check():
    """测试4：批量检查"""
    result = run_tool("batch", "--dir", TEST_FIGURES, "--pattern", "*.png")
    assert result["total"] == 3
    assert result["passed"] + result["failed"] == result["total"]


def test_batch_no_matching_files_fails():
    """测试：批量检查匹配不到图表时不能假装通过"""
    result = run_tool("batch", "--dir", TEST_FIGURES, "--pattern", "no_match_*.png")
    assert result["total"] == 0
    assert result["passed_all"] is False
    assert result["failed"] == 1
    assert result["issues"]


def test_dpi_below_300_warns(tmp_path):
    """测试：低于 300 DPI 的图表必须报警"""
    figure_path = tmp_path / "dpi_200.png"
    img = Image.new("RGB", (400, 300), "white")
    for x in range(50, 350):
        img.putpixel((x, 150), (0, 0, 0))
    img.save(figure_path, dpi=(200, 200))

    result = run_tool("check", "--file", str(figure_path))
    assert result["dpi"][0] < 300
    assert any("DPI" in issue or "dpi" in issue.lower() for issue in result["issues"])


def test_file_size():
    """测试5：文件大小检查"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "normal.png"))
    assert result["file_size"] > 0


def test_dimensions():
    """测试6：尺寸检查"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "normal.png"))
    assert result["width"] > 0
    assert result["height"] > 0


def test_nonexistent_file():
    """测试7：不存在的文件"""
    result = run_tool("check", "--file", "nonexistent.png")
    assert result["exists"] is False


def test_quality_score_range():
    """测试8：质量评分范围"""
    result = run_tool("check", "--file", os.path.join(TEST_FIGURES, "normal.png"))
    assert 0 <= result["quality_score"] <= 100
