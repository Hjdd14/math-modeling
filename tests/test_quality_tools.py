#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.2.0 质量闭环工具测试"""

import hashlib
import json
import shutil
from pathlib import Path

from tools import (
    figure_auditor,
    manifest_checker,
    model_spec_checker,
    robustness_checker,
    schema_checker,
    solution_test_generator,
    unit_checker,
    writer_prompt_checker,
)


SKILL_DIR = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_schema_checker_validates_csv_contract(tmp_path):
    (tmp_path / "data.csv").write_text("id,value,group\n1,10,A\n2,20,B\n", encoding="utf-8")
    write_json(
        tmp_path / "data_schema.json",
        {
            "datasets": [
                {
                    "path": "data.csv",
                    "primary_key": ["id"],
                    "fields": [
                        {"name": "id", "type": "integer", "required": True},
                        {"name": "value", "type": "number", "unit": "kg", "min": 0, "max": 100, "required": True},
                        {"name": "group", "type": "string"},
                    ],
                }
            ]
        },
    )

    result = schema_checker.check_schema(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["datasets_checked"] == 1
    assert any(check["name"] == "columns_present" and check["passed"] for check in result["checks"])


def test_schema_checker_fails_on_missing_required_column(tmp_path):
    (tmp_path / "data.csv").write_text("id,value\n1,10\n", encoding="utf-8")
    write_json(
        tmp_path / "data_schema.json",
        {
            "datasets": [
                {
                    "path": "data.csv",
                    "fields": [
                        {"name": "id", "type": "integer", "required": True},
                        {"name": "missing_col", "type": "number", "required": True},
                    ],
                }
            ]
        },
    )

    result = schema_checker.check_schema(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_column" for issue in result["issues"])


def test_schema_checker_standard_mode_warns_when_schema_missing(tmp_path):
    result = schema_checker.check_schema(str(tmp_path), mode="standard")

    assert result["passed"] is True
    assert result["warning"] is True


def test_model_spec_checker_validates_required_model_sections(tmp_path):
    (tmp_path / "model_decision.md").write_text("## 模型建立\n变量 x 表示产量。\n", encoding="utf-8")
    (tmp_path / "writer_prompt.md").write_text(
        "# 写作交接提示词\n\n本 skill 不生成正式写作正文，只提供写作交接材料。\n\n变量 x 应在模型说明中解释。\n",
        encoding="utf-8",
    )
    (tmp_path / "solution.py").write_text("x = 3\nprint(x)\n", encoding="utf-8")
    write_json(
        tmp_path / "model_spec.json",
        {
            "variables": [{"name": "x", "type": "decision", "unit": "件", "bounds": [0, 10]}],
            "objective": {"sense": "max", "expression": "5*x"},
            "constraints": [{"name": "capacity", "expression": "x <= 10"}],
            "parameters": [{"name": "profit", "unit": "元/件", "value": 5}],
            "data_fields": [{"name": "value", "unit": "件"}],
            "validation_plan": {"oracle": "small enumeration", "sensitivity": "profit perturbation"},
        },
    )

    result = model_spec_checker.check_model_spec(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert any(check["name"] == "required_sections" and check["passed"] for check in result["checks"])


def test_model_spec_checker_fails_without_constraints_in_strict_mode(tmp_path):
    write_json(
        tmp_path / "model_spec.json",
        {
            "variables": [{"name": "x"}],
            "objective": {"sense": "max", "expression": "x"},
            "parameters": [],
            "data_fields": [],
            "validation_plan": {},
        },
    )

    result = model_spec_checker.check_model_spec(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_model_spec_section" for issue in result["issues"])


def test_unit_checker_validates_symbol_table(tmp_path):
    write_json(
        tmp_path / "symbol_table.json",
        {
            "symbols": [
                {"symbol": "x", "meaning": "产量", "unit": "件", "code_name": "x"},
                {"symbol": "p", "meaning": "单位利润", "unit": "元/件", "code_name": "profit"},
            ]
        },
    )

    result = unit_checker.check_units(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["symbols_checked"] == 2


def test_unit_checker_fails_on_missing_unit(tmp_path):
    write_json(tmp_path / "symbol_table.json", {"symbols": [{"symbol": "x", "meaning": "产量"}]})

    result = unit_checker.check_units(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_symbol_field" for issue in result["issues"])


def test_solution_test_generator_writes_pytest_contract(tmp_path):
    result = solution_test_generator.generate_solution_tests(str(tmp_path), language="python")

    generated = tmp_path / "solution_tests.py"
    content = generated.read_text(encoding="utf-8")
    assert result["passed"] is True
    assert generated.exists()
    assert "test_required_outputs_exist" in content
    assert "validation_summary.json" in content
    assert "constraint_residuals" in content


def full_validation_summary() -> dict:
    return {
        "baseline_comparison": {"baseline_name": "naive", "passed": True},
        "oracle_tests": [{"name": "known_case", "passed": True}],
        "solver_cross_checks": [{"name": "alternate_solver", "passed": True}],
        "sensitivity_analysis": {"method": "one_at_a_time", "passed": True},
        "invariants": [{"name": "nonnegative_outputs", "passed": True}],
        "failure_modes": [{"name": "empty_input", "mitigation": "stop_with_error"}],
        "constraint_residuals": {"max_abs": 0.0, "passed": True},
        "optimality_gap": {"value": 0.0, "passed": True},
        "multi_start": {"runs": 5, "best_values": [10, 10, 10], "passed": True},
        "random_seed_stability": {"seeds": [1, 2, 3], "std": 0.0, "passed": True},
        "bootstrap_confidence_interval": {"level": 0.95, "lower": 9.5, "upper": 10.5, "passed": True},
        "perturbation_stability": {"ranking_changed": False, "passed": True},
    }


def test_robustness_checker_requires_numeric_stability_evidence(tmp_path):
    (tmp_path / "results").mkdir()
    write_json(tmp_path / "results" / "validation_summary.json", full_validation_summary())

    result = robustness_checker.check_robustness(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["evidence_items_checked"] >= 6


def test_robustness_checker_fails_when_stability_evidence_missing(tmp_path):
    (tmp_path / "results").mkdir()
    summary = full_validation_summary()
    summary.pop("perturbation_stability")
    write_json(tmp_path / "results" / "validation_summary.json", summary)

    result = robustness_checker.check_robustness(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_robustness_item" for issue in result["issues"])


def test_figure_auditor_writes_publication_quality_report(tmp_path):
    (tmp_path / "results").mkdir()
    shutil.copy2(SKILL_DIR / "tests" / "test_figures" / "normal.png", tmp_path / "results" / "core_result.png")
    write_json(
        tmp_path / "figure_style.json",
        {"dpi": 300, "font_size": 10, "colorblind_safe": True, "formats": ["png", "pdf"]},
    )
    (tmp_path / "figure_storyboard.md").write_text(
        "# Figure Storyboard\n\n- file: core_result.png\n  claim: 最优结果优于 baseline\n  source_data: results/output.csv\n  x_unit: 产品\n  y_unit: 收益\n  supports_question: Q1\n",
        encoding="utf-8",
    )

    result = figure_auditor.audit_figures(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["figures_audited"] == 1
    assert (tmp_path / "results" / "figure_quality_report.json").exists()


def test_writer_prompt_checker_checks_handoff_structure(tmp_path):
    (tmp_path / "writer_prompt.md").write_text(
        """
# 写作交接提示词
本 skill 已完成建模、代码、图表和验证证据，不生成正式写作正文，只提供写作交接材料。
## 题目与评分
- problem_brief.md
## 模型主线
- final_solution.json
## 代码与结果
- results/validation_summary.json
## 图表证据
- figure_storyboard.md
## 验证证据
- reproducibility_manifest.json
## 合规与风险
- judge_panel_review.json
- compliance_record.json
后续写作需披露风险与合规信息。
## 后续写作/提交复核清单
- 匿名、引用、AI 披露、页数、附件和代码提交均需按官方规则复核。
""".strip(),
        encoding="utf-8",
    )

    result = writer_prompt_checker.check_writer_prompt(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["sections_found"] >= 6


def test_writer_prompt_checker_fails_when_prompt_asks_for_formal_body(tmp_path):
    (tmp_path / "writer_prompt.md").write_text("# 正文\n请直接写完整论文。", encoding="utf-8")

    result = writer_prompt_checker.check_writer_prompt(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "writer_prompt_missing_boundary" for issue in result["issues"])


def test_manifest_checker_verifies_reproducibility_hashes(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "data.csv").write_text("id,value\n1,10\n", encoding="utf-8")
    (tmp_path / "results" / "output.csv").write_text("x,value\n1,10\n", encoding="utf-8")
    write_json(
        tmp_path / "reproducibility_manifest.json",
        {
            "os": {"name": "Windows", "version": "11"},
            "python_version": "3.14",
            "matlab_version": None,
            "dependencies": {"numpy": "2.0"},
            "random_seed": 42,
            "solvers": [{"name": "enumeration", "version": "builtin"}],
            "random_libraries": [{"name": "numpy.random", "seed": 42}],
            "execution": {"seconds": 0.1},
            "input_hashes": [{"path": "data.csv", "sha256": sha256(tmp_path / "data.csv")}],
            "output_hashes": [{"path": "results/output.csv", "sha256": sha256(tmp_path / "results" / "output.csv")}],
        },
    )

    result = manifest_checker.check_manifest(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["hashes_checked"] == 2


def test_manifest_checker_fails_on_hash_mismatch(tmp_path):
    (tmp_path / "data.csv").write_text("id,value\n1,10\n", encoding="utf-8")
    write_json(
        tmp_path / "reproducibility_manifest.json",
        {
            "os": {"name": "Windows", "version": "11"},
            "python_version": "3.14",
            "dependencies": {},
            "random_seed": 42,
            "solvers": [{"name": "enumeration"}],
            "random_libraries": [{"name": "numpy.random", "seed": 42}],
            "execution": {"seconds": 0.1},
            "input_hashes": [{"path": "data.csv", "sha256": "wrong"}],
            "output_hashes": [],
        },
    )

    result = manifest_checker.check_manifest(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["code"] == "hash_mismatch" for issue in result["issues"])
