#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奖项级增强 gate 的回归测试"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from tools import (
    award_readiness_checker,
    brief_completeness_checker,
    code_runner,
    compliance_checker,
    data_leakage_checker,
    doctor,
    figure_auditor,
    manifest_checker,
    mini_benchmark_runner,
    model_selection_checker,
    optimization_certificate_checker,
    pipeline_check,
    robustness_checker,
    solution_test_generator,
    source_freshness_checker,
    statistical_validation_checker,
    uncertainty_budget_checker,
    validation_profile_checker,
    writer_prompt_checker,
)


SKILL_DIR = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_normal_png(target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    source = SKILL_DIR / "tests" / "test_figures" / "normal.png"
    target.write_bytes(source.read_bytes())


def make_png(target: Path, dpi: int = 300):
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (500, 360), "white")
    for x in range(70, 430):
        for y in range(250, 255):
            image.putpixel((x, y), (0, 0, 0))
    for y in range(80, 260):
        for x in range(70, 75):
            image.putpixel((x, y), (0, 0, 0))
    for x in range(90, 420):
        y = 245 - int((x - 90) * 0.35)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                px = min(max(x + dx, 0), image.width - 1)
                py = min(max(y + dy, 0), image.height - 1)
                image.putpixel((px, py), (30, 90, 180))
    image.save(target, dpi=(dpi, dpi))


def write_award_readiness_artifacts(root: Path, ambiguity_resolution: str = "resolved", ablation_complete: bool = True):
    write_json(
        root / "ambiguity_register.json",
        {
            "items": [
                {
                    "id": "A1",
                    "severity": "high",
                    "source": "problem_brief.md",
                    "issue": "产能口径是否为全周期",
                    "impact": "影响约束右端项和最优方案",
                    "resolution": ambiguity_resolution,
                    "assumption_if_unresolved": "按全周期处理并做敏感性复核",
                }
            ]
        },
    )
    (root / "assumption_ledger.md").write_text(
        "# 假设台账\n\n| ID | 假设 | 来源 | 影响 | 验证方式 | 状态 |\n|----|------|------|------|----------|------|\n| H1 | 产能为全周期口径 | problem_brief.md | 影响约束上限 | 敏感性分析 | accepted |\n",
        encoding="utf-8",
    )
    (root / "scoring_strategy.md").write_text(
        "# 评分策略\n\n| 小问 | 必答结果 | 评分重点 | 需要图表 | 创新表达 |\n|------|----------|----------|----------|----------|\n| Q1 | 最优方案和数值 | 约束、gap、结果解释 | 是 | baseline 对比 |\n",
        encoding="utf-8",
    )
    experiment = {
        "name": "remove_key_constraint",
        "changed_component": "key constraint",
        "metric_delta": 0.12,
        "interpretation": "关键约束决定主要结论",
        "passed": True,
    }
    if not ablation_complete:
        experiment.pop("interpretation")
    write_json(root / "ablation_study.json", {"experiments": [experiment]})
    (root / "decision_insights.md").write_text(
        "# 决策建议\n\n- 关键结论：最终方案优于 baseline。\n- 工程含义：关键资源是方案瓶颈。\n- 风险提示：参数波动可能影响排名。\n- 可执行策略：优先保障关键资源。\n",
        encoding="utf-8",
    )
    (root / "defense_questions.md").write_text(
        "# 评委质询模拟\n\n| 问题 | 回答要点 | 是否需要修正 |\n|------|----------|--------------|\n| 为什么选择该模型？ | 有 oracle、gap 和 residual 证据 | 否 |\n| 结果是否稳定？ | 三种扰动下排名稳定 | 否 |\n",
        encoding="utf-8",
    )


def test_brief_completeness_checker_fails_on_placeholder_targets(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        """
# problem_brief
## 目标
待 Agent 提取
## 约束
- 产能约束
## 输出要求
- 输出最优方案
""".strip(),
        encoding="utf-8",
    )

    result = brief_completeness_checker.check_brief_completeness(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "brief_placeholder" for issue in result["issues"])


