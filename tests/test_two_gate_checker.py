#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双闸门检查器测试：A 板（框架/范式）与 B 板（方案择定）。

覆盖点与 docs/DESIGN_GATE_PLAN.md 一致：
- A 板 v2 允许 options 为空、必须有 paradigm_set/paradigm_selection、user_locked 必须 false；
- B 板要求 model_advice.json + perspective_trials.json，且数字必须来自工具执行；
- "缺板 + 有交付代码" 必须判 error，不得 skipped。
"""

import hashlib
import json
from pathlib import Path

from tools import design_board_checker as dbc


CONFIRMED_AT = "2026-08-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paradigm(pid: str, family: str) -> dict:
    return {
        "paradigm_id": pid,
        "name": f"范式 {pid}",
        "family": family,
        "source_ref": {"type": "method_card", "ref": f"MC-{pid}", "tier": "tier_a", "verified": True},
        "why_explore": "值得探索",
        "explore_cost": {"level": "medium", "note": "一天"},
    }


def a_board(
    schema: int = 2,
    paradigms: list | None = None,
    selection: list | None = None,
    user_locked: bool = False,
    options: list | None = None,
) -> dict:
    paradigms = paradigms if paradigms is not None else [
        paradigm("P1", "statistical_inference"),
        paradigm("P2", "statistical_inference"),
        paradigm("P3", "optimization"),
    ]
    board = {
        "schema_version": schema,
        "gate": "a",
        "board_id": "b-test-a",
        "language": "python",
        "revision": 1,
        "problem_summary": {"title": "t", "questions": ["Q1"], "key_ambiguities": []},
        "questions": [
            {
                "id": "Q1",
                "goal": "目标",
                "paradigm_set": paradigms,
                "paradigm_selection": selection if selection is not None else ["P1", "P3"],
                "options": options if options is not None else [],
                "user_choice": None,
                "user_locked": user_locked,
                "user_comment": "",
                "confirmed": True,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 2,
        "confirmed_at": CONFIRMED_AT,
        "confirmed_by": "user",
        "receipt_origin": "interactive",
        "confirm_attested": True,
    }
    return board


def finalize_board(root: Path, board: dict, gate: str = "a", rounds: int = 2) -> Path:
    """写板 + 回执，并回填 board_sha256 / confirm_code（与 render 同口径）。"""
    board["board_sha256"] = dbc._content_hash(board)
    board["confirm_code"] = board["board_sha256"][:4].upper()
    name = dbc.BOARD_FILES[gate]
    write_json(root / name, board)
    rounds_dir = root / dbc.ROUNDS_DIRS[gate]
    rounds_dir.mkdir(parents=True, exist_ok=True)
    for index in range(rounds):
        write_json(rounds_dir / f"round_{index + 1:03d}.json", {"round": index + 1, "changes": []})
    return root / name


def codes(result: dict) -> list[str]:
    return [issue["code"] for issue in result["issues"]]


def make_trials(option_ids: list[str], slices: list[str], metric_value: float = 0.5) -> dict:
    perspectives = []
    for index, option_id in enumerate(option_ids):
        runs = []
        for slice_id in slices:
            runs.append(
                {
                    "slice_id": slice_id,
                    "executed_by": "tool",
                    "runner_version": "1.0",
                    "run_seq": 1,
                    "exit_code": 0,
                    "runtime_s": 0.1 + index * 0.01,
                    "stdout_sha256": "abc",
                    "captured_at": CONFIRMED_AT,
                    "metrics": {
                        "comparable": {"runtime_s": 0.1 + index * 0.01, "finished": True},
                        "own": {"score": metric_value + index},
                    },
                    "reproduce_cmd": "python tools/perspective_trial_runner.py run",
                }
            )
        perspectives.append(
            {
                "perspective": f"p{index}",
                "option_id": option_id,
                "script": f"perspective_trials/p{index}.py",
                "script_sha256": "deadbeef",
                "runs": runs,
            }
        )
    return {
        "schema_version": 2,
        "question_id": "Q1",
        "generated_by": "tools/perspective_trial_runner.py",
        "run_id": "run-test",
        "slice_axis": "data_rows",
        "slices": [{"slice_id": sid, "description": sid, "data_ref": "data.csv"} for sid in slices],
        "metric_definitions": {"comparable": [{"key": "runtime_s", "unit": "s"}, {"key": "finished", "unit": "bool"}]},
        "perspectives": perspectives,
    }


def make_advice(option_ids: list[str], slices: list[str], trials: dict) -> dict:
    candidates = []
    for index, option_id in enumerate(option_ids):
        verdict = "recommended" if index == 0 else "not_recommended"
        candidate = {
            "option_id": option_id,
            "origin": f"perspective:p{index}",
            "name": f"模型 {option_id}",
            "paradigm_id": "P1",
            "verdict": verdict,
            "score": 90.0 - index,
            "dimension_scores": {"fit": 90, "rigor": 80, "evidence": 70},
            "pros": ["a", "b"],
            "cons": ["c", "d"],
            "evidence_refs": [],
        }
        if verdict != "recommended":
            candidate["why_not"] = ["x", "y"]
            candidate["when_better"] = "当数据不满足前提时"
        candidates.append(candidate)

    index_by_option = {option_id: position for position, option_id in enumerate(option_ids)}
    rows = []
    for slice_id in slices:
        for option_id in option_ids:
            position = index_by_option[option_id]
            run = next(
                run
                for perspective in trials["perspectives"]
                if perspective["option_id"] == option_id
                for run in perspective["runs"]
                if run["slice_id"] == slice_id
            )
            rows.append(
                {
                    "slice_id": slice_id,
                    "option_id": option_id,
                    "trials_ref": f"{option_id}/{slice_id}",
                    "comparable": dict(run["metrics"]["comparable"]),
                    "own": dict(run["metrics"]["own"]),
                }
            )
        rows.append(
            {
                "slice_id": slice_id,
                "option_id": "baseline",
                "trials_ref": "baseline",
                "comparable": {"runtime_s": 0.001, "finished": True},
            }
        )

    return {
        "schema_version": 2,
        "question_id": "Q1",
        "generated_at": CONFIRMED_AT,
        "is_judge_panel": False,
        "disclaimer": "本文件是选型建议，不是评委审查。",
        "scoring_rubric": {
            "dimensions": [
                {"id": "fit", "name": "契合", "weight": 0.4},
                {"id": "rigor", "name": "严谨", "weight": 0.3},
                {"id": "evidence", "name": "证据", "weight": 0.3},
            ],
            "scale": "0-100",
        },
        "candidates": candidates,
        "data_comparison": {
            "comparable_columns": ["runtime_s", "finished"],
            "rows": rows,
            "baseline_row": {"slice_id": slices[0], "option_id": "baseline",
                             "comparable": {"runtime_s": 0.001, "finished": True}},
        },
        "recommended_option_id": option_ids[0],
        "aggregate_note": "一句话总结",
    }


def b_board(option_ids: list[str], advice: dict, user_choice: str = "O1") -> dict:
    return {
        "schema_version": 2,
        "gate": "b",
        "question_scope": "problem",
        "board_id": "gb-test",
        "language": "python",
        "revision": 1,
        "advice_ref": "model_advice.json",
        "problem_summary": {"title": "t", "questions": ["Q1"]},
        "questions": [
            {
                "id": "Q1",
                "goal": "目标",
                "options": [
                    {"id": option_id, "name": f"模型 {option_id}", "verdict": "recommended" if position == 0 else "not_recommended",
                     "score": 90.0 - position, "origin": f"perspective:p{position}", "paradigm_id": "P1"}
                    for position, option_id in enumerate(option_ids)
                ],
                "advice": advice,
                "user_choice": user_choice,
                "user_locked": True,
                "user_comment": "",
                "confirmed": True,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 2,
        "confirmed_at": CONFIRMED_AT,
        "confirmed_by": "user",
        "receipt_origin": "interactive",
        "confirm_attested": True,
    }


def seed_b_workspace(root: Path, option_ids=("O1", "O2", "O3", "O4", "O5"), slices=("full", "holdout")) -> dict:
    trials = make_trials(list(option_ids), list(slices))
    advice = make_advice(list(option_ids), list(slices), trials)
    write_json(root / dbc.TRIALS_FILENAME, trials)
    write_json(root / dbc.ADVICE_FILENAME, advice)
    board = b_board(list(option_ids), advice)
    digest = hashlib.sha256((root / dbc.ADVICE_FILENAME).read_bytes()).hexdigest()
    board["advice_sha256"] = digest
    finalize_board(root, board, gate="b")
    return board


# ---------------------------------------------------------------------------
# A 闸门
# ---------------------------------------------------------------------------


def test_gate_a_v2_board_passes(tmp_path):
    finalize_board(tmp_path, a_board())
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert result["passed"] is True, result["issues"]
    assert result["gate"] == "a"


def test_gate_a_rejects_user_locked(tmp_path):
    finalize_board(tmp_path, a_board(user_locked=True))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "gate_a_user_locked_forbidden" in codes(result)


def test_gate_a_paradigm_mode_allows_empty_options(tmp_path):
    # A 板不再需要模型候选：options=[] 不得触发 insufficient_options。
    finalize_board(tmp_path, a_board(options=[]))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "insufficient_options" not in codes(result)


def test_gate_a_requires_three_paradigms(tmp_path):
    finalize_board(tmp_path, a_board(paradigms=[paradigm("P1", "stat"), paradigm("P2", "stat")],
                                     selection=["P1", "P2"]))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "paradigm_set_size" in codes(result)


def test_gate_a_requires_heterogeneous_family(tmp_path):
    finalize_board(tmp_path, a_board(
        paradigms=[paradigm("P1", "stat"), paradigm("P2", "stat"), paradigm("P3", "stat")],
        selection=["P1", "P2"],
    ))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "paradigm_no_heterogeneous" in codes(result)


def test_gate_a_requires_selection(tmp_path):
    finalize_board(tmp_path, a_board(selection=["P1"]))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "paradigm_selection_invalid" in codes(result)


def test_gate_a_legacy_board_keeps_old_semantics(tmp_path):
    # 旧板（schema<2）仍然是候选板：两条候选 + mini_trial 必须照样通过。
    legacy = {
        "schema_version": 1,
        "board_id": "b-legacy",
        "language": "python",
        "revision": 1,
        "problem_summary": {"title": "t", "questions": ["Q1"], "key_ambiguities": []},
        "questions": [
            {
                "id": "Q1",
                "goal": "g",
                "options": [
                    {"id": "O1", "name": "A", "tier": "recommended", "rationale": "r",
                     "source_ref": {"type": "method_card", "ref": "X", "tier": "tier_a", "verified": True},
                     "complexity": "low", "dependencies": [], "risk": "low",
                     "mini_trial": {"sample": "s", "output": {}, "seconds": 0.1, "feasible": True}},
                    {"id": "O2", "name": "B", "tier": "alternative", "rationale": "r",
                     "source_ref": {"type": "method_card", "ref": "Y", "tier": "tier_b", "verified": True},
                     "complexity": "low", "dependencies": [], "risk": "low",
                     "mini_trial": {"sample": "s", "output": {}, "seconds": 0.2, "feasible": True}},
                ],
                "user_choice": "O1",
                "user_locked": True,
                "user_comment": "",
                "confirmed": True,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 2,
        "confirmed_at": CONFIRMED_AT,
        "confirmed_by": "user",
        "receipt_origin": "interactive",
        "confirm_attested": True,
    }
    finalize_board(tmp_path, legacy, gate="a")
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True)
    assert "insufficient_options" not in codes(result)
    assert "missing_option_field" not in codes(result)
    assert "paradigm_set_missing" not in codes(result)


# ---------------------------------------------------------------------------
# B 闸门
# ---------------------------------------------------------------------------


def test_gate_b_full_board_passes(tmp_path):
    seed_b_workspace(tmp_path)
    (tmp_path / "model_selection_audit.json").write_text(json.dumps({
        "candidates": [{"name": f"模型 O{i}"} for i in range(1, 6)],
        "final_selection": {"name": "模型 O1"},
    }, ensure_ascii=False), encoding="utf-8")
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=True, skip_timeline=True,
                                    gate="b")
    assert result["passed"] is True, result["issues"]
    assert result["cross_audit"] == "checked"


def test_gate_b_requires_advice_file(tmp_path):
    seed_b_workspace(tmp_path)
    (tmp_path / dbc.ADVICE_FILENAME).unlink()
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "advice_missing" in codes(result)


def test_gate_b_flags_candidate_count(tmp_path):
    seed_b_workspace(tmp_path, option_ids=("O1", "O2", "O3"))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "advice_candidates_count" in codes(result)


def test_gate_b_flags_two_recommended(tmp_path):
    board = seed_b_workspace(tmp_path)
    advice = json.loads((tmp_path / dbc.ADVICE_FILENAME).read_text(encoding="utf-8"))
    advice["candidates"][1]["verdict"] = "recommended"
    advice["candidates"][1]["why_not"] = []
    write_json(tmp_path / dbc.ADVICE_FILENAME, advice)
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "advice_one_recommended" in codes(result)


def test_gate_b_flags_single_slice(tmp_path):
    seed_b_workspace(tmp_path, slices=("full",))
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "advice_data_comparison" in codes(result)


def test_gate_b_flags_hand_edited_numbers(tmp_path):
    seed_b_workspace(tmp_path)
    advice = json.loads((tmp_path / dbc.ADVICE_FILENAME).read_text(encoding="utf-8"))
    advice["data_comparison"]["rows"][0]["comparable"]["runtime_s"] = 123.456
    write_json(tmp_path / dbc.ADVICE_FILENAME, advice)
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "advice_number_mismatch" in codes(result)


def test_gate_b_flags_hand_filled_trials(tmp_path):
    seed_b_workspace(tmp_path)
    trials = json.loads((tmp_path / dbc.TRIALS_FILENAME).read_text(encoding="utf-8"))
    trials["perspectives"][0]["runs"][0]["executed_by"] = "agent"
    write_json(tmp_path / dbc.TRIALS_FILENAME, trials)
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "trials_not_tool_executed" in codes(result)


def test_gate_b_requires_user_choice(tmp_path):
    board = seed_b_workspace(tmp_path)
    board["questions"][0]["user_choice"] = None
    board["advice_sha256"] = hashlib.sha256((tmp_path / dbc.ADVICE_FILENAME).read_bytes()).hexdigest()
    finalize_board(tmp_path, board, gate="b")
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert "user_choice_present" in codes(result)


def test_missing_gate_b_board_with_solution_is_error(tmp_path):
    # 最核心的回归点：板不在、代码在 → error，不能被 skipped 洗掉。
    (tmp_path / "solution.py").write_text("print(1)\n", encoding="utf-8")
    result = dbc.check_design_board(str(tmp_path), "excellence", cross_audit=False, skip_timeline=True,
                                    gate="b")
    assert result["passed"] is False
    assert "code_written_before_gate_b" in codes(result)


def test_gate_b_board_path_is_gate_specific():
    assert dbc.BOARD_FILES["a"] == "design_board.json"
    assert dbc.BOARD_FILES["b"] == "design_board_gate_b.json"
    assert dbc.ROUNDS_DIRS["b"] == "design_rounds_gate_b"
