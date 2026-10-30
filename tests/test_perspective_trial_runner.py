#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perspective_trial_runner 测试：真跑子进程、追加留痕、覆盖矩阵、stale 判定。

对应契约 §7 / §8.2：run 是 perspective_trials.json 的唯一写入口，同一 (perspective, slice)
永不覆盖旧记录，script_sha256 变了但没重跑的 run 必须被 verify 标 stale。
"""

import json
import os
import subprocess
import sys

import pytest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

from tools import perspective_trial_runner as runner


TOOL = os.path.join(SKILL_DIR, "tools", "perspective_trial_runner.py")

OK_SCRIPT = (
    "import argparse, json\n"
    "parser = argparse.ArgumentParser()\n"
    'parser.add_argument("--slice", default="full")\n'
    "args = parser.parse_args()\n"
    'print("trace line before json")\n'
    'print(json.dumps({"comparable": {"primary_error": 0.9}, "own": {"p_value": 0.9}}))\n'
    'print(json.dumps({"comparable": {"primary_error": 0.5}, "own": {"p_value": 0.0258}}))\n'
)

DEFAULT_SLICES = [
    {"slice_id": "full", "description": "全部数据", "data_ref": "data.csv", "selector": {"rows": "all"}},
    {"slice_id": "holdout_b", "description": "留出 20%", "data_ref": "data.csv", "selector": {"rows": "56..70"}},
]


def write_script(workspace, name, body):
    """在工作区写一个试算脚本（perspective_trials/<name>.py）。"""
    path = workspace / "perspective_trials" / (name + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def write_slices(workspace, slices=None, **extra):
    """写 --slices 规格文件。"""
    payload = {"slices": list(slices if slices is not None else DEFAULT_SLICES)}
    payload.update(extra)
    path = workspace / "slices.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def open_trials(workspace, slices=None, **kwargs):
    """初始化 trials 文档（默认两个切片）。"""
    spec = write_slices(workspace, slices)
    return runner.open_document(str(workspace), str(spec), **kwargs)


def load_doc(workspace):
    """读回 perspective_trials.json。"""
    return json.loads((workspace / "perspective_trials.json").read_text(encoding="utf-8"))


def run_cli(*args):
    """以子进程方式跑 CLI，断言 stdout/stderr/退出码契约。"""
    return subprocess.run(
        [sys.executable, TOOL, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=SKILL_DIR,
    )


def test_open_initializes_document(tmp_path):
    result = open_trials(tmp_path, question_id="Q1")

    assert result["ok"] is True
    doc = load_doc(tmp_path)
    assert doc["schema_version"] == 2
    assert doc["generated_by"] == "tools/perspective_trial_runner.py"
    assert doc["question_id"] == "Q1"
    assert doc["slice_axis"] == "data_rows"
    assert [item["slice_id"] for item in doc["slices"]] == ["full", "holdout_b"]
    assert doc["perspectives"] == []
    assert [item["key"] for item in doc["metric_definitions"]["comparable"]] == ["runtime_s", "finished"]
    # run_id 是时间戳 + 6 位十六进制，供多轮试算区分
    assert doc["run_id"].count("-") >= 3
    assert result["warnings"] == []


def test_open_requires_note_for_parameter_axis(tmp_path):
    with pytest.raises(ValueError, match="slice_axis_note"):
        open_trials(tmp_path, axis="parameter")

    result = open_trials(tmp_path, axis="parameter", note="参数轴：在不同初始半径下各跑一次")
    doc = load_doc(tmp_path)
    assert result["ok"] is True
    assert doc["slice_axis"] == "parameter"
    assert "初始半径" in doc["slice_axis_note"]


def test_open_refuses_overwrite_without_force(tmp_path):
    open_trials(tmp_path)
    with pytest.raises(ValueError, match="--force"):
        open_trials(tmp_path)

    forced = open_trials(tmp_path, force=True)
    assert forced["ok"] is True
    assert load_doc(tmp_path)["perspectives"] == []


def test_open_warns_when_single_slice(tmp_path):
    result = open_trials(tmp_path, slices=[DEFAULT_SLICES[0]])
    assert result["ok"] is True
    assert any("slices" in warning for warning in result["warnings"])


def test_run_records_tool_execution(tmp_path):
    open_trials(tmp_path, question_id="Q1")
    script = write_script(tmp_path, "statistician", OK_SCRIPT)

    result = runner.run_trial(str(tmp_path), "statistician", "O1", "full")
    assert result["ok"] is True
    record = result["record"]

    assert record["executed_by"] == "tool"
    assert record["exit_code"] == 0
    assert record["runner_version"] == "1.0"
    assert record["run_seq"] == 1
    assert record["runtime_s"] > 0
    assert len(record["stdout_sha256"]) == 64
    assert record["script_sha256"] == runner._hash_file(script)
    assert record["captured_at"]
    assert "perspective_trial_runner.py run" in record["reproduce_cmd"]
    assert "--perspective statistician" in record["reproduce_cmd"]
    # metrics 取 stdout 里最后一个 JSON 对象，而不是第一个
    assert record["metrics"]["own"]["p_value"] == pytest.approx(0.0258)
    assert record["metrics"]["comparable"]["primary_error"] == pytest.approx(0.5)
    # 可比层由 runner 计时，不采信脚本自报
    assert record["metrics"]["comparable"]["runtime_s"] == record["runtime_s"]
    assert record["metrics"]["comparable"]["finished"] is True

    doc = load_doc(tmp_path)
    entry = doc["perspectives"][0]
    assert entry["perspective"] == "statistician"
    assert entry["option_id"] == "O1"
    assert entry["script"] == "perspective_trials/statistician.py"
    assert len(entry["runs"]) == 1


def test_run_appends_and_never_overwrites(tmp_path):
    open_trials(tmp_path)
    write_script(tmp_path, "statistician", OK_SCRIPT)

    first = runner.run_trial(str(tmp_path), "statistician", "O1", "full")
    snapshot = dict(first["record"])
    second = runner.run_trial(str(tmp_path), "statistician", "O1", "full")

    assert first["run_seq"] == 1
    assert second["run_seq"] == 2
    runs = load_doc(tmp_path)["perspectives"][0]["runs"]
    assert [run["run_seq"] for run in runs] == [1, 2]
    # 旧记录逐字段保留：追加写不是覆盖写
    assert runs[0] == snapshot


def test_run_failure_writes_record_and_cli_exits_nonzero(tmp_path):
    open_trials(tmp_path)
    write_script(tmp_path, "engineer", 'import sys\nprint("boom")\nsys.exit(3)\n')

    cli = run_cli("run", "--workspace", str(tmp_path), "--perspective", "engineer",
                  "--option-id", "O4", "--slice", "full")
    assert cli.returncode == 1
    payload = json.loads(cli.stdout)
    assert payload["ok"] is False
    record = payload["record"]
    assert record["exit_code"] == 3
    assert record["metrics"] is None
    assert record["executed_by"] == "tool"
    assert record["stdout_sha256"]
    # 失败也要落盘，留痕不能因为失败而丢
    assert load_doc(tmp_path)["perspectives"][0]["runs"][0]["exit_code"] == 3


def test_run_parse_failure_marks_parse_error(tmp_path):
    open_trials(tmp_path)
    write_script(tmp_path, "physicist", 'print("narrative output, no json")\n')

    result = runner.run_trial(str(tmp_path), "physicist", "O3", "full")
    assert result["ok"] is False
    record = result["record"]
    assert record["exit_code"] == 0
    assert record["metrics"] is None
    assert "JSON" in record["parse_error"]


def test_run_requires_open_and_known_slice(tmp_path):
    write_script(tmp_path, "statistician", OK_SCRIPT)
    with pytest.raises(FileNotFoundError, match="open"):
        runner.run_trial(str(tmp_path), "statistician", "O1", "full")

    open_trials(tmp_path)
    with pytest.raises(ValueError, match="不在 slices"):
        runner.run_trial(str(tmp_path), "statistician", "O1", "unknown_slice")
    with pytest.raises(ValueError, match="路径分隔符"):
        runner.run_trial(str(tmp_path), "../escape", "O1", "full")


def test_status_reports_coverage_matrix(tmp_path):
    open_trials(tmp_path)
    write_script(tmp_path, "statistician", OK_SCRIPT)
    write_script(tmp_path, "engineer", 'import sys\nsys.exit(2)\n')

    runner.run_trial(str(tmp_path), "statistician", "O1", "full")
    runner.run_trial(str(tmp_path), "engineer", "O4", "full")

    status = runner.trial_status(str(tmp_path))
    assert status["exists"] is True
    assert status["slices"] == ["full", "holdout_b"]
    assert status["perspectives"] == ["statistician", "engineer"]
    assert status["matrix"]["statistician"]["full"]["ok"] is True
    assert status["matrix"]["statistician"]["holdout_b"] is None
    assert status["matrix"]["engineer"]["full"]["ok"] is False
    missing = {(item["perspective"], item["slice"]) for item in status["missing"]}
    assert ("statistician", "holdout_b") in missing
    assert ("engineer", "holdout_b") in missing
    assert [item["perspective"] for item in status["failed"]] == ["engineer"]
    assert status["ready"] is False
    assert status["total_runs"] == 2


def test_status_ready_when_all_cells_succeed(tmp_path):
    open_trials(tmp_path)
    write_script(tmp_path, "statistician", OK_SCRIPT)
    for slice_id in ("full", "holdout_b"):
        runner.run_trial(str(tmp_path), "statistician", "O1", slice_id)

    status = runner.trial_status(str(tmp_path))
    assert status["missing"] == []
    assert status["failed"] == []
    assert status["ready"] is True


def test_verify_marks_stale_after_script_edit(tmp_path):
    open_trials(tmp_path)
    script = write_script(tmp_path, "statistician", OK_SCRIPT)
    runner.run_trial(str(tmp_path), "statistician", "O1", "full")

    fresh = runner.verify_trials(str(tmp_path))
    assert fresh["passed"] is True
    assert fresh["stale"] == []

    script.write_text(OK_SCRIPT + "# 改了脚本但没重跑\n", encoding="utf-8")
    stale = runner.verify_trials(str(tmp_path))
    assert stale["passed"] is False
    assert len(stale["stale"]) == 1
    assert stale["stale"][0]["stale"] is True
    assert "未重跑" in stale["stale"][0]["reason"]
    assert stale["stale"][0]["current_script_sha256"] != stale["stale"][0]["stored_script_sha256"]

    cli = run_cli("verify", "--workspace", str(tmp_path))
    assert cli.returncode == 1
    assert json.loads(cli.stdout)["passed"] is False


def test_verify_flags_run_without_tool_evidence(tmp_path):
    open_trials(tmp_path)
    doc = load_doc(tmp_path)
    doc["perspectives"] = [{
        "perspective": "statistician", "option_id": "O1",
        "script": "perspective_trials/statistician.py", "script_sha256": "deadbeef",
        "runs": [{"slice_id": "full", "run_seq": 1, "exit_code": 0,
                  "runtime_s": 0.9, "captured_at": "2026-11-01T10:00:03+08:00",
                  "metrics": {"comparable": {"runtime_s": 0.9, "finished": True}, "own": {}}}],
    }]
    (tmp_path / "perspective_trials.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    result = runner.verify_trials(str(tmp_path))
    assert result["passed"] is False
    assert result["evidence_issues"]
    assert "executed_by" in result["evidence_issues"][0]["reason"]


def test_cli_help_exits_zero():
    cli = run_cli("--help")
    assert cli.returncode == 0
    assert "open" in cli.stdout and "verify" in cli.stdout
    assert "契约见 docs/DESIGN_GATE_PLAN.md" in cli.stdout


def test_cli_unknown_action_errors_to_stderr(tmp_path):
    cli = run_cli("run", "--workspace", str(tmp_path), "--perspective", "x",
                  "--option-id", "O1", "--slice", "full")
    assert cli.returncode == 1
    assert json.loads(cli.stderr)["error"]
