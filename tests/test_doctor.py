#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor 体验检查工具测试"""

import json
import subprocess
import sys
from pathlib import Path

from tools import doctor


SKILL_DIR = Path(__file__).resolve().parents[1]
TOOL = SKILL_DIR / "tools" / "doctor.py"


def test_doctor_reports_required_files_and_dependencies():
    result = doctor.run_doctor(str(SKILL_DIR))
    check_names = {check["name"] for check in result["checks"]}

    assert "required_files" in check_names
    assert "runtime_dependencies" in check_names
    assert "git_repository" in check_names
    assert "quickstart_example" in check_names
    assert result["summary"]["failed"] == 0


def test_doctor_cli_outputs_json():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--workspace", str(SKILL_DIR)],
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["workspace"].endswith("math-modeling")
    assert "checks" in payload
    assert payload["summary"]["total"] >= 4
