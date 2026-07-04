#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workflow_runner 编排入口测试"""

import os
import shutil

from tools import workflow_runner
from tools import state_manager


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def test_scaffold_creates_workspace_state_and_results_dir(tmp_path):
    result = workflow_runner.scaffold_workspace(str(tmp_path), "python")
    assert result["state"]["language"] == "python"
    assert (tmp_path / "modeling_state.json").exists()
    assert (tmp_path / "modeling_memory.md").exists()
    assert (tmp_path / "results").is_dir()


def test_resume_infers_existing_workspace_without_state(tmp_path):
    for name in ["problem_brief.md", "writer_prompt.md", "solution.py"]:
        shutil.copy2(os.path.join(TEST_DATA, name), tmp_path / name)
    shutil.copytree(os.path.join(TEST_DATA, "results"), tmp_path / "results", dirs_exist_ok=True)

    result = workflow_runner.resume_workspace(str(tmp_path), "python")
    assert result["state"]["artifacts"]["problem_brief"]["exists"] is True
    assert result["state"]["artifacts"]["writer_prompt"]["exists"] is True
    assert result["state"]["artifacts"]["results_dir"]["exists"] is True


def test_resume_preserves_existing_phase_tool_and_agent_history(tmp_path):
    state_manager.init_state(str(tmp_path), "python")
    state_manager.update_phase(str(tmp_path), "phase1", "completed")
    state_manager.record_tool_run(str(tmp_path), "latex_validator", "passed", score=100, summary="ok")
    state_manager.record_agent_run(
        str(tmp_path),
        "phase1",
        "optimizer",
        "initial_modeling_agent",
        "completed",
        "generated initial solution",
        "agent_outputs/phase1/initial_solutions.json",
    )

    for name in ["problem_brief.md", "writer_prompt.md", "solution.py"]:
        shutil.copy2(os.path.join(TEST_DATA, name), tmp_path / name)
    shutil.copytree(os.path.join(TEST_DATA, "results"), tmp_path / "results", dirs_exist_ok=True)

    result = workflow_runner.resume_workspace(str(tmp_path), "python")

    assert result["state"]["current_phase"] == "phase4"
    assert result["state"]["phases"]["phase1"]["status"] == "completed"
    assert result["state"]["tool_runs"][0]["name"] == "latex_validator"
    assert result["state"]["agent_runs"][0]["agent"] == "optimizer"


def test_verify_delegates_to_pipeline_check(tmp_path):
    for name in ["problem_brief.md", "writer_prompt.md", "solution.py"]:
        shutil.copy2(os.path.join(TEST_DATA, name), tmp_path / name)
    shutil.copytree(os.path.join(TEST_DATA, "results"), tmp_path / "results")

    result = workflow_runner.verify_workspace(str(tmp_path), "python")
    assert result["passed"] is True
