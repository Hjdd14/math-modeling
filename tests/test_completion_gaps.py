#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划尾项完成度回归测试"""

import json
from pathlib import Path

from tools import mini_benchmark_checker
from tools import pipeline_check
from tools import writer_prompt_checker


SKILL_DIR = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (SKILL_DIR / path).read_text(encoding="utf-8")


def test_legacy_formal_report_auditor_removed_from_official_surface():
    """正式链路不得再暴露旧报告审计器和 report_quality_report 产物。"""
    assert not (SKILL_DIR / "tools" / "report_auditor.py").exists()
    assert not (SKILL_DIR / "tests" / "test_data" / "report_quality_report.json").exists()
    assert not (SKILL_DIR / "examples" / "solved-python" / "report_quality_report.json").exists()

    official_docs = "\n".join(
        read_text(path)
        for path in [
            "SKILL.md",
            "README.md",
            "references/workflow.md",
            "references/templates.md",
            "references/tools.md",
            "docs/RELEASE_CHECKLIST.md",
            "evals/evals.json",
        ]
    )
    assert "report_auditor.py" not in official_docs
    assert "report_quality_report.json" not in official_docs
    assert "modeling_report.md" not in official_docs


def test_writer_prompt_checker_replaces_report_quality_gate():
    result = writer_prompt_checker.check_writer_prompt(str(SKILL_DIR / "tests" / "test_data"), mode="excellence")

    assert result["passed"] is True
    assert result["sections_found"] >= 6
    assert (SKILL_DIR / "tests" / "test_data" / "writer_prompt_quality.json").exists()


def test_pipeline_excellence_uses_writer_prompt_quality_report():
    result = pipeline_check.run_checks(
        str(SKILL_DIR / "tests" / "test_data"),
        "python",
        evidence_mode="strict",
        quality_mode="excellence",
    )

    assert result["passed"] is True
    assert "writer_prompt_checker" in result["checks"]
    assert result["checks"]["writer_prompt_checker"]["passed"] is True
    assert "report_auditor" not in result["checks"]


def test_mini_contest_benchmark_has_oracles_and_review_artifact():
    benchmark_path = SKILL_DIR / "evals" / "mini_contest_benchmark.json"
    review_path = SKILL_DIR / "evals" / "award_eval_review.json"

    assert benchmark_path.exists()
    assert review_path.exists()

    result = mini_benchmark_checker.check_benchmark(str(benchmark_path), mode="strict")
    assert result["passed"] is True
    assert result["cases_checked"] >= 6
    assert all(item["has_oracle"] for item in result["case_summaries"])

    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["review_method"] == "skill-creator eval viewer"
    assert {"old_skill", "new_skill"} <= set(review["comparison_targets"])
    assert len(review["rubric"]) >= 5
