#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pre_tool_use_guard.py 的自测脚本（零第三方依赖）。

模拟 10 个场景，把宿主事件 JSON 从 stdin 喂给 guard，再断言 stdout /
stderr / exit code：

1. 未确认 + 写 solution.py              -> deny
2. 已确认 + 写 solution.py              -> allow（含“逐题 confirmed”兼容写法）
3. 未确认 + 写 README.md（非保护文件）  -> allow
4. 未确认 + 写 solution_tests.py        -> deny
5. MM_GATE_BYPASS=1 + 未确认 + solution.py -> allow，且 stderr 有警告
6. 缺字段 / 非法 JSON                   -> 不崩，allow（fail-open）
7. B 闸门（方案择定）未确认 + 写 questions/q1/solution.py -> deny（提示 B 闸门）
8. B 闸门已确认 + 写 questions/q1/solution.py 与根 solution.py -> allow
9. 写 questions/q1/perspective_trials/statistician.py -> allow（试算代码放行）
10. legacy 工作区（A 板 schema_version < 2、无 B 板）-> allow + stderr 警告

运行：``python hooks/selftest.py``
全部通过打印 ``10/10 passed`` 并 exit 0；否则打印失败详情并 exit 1。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
GUARD = HERE / "pre_tool_use_guard.py"
PROJECT_ROOT = HERE.parent

# 管道 / CI 下统一按 UTF-8 输出，避免 Windows 默认代码页把中文标签打乱
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


UNCONFIRMED_BOARD = {
    "schema_version": 1,
    "questions": [{"id": "Q1", "confirmed": False}],
    "confirmed": False,
    "no_change_rounds": 0,
}

CONFIRMED_BOARD = {
    "schema_version": 1,
    "questions": [{"id": "Q1", "confirmed": True}],
    "confirmed": True,
    "confirmed_at": "2026-06-28T12:00:00+00:00",
    "confirmed_by": "user",
    "confirm_code": "1402",
    "confirm_attested": True,
}

QUESTIONS_ONLY_BOARD = {
    "schema_version": 1,
    "questions": [{"id": "Q1", "confirmed": True}, {"id": "Q2", "confirmed": True}],
}

# A 板 schema v2（双闸门新流程）：只确认题意框架与待探索范式，不锁定模型选型。
GATE_A_V2_CONFIRMED = {
    "schema_version": 2,
    "gate": "a",
    "board_id": "b-2026-10-30-selftest",
    "questions": [
        {
            "id": "Q1",
            "paradigm_set": [{"paradigm_id": "P1", "family": "statistical_inference"}],
            "paradigm_selection": ["P1"],
            "options": [],
            "user_choice": None,
            "user_locked": False,
            "confirmed": True,
        }
    ],
    "confirmed": True,
    "confirmed_at": "2026-10-30T12:00:00+00:00",
    "confirmed_by": "user",
}

GATE_B_UNCONFIRMED = {
    "schema_version": 2,
    "gate": "b",
    "question_scope": "question",
    "questions": [{"id": "Q1", "user_choice": None, "confirmed": False}],
    "confirmed": False,
}

GATE_B_CONFIRMED = {
    "schema_version": 2,
    "gate": "b",
    "question_scope": "question",
    "questions": [{"id": "Q1", "user_choice": "O1", "confirmed": True}],
    "confirmed": True,
    "confirmed_at": "2026-10-30T12:30:00+00:00",
    "confirmed_by": "user",
}


def _write_named(directory, name, payload):
    """把 payload（dict 或原始文本）写到 directory/name。"""
    directory.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _write_board(workspace, payload):
    """写 A 板（design_board.json）。"""
    _write_named(workspace, "design_board.json", payload)
    return workspace


def _write_gate_b(workspace, payload):
    """写 B 板（design_board_gate_b.json）。"""
    _write_named(workspace, "design_board_gate_b.json", payload)
    return workspace


def _run(payload=None, raw=None, env_extra=None):
    """运行 guard，返回 CompletedProcess（stdout/stderr 为 bytes）。"""
    env = os.environ.copy()
    for key in ("MM_GATE_BYPASS", "MM_HOOK_STYLE"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)

    if raw is None:
        raw = json.dumps(payload, ensure_ascii=False)

    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=raw.encode("utf-8"),
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=30,
    )


def _stdout(proc):
    return proc.stdout.decode("utf-8", "replace")


def _stderr(proc):
    return proc.stderr.decode("utf-8", "replace")


def _check(condition, message, proc):
    if condition:
        return
    raise AssertionError(
        "%s\n  exit=%s\n  stdout=%r\n  stderr=%r"
        % (message, proc.returncode, _stdout(proc), _stderr(proc))
    )


