#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brief_validator 工具测试"""

import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "brief_validator.py")
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def run_tool(*args):
    """运行工具并返回解析后的 JSON"""
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_extract_structure():
    """测试1：提取结构化信息"""
    result = run_tool("extract", "--brief", os.path.join(TEST_DATA, "problem_brief.md"))
    assert len(result["solve_targets"]) > 0
    assert len(result["known_conditions"]) > 0
    assert len(result["constraints"]) > 0


def test_validate_model():
    """测试2：验证建模结果"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    assert "passed" in result
    assert len(result["checks"]) > 0


def test_validate_document_alias_matches_model():
    """测试：document 阶段必须执行与 model 阶段相同的非空检查"""
    model_result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                            "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    document_result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                               "--stage", "document", "--target", os.path.join(TEST_DATA, "model_decision.md"))

    assert len(document_result["checks"]) > 0
    assert document_result["checks"] == model_result["checks"]
    assert document_result["score"] == model_result["score"]
    assert document_result["passed"] == model_result["passed"]


def test_validate_document_alias_does_not_pass_empty_checks(tmp_path):
    """测试：document 阶段不能因空检查列表直接 100 分通过"""
    sparse_doc = tmp_path / "sparse_report.md"
    sparse_doc.write_text("# 空报告\n\n没有覆盖题目目标。\n", encoding="utf-8")

    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "document", "--target", str(sparse_doc))

    assert len(result["checks"]) > 0
    assert result["score"] < 100


def test_validate_code():
    """测试3：验证代码实现"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "code", "--target", os.path.join(TEST_DATA, "solution.py"))
    assert all(check["status"] in ["pass", "fail", "warning"] for check in result["checks"])


def test_validate_output():
    """测试4：验证输出完整性"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "output", "--target", os.path.join(TEST_DATA, "results"))
    assert any("目标" in check["item"] or "求解" in check["item"] for check in result["checks"])


def test_report_generation():
    """测试5：报告生成"""
    files_json = json.dumps({"model": os.path.join(TEST_DATA, "model_decision.md")})
    result = run_tool("report", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--files", files_json)
    assert "checks" in result
    assert "overall_score" in result


def test_missing_brief():
    """测试6：缺失brief文件"""
    result = subprocess.run(
        [sys.executable, TOOL, "extract", "--brief", "nonexistent.md"],
        capture_output=True, text=True, cwd=SKILL_DIR
    )
    assert result.returncode != 0


def test_score_range():
    """测试7：评分范围"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    assert 0 <= result["score"] <= 100


def test_check_details():
    """测试8：检查项详情"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    for check in result["checks"]:
        assert "item" in check
        assert "status" in check
        assert "detail" in check
