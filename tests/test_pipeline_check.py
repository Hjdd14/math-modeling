#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline_check 总控验证测试"""

import os
import json
import shutil
from datetime import datetime

from tools import design_board, pipeline_check


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
    # final_solution.json 自 P0 任务 5 起是决策产物硬门（`_check_decision_artifacts`），
    # 结构对齐 tests/test_data/final_solution.json；模型名与上面的
    # model_selection_audit.json 候选（整数规划 / 贪心启发式）保持一致。
    (workspace / "final_solution.json").write_text(
        json.dumps(
            {
                "selected_model": "整数规划",
                "problem_taxonomy": {"primary_types": ["优化"], "secondary_types": ["整数规划"]},
                "score_matrix": [
                    {
                        "model_name": "整数规划",
                        "problem_fit": 92,
                        "interpretability": 88,
                        "computability": 90,
                        "data_requirement": 80,
                        "robustness": 82,
                        "validation_difficulty": 30,
                        "paper_presentation": 86,
                        "decision": "selected",
                    },
                    {
                        "model_name": "贪心启发式",
                        "problem_fit": 70,
                        "interpretability": 85,
                        "computability": 95,
                        "data_requirement": 70,
                        "robustness": 60,
                        "validation_difficulty": 40,
                        "paper_presentation": 72,
                        "decision": "rejected",
                    },
                ],
                "validation_plan": {
                    "baseline_comparison": "贪心启发式 baseline",
                    "oracle_tests": "小规模枚举 oracle",
                    "solver_cross_checks": "枚举与贪心交叉验证",
                    "sensitivity_analysis": "profit ± 5%",
                    "invariants": ["产量非负", "产能约束"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
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
    write_design_board(workspace)


def write_design_board(workspace):
    """写 Phase 0.5 决策板夹具。

    `board_sha256` 必须用权威实现（`design_board.compute_board_sha256`）动态计算：
    写死哈希会在 `design_board_checker` 处撞 `board_hash_mismatch`。
    候选名必须与上面的 `model_selection_audit.json` 对得上（`整数规划` / `贪心启发式`），
    否则 `board_audit_candidate_mismatch` 会让 excellence 判定失败。
    """
    board = {
        "schema_version": 1,
        "board_id": "b-2026-06-28-quality-fixture",
        "board_sha256": "",
        "language": "python",
        "created_at": "2026-06-28T10:00:00+00:00",
        "revision": 2,
        "problem_summary": {
            "title": "单变量产量最大化（pipeline excellence 夹具）",
            "questions": ["问题一：在产能上限内确定产量 x，使利润最大"],
            "key_ambiguities": [
                {
                    "id": "A1",
                    "severity": "low",
                    "issue": "产量是否必须为整数",
                    "resolution": "resolved",
                }
            ],
        },
        "mindmap": {"format": "mermaid", "source": "graph LR\n  P[产量最大化] --> Q1[问题一]"},
        "questions": [
            {
                "id": "Q1",
                "goal": "确定产量 x 使利润 10*x 最大，且 x <= 100",
                "options": [
                    {
                        "id": "O1",
                        "name": "整数规划",
                        "tier": "recommended",
                        "rationale": "可行域仅 101 个整点，枚举即可证明全局最优",
                        "source_ref": {
                            "type": "method_card",
                            "ref": "OPT-01",
                            "tier": "tier_a",
                            "verified": True,
                        },
                        "complexity": "O(101)",
                        "dependencies": [],
                        "risk": "规模增大需改用求解器",
                        "mini_trial": {
                            "sample": "全量可行域 101 个整点",
                            "output": {"objective": 1000},
                            "seconds": 0.001,
                            "feasible": True,
                        },
                    },
                    {
                        "id": "O2",
                        "name": "贪心启发式",
                        "tier": "alternative",
                        "rationale": "实现最简单，可作 baseline 对比",
                        "source_ref": {
                            "type": "method_card",
                            "ref": "OPT-02",
                            "tier": "tier_a",
                            "verified": True,
                        },
                        "complexity": "O(1)",
                        "dependencies": [],
                        "risk": "无最优性保证，无法给出 gap",
                        "mini_trial": {
                            "sample": "贪心路径",
                            "output": {"objective": 1000},
                            "seconds": 0.0001,
                            "feasible": True,
                        },
                    },
                ],
                "user_choice": "O1",
                "user_locked": True,
                "user_comment": "用整数规划，并给出 LP 下界与 gap",
                "confirmed": True,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 2,
        "confirmed_at": "2026-06-28T12:00:00+00:00",
        "confirmed_by": "user",
        "receipt_origin": "browser-submit",
        "confirm_code": "",
        "confirm_attested": True,
    }
    board["board_sha256"] = design_board.compute_board_sha256(board)
    board["confirm_code"] = design_board.derive_confirm_code(board["board_sha256"])
    (workspace / "design_board.json").write_text(
        json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rounds_dir = workspace / "design_rounds"
    rounds_dir.mkdir(exist_ok=True)
    for round_no in (1, 2):
        (rounds_dir / f"round_{round_no:03d}.json").write_text(
            json.dumps(
                {
                    "round": round_no,
                    "at": "2026-06-28T11:00:00+00:00",
                    "board_id": board["board_id"],
                    "board_sha256": board["board_sha256"],
                    "user_edited": False,
                    "changes": [],
                    "receipt_origin": "browser-submit",
                    "receipt_nonce": f"fixture-{round_no}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # 时间线校验要求代码/结果文件的 mtime 不早于 confirmed_at。
    # `copy_workspace` 用 `shutil.copy2`，会保留 `tests/test_data` 里的旧 mtime；
    # 而 tmp_path 不命中 `FIXTURE_MARKERS`（路径不含 tests/test_data），时间线会真的执行。
    # 因此这里显式把 mtime 归一到 confirmed_at 之后，避免误报 code_written_before_confirm。
    confirmed_ts = datetime.fromisoformat(board["confirmed_at"]).timestamp()
    stale_targets = ["solution.py", "solution_tests.py"]
    results_dir = workspace / "results"
    if results_dir.is_dir():
        stale_targets += [
            str(path.relative_to(workspace)) for path in results_dir.rglob("*") if path.is_file()
        ]
    for rel in stale_targets:
        target = workspace / rel
        if target.exists():
            os.utime(target, (confirmed_ts + 60, confirmed_ts + 60))


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
        "decision_artifacts",
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


def test_decision_artifacts_are_hard_gate_not_recommended(tmp_path):
    """决策产物已从软清单升为硬门，不应再出现在 RECOMMENDED_ARTIFACTS 里。"""
    assert pipeline_check.DECISION_ARTIFACTS == ("final_solution.json", "model_decision.md")
    for name in pipeline_check.DECISION_ARTIFACTS:
        assert name not in pipeline_check.RECOMMENDED_ARTIFACTS


def test_pipeline_check_excellence_requires_final_solution_artifact(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)
    (workspace / "final_solution.json").unlink()

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is False
    assert result["checks"]["decision_artifacts"]["passed"] is False
    assert {issue["code"] for issue in result["checks"]["decision_artifacts"]["issues"]} == {
        "missing_decision_artifact"
    }
    assert {issue["file"] for issue in result["checks"]["decision_artifacts"]["issues"]} == {
        "final_solution.json"
    }


def test_pipeline_check_excellence_requires_model_decision_artifact(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)
    (workspace / "model_decision.md").unlink()

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is False
    assert result["checks"]["decision_artifacts"]["passed"] is False
    assert {issue["code"] for issue in result["checks"]["decision_artifacts"]["issues"]} == {
        "missing_decision_artifact"
    }
    assert {issue["file"] for issue in result["checks"]["decision_artifacts"]["issues"]} == {
        "model_decision.md"
    }


def test_pipeline_check_standard_quality_warns_when_decision_artifacts_missing(tmp_path):
    """standard 模式保持旧工作区兼容：缺决策产物只 warning，不影响 passed。"""
    workspace = copy_workspace(tmp_path)
    (workspace / "model_decision.md").unlink()  # final_solution.json 本就不在夹具里

    result = pipeline_check.run_checks(str(workspace), "python", quality_mode="standard")

    assert result["passed"] is True
    decision = result["checks"]["decision_artifacts"]
    assert decision["passed"] is True
    assert decision["warning"] is True
    assert {issue["severity"] for issue in decision["issues"]} == {"warning"}
    assert {issue["file"] for issue in decision["issues"]} == {
        "final_solution.json",
        "model_decision.md",
    }


def test_pipeline_check_decision_artifacts_pass_when_present(tmp_path):
    workspace = copy_workspace(tmp_path)
    write_quality_artifacts(workspace)

    result = pipeline_check.run_checks(
        str(workspace),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    decision = result["checks"]["decision_artifacts"]
    assert decision["passed"] is True
    assert decision["warning"] is False
    assert decision["issues"] == []
    assert decision["checks"] == [{"name": "decision_artifacts", "passed": True, "missing": []}]


# ---------------------------------------------------------------------------
# 双闸门：--stage final 的跨板硬门槛（A 板 schema v2 ⇒ 必须有已确认的 B 板）
# ---------------------------------------------------------------------------


def _paradigm(paradigm_id, family):
    return {
        "paradigm_id": paradigm_id,
        "name": "范式" + paradigm_id,
        "family": family,
        "source_ref": {
            "type": "method_card",
            "ref": "STA-03",
            "tier": "tier_a",
            "verified": True,
        },
        "why_explore": "覆盖不同方法族，避免五视角同族互抄",
        "explore_cost": {"level": "low", "note": "样例数据可跑"},
    }


def write_gate_a_board(workspace, schema_version=2, confirmed=True):
    """写 A 板夹具（默认 schema v2：只确认框架 + 待探索范式，不锁定选型）。"""
    board = {
        "schema_version": schema_version,
        "gate": "a",
        "board_id": "b-2026-10-30-pipeline-fixture",
        "language": "python",
        "revision": 1,
        "problem_summary": {
            "title": "双闸门总控夹具",
            "questions": ["问题一：求最优产量"],
            "key_ambiguities": [],
        },
        "mindmap": {"format": "mermaid", "source": "graph LR\n  P[产量最大化] --> Q1[问题一]"},
        "questions": [
            {
                "id": "Q1",
                "goal": "确定产量 x 使利润最大",
                "paradigm_set": [
                    _paradigm("P1", "statistical_inference"),
                    _paradigm("P2", "optimization"),
                    _paradigm("P3", "simulation"),
                ],
                "paradigm_selection": ["P1", "P2"],
                "options": [],
                "user_choice": None,
                "user_locked": False,
                "user_comment": "",
                "confirmed": confirmed,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 0,
        "confirmed": confirmed,
        "confirmed_at": "2026-10-30T12:00:00+00:00",
        "confirmed_by": "user",
    }
    (workspace / "design_board.json").write_text(
        json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return board


def write_gate_b_board(workspace, confirmed=True, user_choice="O1"):
    """写 B 板夹具（只保证"板在 + 已确认 + 有选择"这三件，B 组细节由 checker 自己查）。"""
    board = {
        "schema_version": 2,
        "gate": "b",
        "question_scope": "problem",
        "board_id": "gb-2026-10-30-pipeline-fixture",
        "advice_ref": "model_advice.json",
        "language": "python",
        "revision": 1,
        "problem_summary": {"title": "双闸门总控夹具", "questions": ["Q1"]},
        "questions": [
            {
                "id": "Q1",
                "goal": "确定产量 x 使利润最大",
                "options": [{"id": "O1", "name": "整数规划", "verdict": "recommended", "score": 86.5}],
                "user_choice": user_choice,
                "user_locked": True,
                "confirmed": confirmed,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 0,
        "confirmed": confirmed,
        "confirmed_at": "2026-10-30T12:30:00+00:00",
        "confirmed_by": "user",
    }
    (workspace / "design_board_gate_b.json").write_text(
        json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return board


def test_stage_final_errors_when_schema_v2_board_has_no_gate_b(tmp_path):
    """A 板 schema_version>=2 但缺 B 板 -> error（与 quality_mode 无关）。"""
    write_gate_a_board(tmp_path, schema_version=2)

    result = pipeline_check._two_gate_stage(tmp_path, "standard", "final")

    assert result["passed"] is False
    assert result["gate_a"]["new_flow"] is True
    codes = {issue["code"] for issue in result["issues"]}
    assert "missing_gate_b_board" in codes
    issue = next(i for i in result["issues"] if i["code"] == "missing_gate_b_board")
    assert issue["severity"] == "error"
    assert "--gate b" in issue["message"]


def test_stage_final_only_warns_for_legacy_board_without_gate_b(tmp_path):
    """legacy A 板（schema<2）缺 B 板 -> warning，旧工作区不阻断。"""
    write_gate_a_board(tmp_path, schema_version=1)

    result = pipeline_check._two_gate_stage(tmp_path, "excellence", "final")

    assert result["passed"] is True
    assert result["warning"] is True
    assert result["gate_a"]["new_flow"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert codes == {"gate_b_missing_legacy_workspace"}
    assert {issue["severity"] for issue in result["issues"]} == {"warning"}


def test_stage_final_passes_with_confirmed_gate_b_and_choices(tmp_path):
    """A 板 v2 + B 板已确认 + 每题 user_choice 非空 -> 跨板门槛全过。"""
    write_gate_a_board(tmp_path, schema_version=2)
    write_gate_b_board(tmp_path, confirmed=True, user_choice="O1")

    result = pipeline_check._two_gate_stage(tmp_path, "excellence", "final")

    assert result["passed"] is True
    assert result["issues"] == []
    assert result["gate_b"]["confirmed"] is True
    assert result["gate_b"]["choices_complete"] is True
    assert result["gate_b"]["questions"] == 1


def test_stage_final_reports_unconfirmed_and_unchosen_gate_b(tmp_path):
    """B 板在但没确认 / 没有 user_choice：各报一个 error，不能合并吞掉。"""
    write_gate_a_board(tmp_path, schema_version=2)
    write_gate_b_board(tmp_path, confirmed=False, user_choice=None)

    result = pipeline_check._two_gate_stage(tmp_path, "excellence", "final")

    assert result["passed"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert "gate_b_not_confirmed" in codes
    assert "gate_b_choice_missing" in codes
    choice_issue = next(i for i in result["issues"] if i["code"] == "gate_b_choice_missing")
    assert choice_issue["questions"] == ["Q1"]


def test_stage_final_flags_invalid_gate_b_json(tmp_path):
    """B 板存在但 JSON 坏掉：不能当成"没有 B 板"轻轻放过。"""
    write_gate_a_board(tmp_path, schema_version=2)
    (tmp_path / "design_board_gate_b.json").write_text("{ not json", encoding="utf-8")

    result = pipeline_check._two_gate_stage(tmp_path, "excellence", "final")

    assert result["passed"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert "invalid_gate_b_board" in codes


def test_gate_b_check_is_skipped_when_board_absent(tmp_path):
    """B 板不在场时不调 checker 的 gate b（缺板判定由 two_gate_stage 统一给出）。"""
    result = pipeline_check._design_board_gate_b(tmp_path, "excellence", "final")

    assert result["passed"] is True
    assert result["skipped"] is True
    assert result["reason"] == "missing_gate_b_board"


def test_gate_b_check_delegates_advice_rules_to_checker(tmp_path):
    """B 板在场时跑 B 组全量检查：缺 model_advice.json 必须由 checker 报出来。"""
    write_gate_a_board(tmp_path, schema_version=2)
    write_gate_b_board(tmp_path, confirmed=True, user_choice="O1")

    result = pipeline_check._design_board_gate_b(tmp_path, "excellence", "final")

    assert result.get("gate") == "b"
    assert result.get("skipped") is not True
    codes = {issue["code"] for issue in result.get("issues", [])}
    # advice / trials 的规则由 checker 内部完成，pipeline 不再重复实现。
    assert "advice_missing" in codes


def test_run_checks_exposes_two_gate_stage_and_gate_b(tmp_path):
    """run_checks 必须把 A 板、B 板、跨板门槛三个结果都并进 checks。"""
    copy_workspace(tmp_path)
    write_gate_a_board(tmp_path, schema_version=2)

    result = pipeline_check.run_checks(str(tmp_path), "python", quality_mode="standard")

    assert result["stage"] == "final"
    assert "design_board_checker" in result["checks"]
    assert "design_board_gate_b" in result["checks"]
    assert "two_gate_stage" in result["checks"]
    assert result["checks"]["two_gate_stage"]["passed"] is False
    assert result["passed"] is False


def test_main_repo_stage_has_no_question_variant(tmp_path):
    """主仓库只提供 --stage final；question 是分支特性，不得在此暴露。"""
    assert pipeline_check.STAGE_CHOICES == ("final",)
    assert "question" not in pipeline_check.STAGE_CHOICES
    assert pipeline_check.DEFAULT_STAGE == "final"
    # 代码层仍容忍分支传进来的 stage（不崩、不改变主仓库判定范围）
    result = pipeline_check._two_gate_stage(tmp_path, "standard", "question")
    assert result["stage"] == "question"

def test_stage_final_gate_b_missing_with_delivery_code_is_error(tmp_path):
    """A 板 v2 + 已有 solution.py + 缺 B 板：必须是 error（"缺板+有代码"不得降级）。"""
    copy_workspace(tmp_path)
    write_gate_a_board(tmp_path, schema_version=2)
    assert (tmp_path / "solution.py").is_file()
    assert not (tmp_path / "design_board_gate_b.json").exists()

    two_gate = pipeline_check._two_gate_stage(tmp_path, "standard", "final")

    # 与 quality_mode 无关：A 板自己声明了新流程，B 板就是硬门槛。
    assert two_gate["passed"] is False
    assert "missing_gate_b_board" in {issue["code"] for issue in two_gate["issues"]}

    result = pipeline_check.run_checks(str(tmp_path), "python", quality_mode="standard")
    assert result["passed"] is False
    assert result["checks"]["two_gate_stage"]["passed"] is False


def test_stage_final_legacy_with_delivery_code_and_no_gate_b_is_warning(tmp_path):
    """legacy A 板 + 已有 solution.py + 缺 B 板：只 warning，旧工作区不被判死。"""
    copy_workspace(tmp_path)
    write_gate_a_board(tmp_path, schema_version=1)

    two_gate = pipeline_check._two_gate_stage(tmp_path, "excellence", "final")

    assert two_gate["passed"] is True
    assert two_gate["warning"] is True
    assert {issue["code"] for issue in two_gate["issues"]} == {"gate_b_missing_legacy_workspace"}


def test_stage_final_gate_b_failure_propagates_into_overall_result(tmp_path):
    """B 板在场但 B 组规则不过（缺 advice）：整体 passed 必须为 False。"""
    copy_workspace(tmp_path)
    write_gate_a_board(tmp_path, schema_version=2)
    write_gate_b_board(tmp_path, confirmed=True, user_choice="O1")

    result = pipeline_check.run_checks(
        str(tmp_path), "python", evidence_mode="standard", quality_mode="excellence"
    )

    gate_b = result["checks"]["design_board_gate_b"]
    assert gate_b.get("skipped") is not True
    assert gate_b["passed"] is False
    assert "advice_missing" in {issue["code"] for issue in gate_b["issues"]}
    assert result["passed"] is False
