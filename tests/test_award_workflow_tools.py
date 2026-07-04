#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奖项级建模与代码交付工具测试"""

import json

from tools import compliance_checker
from tools import innovation_checker
from tools import judge_panel_checker
from tools import robustness_checker
from tools import solution_test_generator


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_innovation_register():
    return {
        "innovations": [
            {
                "id": "I1",
                "claim": "用 Pareto 前沿筛选多目标调度方案",
                "problem_pain_point": "单一加权和会掩盖利润与碳排的冲突",
                "baseline_gain": {
                    "metric": "profit_per_emission",
                    "delta": 0.12,
                    "evidence": "ablation_study.json",
                },
                "implementation_cost": "medium",
                "interpretability": "可用 Pareto 图解释不同权衡方案",
                "verification_evidence": ["baseline_comparison", "ablation_study", "sensitivity_analysis"],
                "failure_risk": "数据过少时 Pareto 前沿可能不稳定",
                "decision": "accepted",
            }
        ]
    }


def valid_judge_panel_review():
    return {
        "judges": [
            {"judge_type": "national_modeling_judge", "score": 88, "issues": [], "passed": True},
            {"judge_type": "comap_judge", "score": 86, "issues": [], "passed": True},
            {"judge_type": "code_reproducibility_judge", "score": 91, "issues": [], "passed": True},
            {"judge_type": "figure_evidence_judge", "score": 84, "issues": [], "passed": True},
            {"judge_type": "engineering_business_judge", "score": 87, "issues": [], "passed": True},
        ],
        "chair_summary": {
            "overall_score": 87,
            "decision": "pass",
            "required_fixes": [],
            "summary": "模型、代码、图表和验证证据可以交给写作阶段。",
        },
    }


def valid_compliance_record():
    return {
        "ai_usage": {
            "used": True,
            "tools": [{"name": "Codex", "version": "GPT-5", "purpose": "代码与验证辅助"}],
            "disclosure_required": True,
            "human_reviewed": True,
        },
        "anonymity": {"checked": True, "identity_terms_found": []},
        "external_sources": [
            {"source": "COMAP instructions", "citation_location": "writer_prompt.md#sources"}
        ],
        "reproducibility": {
            "manifest": "reproducibility_manifest.json",
            "commands": ["python solution.py", "python tools/pipeline_check.py --quality-mode excellence"],
            "input_hashes_recorded": True,
            "output_hashes_recorded": True,
        },
    }


def test_innovation_checker_passes_when_every_claim_has_evidence(tmp_path):
    write_json(tmp_path / "innovation_register.json", valid_innovation_register())

    result = innovation_checker.check_innovations(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["innovations_checked"] == 1


def test_innovation_checker_fails_empty_or_unsupported_innovation(tmp_path):
    payload = valid_innovation_register()
    payload["innovations"][0]["baseline_gain"] = {}
    payload["innovations"][0]["verification_evidence"] = []
    payload["innovations"][0]["claim"] = "使用高级智能算法提升模型"
    write_json(tmp_path / "innovation_register.json", payload)

    result = innovation_checker.check_innovations(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] in {"missing_innovation_evidence", "vague_innovation_claim"} for issue in result["issues"])


def test_judge_panel_checker_requires_five_independent_judge_roles(tmp_path):
    write_json(tmp_path / "judge_panel_review.json", valid_judge_panel_review())

    result = judge_panel_checker.check_judge_panel(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["roles_present"] >= 5


def test_judge_panel_checker_fails_unresolved_high_severity_issue(tmp_path):
    payload = valid_judge_panel_review()
    payload["judges"][0]["issues"] = [
        {"severity": "high", "status": "open", "description": "模型没有证明约束可行性"}
    ]
    write_json(tmp_path / "judge_panel_review.json", payload)

    result = judge_panel_checker.check_judge_panel(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "unresolved_high_severity_issue" for issue in result["issues"])


def test_compliance_checker_validates_ai_anonymity_sources_and_reproducibility(tmp_path):
    write_json(tmp_path / "compliance_record.json", valid_compliance_record())

    result = compliance_checker.check_compliance(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["checks_passed"] >= 4


def test_compliance_checker_fails_missing_disclosure_or_identity_leak(tmp_path):
    payload = valid_compliance_record()
    payload["ai_usage"].pop("tools")
    payload["anonymity"]["identity_terms_found"] = ["某某大学"]
    write_json(tmp_path / "compliance_record.json", payload)

    result = compliance_checker.check_compliance(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_ai_usage_detail" for issue in result["issues"])
    assert any(issue["code"] == "identity_leak" for issue in result["issues"])


def test_solution_test_generator_creates_real_contract_tests(tmp_path):
    result = solution_test_generator.generate_solution_tests(str(tmp_path), language="python")

    content = (tmp_path / "solution_tests.py").read_text(encoding="utf-8")

    assert result["passed"] is True
    for expected in [
        "test_constraint_invariants_pass",
        "test_oracle_checks_pass",
        "test_baseline_not_worse_than_required_threshold",
        "test_random_seed_stability_recorded",
    ]:
        assert expected in content


def test_robustness_checker_fails_bad_numeric_threshold_even_if_marked_passed(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(
        tmp_path / "results" / "validation_summary.json",
        {
            "constraint_residuals": {"max_abs": 0.5, "tolerance": 1e-6, "passed": True},
            "optimality_gap": {"value": 0.25, "tolerance": 1e-4, "passed": True},
            "multi_start": {"runs": 1, "best_values": [10], "passed": True},
            "random_seed_stability": {"seeds": [42], "std": 0.0, "passed": True},
            "bootstrap_confidence_interval": {"level": 0.95, "lower": 9, "upper": 11, "passed": True},
            "perturbation_stability": {"ranking_changed": False, "passed": True},
        },
    )

    result = robustness_checker.check_robustness(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "robustness_threshold_failed" for issue in result["issues"])