def _is_allow(proc):
    """exit 0，且输出里没有 deny。"""
    if proc.returncode != 0:
        return False
    text = _stdout(proc).strip()
    if not text:
        return True
    try:
        data = json.loads(text)
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    return data.get("decision") != "deny" and data.get("permission") != "deny"


def _is_claude_deny(proc):
    """exit 0，stdout 是 {"decision": "deny", "reason": ...}。"""
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(_stdout(proc).strip() or "{}")
    except ValueError:
        return False
    if not isinstance(data, dict) or data.get("decision") != "deny":
        return False
    reason = data.get("reason") or ""
    return "设计闸门未通过" in reason and "design_board.json" in reason


def _write_event(target, tool_name="Write"):
    return {"tool_name": tool_name, "tool_input": {"file_path": str(target)}}


def scenario_1(root):
    """未确认 + 写 solution.py -> deny；同时验证 Cursor 风格与解析失败。"""
    workspace = _write_board(root / "ws_unconfirmed", UNCONFIRMED_BOARD)
    target = workspace / "solution.py"

    proc = _run(_write_event(target))
    _check(_is_claude_deny(proc), "未确认时写 solution.py 应被 deny", proc)
    _check(
        str(target) in json.loads(_stdout(proc))["reason"],
        "deny 原因里应包含目标路径",
        proc,
    )

    # Cursor 风格：exit 2 + stderr 原因，stdout 不应再输出 JSON
    cursor = _run(_write_event(target), env_extra={"MM_HOOK_STYLE": "cursor"})
    _check(cursor.returncode == 2, "Cursor 风格拒绝应 exit 2", cursor)
    _check("设计闸门未通过" in _stderr(cursor), "Cursor 拒绝应在 stderr 说明原因", cursor)
    _check(_stdout(cursor).strip() == "", "Cursor 拒绝时 stdout 应为空", cursor)

    # design_board.json 解析失败 -> 目标已确定受保护，必须 fail-closed
    broken = _write_board(root / "ws_broken", "{ this is not valid json")
    broken_target = broken / "solution.py"
    broken_proc = _run(_write_event(broken_target))
    _check(
        _is_claude_deny(broken_proc),
        "design_board.json 解析失败时应 fail-closed 拒绝",
        broken_proc,
    )
    _check(
        "[design-gate] hook error:" in _stderr(broken_proc),
        "解析失败应留下 hook error 痕迹",
        broken_proc,
    )


def scenario_2(root):
    """已确认 + 写 solution.py -> allow（顶层 confirmed 与逐题 confirmed 都兼容）。"""
    workspace = _write_board(root / "ws_confirmed", CONFIRMED_BOARD)
    target = workspace / "solution.py"
    proc = _run(_write_event(target))
    _check(_is_allow(proc), "顶层 confirmed=true 时应放行 solution.py", proc)
    _check(_stdout(proc).strip() == "", "Claude 风格放行时 stdout 应为空", proc)

    questions_workspace = _write_board(root / "ws_questions_confirmed", QUESTIONS_ONLY_BOARD)
    questions_target = questions_workspace / "solution.py"
    questions_proc = _run(_write_event(questions_target))
    _check(
        _is_allow(questions_proc),
        "所有 question 的 confirmed 都为 true 时应放行",
        questions_proc,
    )


def scenario_3(root):
    """未确认 + 写 README.md（非保护文件）-> allow。"""
    workspace = _write_board(root / "ws_unconfirmed", UNCONFIRMED_BOARD)
    target = workspace / "README.md"
    proc = _run(_write_event(target))
    _check(_is_allow(proc), "非保护文件不应被设计闸门拦截", proc)


def scenario_4(root):
    """未确认 + 写 solution_tests.py -> deny。"""
    workspace = _write_board(root / "ws_unconfirmed", UNCONFIRMED_BOARD)
    target = workspace / "solution_tests.py"
    proc = _run(_write_event(target))
    _check(_is_claude_deny(proc), "未确认时写 solution_tests.py 应被 deny", proc)


def scenario_5(root):
    """MM_GATE_BYPASS=1 + 未确认 + solution.py -> allow，且 stderr 有警告。"""
    workspace = _write_board(root / "ws_unconfirmed", UNCONFIRMED_BOARD)
    target = workspace / "solution.py"
    proc = _run(_write_event(target), env_extra={"MM_GATE_BYPASS": "1"})
    _check(_is_allow(proc), "MM_GATE_BYPASS=1 时应一律放行", proc)
    _check(
        "MM_GATE_BYPASS" in _stderr(proc),
        "旁路开关应在 stderr 留下警告",
        proc,
    )


