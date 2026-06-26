#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""示例解答契约测试"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_required_outputs_exist():
    for path in ["results/output.csv", "results/summary.json", "results/validation_summary.json"]:
        assert (ROOT / path).exists()


def test_validation_summary_has_quality_fields():
    data = json.loads((ROOT / "results" / "validation_summary.json").read_text(encoding="utf-8"))
    for key in ["baseline_comparison", "oracle_tests", "solver_cross_checks", "constraint_residuals", "optimality_gap"]:
        assert key in data

