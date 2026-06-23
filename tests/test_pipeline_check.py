#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline_check 总控验证测试"""

import os
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


def test_pipeline_check_fails_when_results_are_missing(tmp_path):
    workspace = copy_workspace(tmp_path)
    shutil.rmtree(workspace / "results")
    result = pipeline_check.run_checks(str(workspace), "python")
    assert result["passed"] is False
    assert result["checks"]["required_files"]["passed"] is False
    assert "results" in "\n".join(result["checks"]["required_files"]["missing"])
