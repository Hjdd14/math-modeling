#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端工作流测试"""

import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(SKILL_DIR, "tools")
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def run_tool(tool_name, *args):
    """运行指定工具并返回结果"""
    tool_path = os.path.join(TOOLS_DIR, tool_name)
    result = subprocess.run(
        [sys.executable, tool_path] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    if result.returncode != 0:
        return {"error": result.stderr, "exit_code": result.returncode}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw_output": result.stdout, "exit_code": 0}


def test_e2e_data_analysis():
    """测试1：完整数据分析流程"""
    data_file = os.path.join(TEST_DATA, "data.xlsx")

    read_result = run_tool("data_analyzer.py", "read", "--file", data_file)
    assert "sheets" in read_result
    assert read_result["sheets"][0]["rows"] == 100

    stats_result = run_tool("data_analyzer.py", "stats", "--file", data_file)
    assert "columns" in stats_result
    assert len(stats_result["columns"]) == 5

    quality_result = run_tool("data_analyzer.py", "quality", "--file", data_file)
    assert "quality_score" in quality_result
    assert 0 <= quality_result["quality_score"] <= 100


def test_e2e_validation_flow():
    """测试2：完整验证流程"""
    brief_file = os.path.join(TEST_DATA, "problem_brief.md")
    model_file = os.path.join(TEST_DATA, "model_decision.md")
    code_file = os.path.join(TEST_DATA, "solution.py")

    extract_result = run_tool("brief_validator.py", "extract", "--brief", brief_file)
    assert "solve_targets" in extract_result
    assert len(extract_result["solve_targets"]) > 0

    model_check = run_tool("brief_validator.py", "validate",
                           "--brief", brief_file, "--stage", "model", "--target", model_file)
    assert "passed" in model_check
    assert "checks" in model_check

    code_check = run_tool("brief_validator.py", "validate",
                          "--brief", brief_file, "--stage", "code", "--target", code_file)
    assert "passed" in code_check

    report_result = run_tool("brief_validator.py", "report",
                             "--brief", brief_file,
                             "--files", json.dumps({"model": model_file, "code": code_file}))
    assert "overall_score" in report_result


def test_e2e_code_execution():
    """测试3：完整代码执行流程"""
    code_file = os.path.join(TEST_DATA, "solution.py")

    run_result = run_tool("code_runner.py", "run", "--file", code_file, "--lang", "python", "--timeout", "30")
    assert "success" in run_result
    assert "execution_time" in run_result


def test_e2e_figure_check():
    """测试4：完整图表检查流程"""
    figures_dir = os.path.join(SKILL_DIR, "tests", "test_figures")

    batch_result = run_tool("figure_checker.py", "batch", "--dir", figures_dir, "--pattern", "*.png")
    assert "total" in batch_result
    assert batch_result["total"] == 3
    assert "passed" in batch_result
    assert "failed" in batch_result


def test_e2e_latex_validation():
    """测试5：完整LaTeX验证流程"""
    valid_doc = os.path.join(SKILL_DIR, "tests", "test_docs", "valid_latex.md")
    invalid_doc = os.path.join(SKILL_DIR, "tests", "test_docs", "invalid_latex.md")

    valid_result = run_tool("latex_validator.py", "validate", "--file", valid_doc)
    assert valid_result["invalid"] == 0

    invalid_result = run_tool("latex_validator.py", "validate", "--file", invalid_doc)
    assert invalid_result["invalid"] > 0


def test_e2e_consistency_check():
    """测试6：完整一致性检查流程"""
    doc_file = os.path.join(SKILL_DIR, "tests", "test_docs", "report.md")
    code_file = os.path.join(TEST_DATA, "solution.py")

    formula_result = run_tool("consistency_checker.py", "formula",
                              "--doc", doc_file, "--code", code_file, "--lang", "python")
    assert "consistency_score" in formula_result

    var_result = run_tool("consistency_checker.py", "variable",
                          "--doc", doc_file, "--code", code_file, "--lang", "python")
    assert "common" in var_result
    assert "only_in_doc" in var_result


def test_e2e_full_pipeline():
    """测试7：完整全流程管线"""
    data_file = os.path.join(TEST_DATA, "data.xlsx")
    brief_file = os.path.join(TEST_DATA, "problem_brief.md")
    model_file = os.path.join(TEST_DATA, "model_decision.md")
    valid_latex_file = os.path.join(SKILL_DIR, "tests", "test_docs", "valid_latex.md")
    consistency_doc = os.path.join(SKILL_DIR, "tests", "test_docs", "report.md")
    code_file = os.path.join(TEST_DATA, "solution.py")

    read_result = run_tool("data_analyzer.py", "read", "--file", data_file)
    assert "sheets" in read_result

    quality_result = run_tool("data_analyzer.py", "quality", "--file", data_file)
    assert "quality_score" in quality_result

    model_check = run_tool("brief_validator.py", "validate",
                           "--brief", brief_file, "--stage", "model", "--target", model_file)
    assert "checks" in model_check

    code_check = run_tool("brief_validator.py", "validate",
                          "--brief", brief_file, "--stage", "code", "--target", code_file)
    assert "checks" in code_check

    latex_check = run_tool("latex_validator.py", "validate", "--file", valid_latex_file)
    assert "score" in latex_check

    consistency = run_tool("consistency_checker.py", "formula",
                           "--doc", consistency_doc, "--code", code_file, "--lang", "python")
    assert "consistency_score" in consistency

    print("Full pipeline completed successfully")
