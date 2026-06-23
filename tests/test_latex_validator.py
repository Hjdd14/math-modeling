#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_validator 工具测试"""

import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "latex_validator.py")
TEST_DOCS = os.path.join(SKILL_DIR, "tests", "test_docs")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_valid_latex():
    """测试1：正确公式"""
    result = run_tool("validate", "--file", os.path.join(TEST_DOCS, "valid_latex.md"))
    assert result["invalid"] == 0
    assert result["score"] == 100


def test_invalid_latex():
    """测试2：错误公式"""
    result = run_tool("validate", "--file", os.path.join(TEST_DOCS, "invalid_latex.md"))
    assert result["invalid"] > 0
    assert any(not d["valid"] for d in result["details"])


def test_mixed_content():
    """测试3：混合内容"""
    result = run_tool("validate", "--file", os.path.join(TEST_DOCS, "mixed.md"))
    assert result["total_formulas"] > 0


def test_inline_formula():
    """测试4：行内公式"""
    result = run_tool("extract", "--file", os.path.join(TEST_DOCS, "inline.md"))
    assert any(f["type"] == "inline" for f in result["formulas"])


def test_display_formula():
    """测试5：行间公式"""
    result = run_tool("extract", "--file", os.path.join(TEST_DOCS, "display.md"))
    assert any(f["type"] == "display" for f in result["formulas"])


def test_score_range():
    """测试6：评分范围"""
    result = run_tool("validate", "--file", os.path.join(TEST_DOCS, "mixed.md"))
    assert 0 <= result["score"] <= 100


def test_unclosed_begin_environment_is_invalid(tmp_path):
    """测试：未闭合的 LaTeX 环境必须判为无效"""
    doc = tmp_path / "unclosed_env.md"
    doc.write_text("$$\\begin{cases} x > 0$$\n", encoding="utf-8")

    result = run_tool("validate", "--file", str(doc))
    assert result["invalid"] == 1
    assert any("环境" in issue or "begin" in issue for issue in result["details"][0]["issues"])


def test_operatorname_argmin_is_valid(tmp_path):
    """测试：常见合法命令 \\operatorname 与 \\argmin 不应误报"""
    doc = tmp_path / "operatorname.md"
    doc.write_text("$$x^* = \\operatorname{argmin}_{x} f(x) + \\argmax_{y} g(y)$$\n", encoding="utf-8")

    result = run_tool("validate", "--file", str(doc))
    assert result["invalid"] == 0
