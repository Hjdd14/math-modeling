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
    }
    (workspace / "results" / "validation_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
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


def test_pipeline_check_fails_when_results_are_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    shutil.rmtree(workspace / "results")
    result = pipeline_check.run_checks(str(workspace), "python")
    assert result["passed"] is False
    assert result["checks"]["required_files"]["passed"] is False
    assert "results" in "\n".join(result["checks"]["required_files"]["missing"])
