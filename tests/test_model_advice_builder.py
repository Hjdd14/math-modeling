#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model_advice_builder 测试：骨架回填与契约 §6 硬规则逐条落地。

两条主线：
1. assemble 只回填工具能证明的东西（候选身份 + trials 数值），判断类字段留空给 Agent；
2. validate 把 §6 的每条硬规则映射成独立 issue code，尤其是"数字被改"与"trials 手填"。
"""

import json
import os
import subprocess
import sys

import pytest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

from tools import model_advice_builder as builder
from tools import perspective_trial_runner as runner


TOOL = os.path.join(SKILL_DIR, "tools", "model_advice_builder.py")

PERSPECTIVES = [
    ("statistician", "O1"),
    ("optimizer", "O2"),
    ("physicist", "O3"),
    ("engineer", "O4"),
    ("innovator", "O5"),
]
SLICES = ("full", "holdout_b")


def build_trials(slice_ids=SLICES, perspectives=PERSPECTIVES, *, hand_filled=False, drop=None):
    """构造一份结构完整的 perspective_trials.json 文档。

    hand_filled=True 时去掉工具执行留痕（模拟 Agent 手填）；drop 指定要缺掉的 (option_id, slice_id)。
    """
    slices = [{"slice_id": slice_id, "description": slice_id, "data_ref": "data.csv",
               "selector": {"rows": slice_id}} for slice_id in slice_ids]
    entries = []
    for index, (name, option_id) in enumerate(perspectives):
        runs = []
        for slice_index, slice_id in enumerate(slice_ids):
            if drop == (option_id, slice_id):
                continue
            runtime_s = round(0.9 + index * 0.1 + slice_index * 0.01, 6)
            own = {"p_value": round(0.0258 + index * 0.01, 6), "objective": round(10.5 + index, 6)}
            run = {
                "slice_id": slice_id,
                "run_seq": 1,
                "exit_code": 0,
                "runtime_s": runtime_s,
                "captured_at": "2026-11-01T10:00:03+08:00",
                "metrics": {
                    "comparable": {"runtime_s": runtime_s, "finished": True},
                    "own": own,
                },
                "reproduce_cmd": (
                    "python tools/perspective_trial_runner.py run --workspace . "
                    f"--perspective {name} --option-id {option_id} --slice {slice_id}"
                ),
            }
            if not hand_filled:
                run.update({"executed_by": "tool", "runner_version": "1.0",
                            "stdout_sha256": "a" * 64, "script_sha256": "b" * 64})
            else:
                run.pop("captured_at")
            runs.append(run)
        entries.append({
            "perspective": name, "option_id": option_id,
            "script": f"perspective_trials/{name}.py", "script_sha256": "b" * 64,
            "runs": runs,
        })
    return {
        "schema_version": 2,
        "question_id": "Q1",
        "generated_by": "tools/perspective_trial_runner.py",
        "run_id": "2026-11-01T10:00:00+08:00-3f9a1c",
        "slice_axis": "data_rows",
        "slice_axis_note": "",
        "slices": slices,
        "metric_definitions": {
            "comparable": [{"key": "runtime_s", "unit": "s"}, {"key": "finished", "unit": "bool"}],
            "own": {},
        },
        "perspectives": entries,
    }


def write_trials(workspace, doc):
    """把 trials 文档写到工作区。"""
    path = workspace / "perspective_trials.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_advice(workspace):
    """读回 model_advice.json。"""
    return json.loads((workspace / "model_advice.json").read_text(encoding="utf-8"))


def write_advice(workspace, advice):
    """写回 model_advice.json（模拟 Agent 编辑）。"""
    (workspace / "model_advice.json").write_text(
        json.dumps(advice, ensure_ascii=False, indent=2), encoding="utf-8")
    return advice


def fill_advice(advice, *, recommended_index=0):
    """模拟建议 Agent 填判断类字段（不碰工具回填的数字）。"""
    dims = [item["id"] for item in advice["scoring_rubric"]["dimensions"]]
    for index, candidate in enumerate(advice["candidates"]):
        candidate["verdict"] = "recommended" if index == recommended_index else "not_recommended"
        candidate["score"] = 90 - index
        candidate["dimension_scores"] = {dim: 80 + index for dim in dims}
        candidate["pros"] = ["优点一", "优点二"]
        candidate["cons"] = ["缺点一", "缺点二"]
        if index != recommended_index:
            candidate["why_not"] = ["理由一", "理由二"]
            candidate["when_better"] = "当正态性不成立且样本量小时更优"
    advice["recommended_option_id"] = advice["candidates"][recommended_index]["option_id"]
    advice["aggregate_note"] = "推荐它的理由与剩余风险由 Phase 4 评审覆盖。"
    return advice


def codes(result):
    """issues 里的 code 集合。"""
    return {issue["code"] for issue in result["issues"]}


def assembled(tmp_path, *, trials=None, fill=True, **kwargs):
    """写 trials → assemble → 可选 fill，返回 advice。"""
    write_trials(tmp_path, trials or build_trials(**kwargs))
    builder.assemble(str(tmp_path), question_id="Q1")
    advice = read_advice(tmp_path)
    if fill:
        advice = fill_advice(advice)
        write_advice(tmp_path, advice)
    return advice


def run_cli(*args):
    """子进程跑 CLI，检查 stdout/stderr/退出码契约。"""
    return subprocess.run(
        [sys.executable, TOOL, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=SKILL_DIR,
    )


# ---------------------------------------------------------------- assemble

def test_assemble_builds_skeleton_from_trials(tmp_path):
    trials = build_trials()
    write_trials(tmp_path, trials)
    result = builder.assemble(str(tmp_path), question_id="Q1")

    assert result["ok"] is True
    assert result["candidates"] == 5
    assert result["rows"] == 10
    assert result["missing_trial_cells"] == []
    assert result["warnings"] == []

    advice = read_advice(tmp_path)
    assert advice["schema_version"] == 2
    assert advice["question_id"] == "Q1"
    assert advice["is_judge_panel"] is False
    assert advice["disclaimer"]
    assert advice["data_comparison"]["comparable_columns"] == ["runtime_s", "finished"]

    first = advice["candidates"][0]
    assert first["option_id"] == "O1"
    assert first["origin"] == "perspective:statistician"
    # 判断类字段一律留空：工具不替 Agent 推荐、不打分
    assert first["verdict"] is None
    assert first["score"] is None
    assert first["pros"] == [] and first["cons"] == []
    assert first["why_not"] == [] and first["when_better"] is None
    assert advice["recommended_option_id"] is None
    assert advice["aggregate_note"] is None
    # 维度键集合已经固定，Agent 只需填数
    assert set(first["dimension_scores"]) == {item["id"] for item in advice["scoring_rubric"]["dimensions"]}
    assert all(value is None for value in first["dimension_scores"].values())
    assert first["evidence_refs"] == ["perspective_trials.json#O1/full",
                                      "perspective_trials.json#O1/holdout_b"]

    # data_comparison 的数值必须逐字等于 trials
    rows = {(row["option_id"], row["slice_id"]): row for row in advice["data_comparison"]["rows"]}
    run = trials["perspectives"][0]["runs"][0]
    assert rows[("O1", "full")]["comparable"] == run["metrics"]["comparable"]
    assert rows[("O1", "full")]["own"] == run["metrics"]["own"]
    assert rows[("O1", "full")]["trials_ref"] == "O1/full"


def test_assemble_uses_revised_outputs_for_name_and_paradigm(tmp_path):
    (tmp_path / "agent_outputs").mkdir()
    (tmp_path / "agent_outputs" / "revised_statistician.json").write_text(
        json.dumps({"model_name": "配对差单样本 t 检验族", "paradigm_id": "P1"}, ensure_ascii=False),
        encoding="utf-8")
    write_trials(tmp_path, build_trials())

    builder.assemble(str(tmp_path), question_id="Q1")
    advice = read_advice(tmp_path)
    first = advice["candidates"][0]
    assert first["name"] == "配对差单样本 t 检验族"
    assert first["paradigm_id"] == "P1"
    # 没有 revised 产物的视角退回视角名占位，不编造模型名
    assert advice["candidates"][1]["name"] == "optimizer"


def test_assemble_keeps_agent_fields_on_rerun(tmp_path):
    assembled(tmp_path)
    before = read_advice(tmp_path)

    builder.assemble(str(tmp_path), question_id="Q1")
    after = read_advice(tmp_path)

    assert [item["score"] for item in after["candidates"]] == [item["score"] for item in before["candidates"]]
    assert after["recommended_option_id"] == before["recommended_option_id"]
    assert after["candidates"][0]["verdict"] == "recommended"


def test_assemble_does_not_fabricate_missing_cells(tmp_path):
    trials = build_trials(drop=("O3", "holdout_b"))
    write_trials(tmp_path, trials)

    result = builder.assemble(str(tmp_path), question_id="Q1")
    assert "O3/holdout_b" in result["missing_trial_cells"]
    assert any("没有成功试算" in warning for warning in result["warnings"])

    advice = read_advice(tmp_path)
    assert not any(row["option_id"] == "O3" and row["slice_id"] == "holdout_b"
                   for row in advice["data_comparison"]["rows"])


def test_assemble_requires_trials(tmp_path):
    with pytest.raises(FileNotFoundError, match="perspective_trials"):
        builder.assemble(str(tmp_path))


# ---------------------------------------------------------------- validate 通过

def test_validate_passes_when_agent_fields_filled(tmp_path):
    assembled(tmp_path)
    result = builder.validate(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["issues"] == []
    assert result["candidates"] == 5
    assert result["rows"] == 10


def test_validate_accepts_float_noise_within_tolerance(tmp_path):
    advice = assembled(tmp_path)
    advice["data_comparison"]["rows"][0]["comparable"]["runtime_s"] += 1e-12
    write_advice(tmp_path, advice)
    assert builder.validate(str(tmp_path))["passed"] is True


# ---------------------------------------------------------------- validate 负例

def test_validate_flags_hand_filled_trials(tmp_path):
    assembled(tmp_path, trials=build_trials(hand_filled=True))
    result = builder.validate(str(tmp_path))

    assert result["passed"] is False
    assert "trials_not_tool_executed" in codes(result)
    message = next(issue["message"] for issue in result["issues"]
                   if issue["code"] == "trials_not_tool_executed")
    assert "captured_at" in message


def test_validate_flags_number_mismatch(tmp_path):
    advice = assembled(tmp_path)
    advice["data_comparison"]["rows"][0]["comparable"]["runtime_s"] += 0.001
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_number_mismatch" in codes(result)


def test_validate_flags_own_metric_mismatch(tmp_path):
    advice = assembled(tmp_path)
    advice["data_comparison"]["rows"][1]["own"]["p_value"] = 0.5
    write_advice(tmp_path, advice)
    assert "advice_number_mismatch" in codes(builder.validate(str(tmp_path)))


def test_validate_flags_candidates_count(tmp_path):
    advice = assembled(tmp_path)
    keep = {candidate["option_id"] for candidate in advice["candidates"][:3]}
    advice["candidates"] = [item for item in advice["candidates"] if item["option_id"] in keep]
    advice["data_comparison"]["rows"] = [row for row in advice["data_comparison"]["rows"]
                                         if row["option_id"] in keep]
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path), mode="excellence")
    assert result["passed"] is False
    assert "advice_candidates_count" in codes(result)


def test_validate_flags_two_recommended(tmp_path):
    advice = assembled(tmp_path)
    advice["candidates"][1]["verdict"] = "recommended"
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_one_recommended" in codes(result)


def test_validate_flags_single_slice(tmp_path):
    assembled(tmp_path, trials=build_trials(slice_ids=("full",)))
    result = builder.validate(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert "advice_data_comparison" in codes(result)


def test_validate_flags_slice_missing_candidate(tmp_path):
    advice = assembled(tmp_path)
    advice["data_comparison"]["rows"] = [row for row in advice["data_comparison"]["rows"]
                                         if not (row["option_id"] == "O2" and row["slice_id"] == "full")]
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert "advice_data_comparison" in codes(result)
    message = next(issue["message"] for issue in result["issues"]
                   if issue["code"] == "advice_data_comparison" and "缺少候选" in issue["message"])
    assert "O2" in message


def test_validate_flags_comparable_key_mismatch(tmp_path):
    advice = assembled(tmp_path)
    row = next(item for item in advice["data_comparison"]["rows"]
               if item["option_id"] == "O1" and item["slice_id"] == "full")
    row["comparable"].pop("finished")
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_comparable_metrics" in codes(result)
    assert "advice_number_mismatch" in codes(result)


def test_validate_flags_invalid_trials_ref(tmp_path):
    advice = assembled(tmp_path)
    advice["data_comparison"]["rows"][0]["trials_ref"] = "O1/nowhere"
    write_advice(tmp_path, advice)
    assert "advice_trials_ref_valid" in codes(builder.validate(str(tmp_path)))

    advice["data_comparison"]["rows"][0]["trials_ref"] = None
    write_advice(tmp_path, advice)
    assert "advice_trials_ref_valid" in codes(builder.validate(str(tmp_path)))


def test_validate_flags_every_cell_when_trials_missing(tmp_path):
    assembled(tmp_path)
    (tmp_path / "perspective_trials.json").unlink()

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_trials_ref_valid" in codes(result)


def test_validate_flags_scores_incomplete(tmp_path):
    advice = assembled(tmp_path)
    advice["candidates"][0]["score"] = None
    advice["candidates"][1]["dimension_scores"].pop("rigor")
    advice["candidates"][2]["score"] = 140
    write_advice(tmp_path, advice)
    assert "advice_scores_complete" in codes(builder.validate(str(tmp_path)))


def test_validate_flags_thin_pros_cons(tmp_path):
    advice = assembled(tmp_path)
    advice["candidates"][0]["pros"] = ["只有一条"]
    advice["candidates"][0]["cons"] = []
    write_advice(tmp_path, advice)
    assert "advice_pros_cons" in codes(builder.validate(str(tmp_path)))


def test_validate_flags_missing_why_not_and_when_better(tmp_path):
    advice = assembled(tmp_path)
    advice["candidates"][1]["why_not"] = ["只有一条"]
    advice["candidates"][1]["when_better"] = "  "
    write_advice(tmp_path, advice)
    assert "advice_why_not_when_better" in codes(builder.validate(str(tmp_path)))


def test_validate_flags_judge_panel_pretence(tmp_path):
    advice = assembled(tmp_path)
    advice["is_judge_panel"] = True
    advice["disclaimer"] = ""
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_is_not_judge_panel" in codes(result)


def test_validate_flags_judge_wording(tmp_path):
    advice = assembled(tmp_path)
    advice["aggregate_note"] = "评审结论：本候选通过。"
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path))
    assert result["passed"] is False
    assert "advice_no_judge_wording" in codes(result)


def test_validate_requires_advice_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="assemble"):
        builder.validate(str(tmp_path))


# ---------------------------------------------------------------- mode 映射

def _three_candidate_advice(tmp_path):
    """构造只触发三条可降级规则的建议：候选 3 个、单 slice、某候选 pros 只有 1 条。"""
    assembled(tmp_path, trials=build_trials(slice_ids=("full",), perspectives=PERSPECTIVES[:3]))
    advice = read_advice(tmp_path)
    advice["candidates"][0]["pros"] = ["只有一条优点"]
    write_advice(tmp_path, advice)
    return advice


def test_standard_downgrades_three_codes_to_warning(tmp_path):
    _three_candidate_advice(tmp_path)
    result = builder.validate(str(tmp_path), mode="standard")

    downgraded = {"advice_candidates_count", "advice_data_comparison", "advice_pros_cons"}
    assert set(codes(result)) == downgraded
    assert all(issue["severity"] == "warning" for issue in result["issues"])
    assert result["passed"] is True


def test_excellence_keeps_downgraded_codes_as_error(tmp_path):
    _three_candidate_advice(tmp_path)
    result = builder.validate(str(tmp_path), mode="excellence")

    assert {issue["code"] for issue in result["issues"]} == {
        "advice_candidates_count", "advice_data_comparison", "advice_pros_cons"}
    assert all(issue["severity"] == "error" for issue in result["issues"])
    assert result["passed"] is False


def test_standard_keeps_evidence_failures_as_error(tmp_path):
    advice = _three_candidate_advice(tmp_path)
    advice["data_comparison"]["rows"][0]["comparable"]["runtime_s"] += 0.001
    write_advice(tmp_path, advice)

    result = builder.validate(str(tmp_path), mode="standard")
    severities = {issue["code"]: issue["severity"] for issue in result["issues"]}
    assert severities["advice_number_mismatch"] == "error"
    assert severities["advice_candidates_count"] == "warning"
    assert result["passed"] is False


# ---------------------------------------------------------------- CLI 与 runner 集成

def test_cli_help_and_validate_exit_codes(tmp_path):
    cli = run_cli("--help")
    assert cli.returncode == 0
    assert "assemble" in cli.stdout and "validate" in cli.stdout
    assert "契约见 docs/DESIGN_GATE_PLAN.md" in cli.stdout

    assembled(tmp_path, fill=False)
    failed = run_cli("validate", "--workspace", str(tmp_path), "--mode", "standard")
    assert failed.returncode == 1
    payload = json.loads(failed.stdout)
    assert payload["passed"] is False
    assert payload["issues"]

    advice = read_advice(tmp_path)
    fill_advice(advice)
    write_advice(tmp_path, advice)
    ok = run_cli("validate", "--workspace", str(tmp_path), "--mode", "excellence")
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["passed"] is True


def test_assemble_cli_consumes_runner_output(tmp_path):
    """与 runner 的真产物对接：assemble 骨架 → Agent 填 → validate 通过。"""
    scripts = tmp_path / "perspective_trials"
    scripts.mkdir()
    for name, _ in PERSPECTIVES:
        (scripts / f"{name}.py").write_text(
            "import argparse, json\n"
            "parser = argparse.ArgumentParser()\n"
            'parser.add_argument("--slice", default="full")\n'
            "args = parser.parse_args()\n"
            'ratio = 1.0 if args.slice == "full" else 0.8\n'
            'print(json.dumps({"own": {"p_value": 0.0258 * ratio}}))\n',
            encoding="utf-8",
        )
    slices_path = tmp_path / "slices.json"
    slices_path.write_text(json.dumps({
        "slices": [{"slice_id": "full", "description": "全部数据", "data_ref": "data.csv",
                    "selector": {"rows": "all"}},
                   {"slice_id": "holdout_b", "description": "留出 20%", "data_ref": "data.csv",
                    "selector": {"rows": "56..70"}}],
    }, ensure_ascii=False), encoding="utf-8")
    runner.open_document(str(tmp_path), str(slices_path), question_id="Q1")
    for name, option_id in PERSPECTIVES:
        for slice_id in SLICES:
            assert runner.run_trial(str(tmp_path), name, option_id, slice_id)["ok"] is True
    assert runner.verify_trials(str(tmp_path))["passed"] is True

    cli = run_cli("assemble", "--workspace", str(tmp_path), "--question-id", "Q1")
    assert cli.returncode == 0
    payload = json.loads(cli.stdout)
    assert payload["candidates"] == 5
    assert payload["rows"] == 10
    assert payload["missing_trial_cells"] == []

    advice = read_advice(tmp_path)
    fill_advice(advice)
    write_advice(tmp_path, advice)
    result = builder.validate(str(tmp_path), mode="excellence")
    assert result["passed"] is True, result["issues"]