def scenario_6(root):
    """缺字段 / 非法 JSON -> 不崩，allow（fail-open）。"""
    raws = [
        "",
        "not-json",
        "{}",
        '{"tool_name": "Write"}',
        '{"tool": "edit", "input": {}}',
    ]
    for raw in raws:
        proc = _run(raw=raw)
        _check(
            proc.returncode == 0,
            "畸形事件 %r 不应让 guard 崩溃（exit 0）" % (raw,),
            proc,
        )
        _check(
            _is_allow(proc),
            "畸形事件 %r 应 fail-open 放行" % (raw,),
            proc,
        )


def _deny_reason(proc):
    """取 Claude Code 风格 deny 的 reason；不是 deny 返回空串。"""
    try:
        data = json.loads(_stdout(proc).strip() or "{}")
    except ValueError:
        return ""
    if not isinstance(data, dict) or data.get("decision") != "deny":
        return ""
    return data.get("reason") or ""


def scenario_7(root):
    """B 闸门未确认：questions/q1/solution.py 与根 solution.py 都必须 deny。"""
    # 分支形态：每问一块 B 板，放在 questions/q1/ 下，未确认
    workspace = _write_board(root / "ws_gate_b_pending", GATE_A_V2_CONFIRMED)
    question_dir = workspace / "questions" / "q1"
    _write_named(question_dir, "design_board_gate_b.json", GATE_B_UNCONFIRMED)
    target = question_dir / "solution.py"

    proc = _run(_write_event(target))
    reason = _deny_reason(proc)
    _check(bool(reason), "B 板未确认时写 questions/q1/solution.py 应被 deny", proc)
    _check("设计闸门未通过" in reason, "拒绝文案应说明设计闸门未通过", proc)
    _check("B 闸门" in reason, "拒绝文案应明确指出这是 B 闸门", proc)
    _check(
        "design_board_gate_b.json" in reason,
        "拒绝文案应点名 design_board_gate_b.json",
        proc,
    )
    _check(
        "confirm --gate b" in reason and "render --gate b" in reason,
        "拒绝文案应给出 B 板 render/confirm 命令",
        proc,
    )
    _check(
        "design_board.json" in reason,
        "拒绝文案应同时给出 A 板命令（两板命令都要有）",
        proc,
    )

    # Cursor 风格同样拒绝
    cursor = _run(_write_event(target), env_extra={"MM_HOOK_STYLE": "cursor"})
    _check(cursor.returncode == 2, "B 闸门 Cursor 风格拒绝应 exit 2", cursor)
    _check("B 闸门" in _stderr(cursor), "Cursor 拒绝应在 stderr 说明原因", cursor)

    # 主仓库形态：工作区根一块 B 板缺失，A 板已是 schema v2 → 根 solution.py 也 deny
    root_ws = _write_board(root / "ws_gate_b_missing", GATE_A_V2_CONFIRMED)
    root_target = root_ws / "solution.py"
    root_proc = _run(_write_event(root_target))
    root_reason = _deny_reason(root_proc)
    _check(
        "design_board_gate_b.json" in root_reason,
        "A 板 schema v2 + 同级无 B 板时根 solution.py 应 deny",
        root_proc,
    )


def scenario_8(root):
    """B 闸门已确认：questions/q1 与工作区根的交付代码都放行。"""
    workspace = _write_board(root / "ws_gate_b_confirmed", GATE_A_V2_CONFIRMED)
    question_dir = workspace / "questions" / "q1"
    _write_named(question_dir, "design_board_gate_b.json", GATE_B_CONFIRMED)
    target = question_dir / "solution.py"

    proc = _run(_write_event(target))
    _check(_is_allow(proc), "B 板已确认时应放行 questions/q1/solution.py", proc)
    _check(_stdout(proc).strip() == "", "Claude 风格放行时 stdout 应为空", proc)

    # 主仓库形态：A 板 v2 + 同级 B 板已确认 → 根 solution.py 放行
    root_ws = _write_board(root / "ws_gate_b_root_confirmed", GATE_A_V2_CONFIRMED)
    _write_gate_b(root_ws, GATE_B_CONFIRMED)
    root_proc = _run(_write_event(root_ws / "solution.py"))
    _check(_is_allow(root_proc), "A 板 v2 + 同级 B 板已确认时应放行根 solution.py", root_proc)


