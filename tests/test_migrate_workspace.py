#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧工作区迁移脚本 migrate_workspace 与 --allow-legacy 逃生口的测试。

覆盖：
1. 已有 design_board.json 时绝不覆盖（进程内 + CLI 两种入口）；
2. 空工作区生成的占位板能被 design_board.load_board 加载，且不伪造确认；
3. problem_brief.md 首行 → 题目，超长截断；
4. model_selection_audit.json 的候选 → options，final_selection 对应的 tier 为 recommended；
5. 迁移后 checker 在 excellence 下仍因 unconfirmed_board 失败（迁移不伪造确认）；
6. --allow-legacy 只在"缺板"时降级，且不放松其它任何失败码。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import design_board
from tools import design_board_checker
from tools import migrate_workspace


SKILL_DIR = Path(__file__).resolve().parents[1]
MIGRATE_TOOL = SKILL_DIR / "tools" / "migrate_workspace.py"
CHECKER_TOOL = SKILL_DIR / "tools" / "design_board_checker.py"


# ---------------------------------------------------------------------------
# 夹具辅助
# ---------------------------------------------------------------------------


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def issue_codes(result):
    return {issue["code"] for issue in result["issues"]}


def run_tool(tool, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, str(tool), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(SKILL_DIR),
        env=env,
    )


def make_unconfirmed_board():
    """结构合法、但未确认的板：用来验证 allow_legacy 不放松其它失败码。"""

    def option(option_id, name):
        return {
            "id": option_id,
            "name": name,
            "rationale": "约束线性、规模可控",
            "risk": "规模翻倍需要换求解器",
            "source_ref": {"type": "method_card", "ref": "OPT-01", "verified": True},
            "mini_trial": {"sample": "前 20 行真实数据", "output": {"ok": True}},
        }

    return {
        "questions": [
            {
                "id": "Q1",
                "options": [option("O1", "方案A"), option("O2", "方案B")],
                "user_choice": None,
            }
        ]
    }


# ---------------------------------------------------------------------------
# 1. 已存在 design_board.json → 报错退出，绝不覆盖
# ---------------------------------------------------------------------------


