#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""consistency_checker 工具测试"""

import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "consistency_checker.py")
TEST_DOCS = os.path.join(SKILL_DIR, "tests", "test_docs")
TEST_CODE = os.path.join(SKILL_DIR, "tests", "test_code")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_consistent_formula():
    """测试1：公式一致"""
    result = run_tool("formula", "--doc", os.path.join(TEST_DOCS, "report.md"),
                      "--code", os.path.join(SKILL_DIR, "tests", "test_data", "solution.py"),
                      "--lang", "python")
    assert "consistency_score" in result
    assert result["consistency_score"] >= 0


def test_inconsistent_formula():
    """测试2：公式不一致"""
    result = run_tool("formula", "--doc", os.path.join(TEST_DOCS, "report_modified.md"),
                      "--code", os.path.join(SKILL_DIR, "tests", "test_data", "solution.py"),
                      "--lang", "python")
    assert "consistency_score" in result
    assert result["mismatches"]
    assert any(m["type"] in {"doc_only_symbol", "code_only_symbol", "numeric_constant_mismatch"} for m in result["mismatches"])
    assert result["passed"] is False


def test_variable_check():
    """测试3：变量名检查"""
    result = run_tool("variable", "--doc", os.path.join(TEST_DOCS, "report.md"),
                      "--code", os.path.join(SKILL_DIR, "tests", "test_data", "solution.py"),
                      "--lang", "python")
    assert "common" in result
    assert "only_in_doc" in result
    assert "only_in_code" in result


def test_score_range():
    """测试4：评分范围"""
    result = run_tool("formula", "--doc", os.path.join(TEST_DOCS, "report.md"),
                      "--code", os.path.join(SKILL_DIR, "tests", "test_data", "solution.py"),
                      "--lang", "python")
    assert 0 <= result["consistency_score"] <= 100


def test_missing_doc():
    """测试5：缺失文档"""
    result = subprocess.run(
        [sys.executable, TOOL, "formula", "--doc", "nonexistent.md",
         "--code", os.path.join(SKILL_DIR, "tests", "test_data", "solution.py"), "--lang", "python"],
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode != 0


def test_missing_code():
    """测试6：缺失代码"""
    result = subprocess.run(
        [sys.executable, TOOL, "formula", "--doc", os.path.join(TEST_DOCS, "report.md"),
         "--code", "nonexistent.py", "--lang", "python"],
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode != 0


def test_python_formula_check_ignores_ast_structure_noise(tmp_path):
    """测试7：字典和函数代码不应产生 AST 结构词噪声"""
    doc = tmp_path / "report.md"
    code = tmp_path / "solution.py"
    doc.write_text(
        """
        # Report

        目标函数为
        $$ Z = 120A + 160B + 90C $$
        装配约束为
        $$ 3A + 4B + 2C \\leq 240 $$
        """,
        encoding="utf-8",
    )
    code.write_text(
        """
        PRODUCTS = {
            "A": {"profit": 120, "assembly": 3},
            "B": {"profit": 160, "assembly": 4},
            "C": {"profit": 90, "assembly": 2},
        }

        def objective(A, B, C):
            return 120 * A + 160 * B + 90 * C

        def assembly_used(A, B, C):
            return 3 * A + 4 * B + 2 * C

        def feasible(A, B, C):
            return assembly_used(A, B, C) <= 240
        """,
        encoding="utf-8",
    )

    result = run_tool("formula", "--doc", str(doc), "--code", str(code), "--lang", "python")
    noisy_symbols = {"Dict", "Constant", "Subscript", "Load", "Store", "keyword", "PRODUCTS"}
    reported_code_symbols = {
        mismatch.get("symbol")
        for mismatch in result["mismatches"]
        if mismatch["type"] == "code_only_symbol"
    }

    assert noisy_symbols.isdisjoint(reported_code_symbols)
    assert result["consistency_score"] >= 80
    assert result["passed"] is True


def test_formula_check_does_not_report_long_python_container_names_as_code_only_symbols(tmp_path):
    doc = tmp_path / "report.md"
    code = tmp_path / "solution.py"
    doc.write_text(
        """
        $$ Z = 5A + 7B $$
        $$ 2A + 3B \\leq 20 $$
        """,
        encoding="utf-8",
    )
    code.write_text(
        """
        PRODUCTS = {
            "A": {"profit": 5, "resource": 2},
            "B": {"profit": 7, "resource": 3},
        }
        CAPACITIES = {"resource": 20}

        def objective(A, B):
            quantities = {"A": A, "B": B}
            return sum(PRODUCTS[p]["profit"] * quantities[p] for p in PRODUCTS)

        def feasible(A, B):
            return sum(PRODUCTS[p]["resource"] * {"A": A, "B": B}[p] for p in PRODUCTS) <= CAPACITIES["resource"]
        """,
        encoding="utf-8",
    )

    result = run_tool("formula", "--doc", str(doc), "--code", str(code), "--lang", "python")
    reported_code_symbols = {
        mismatch.get("symbol")
        for mismatch in result["mismatches"]
        if mismatch["type"] == "code_only_symbol"
    }
    assert "PRODUCTS" not in reported_code_symbols
    assert "CAPACITIES" not in reported_code_symbols
    assert result["passed"] is True
