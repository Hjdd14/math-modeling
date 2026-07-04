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


def test_hard_problem_evals_cover_evidence_chain():
    path = os.path.join(SKILL_DIR, "evals", "evals.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hard_evals = [item for item in data["evals"] if item.get("category") == "hard_problem"]
    assert len(hard_evals) >= 5
    prompts = "\n".join(item["prompt"] for item in hard_evals)
    for keyword in ["多目标", "缺失数据", "图", "随机", "非线性"]:
        assert keyword in prompts

    for item in hard_evals:
        assertions = "\n".join(item["assertions"])
        assert "题意审计" in assertions
        assert "baseline" in assertions
        assert "动态专家" in assertions
        assert "validation_summary.json" in assertions
        assert "独立复现" in assertions


def test_excellence_evals_cover_quality_chain():
    path = os.path.join(SKILL_DIR, "evals", "evals.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    quality_evals = [item for item in data["evals"] if item.get("category") == "excellence_delivery"]
    assert len(quality_evals) >= 4
    combined = "\n".join(
        item["prompt"] + "\n" + "\n".join(item["assertions"])
        for item in quality_evals
    )
    for keyword in [
        "model_spec.json",
        "data_schema.json",
        "solution_tests.py",
        "figure_auditor.py",
        "figure_storyboard.md",
        "writer_prompt.md",
        "innovation_register.json",
        "judge_panel_review.json",
        "compliance_record.json",
        "reproducibility_manifest.json",
        "defense_questions.md",
    ]:
        assert keyword in combined


def test_award_delivery_evals_cover_handoff_and_compliance_chain():
    path = os.path.join(SKILL_DIR, "evals", "evals.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    award_evals = [item for item in data["evals"] if item.get("category") == "award_delivery"]
    assert len(award_evals) >= 3
    combined = "\n".join(
        item["prompt"] + "\n" + "\n".join(item["assertions"])
        for item in award_evals
    )
    for keyword in [
        "不生成正式写作正文",
        "writer_prompt.md",
        "innovation_register.json",
        "judge_panel_review.json",
        "compliance_record.json",
        "多评委并行审查",
    ]:
        assert keyword in combined


def test_competition_repository_evals_cover_new_source_families():
    path = os.path.join(SKILL_DIR, "evals", "evals.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    source_evals = [item for item in data["evals"] if item.get("category") == "competition_repository"]
    assert len(source_evals) >= 7
    combined = "\n".join(
        item["prompt"] + "\n" + "\n".join(item["assertions"])
        for item in source_evals
    )
    for keyword in ["MathorCup", "电工杯", "统计建模", "深圳杯", "研究生赛", "APMCM", "五一杯"]:
        assert keyword in combined
    for item in source_evals:
        assertions = "\n".join(item["assertions"])
        assert "资料库检索" in assertions
        assert "case_retrieval.json" in assertions
        assert "模型选择" in assertions
        assert "results/validation_summary.json" in assertions
        assert "图表证据" in assertions
        assert "多评委审查" in assertions


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