def test_existing_board_is_never_overwritten(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = workspace / "design_board.json"
    original = '{\n  "marker": "原文件不能被覆盖",\n  "questions": []\n}\n'
    path.write_text(original, encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ValueError) as excinfo:
        migrate_workspace.migrate_workspace(str(workspace), apply=True)
    assert "已存在" in str(excinfo.value)
    assert path.read_bytes() == before

    # dry-run 同样必须拒绝（不能在预览阶段就暗示会覆盖）
    with pytest.raises(ValueError):
        migrate_workspace.migrate_workspace(str(workspace), apply=False)
    assert path.read_bytes() == before

    # CLI：exit 1，stderr 给出可读错误，文件内容一字不改
    proc = run_tool(MIGRATE_TOOL, "--workspace", str(workspace), "--apply")
    assert proc.returncode == 1
    assert "已存在" in proc.stderr
    assert path.read_bytes() == before


# ---------------------------------------------------------------------------
# 2. 空 workspace → 占位板，可加载、未确认
# ---------------------------------------------------------------------------


def test_empty_workspace_generates_placeholder_board(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    preview = migrate_workspace.migrate_workspace(str(workspace))
    assert preview["written"] is False
    assert not (workspace / "design_board.json").exists()
    assert Path(preview["path"]) == (workspace / "design_board.json").resolve()
    assert preview["inferred"]["questions"] == 1
    assert preview["inferred"]["options"] == 2
    assert len(preview["next_steps"]) == 3
    assert preview["board_preview"]["problem_summary"]["title"] == "（迁移占位，请补充）"

    applied = migrate_workspace.migrate_workspace(str(workspace), apply=True)
    assert applied["written"] is True
    assert (workspace / "design_board.json").is_file()

    # 必须能通过权威实现的 load_board（含 for_render 要求的 mindmap.source）
    board = design_board.load_board(workspace, for_render=True)
    assert board["problem_summary"]["title"] == "（迁移占位，请补充）"
    assert board["mindmap"]["source"].startswith("graph LR")
    assert board["no_change_rounds"] == 0

    # 迁移绝不能伪造确认状态（连键都不该出现）
    assert board.get("confirmed") is not True
    for forbidden in ("confirmed", "confirm_code", "confirmed_at", "confirmed_by", "receipt_origin"):
        assert forbidden not in board, forbidden

    question = board["questions"][0]
    assert question["id"] == "Q1"
    assert question["user_choice"] is None
    assert [option["name"] for option in question["options"]] == ["待补充候选 A", "待补充候选 B"]
    assert [option["id"] for option in question["options"]] == ["O1", "O2"]
    for option in question["options"]:
        for field in ("rationale", "risk", "source_ref", "mini_trial"):
            assert option[field], field
        assert option["source_ref"]["verified"] is False
        assert option["source_ref"]["unverified_reason"] == "迁移生成，未核验来源"
        assert option["tier"] == "alternative"


# ---------------------------------------------------------------------------
# 3. problem_brief.md 首行 → 标题，超长截断到 120 字
# ---------------------------------------------------------------------------


def test_brief_first_line_becomes_title_and_is_truncated(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    long_title = "某超长题目" + "甲" * 200
    (workspace / "problem_brief.md").write_text(f"\n\n# {long_title}\n\n正文略\n", encoding="utf-8")

    migrate_workspace.migrate_workspace(str(workspace), apply=True)
    board = design_board.load_board(workspace)

    title = board["problem_summary"]["title"]
    assert title.startswith("某超长题目")
    assert len(title) <= 120
    assert title.endswith("…")
    assert board["problem_summary"]["source"].startswith("problem_brief.md")


# ---------------------------------------------------------------------------
# 4. model_selection_audit.json → options，final_selection 对应的 tier 正确
# ---------------------------------------------------------------------------


def test_audit_candidates_become_options_with_recommended_tier(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "problem_brief.md").write_text("# 生产计划优化\n", encoding="utf-8")
    write_json(
        workspace / "model_selection_audit.json",
        {
            "candidates": [
                {"name": "整数规划", "score": 0.91, "evidence": ["oracle"]},
                {"name": "贪心启发式", "score": 0.72, "evidence": ["baseline"]},
                {"name": "元启发式搜索", "score": 0.65, "evidence": []},
            ],
            "final_selection": {"name": "整数规划", "score": 0.91},
        },
    )

    result = migrate_workspace.migrate_workspace(str(workspace), apply=True)
    board = design_board.load_board(workspace, for_render=True)
    options = board["questions"][0]["options"]

    assert [option["name"] for option in options] == ["整数规划", "贪心启发式", "元启发式搜索"]
    assert [option["id"] for option in options] == ["O1", "O2", "O3"]
    assert {option["name"]: option["tier"] for option in options} == {
        "整数规划": "recommended",
        "贪心启发式": "alternative",
        "元启发式搜索": "alternative",
    }
    assert result["inferred"]["recommended"] == ["整数规划"]
    assert result["inferred"]["options"] == 3
    assert board["problem_summary"]["title"] == "生产计划优化"
    assert "整数规划" in board["mindmap"]["source"]
    for option in options:
        assert option["source_ref"]["verified"] is False
        assert option["source_ref"]["ref"].startswith("model_selection_audit.json#candidates[")


# ---------------------------------------------------------------------------
# 5. 迁移后仍必须失败：迁移不能代替用户确认
# ---------------------------------------------------------------------------


def test_generated_board_still_fails_excellence_until_confirmed(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_json(
        workspace / "model_selection_audit.json",
        {
            "candidates": [{"name": "整数规划"}, {"name": "贪心启发式"}],
            "final_selection": {"name": "整数规划"},
        },
    )
    migrate_workspace.migrate_workspace(str(workspace), apply=True)

    result = design_board_checker.check_design_board(str(workspace), "excellence")

    codes = issue_codes(result)
    assert result["passed"] is False
    assert result["confirmed"] is False
    assert "unconfirmed_board" in codes
    assert "missing_design_board" not in codes
    assert "legacy_workspace_without_board" not in codes


def test_migrated_board_can_render_but_stays_unconfirmed(tmp_path):
    """最小可用性：迁移后的板能走 render（生成确认码），但确认状态仍为未确认。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    migrate_workspace.migrate_workspace(str(workspace), apply=True)

    rendered = design_board.render_board(str(workspace))

    assert len(rendered["board_sha256"]) == 64
    assert rendered["confirm_code"] == rendered["board_sha256"][:4].upper()
    board = read_json(workspace / "design_board.json")
    assert board["confirm_code"] == rendered["confirm_code"]
    assert board.get("confirmed") is not True
    assert board["questions"][0].get("confirmed") is not True
    assert (workspace / "design_board.md").is_file()


# ---------------------------------------------------------------------------
# 6. --allow-legacy：缺板时降级为 warning，差异只在 code 与 legacy_mode
# ---------------------------------------------------------------------------


def test_allow_legacy_downgrades_missing_board_only(tmp_path):
    workspace = tmp_path / "legacy"
    workspace.mkdir()

    default = design_board_checker.check_design_board(str(workspace), "excellence")
    assert default["passed"] is False
    assert default["warning"] is False
    assert "missing_design_board" in issue_codes(default)
    assert "legacy_workspace_without_board" not in issue_codes(default)

    legacy = design_board_checker.check_design_board(str(workspace), "excellence", allow_legacy=True)
    assert legacy["passed"] is True
    assert legacy["warning"] is True
    assert "legacy_workspace_without_board" in issue_codes(legacy)
    assert "missing_design_board" not in issue_codes(legacy)

    issue = next(item for item in legacy["issues"] if item["code"] == "legacy_workspace_without_board")
    assert issue["severity"] == "warning"
    legacy_check = next(check for check in legacy["checks"] if check["name"] == "legacy_mode")
    assert legacy_check["passed"] is True
    assert legacy_check["note"]

    # CLI 开关必须与函数参数同义
    blocked = run_tool(CHECKER_TOOL, "--workspace", str(workspace), "--mode", "excellence")
    assert blocked.returncode == 1
    assert "missing_design_board" in issue_codes(json.loads(blocked.stdout))

    allowed = run_tool(
        CHECKER_TOOL, "--workspace", str(workspace), "--mode", "excellence", "--allow-legacy"
    )
    assert allowed.returncode == 0, allowed.stderr
    payload = json.loads(allowed.stdout)
    assert payload["passed"] is True
    assert "legacy_workspace_without_board" in issue_codes(payload)


# ---------------------------------------------------------------------------
# 7. --allow-legacy 不放松任何其它失败码
# ---------------------------------------------------------------------------


def test_allow_legacy_does_not_relax_other_failure_codes(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_json(workspace / "design_board.json", make_unconfirmed_board())

    default = design_board_checker.check_design_board(str(workspace), "excellence")
    legacy = design_board_checker.check_design_board(str(workspace), "excellence", allow_legacy=True)

    assert default["passed"] is False
    assert legacy["passed"] is False
    assert "unconfirmed_board" in issue_codes(legacy)
    assert "legacy_workspace_without_board" not in issue_codes(legacy)
    # 除"缺板"这一条外，allow_legacy 不得改变任何失败码：这里两者的码集必须完全一致。
    assert issue_codes(legacy) == issue_codes(default)

# ---------------------------------------------------------------------------
# 8. 双闸门：新骨架是 A 板 schema v2（范式集合占位），且不生成 B 板
# ---------------------------------------------------------------------------


def test_generated_skeleton_is_gate_a_schema_v2(tmp_path):
    """新骨架必须是 schema v2 + paradigm_set 占位，且绝不伪造 B 板。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()

    result = migrate_workspace.migrate_workspace(str(workspace), apply=True)
    board = read_json(workspace / "design_board.json")

    assert board["schema_version"] == 2
    assert board["gate"] == "a"
    assert result["schema_version"] == 2
    assert result["requires_gate_b"] is True
    assert result["gate_b_written"] is False
    assert not (workspace / "design_board_gate_b.json").exists()

    question = board["questions"][0]
    assert len(question["paradigm_set"]) == 3
    families = {item["family"] for item in question["paradigm_set"]}
    assert len(families) >= 2, "范式集合必须含至少 1 个异质族"
    for paradigm in question["paradigm_set"]:
        for field in ("paradigm_id", "name", "family", "source_ref", "why_explore", "explore_cost"):
            assert paradigm[field], field
        assert paradigm["explore_cost"]["level"] in ("low", "medium", "high")
        assert paradigm["source_ref"]["verified"] is False
        assert paradigm["source_ref"]["unverified_reason"]
    selection = question["paradigm_selection"]
    assert len(selection) >= 2
    ids = {item["paradigm_id"] for item in question["paradigm_set"]}
    assert set(selection) <= ids
    # A 板不得锁定选型
    assert question["user_locked"] is False
    assert question["user_choice"] is None


# ---------------------------------------------------------------------------
# 9. --annotate-legacy：解锁旧板、写 legacy 留痕、不伪造 B 板
# ---------------------------------------------------------------------------


def make_legacy_confirmed_board():
    """造一份"旧流程"已确认板：user_locked=true、schema_version=1。"""
    board = {
        "schema_version": 1,
        "board_id": "b-legacy-2026-10-30",
        "language": "python",
        "revision": 2,
        "problem_summary": {"title": "旧工作区", "questions": ["Q1"], "key_ambiguities": []},
        "mindmap": {"format": "mermaid", "source": "graph LR\n  P[旧题] --> Q1[Q1]"},
        "questions": [
            {
                "id": "Q1",
                "goal": "求最优方案",
                "options": [
                    {
                        "id": "O1",
                        "name": "整数规划",
                        "rationale": "线性结构清晰",
                        "risk": "规模变大需换求解器",
                        "source_ref": {"type": "method_card", "ref": "OPT-01", "verified": True},
                    },
                    {
                        "id": "O2",
                        "name": "贪心启发式",
                        "rationale": "实现简单",
                        "risk": "无最优性保证",
                        "source_ref": {"type": "method_card", "ref": "OPT-02", "verified": True},
                    },
                ],
                "user_choice": "O1",
                "user_locked": True,
                "user_comment": "已锁定 O1",
                "confirmed": True,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 2,
        "confirmed": True,
        "confirmed_at": "2026-10-20T10:00:00+00:00",
        "confirmed_by": "user",
        "confirm_attested": True,
    }
    board["board_sha256"] = design_board.compute_board_sha256(board)
    board["confirm_code"] = design_board.derive_confirm_code(board["board_sha256"])
    return board


def test_annotate_legacy_unlocks_selection_and_marks_gate_a_only(tmp_path):
    """旧板 user_locked=true 迁移为 false + migrated_release_lock；无 B 板写 legacy 标记。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_json(workspace / "design_board.json", make_legacy_confirmed_board())
    (workspace / "solution.py").write_text("print('legacy')\n", encoding="utf-8")

    report = migrate_workspace.annotate_legacy_board(str(workspace), apply=True)

    board = read_json(workspace / "design_board.json")
    question = board["questions"][0]
    assert question["user_locked"] is False, "A 板不得锁定模型选型"
    assert question["user_choice"] == "O1", "迁移不改用户已做出的选择记录"
    assert board["migrated_release_lock"] is True
    assert board["legacy_gate_a_only"] is True
    assert board["legacy_pre_two_gate"] is True
    assert report["written"] is True
    assert report["unlocked_questions"] == ["Q1"]
    assert report["requires_gate_b"] is True
    assert report["legacy_gate_a_only"] is True

    # 绝不伪造确认：确认字段一字不动，也绝不生成 B 板
    assert board["confirmed"] is True
    assert board["confirmed_by"] == "user"
    assert board["confirm_attested"] is True
    assert report["gate_b_written"] is False
    assert not (workspace / "design_board_gate_b.json").exists()
    assert any("--gate b" in step for step in report["next_steps"])

    # 标注改了顶层字段 → board_sha256 / confirm_code 必须重新对齐
    assert board["board_sha256"] == design_board.compute_board_sha256(board)
    assert board["confirm_code"] == board["board_sha256"][:4].upper()
    assert report["board_sha256_recomputed"] is True


def test_annotate_legacy_dry_run_never_writes(tmp_path):
    """默认 dry-run：报告要说清会改什么，文件一个字节都不能动。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = workspace / "design_board.json"
    write_json(path, make_legacy_confirmed_board())
    before = path.read_bytes()

    report = migrate_workspace.annotate_legacy_board(str(workspace), apply=False)

    assert report["written"] is False
    assert report["changed"] is True
    assert report["board_preview"]["questions"][0]["user_locked"] is False
    assert path.read_bytes() == before


def test_annotate_legacy_is_idempotent(tmp_path):
    """第二次标注不应再改任何东西（changed=False，不写盘）。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_json(workspace / "design_board.json", make_legacy_confirmed_board())
    migrate_workspace.annotate_legacy_board(str(workspace), apply=True)
    before = (workspace / "design_board.json").read_bytes()

    report = migrate_workspace.annotate_legacy_board(str(workspace), apply=True)

    assert report["changed"] is False
    assert report["written"] is False
    assert (workspace / "design_board.json").read_bytes() == before


def test_annotate_legacy_drops_stale_marker_when_gate_b_exists(tmp_path):
    """已有 B 板时不得再挂 legacy_gate_a_only（会把新流程误判成旧工作区）。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    board = make_legacy_confirmed_board()
    board["legacy_gate_a_only"] = True
    write_json(workspace / "design_board.json", board)
    write_json(
        workspace / "design_board_gate_b.json",
        {"schema_version": 2, "gate": "b", "questions": [{"id": "Q1", "confirmed": False}]},
    )

    report = migrate_workspace.annotate_legacy_board(str(workspace), apply=True)

    updated = read_json(workspace / "design_board.json")
    assert "legacy_gate_a_only" not in updated
    assert report["requires_gate_b"] is False
    assert report["next_steps"] == []
    assert report["gate_b_written"] is False


def test_annotate_legacy_requires_existing_board(tmp_path):
    """空工作区没有旧板可标注：必须报错，而不是偷偷造一份。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()

    with pytest.raises(ValueError) as excinfo:
        migrate_workspace.annotate_legacy_board(str(workspace), apply=True)
    assert "缺少 design_board.json" in str(excinfo.value)
    assert not (workspace / "design_board.json").exists()


def test_annotate_legacy_cli_writes_and_reports(tmp_path):
    """CLI 入口：--annotate-legacy --apply 退出 0，stdout 是 JSON 报告。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_json(workspace / "design_board.json", make_legacy_confirmed_board())

    proc = run_tool(MIGRATE_TOOL, "--workspace", str(workspace), "--annotate-legacy", "--apply")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["action"] == "annotate-legacy"
    assert payload["written"] is True
    assert payload["legacy_gate_a_only"] is True
    assert payload["gate_b_written"] is False
    assert read_json(workspace / "design_board.json")["legacy_gate_a_only"] is True
