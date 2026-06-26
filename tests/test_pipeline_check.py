#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline_check 总控验证测试"""

import os
import json
import shutil

from tools import pipeline_check


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def copy_workspace(tmp_path):
    for name in ["problem_brief.md", "modeling_report.md", "solution.py"]:
        shutil.copy2(os.path.join(TEST_DATA, name), tmp_path / name)
    shutil.copytree(os.path.join(TEST_DATA, "results"), tmp_path / "results")
    return tmp_path


def test_pipeline_check_passes_python_fixture(tmp_path):
    workspace = copy_workspace(tmp_path)
    result = pipeline_check.run_checks(str(workspace), "python")
    assert result["passed"] is True
    assert result["checks"]["code_runner"]["success"] is True
    assert result["checks"]["figure_checker"]["passed_all"] is True
    assert result["checks"]["brief_output"]["passed"] is True
    assert result["checks"]["evidence_checker"]["passed"] is True
    assert result["checks"]["evidence_checker"]["warning"] is False


def write_validation_summary(workspace):
    payload = {
        "baseline_comparison": {"baseline_name": "naive", "passed": True},
        "oracle_tests": [{"name": "known_case", "passed": True}],
        "solver_cross_checks": [{"name": "alternate_solver", "passed": True}],
        "sensitivity_analysis": {"method": "one_at_a_time", "passed": True},
        "invariants": [{"name": "nonnegative_outputs", "passed": True}],
        "failure_modes": [{"name": "empty_input", "mitigation": "stop_with_error"}],
        "constraint_residuals": {"max_abs": 0.0, "passed": True},
        "optimality_gap": {"value": 0.0, "passed": True},
        "multi_start": {"runs": 3, "best_values": [10, 10, 10], "passed": True},
        "random_seed_stability": {"seeds": [1, 2, 3], "std": 0.0, "passed": True},
        "bootstrap_confidence_interval": {"level": 0.95, "lower": 9.5, "upper": 10.5, "passed": True},
        "perturbation_stability": {"ranking_changed": False, "passed": True},
    }
    (workspace / "results" / "validation_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_quality_artifacts(workspace):
    (workspace / "data.csv").write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    write_validation_summary(workspace)
    artifacts = {
        "data_schema.json": {
            "datasets": [
                {
                    "path": "data.csv",
                    "primary_key": ["id"],
                    "fields": [
                        {"name": "id", "type": "integer", "required": True},
                        {"name": "value", "type": "number", "unit": "件", "required": True, "min": 0},
                    ],
                }
            ]
        },
        "model_spec.json": {
            "variables": [{"name": "x", "type": "decision", "unit": "件", "bounds": [0, 100]}],
            "objective": {"sense": "max", "expression": "10*x"},
            "constraints": [{"name": "capacity", "expression": "x <= 100"}],
            "parameters": [{"name": "profit", "unit": "元/件", "value": 10}],
            "data_fields": [{"name": "value", "unit": "件"}],
            "validation_plan": {"oracle": "small enumeration", "sensitivity": "profit perturbation"},
        },
        "symbol_table.json": {"symbols": [{"symbol": "x", "meaning": "产量", "unit": "件", "code_name": "x"}]},
        "solver_strategy.json": {
            "primary_solver": "enumeration",
            "fallback_solvers": ["brute_force"],
            "timeout_seconds": 60,
            "cross_validation": "enumeration",
        },
        "figure_style.json": {"dpi": 300, "font_size": 10, "colorblind_safe": True, "formats": ["png"]},
        "reproducibility_manifest.json": {
            "python_version": "3.14",
            "dependencies": {"numpy": "2.0"},
            "random_seed": 42,
            "input_hashes": [],
            "output_hashes": [],
        },
    }
    for name, payload in artifacts.items():
        (workspace / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (workspace / "solution_tests.py").write_text(
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    (workspace / "figure_storyboard.md").write_text(
        "# Figure Storyboard\n\n- `figure.png`: 回答最终结果是否稳定，放在模型求解节。\n",
        encoding="utf-8",
    )
    (workspace / "scoring_strategy.md").write_text("每问评分点、数值答案和图表支撑已列出。", encoding="utf-8")
    (workspace / "ablation_study.json").write_text(
        json.dumps({"experiments": [{"name": "remove_capacity", "passed": True}]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (workspace / "decision_insights.md").write_text("关键结论、风险提示和可执行策略。", encoding="utf-8")
    (workspace / "defense_questions.md").write_text("为什么选择该模型？结果是否稳定？", encoding="utf-8")
    (workspace / "modeling_report.md").write_text(
        """
# 摘要
本文给出方法、结果和结论。
## 问题重述
回应所有小问。
## 模型假设
列出假设。
## 符号说明
x 为产量。
## 模型建立
目标函数为 max 10x，约束为 x <= 100。
## 模型求解
见图 1。![图1](results/figure.png)
## 模型验证
包含 baseline、oracle、交叉验证和敏感性分析。
## 敏感性分析
参数扰动后排名稳定。
## 模型评价
说明优缺点。
## 结论
给出可执行建议。
""".strip(),
        encoding="utf-8",
    )


def test_pipeline_check_strict_evidence_fails_when_summary_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    (workspace / "results" / "validation_summary.json").unlink()

    result = pipeline_check.run_checks(str(workspace), "python", evidence_mode="strict")

    assert result["passed"] is False
    assert result["checks"]["evidence_checker"]["passed"] is False


def test_pipeline_check_standard_evidence_warns_when_summary_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    (workspace / "results" / "validation_summary.json").unlink()

    result = pipeline_check.run_checks(str(workspace), "python", evidence_mode="standard")

    assert result["passed"] is True
    assert result["checks"]["evidence_checker"]["passed"] is True
    assert result["checks"]["evidence_checker"]["warning"] is True


def test_pipeline_check_strict_evidence_passes_with_summary(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_validation_summary(workspace)

    result = pipeline_check.run_checks(str(workspace), "python", evidence_mode="strict")

    assert result["passed"] is True
    assert result["checks"]["evidence_checker"]["passed"] is True


def test_pipeline_check_standard_quality_warns_without_1_2_artifacts(tmp_path):
    workspace = copy_workspace(tmp_path)

    result = pipeline_check.run_checks(str(workspace), "python", quality_mode="standard")

    assert result["passed"] is True
    assert result["checks"]["schema_checker"]["warning"] is True
    assert result["checks"]["model_spec_checker"]["warning"] is True
    assert result["checks"]["figure_auditor"]["passed"] is True


def test_pipeline_check_excellence_quality_fails_without_1_2_artifacts(tmp_path):
    workspace = copy_workspace(tmp_path)

    result = pipeline_check.run_checks(str(workspace), "python", quality_mode="excellence")

    assert result["passed"] is False
    assert result["checks"]["schema_checker"]["passed"] is False
    assert result["checks"]["model_spec_checker"]["passed"] is False


def test_pipeline_check_excellence_quality_passes_with_full_artifacts(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is True
    for name in [
        "schema_checker",
        "model_spec_checker",
        "unit_checker",
        "robustness_checker",
        "figure_auditor",
        "report_auditor",
        "manifest_checker",
    ]:
        assert result["checks"][name]["passed"] is True


def test_pipeline_check_fails_when_results_are_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    shutil.rmtree(workspace / "results")
    result = pipeline_check.run_checks(str(workspace), "python")
    assert result["passed"] is False
    assert result["checks"]["required_files"]["passed"] is False
    assert "results" in "\n".join(result["checks"]["required_files"]["missing"])
