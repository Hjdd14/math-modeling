#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evidence_checker 可信度证据检查测试"""

import json

from tools import evidence_checker


def write_validation_summary(workspace, payload):
    results = workspace / "results"
    results.mkdir()
    path = results / "validation_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def complete_payload():
    return {
        "baseline_comparison": {
            "baseline_name": "naive_feasible_solution",
            "metric": "objective",
            "baseline_value": 120.0,
            "model_value": 156.0,
            "passed": True,
        },
        "oracle_tests": [
            {
                "name": "brute_force_small_integer_program",
                "expected": 18,
                "actual": 18,
                "passed": True,
            }
        ],
        "solver_cross_checks": [
            {
                "name": "enumeration_vs_scipy",
                "primary": 156.0,
                "secondary": 156.0,
                "passed": True,
            }
        ],
        "sensitivity_analysis": {
            "method": "one_at_a_time",
            "max_relative_change": 0.08,
            "passed": True,
        },
        "invariants": [
            {
                "name": "capacity_constraints_nonnegative",
                "passed": True,
            }
        ],
        "failure_modes": [
            {
                "name": "missing_data",
                "impact": "fallback_to_baseline",
                "mitigation": "report_and_skip_invalid_rows",
            }
        ],
    }


def test_complete_validation_summary_passes_strict_mode(tmp_path):
    write_validation_summary(tmp_path, complete_payload())

    result = evidence_checker.check_evidence(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert result["exists"] is True
    assert all(item["passed"] for item in result["checks"])


def test_missing_validation_summary_is_warning_in_standard_mode(tmp_path):
    result = evidence_checker.check_evidence(str(tmp_path), mode="standard")

    assert result["passed"] is True
    assert result["warning"] is True
    assert result["exists"] is False
    assert result["issues"][0]["severity"] == "warning"


def test_missing_baseline_fails_in_strict_mode(tmp_path):
    payload = complete_payload()
    payload.pop("baseline_comparison")
    write_validation_summary(tmp_path, payload)

    result = evidence_checker.check_evidence(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["check"] == "baseline_comparison" for issue in result["issues"])


def test_missing_oracle_fails_in_strict_mode(tmp_path):
    payload = complete_payload()
    payload.pop("oracle_tests")
    write_validation_summary(tmp_path, payload)

    result = evidence_checker.check_evidence(str(tmp_path), mode="strict")

    assert result["passed"] is False
    assert any(issue["check"] == "oracle_tests" for issue in result["issues"])


def test_failed_sensitivity_fails_even_in_standard_mode(tmp_path):
    payload = complete_payload()
    payload["sensitivity_analysis"]["passed"] = False
    write_validation_summary(tmp_path, payload)

    result = evidence_checker.check_evidence(str(tmp_path), mode="standard")

    assert result["passed"] is False
    assert any(issue["check"] == "sensitivity_analysis" for issue in result["issues"])


def test_invalid_json_fails(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "validation_summary.json").write_text("{not-json", encoding="utf-8")

    result = evidence_checker.check_evidence(str(tmp_path), mode="standard")

    assert result["passed"] is False
    assert result["issues"][0]["check"] == "validation_summary_json"


def test_integer_program_oracle_fixture_documents_bruteforce_check(tmp_path):
    payload = complete_payload()
    payload["oracle_tests"] = [
        {
            "name": "brute_force_two_variable_integer_fixture",
            "method": "enumerate all x,y in [0, 8]",
            "expected": {"objective": 18, "x": 3, "y": 4},
            "actual": {"objective": 18, "x": 3, "y": 4},
            "passed": True,
        }
    ]
    write_validation_summary(tmp_path, payload)

    result = evidence_checker.check_evidence(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert "brute_force" in json.dumps(result, ensure_ascii=False)


def test_forecasting_fixture_documents_naive_baseline_and_holdout(tmp_path):
    payload = complete_payload()
    payload["baseline_comparison"] = {
        "baseline_name": "naive_last_value",
        "holdout_metric": "MAE",
        "baseline_value": 4.2,
        "model_value": 3.1,
        "passed": True,
    }
    write_validation_summary(tmp_path, payload)

    result = evidence_checker.check_evidence(str(tmp_path), mode="strict")

    assert result["passed"] is True
    assert "naive_last_value" in json.dumps(result, ensure_ascii=False)
