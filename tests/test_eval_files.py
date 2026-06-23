#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval 配置文件测试"""

import json
import os


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_task_evals_schema():
    path = os.path.join(SKILL_DIR, "evals", "evals.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["skill_name"] == "math-modeling"
    assert len(data["evals"]) >= 5
    for item in data["evals"]:
        assert {"id", "prompt", "expected_output", "assertions"} <= set(item)
        assert any("并行" in assertion for assertion in item["assertions"])


def test_trigger_eval_has_positive_and_negative_cases():
    path = os.path.join(SKILL_DIR, "evals", "trigger_eval.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 20
    positives = [item for item in data if item["should_trigger"]]
    negatives = [item for item in data if not item["should_trigger"]]
    assert len(positives) >= 8
    assert len(negatives) >= 8
    assert any("数学建模" in item["query"] for item in positives)
    assert any("翻译" in item["query"] for item in negatives)