def scenario_9(root):
    """perspective_trials/** 是试算代码，不是交付代码：无论板状态都放行。"""
    # 分支形态：A 板 v2 未确认（甚至没有 B 板），试算脚本仍然放行
    workspace = root / "ws_trials"
    question_dir = workspace / "questions" / "q1"
    _write_named(
        question_dir,
        "design_board.json",
        {"schema_version": 2, "questions": [{"id": "Q1", "confirmed": False}]},
    )
    trials_target = question_dir / "perspective_trials" / "statistician.py"
    proc = _run(_write_event(trials_target))
    _check(
        _is_allow(proc),
        "perspective_trials/ 下的试算脚本应放行（闸门只拦交付代码）",
        proc,
    )

    # 工作区根形态：连板都没有也必须放行
    bare = root / "ws_trials_bare"
    bare_trials = bare / "perspective_trials" / "optimizer.py"
    bare_proc = _run(_write_event(bare_trials))
    _check(_is_allow(bare_proc), "无任何板时写 perspective_trials/ 也应放行", bare_proc)


def scenario_10(root):
    """legacy 工作区（A 板 schema < 2、无 B 板）：放行但必须留下警告。"""
    workspace = _write_board(root / "ws_legacy_gate_a_only", CONFIRMED_BOARD)
    question_dir = workspace / "questions" / "q1"
    question_dir.mkdir(parents=True, exist_ok=True)
    target = question_dir / "solution.py"

    proc = _run(_write_event(target))
    _check(_is_allow(proc), "legacy 板 + 无 B 板时 questions/q1/solution.py 应放行", proc)
    stderr = _stderr(proc)
    _check("警告" in stderr, "legacy 放行必须在 stderr 留下警告", proc)
    _check("旧版 A 板" in stderr, "警告应说明这是旧版 A 板（legacy）", proc)
    _check("--gate b" in stderr, "警告应提示补做 B 闸门的命令", proc)

    # 工作区根同样放行 + 警告
    root_proc = _run(_write_event(workspace / "solution.py"))
    _check(_is_allow(root_proc), "legacy 板时根 solution.py 应放行", root_proc)
    _check("旧版 A 板" in _stderr(root_proc), "根交付代码的 legacy 放行也应警告", root_proc)

    # legacy 板但未确认 → 仍必须 deny（旧规则不放宽）
    stale = _write_board(root / "ws_legacy_unconfirmed", UNCONFIRMED_BOARD)
    stale_question = stale / "questions" / "q1"
    stale_question.mkdir(parents=True, exist_ok=True)
    stale_proc = _run(_write_event(stale_question / "solution.py"))
    _check(
        bool(_deny_reason(stale_proc)),
        "legacy 板未确认时仍应 deny（legacy 只免 B 板，不免 A 板确认）",
        stale_proc,
    )


SCENARIOS = [
    (1, "未确认 + solution.py -> deny（含 Cursor/解析失败子用例）", scenario_1),
    (2, "已确认 + solution.py -> allow", scenario_2),
    (3, "未确认 + README.md -> allow", scenario_3),
    (4, "未确认 + solution_tests.py -> deny", scenario_4),
    (5, "MM_GATE_BYPASS=1 -> allow 且 stderr 警告", scenario_5),
    (6, "缺字段 / 非法 JSON -> fail-open", scenario_6),
    (7, "B 闸门未确认 -> deny（含两板命令）", scenario_7),
    (8, "B 闸门已确认 -> allow", scenario_8),
    (9, "perspective_trials/** -> allow", scenario_9),
    (10, "legacy A 板 + 无 B 板 -> allow + 警告", scenario_10),
]


def main():
    if not GUARD.is_file():
        print("找不到 guard 脚本：%s" % GUARD, file=sys.stderr)
        return 1

    root = Path(tempfile.mkdtemp(prefix="design-gate-selftest-"))
    failures = []
    try:
        for number, name, func in SCENARIOS:
            try:
                func(root)
            except AssertionError as exc:
                failures.append((number, name, str(exc)))
                print("[%d/%d] FAILED  %s" % (number, len(SCENARIOS), name))
                print("      %s" % str(exc).replace("\n", "\n      "))
            except Exception as exc:  # 自测脚本自身的意外错误
                failures.append((number, name, "%s: %s" % (type(exc).__name__, exc)))
                print("[%d/%d] ERROR   %s" % (number, len(SCENARIOS), name))
                print("      %s: %s" % (type(exc).__name__, exc))
            else:
                print("[%d/%d] ok      %s" % (number, len(SCENARIOS), name))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    total = len(SCENARIOS)
    if failures:
        print("\n%d/%d passed" % (total - len(failures), total))
        return 1

    print("\n%d/%d passed" % (total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
