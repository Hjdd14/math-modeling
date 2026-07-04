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
    for name in ["problem_brief.md", "model_decision.md", "writer_prompt.md", "solution.py"]:
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
            "os": {"name": "Windows", "version": "11"},
            "python_version": "3.14",
            "matlab_version": None,
            "dependencies": {"numpy": "2.0"},
            "random_seed": 42,
            "solvers": [{"name": "enumeration", "version": "builtin"}],
            "random_libraries": [{"name": "numpy.random", "seed": 42}],
            "execution": {"seconds": 0.1},
            "input_hashes": [],
            "output_hashes": [],
        },
        "model_selection_audit.json": {
            "candidates": [
                {"name": "integer_programming", "score": 0.92, "evidence": ["oracle_tests", "gap=0"]},
                {"name": "greedy", "score": 0.6, "rejection_reason": "cannot certify optimality", "evidence": ["baseline"]},
            ],
            "final_selection": {"name": "integer_programming", "score": 0.92, "evidence": ["gap=0", "residual=0"]},
        },
        "optimization_certificate.json": {
            "feasibility_residual": {"max_abs": 0.0, "tolerance": 1e-6},
            "bounds": {"lower": 12000, "upper": 12000},
            "optimality_gap": {"value": 0.0, "tolerance": 1e-4},
            "enumeration_oracle": {"method": "small enumeration", "best_value": 12000},
        },
        "uncertainty_budget.json": {
            "data": {"impact": "low", "mitigation": "schema checks"},
            "parameter": {"impact": "medium", "sensitivity": "profit perturbation"},
            "model": {"impact": "low", "evidence": "oracle"},
            "random": {"impact": "low", "mitigation": "three seeds"},
        },
        "validation_profile.json": {
            "profile": "optimization",
            "evidence": {
                "baseline": {"passed": True},
                "oracle": {"passed": True},
                "gap": {"value": 0.0},
                "residuals": {"max_abs": 0.0},
                "sensitivity": {"passed": True},
            },
        },
        "data_validation.json": {
            "task_type": "optimization",
            "target": "profit",
            "features": ["capacity", "labor", "unit_profit"],
            "split": {"type": "not_applicable"},
            "preprocessing": [{"name": "normalize", "fit_on": "train"}],
        },
        "statistical_validation.json": {
            "holdout": {"method": "oracle", "passed": True},
            "metrics": {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0},
            "residuals": {"checked": True},
            "intervals": {"level": 0.95},
            "robustness": {"passed": True},
            "overfitting_risk": {"level": "low"},
        },
        "model_selection_audit.json": {
            "candidates": [
                {"name": "整数规划", "score": 0.91, "rejection_reason": "", "evidence": ["oracle"]},
                {"name": "贪心启发式", "score": 0.72, "rejection_reason": "不能保证全局最优", "evidence": ["baseline"]},
            ],
            "final_selection": {"name": "整数规划", "score": 0.91, "evidence": ["gap=0", "residual=0"]},
        },
        "optimization_certificate.json": {
            "feasibility_residual": {"max_abs": 0.0, "tolerance": 1e-6},
            "bounds": {"lower": 10, "upper": 10},
            "optimality_gap": {"value": 0.0, "tolerance": 1e-4},
            "enumeration_oracle": {"passed": True, "case": "small_grid"},
        },
        "uncertainty_budget.json": {
            "data": {"impact": "low", "mitigation": "schema checks"},
            "parameter": {"impact": "medium", "sensitivity": "profit +/- 5%"},
            "model": {"impact": "medium", "evidence": "baseline comparison"},
            "random": {"impact": "low", "evidence": "three seeds"},
        },
        "validation_profile.json": {
            "profile": "optimization",
            "evidence": {
                "baseline": {"passed": True},
                "oracle": {"passed": True},
                "gap": {"value": 0.0, "passed": True},
                "residuals": {"max_abs": 0.0, "passed": True},
                "sensitivity": {"passed": True},
            },
        },
        "data_validation.json": {
            "task_type": "optimization",
            "target": "profit",
            "features": ["capacity", "cost"],
            "split": {"type": "holdout"},
            "preprocessing": [{"name": "scale", "fit_on": "train"}],
        },
        "statistical_validation.json": {
            "holdout": {"method": "known_case", "passed": True},
            "metrics": {"MAE": 0.0, "RMSE": 0.0},
            "residuals": {"checked": True, "passed": True},
            "intervals": {"level": 0.95, "passed": True},
            "robustness": {"passed": True},
            "overfitting_risk": {"level": "low", "passed": True},
        },
        "source_registry.json": {
            "sources": [
                {
                    "name": "COMAP",
                    "url": "https://www.contest.comap.com/undergraduate/contests/mcm/previous-contests.php",
                    "years": [2025, 2026],
                    "tier": "official",
                    "checked_at": "2026-06-28",
                }
            ]
        },
    }
    for name, payload in artifacts.items():
        (workspace / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (workspace / "solution_tests.py").write_text(
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    (workspace / "figure_storyboard.md").write_text(
        "# Figure Storyboard\n\n- file: figure.png\n  claim: 最优方案稳定优于 baseline\n  source_data: results/output.csv\n  x_unit: 产品类别\n  y_unit: 件\n  supports_question: Q1-Q2\n",
        encoding="utf-8",
    )
    (workspace / "ambiguity_register.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "A1",
                        "severity": "low",
                        "source": "problem_brief.md",
                        "issue": "产品产量是否必须为整数",
                        "impact": "影响求解器选择和可行解解释",
                        "resolution": "resolved",
                        "assumption_if_unresolved": "按连续产量处理并做整数敏感性复核",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "assumption_ledger.md").write_text(
        "# 假设台账\n\n| ID | 假设 | 来源 | 影响 | 验证方式 | 状态 |\n|----|------|------|------|----------|------|\n| H1 | 利润和工时保持线性 | problem_brief.md | 支持线性规划建模 | oracle 与敏感性分析 | accepted |\n",
        encoding="utf-8",
    )
    (workspace / "scoring_strategy.md").write_text(
        "# 评分策略\n\n| 小问 | 必答结果 | 评分重点 | 需要图表 | 创新表达 |\n|------|----------|----------|----------|----------|\n| 生产优化 | A/B 产量和最大利润 | 约束满足、最优性和数值答案 | 是 | baseline vs final |\n",
        encoding="utf-8",
    )
    (workspace / "ablation_study.json").write_text(
        json.dumps(
            {
                "experiments": [
                    {
                        "name": "remove_capacity",
                        "changed_component": "capacity constraint",
                        "metric_delta": 0.1,
                        "interpretation": "产能约束是利润提升的主要瓶颈",
                        "passed": True,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "decision_insights.md").write_text(
        "# 决策建议\n\n- 关键结论：最优方案稳定优于 baseline。\n- 工程含义：产能约束是主要瓶颈。\n- 风险提示：利润参数变化可能改变边际收益。\n- 可执行策略：优先保障高利润产品资源。\n",
        encoding="utf-8",
    )
    (workspace / "defense_questions.md").write_text(
        "# 评委质询模拟\n\n| 问题 | 回答要点 | 是否需要修正 |\n|------|----------|--------------|\n| 为什么选择该模型？ | 线性结构清晰，oracle 与 gap 证明可复核 | 否 |\n| 结果是否稳定？ | 三种扰动和多初值验证均通过 | 否 |\n",
        encoding="utf-8",
    )
    (workspace / "writer_prompt.md").write_text(
        """
# 写作交接提示词

本 skill 已完成模型、代码、图表和验证证据，不生成正式写作正文，只提供写作交接材料。

## 题目与评分
- problem_brief.md

## 模型主线
- final_solution.json

## 代码与结果
- results/validation_summary.json

## 图表证据
- figure_storyboard.md
- figure: figure.png 支撑结论：最优方案稳定优于 baseline。

## 验证证据
- judge_panel_review.json
- reproducibility_manifest.json

## 合规与风险
- compliance_record.json
- 请保持匿名性，披露 AI 工具使用情况，不复制优秀论文原文。
- 风险提示：正文不得新增未验证结论。

## 后续写作/提交复核清单
- 匿名、引用、AI 披露、页数、附件和代码提交均按官方规则复核。
""".strip(),
        encoding="utf-8",
    )
    (workspace / "case_retrieval.json").write_text(
        json.dumps(
            {
                "problem_domain": "生产调度优化",
                "matched_problem_types": ["优化调度", "多目标鲁棒"],
                "matched_cases": [
                    {
                        "rank": 1,
                        "source_competition": "高教社杯全国大学生数学建模竞赛",
                        "year": "2024",
                        "problem_id": "B",
                        "problem_type": "优化调度",
                        "similarity_reason": "同属资源约束下的生产排程与方案选择。",
                        "borrowable_methods": ["整数规划", "小规模枚举 oracle", "敏感性分析"],
                        "cannot_copy_risks": ["数据规模和业务约束不同，不能照搬变量定义。"],
                        "validation_needed": ["baseline", "constraint_residuals", "sensitivity_analysis"],
                    }
                ],
                "candidate_methods": ["integer_programming", "pareto_front", "scenario_analysis"],
                "cannot_copy_risks": ["优秀案例只提供方法启发，必须按本题数据重新建模。"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "innovation_register.json").write_text(
        json.dumps(
            {
                "innovations": [
                    {
                        "id": "I1",
                        "claim": "用 Pareto 前沿解释多目标权衡",
                        "problem_pain_point": "单一目标会掩盖冲突",
                        "baseline_gain": {"metric": "profit", "delta": 0.1, "evidence": "ablation_study.json"},
                        "implementation_cost": "medium",
                        "interpretability": "通过权衡图解释",
                        "verification_evidence": ["baseline_comparison", "ablation_study"],
                        "failure_risk": "样本过少时前沿不稳定",
                        "decision": "accepted",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "judge_panel_review.json").write_text(
        json.dumps(
            {
                "judges": [
                    {"judge_type": "national_modeling_judge", "score": 88, "issues": [], "passed": True},
                    {"judge_type": "comap_judge", "score": 86, "issues": [], "passed": True},
                    {"judge_type": "code_reproducibility_judge", "score": 91, "issues": [], "passed": True},
                    {"judge_type": "figure_evidence_judge", "score": 84, "issues": [], "passed": True},
                    {"judge_type": "engineering_business_judge", "score": 87, "issues": [], "passed": True},
                ],
                "chair_summary": {"overall_score": 87, "decision": "pass", "required_fixes": []},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (workspace / "compliance_record.json").write_text(
        json.dumps(
            {
                "ai_usage": {
                    "used": True,
                    "tools": [{"name": "Codex", "version": "GPT-5", "purpose": "建模代码与验证辅助"}],
                    "disclosure_required": True,
                    "human_reviewed": True,
                },
                "anonymity": {"checked": True, "identity_terms_found": []},
                "external_sources": [
                    {"source": "COMAP instructions", "citation_location": "writer_prompt.md#sources"}
                ],
                "reproducibility": {
                    "manifest": "reproducibility_manifest.json",
                    "commands": ["python solution.py"],
                    "input_hashes_recorded": True,
                    "output_hashes_recorded": True,
                },
                "final_submission": {
                    "anonymity": True,
                    "ai_disclosure": True,
                    "citation_check": True,
                    "page_limit_checked": True,
                    "attachment_check": True,
                    "code_submission_note": "submit reproducible code",
                    "official_rules_reviewed": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
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
        "model_selection_checker",
        "optimization_certificate_checker",
        "uncertainty_budget_checker",
        "validation_profile_checker",
        "data_leakage_checker",
        "statistical_validation_checker",
        "robustness_checker",
        "figure_auditor",
        "manifest_checker",
        "source_freshness_checker",
        "award_readiness_checker",
        "innovation_checker",
        "judge_panel_checker",
        "compliance_checker",
        "source_registry_checker",
        "case_retrieval_checker",
        "writer_prompt_checker",
    ]:
        assert result["checks"][name]["passed"] is True


def test_pipeline_check_runs_online_source_materials_only_when_flag_enabled(monkeypatch, tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)
    calls = []

    def fake_check_source_materials(skill_root, mode="standard", timeout=15, max_bytes=2_000_000, sample_documents=2):
        calls.append(
            {
                "skill_root": skill_root,
                "mode": mode,
                "timeout": timeout,
                "max_bytes": max_bytes,
                "sample_documents": sample_documents,
            }
        )
        return {
            "skill_root": skill_root,
            "mode": mode,
            "passed": True,
            "warning": False,
            "sources_checked": 1,
            "sources_with_material": 1,
            "sources_with_readable_documents": 1,
            "source_results": [],
            "issues": [],
        }

    monkeypatch.setattr(pipeline_check, "check_source_materials", fake_check_source_materials)

    default_result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert default_result["passed"] is True
    assert "source_material_reader" not in default_result["checks"]
    assert calls == []

    online_result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
        online_source_materials=True,
    )

    assert online_result["passed"] is True
    assert online_result["checks"]["source_material_reader"]["passed"] is True
    assert len(calls) == 1
    assert calls[0]["mode"] == "excellence"


def test_pipeline_check_excellence_requires_award_handoff_and_retrieval_artifacts(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)
    for name in [
        "case_retrieval.json",
        "writer_prompt.md",
        "innovation_register.json",
        "judge_panel_review.json",
        "compliance_record.json",
    ]:
        (workspace / name).unlink()

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is False
    assert result["checks"]["case_retrieval_checker"]["passed"] is False
    assert result["checks"]["writer_prompt_checker"]["passed"] is False
    assert result["checks"]["innovation_checker"]["passed"] is False
    assert result["checks"]["judge_panel_checker"]["passed"] is False
    assert result["checks"]["compliance_checker"]["passed"] is False


def test_pipeline_check_excellence_does_not_need_formal_report_body(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is True
    assert result["checks"]["required_files"]["passed"] is True
    assert not (workspace / "modeling_report.md").exists()
    assert "report_auditor" not in result["checks"]


def test_pipeline_check_excellence_requires_award_readiness_artifacts(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)
    for name in [
        "ambiguity_register.json",
        "assumption_ledger.md",
        "scoring_strategy.md",
        "ablation_study.json",
        "decision_insights.md",
        "defense_questions.md",
    ]:
        (workspace / name).unlink()

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is False
    assert result["checks"]["award_readiness_checker"]["passed"] is False
    assert {issue["code"] for issue in result["checks"]["award_readiness_checker"]["issues"]} == {
        "missing_award_artifact"
    }


def test_pipeline_check_fails_when_results_are_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    shutil.rmtree(workspace / "results")
    result = pipeline_check.run_checks(str(workspace), "python")
    assert result["passed"] is False
    assert result["checks"]["required_files"]["passed"] is False
    assert "results" in "\n".join(result["checks"]["required_files"]["missing"])
