#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MATLAB 支持测试"""

import os
import shutil
import subprocess
import sys

import pytest


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_matlab_template_and_fixture_use_results_dir():
    templates = os.path.join(SKILL_DIR, "references", "templates.md")
    fixture = os.path.join(SKILL_DIR, "tests", "test_data", "solution.m")

    with open(templates, "r", encoding="utf-8") as f:
        template_content = f.read()
    with open(fixture, "r", encoding="utf-8") as f:
        fixture_content = f.read()

    assert "MATLAB" in template_content
    assert "results" in template_content
    assert "results" in fixture_content
    assert "writetable" in fixture_content or "writecell" in fixture_content
    assert "validation_summary.json" in template_content
    assert "validation_summary.json" in fixture_content
    assert "run_baseline" in template_content
    assert "run_known_case_tests" in template_content
    assert "run_sensitivity_analysis" in template_content


def test_matlab_fixture_optional_runtime(tmp_path):
    if shutil.which("matlab") is None or os.environ.get("RUN_MATLAB_TESTS") != "1":
        pytest.skip("设置 RUN_MATLAB_TESTS=1 且安装 MATLAB 后运行实测")

    fixture = os.path.join(SKILL_DIR, "tests", "test_data", "solution.m")
    work_file = tmp_path / "solution.m"
    shutil.copy2(fixture, work_file)
    result = subprocess.run(
        [sys.executable, os.path.join(SKILL_DIR, "tools", "code_runner.py"), "run", "--file", str(work_file), "--lang", "matlab", "--timeout", "180"],
        capture_output=True,
        text=True,
        cwd=SKILL_DIR,
    )
    assert result.returncode == 0
    assert '"success": true' in result.stdout
