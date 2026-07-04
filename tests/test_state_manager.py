#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""state_manager 工具测试"""

import subprocess
import sys
from pathlib import Path

from tools import state_manager


def test_state_manager_records_phase_artifacts_tools_and_agents(tmp_path):
    state = state_manager.init_state(str(tmp_path), "python")
    assert state["schema_version"] == 1
    assert state["language"] == "python"
    assert (tmp_path / "modeling_state.json").exists()

    brief = tmp_path / "problem_brief.md"
    brief.write_text("# brief", encoding="utf-8")

    state_manager.record_artifact(str(tmp_path), "problem_brief", str(brief))
    state_manager.update_phase(str(tmp_path), "phase1", "completed")
    state_manager.record_tool_run(str(tmp_path), "brief_validator", "passed", score=95.0, summary="ok")
    state_manager.record_agent_run(
        str(tmp_path),
        "phase1",
        "initial_optimizer",
        "optimizer",
        "completed",
        "线性规划方案",
        "final_solution.json",
    )

    loaded = state_manager.load_state(str(tmp_path))
    assert loaded["current_phase"] == "phase1"
    assert loaded["phases"]["phase1"]["status"] == "completed"
    assert loaded["artifacts"]["problem_brief"]["exists"] is True
    assert loaded["tool_runs"][0]["name"] == "brief_validator"
    assert loaded["agent_runs"][0]["agent"] == "initial_optimizer"


def test_inspect_workspace_infers_existing_artifacts(tmp_path):
    for name in ["problem_brief.md", "final_solution.json", "writer_prompt.md", "solution.py"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "results").mkdir()

    result = state_manager.inspect_workspace(str(tmp_path), "python")
    assert result["artifacts"]["problem_brief"]["exists"] is True
    assert result["artifacts"]["final_solution"]["exists"] is True
    assert result["artifacts"]["solution"]["path"].endswith("solution.py")
    assert result["artifacts"]["results_dir"]["exists"] is True


def test_record_artifact_resolves_relative_path_inside_workspace(tmp_path, monkeypatch):
    state_manager.init_state(str(tmp_path), "python")
    (tmp_path / "final_solution.json").write_text("{}", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    state_manager.record_artifact(str(tmp_path), "final_solution", "final_solution.json")

    loaded = state_manager.load_state(str(tmp_path))
    artifact = loaded["artifacts"]["final_solution"]
    assert artifact["exists"] is True
    assert artifact["path"] == "final_solution.json"


def test_concurrent_tool_run_updates_are_not_lost(tmp_path):
    state_manager.init_state(str(tmp_path), "python")
    script = Path(state_manager.__file__).resolve()
    processes = []
    for index in range(12):
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(script),
                    "tool-run",
                    "--workspace",
                    str(tmp_path),
                    "--name",
                    f"tool_{index}",
                    "--status",
                    "passed",
                    "--summary",
                    "ok",
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    failures = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=20)
        if process.returncode != 0:
            failures.append((process.returncode, stdout, stderr))

    assert failures == []
    loaded = state_manager.load_state(str(tmp_path))
    assert {run["name"] for run in loaded["tool_runs"]} == {f"tool_{i}" for i in range(12)}