def test_brief_completeness_checker_passes_complete_brief(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        """
# problem_brief
## 目标
最大化总收益并给出各小问对应答案。
## 约束
- 产能、预算和非负约束必须满足。
## 输出要求
- 输出方案表、关键指标、验证摘要和图表。
""".strip(),
        encoding="utf-8",
    )

    result = brief_completeness_checker.check_brief_completeness(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["checks_passed"] >= 3


def test_award_readiness_checker_passes_complete_artifacts(tmp_path):
    write_award_readiness_artifacts(tmp_path)

    result = award_readiness_checker.check_award_readiness(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["warning"] is False


def test_award_readiness_checker_fails_unresolved_high_ambiguity(tmp_path):
    write_award_readiness_artifacts(tmp_path, ambiguity_resolution="pending")

    result = award_readiness_checker.check_award_readiness(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "unresolved_high_ambiguity" for issue in result["issues"])


def test_award_readiness_checker_fails_incomplete_ablation(tmp_path):
    write_award_readiness_artifacts(tmp_path, ablation_complete=False)

    result = award_readiness_checker.check_award_readiness(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_ablation_field" for issue in result["issues"])


def test_award_readiness_checker_standard_warns_missing_artifacts(tmp_path):
    result = award_readiness_checker.check_award_readiness(str(tmp_path), mode="standard")

    assert result["passed"] is True
    assert result["warning"] is True
    assert all(issue["severity"] == "warning" for issue in result["issues"])


def test_robustness_checker_uses_excellence_confidence_threshold(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(
        tmp_path / "results" / "validation_summary.json",
        {
            "constraint_residuals": {"max_abs": 0, "tolerance": 1e-6, "passed": True},
            "optimality_gap": {"value": 0, "tolerance": 1e-4, "passed": True},
            "multi_start": {"runs": 3, "passed": True},
            "random_seed_stability": {"seeds": [1, 2, 3], "passed": True},
            "bootstrap_confidence_interval": {"level": 0.9, "lower": 1, "upper": 2, "passed": True},
            "perturbation_stability": {"ranking_changed": False, "passed": True},
        },
    )

    result = robustness_checker.check_robustness(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue.get("item") == "bootstrap_confidence_interval" for issue in result["issues"])


def test_solution_test_generator_requires_three_seeds_multistart_and_95_ci(tmp_path):
    solution_test_generator.generate_solution_tests(str(tmp_path), language="python")
    content = (tmp_path / "solution_tests.py").read_text(encoding="utf-8")

    assert "len(seeds) >= 3" in content
    assert "test_multi_start_runs_recorded" in content
    assert "runs >= 3" in content
    assert "test_bootstrap_confidence_level_recorded" in content
    assert "level >= 0.95" in content


def test_model_selection_checker_rejects_vague_audit(tmp_path):
    write_json(
        tmp_path / "model_selection_audit.json",
        {"candidates": [{"name": "模型A"}], "final_selection": {"name": "模型A"}},
    )

    result = model_selection_checker.check_model_selection(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_model_selection_evidence" for issue in result["issues"])


def test_model_selection_checker_accepts_scored_candidates(tmp_path):
    write_json(
        tmp_path / "model_selection_audit.json",
        {
            "candidates": [
                {"name": "整数规划", "score": 0.91, "rejection_reason": "", "evidence": ["oracle"]},
                {"name": "启发式", "score": 0.72, "rejection_reason": "不能证明最优性", "evidence": ["baseline"]},
            ],
            "final_selection": {"name": "整数规划", "score": 0.91, "evidence": ["gap=0", "residual=0"]},
        },
    )

    result = model_selection_checker.check_model_selection(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["candidates_checked"] == 2


def test_optimization_certificate_checker_requires_gap_and_oracle(tmp_path):
    write_json(
        tmp_path / "optimization_certificate.json",
        {"feasibility_residual": {"max_abs": 0}, "bounds": {"lower": 10, "upper": 12}},
    )

    result = optimization_certificate_checker.check_optimization_certificate(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_optimization_certificate_field" for issue in result["issues"])


def test_uncertainty_budget_checker_requires_all_error_sources(tmp_path):
    write_json(
        tmp_path / "uncertainty_budget.json",
        {"data": {"impact": "low"}, "parameter": {"impact": "medium"}},
    )

    result = uncertainty_budget_checker.check_uncertainty_budget(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert {"model", "random"} <= {issue.get("field") for issue in result["issues"]}


def test_validation_profile_checker_covers_profile_specific_success_and_failure(tmp_path):
    write_json(
        tmp_path / "validation_profile.json",
        {
            "profile": "forecasting",
            "evidence": {
                "holdout": {"method": "time_split", "passed": True},
                "cv": {"folds": 5},
                "metrics": {"MAE": 1.0, "RMSE": 1.4, "MAPE": 0.08},
                "residuals": {"checked": True},
                "interval_coverage": {"level": 0.95, "coverage": 0.94},
            },
        },
    )
    passed = validation_profile_checker.check_validation_profile(str(tmp_path), mode="excellence")
    assert passed["passed"] is True

    write_json(
        tmp_path / "validation_profile.json",
        {"profile": "graph_network", "evidence": {"path_validity": {"starts_at": "S", "ends_at": "T"}}},
    )
    failed = validation_profile_checker.check_validation_profile(str(tmp_path), mode="excellence")
    assert failed["passed"] is False
    assert any(issue["code"] == "missing_validation_profile_field" for issue in failed["issues"])


def test_validation_profile_checker_parametrized_success_and_failure(tmp_path):
    profiles = {
        "optimization": (
            {
                "baseline": {"passed": True},
                "oracle": {"passed": True},
                "gap": {"value": 0.0},
                "residuals": {"max_abs": 0.0},
                "sensitivity": {"passed": True},
            },
            "sensitivity",
        ),
        "forecasting": (
            {
                "holdout": {"method": "time_split"},
                "cv": {"folds": 5},
                "metrics": {"MAE": 1.0, "RMSE": 1.2, "MAPE": 0.05},
                "residuals": {"checked": True},
                "interval_coverage": {"level": 0.95},
            },
            "interval_coverage",
        ),
        "graph_network": (
            {
                "path_validity": {"starts_at": "S", "ends_at": "T"},
                "edge_existence": {"passed": True},
                "connectivity": {"passed": True},
                "cost_recalculation": {"value": 4},
            },
            "cost_recalculation",
        ),
        "stochastic_simulation": (
            {
                "multi_seed": {"seeds": [1, 2, 3]},
                "confidence_interval": {"level": 0.95, "lower": 1, "upper": 2},
                "convergence_or_variance": {"passed": True},
            },
            "convergence_or_variance",
        ),
        "physical_mechanism": (
            {
                "units": {"checked": True},
                "conservation": {"passed": True},
                "boundary_conditions": {"passed": True},
                "known_special_case": {"passed": True},
            },
            "known_special_case",
        ),
        "policy_decision": (
            {
                "weights_sum_to_one": {"value": 1.0},
                "ranking_stability": {"passed": True},
                "scenario_explanation": {"scenarios": ["baseline", "stress"]},
            },
            "scenario_explanation",
        ),
    }

    for profile, (evidence, missing_field) in profiles.items():
        write_json(tmp_path / "validation_profile.json", {"profile": profile, "evidence": evidence})
        passed = validation_profile_checker.check_validation_profile(str(tmp_path), mode="excellence")
        assert passed["passed"] is True, profile

        incomplete = dict(evidence)
        incomplete.pop(missing_field)
        write_json(tmp_path / "validation_profile.json", {"profile": profile, "evidence": incomplete})
        failed = validation_profile_checker.check_validation_profile(str(tmp_path), mode="excellence")
        assert failed["passed"] is False, profile
        assert any(
            issue["code"] == "missing_validation_profile_field" and issue.get("field") == missing_field
            for issue in failed["issues"]
        )


def test_data_leakage_checker_rejects_target_feature_and_random_time_split(tmp_path):
    write_json(
        tmp_path / "data_validation.json",
        {
            "task_type": "forecasting",
            "target": "sales",
            "features": ["sales", "price"],
            "split": {"type": "random"},
            "preprocessing": [{"name": "standardize", "fit_on": "all"}],
        },
    )

    result = data_leakage_checker.check_data_leakage(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert {"target_leakage", "invalid_time_split", "preprocessing_leakage"} <= codes


def test_statistical_validation_checker_requires_holdout_residuals_and_overfit_check(tmp_path):
    write_json(tmp_path / "statistical_validation.json", {"metrics": {"MAE": 1.0}})

    result = statistical_validation_checker.check_statistical_validation(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_statistical_validation_field" for issue in result["issues"])


def test_figure_auditor_requires_storyboard_claim_units_and_writer_handoff(tmp_path):
    copy_normal_png(tmp_path / "results" / "core_result.png")
    write_json(tmp_path / "figure_style.json", {"dpi": 300, "font_size": 10, "colorblind_safe": True, "formats": ["png"]})
    (tmp_path / "figure_storyboard.md").write_text(
        """
# Figure Storyboard
- file: core_result.png
  claim: 模型收益稳定高于 baseline
  source_data: results/output.csv
  x_unit: 周
  y_unit: 元
  supports_question: Q1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "writer_prompt.md").write_text(
        """
# 写作交接提示词
本 skill 不生成正式写作正文，只提供写作交接材料。
## 题目与评分
problem_brief
## 模型主线
final_solution
## 代码与结果
validation_summary
## 图表证据
figure: core_result.png 支撑结论：模型收益稳定高于 baseline，回答 Q1。
## 验证证据
judge_panel_review reproducibility
## 合规与风险
compliance_record 风险 合规
## 后续写作/提交复核清单
匿名、引用、AI 披露、页数、附件和代码提交均需按官方规则复核。
""".strip(),
        encoding="utf-8",
    )

    figure_result = figure_auditor.audit_figures(str(tmp_path), mode="excellence")
    prompt_result = writer_prompt_checker.check_writer_prompt(str(tmp_path), mode="excellence")

    assert figure_result["passed"] is True
    assert prompt_result["passed"] is True

    (tmp_path / "figure_storyboard.md").write_text("- file: core_result.png\n  claim: 缺少单位\n", encoding="utf-8")
    failed = figure_auditor.audit_figures(str(tmp_path), mode="excellence")
    assert failed["passed"] is False
    assert any(issue["code"] == "missing_storyboard_field" for issue in failed["issues"])


def test_figure_auditor_excellence_rejects_low_dpi(tmp_path):
    make_png(tmp_path / "results" / "low_dpi.png", dpi=72)
    write_json(tmp_path / "figure_style.json", {"dpi": 300, "font_size": 10, "colorblind_safe": True, "formats": ["png"]})
    (tmp_path / "figure_storyboard.md").write_text(
        """
# Figure Storyboard
- file: low_dpi.png
  claim: 低 DPI 图不应通过奖项级图表 gate
  source_data: results/output.csv
  x_unit: 类别
  y_unit: 值
  supports_question: Q1
""".strip(),
        encoding="utf-8",
    )

    standard = figure_auditor.audit_figures(str(tmp_path), mode="standard")
    excellence = figure_auditor.audit_figures(str(tmp_path), mode="excellence")

    assert standard["passed"] is True
    assert excellence["passed"] is False
    assert any(issue["code"] == "figure_low_dpi" for issue in excellence["issues"])


def test_source_freshness_checker_offline_structure_and_year_coverage(tmp_path):
    write_json(
        tmp_path / "source_registry.json",
        {
            "sources": [
                {
                    "name": "COMAP",
                    "url": "https://www.comap.com/",
                    "years": [2024, 2025, 2026],
                    "tier": "official",
                    "checked_at": "2026-06-28",
                }
            ]
        },
    )

    result = source_freshness_checker.check_source_freshness(str(tmp_path), mode="excellence", online=False)

    assert result["passed"] is True
    assert result["sources_checked"] == 1


def test_source_freshness_uses_secondary_url_when_primary_tls_fails(monkeypatch, tmp_path):
    write_json(
        tmp_path / "source_registry.json",
        {
            "sources": [
                {
                    "name": "华中杯",
                    "url": "https://primary.example/",
                    "secondary_urls": ["https://backup.example/award"],
                    "years": [2025, 2026],
                    "tier": "official",
                    "checked_at": "2026-06-28",
                }
            ]
        },
    )

    def fake_reachable(url, timeout=8):
        if "primary" in url:
            return False, "certificate verify failed: certificate has expired"
        return True, "200"

    monkeypatch.setattr(source_freshness_checker, "_url_reachable", fake_reachable)

    result = source_freshness_checker.check_source_freshness(str(tmp_path), mode="excellence", online=True)

    assert result["passed"] is True
    assert result["warning"] is True
    assert result["reachable_checked"] == 2
    check = next(item for item in result["checks"] if item["name"] == "source_0_reachable")
    assert check["passed"] is True
    assert check["primary_reachable"] is False
    assert check["reachable_url"] == "https://backup.example/award"
    assert check["fallback_used"] is True
    assert "certificate" in check["primary_issue"]
    assert any(issue["code"] == "primary_url_tls_issue" for issue in result["issues"])


def test_source_freshness_fails_when_all_urls_unreachable(monkeypatch, tmp_path):
    write_json(
        tmp_path / "source_registry.json",
        {
            "sources": [
                {
                    "name": "失效来源",
                    "url": "https://primary.example/",
                    "secondary_urls": ["https://backup-a.example/", "https://backup-b.example/"],
                    "years": [2025, 2026],
                    "tier": "official",
                    "checked_at": "2026-06-28",
                }
            ]
        },
    )

    def fake_reachable(url, timeout=8):
        return False, f"{url} unreachable"

    monkeypatch.setattr(source_freshness_checker, "_url_reachable", fake_reachable)

    result = source_freshness_checker.check_source_freshness(str(tmp_path), mode="excellence", online=True)

    assert result["passed"] is False
    assert result["reachable_checked"] == 3
    check = next(item for item in result["checks"] if item["name"] == "source_0_reachable")
    assert check["passed"] is False
    assert check["reachable_url"] is None
    assert check["fallback_used"] is False
    assert any(issue["code"] == "source_url_unreachable" for issue in result["issues"])


def test_compliance_checker_requires_submission_constraints(tmp_path):
    write_json(
        tmp_path / "compliance_record.json",
        {
            "ai_usage": {"tools": [{"name": "Codex"}], "human_reviewed": True},
            "anonymity": {"checked": True, "identity_terms_found": ["某某大学"]},
            "external_sources": [],
            "reproducibility": {
                "manifest": "reproducibility_manifest.json",
                "commands": ["python solution.py"],
                "input_hashes_recorded": True,
                "output_hashes_recorded": True,
            },
            "final_submission": {"citation_check": True},
        },
    )

    result = compliance_checker.check_compliance(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    codes = {issue["code"] for issue in result["issues"]}
    assert "identity_leak" in codes
    assert "missing_submission_constraint" in codes


def test_manifest_checker_requires_runtime_environment_and_hashes(tmp_path):
    (tmp_path / "data.csv").write_text("id,value\n1,10\n", encoding="utf-8")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "output.csv").write_text("id,value\n1,10\n", encoding="utf-8")
    write_json(
        tmp_path / "reproducibility_manifest.json",
        {
            "os": {"name": "Windows", "version": "11"},
            "python_version": "3.12",
            "matlab_version": None,
            "solvers": [{"name": "enumeration", "version": "builtin"}],
            "random_libraries": [{"name": "numpy.random", "seed": 42}],
            "execution": {"seconds": 0.2},
            "dependencies": {"numpy": "2.0"},
            "random_seed": 42,
            "input_hashes": [{"path": "data.csv", "sha256": sha256(tmp_path / "data.csv")}],
            "output_hashes": [{"path": "results/output.csv", "sha256": sha256(tmp_path / "results" / "output.csv")}],
        },
    )

    result = manifest_checker.check_manifest(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["hashes_checked"] == 2


def test_code_runner_tracks_nested_result_hashes(tmp_path):
    (tmp_path / "solution.py").write_text(
        """
from pathlib import Path
Path("results/nested").mkdir(parents=True, exist_ok=True)
Path("results/nested/output.json").write_text('{"value": 42}', encoding="utf-8")
""".strip(),
        encoding="utf-8",
    )

    result = code_runner.run_code(str(tmp_path / "solution.py"), "python", timeout=30, workdir=str(tmp_path))

    assert result["success"] is True
    assert "results/nested/output.json" in result["generated_files"]
    assert result["file_hashes"]["results/nested/output.json"]


def test_mini_benchmark_runner_executes_cases_and_checks_oracles(tmp_path):
    result = mini_benchmark_runner.run_benchmark(
        str(SKILL_DIR / "evals" / "mini_contest_benchmark.json"),
        mode="strict",
        keep_workspaces=False,
    )

    assert result["passed"] is True
    assert result["cases_checked"] >= 6
    assert all(case["passed"] for case in result["case_results"])


def test_pipeline_excellence_includes_all_award_level_gates():
    result = pipeline_check.run_checks(
        str(SKILL_DIR / "tests" / "test_data"),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is True
    for name in [
        "brief_completeness_checker",
        "model_selection_checker",
        "optimization_certificate_checker",
        "uncertainty_budget_checker",
        "validation_profile_checker",
        "data_leakage_checker",
        "statistical_validation_checker",
        "source_freshness_checker",
        "award_readiness_checker",
    ]:
        assert result["checks"][name]["passed"] is True


def test_trigger_eval_no_longer_requests_formal_report_body():
    text = (SKILL_DIR / "evals" / "trigger_eval.json").read_text(encoding="utf-8")

    assert "建模报告" not in text
    assert "建模论文" not in text
    assert "写作交接提示词" in text


def test_ci_runs_excellence_source_registry_mini_benchmark_and_node_checks():
    text = (SKILL_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "--quality-mode excellence" in text
    assert "source_registry_checker.py" in text
    assert "source_freshness_checker.py --workspace . --mode excellence" in text
    assert "award_readiness_checker.py --workspace tests/test_data --mode excellence" in text
    assert "mini_benchmark_checker.py" in text
    assert "mini_benchmark_runner.py" in text
    assert "node --check" in text


def test_doctor_counts_dirty_git_as_warning():
    summary = doctor.summarize(
        [
            {"name": "required_files", "passed": True, "severity": "error"},
            {"name": "git_repository", "passed": True, "severity": "warning", "clean": False},
        ]
    )

    assert summary["failed"] == 0
    assert summary["warnings"] == 1


def test_mini_benchmark_runner_cli_outputs_json():
    result = subprocess.run(
        [
            sys.executable,
            str(SKILL_DIR / "tools" / "mini_benchmark_runner.py"),
            "--benchmark",
            str(SKILL_DIR / "evals" / "mini_contest_benchmark.json"),
            "--mode",
            "strict",
        ],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["cases_checked"] >= 6
