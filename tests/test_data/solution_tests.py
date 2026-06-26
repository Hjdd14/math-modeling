#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试夹具契约测试"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_validation_summary_exists():
    assert (ROOT / "results" / "validation_summary.json").exists()


def test_validation_summary_core_fields():
    data = json.loads((ROOT / "results" / "validation_summary.json").read_text(encoding="utf-8"))
    for key in ["baseline_comparison", "oracle_tests", "solver_cross_checks", "constraint_residuals"]:
        assert key in data

