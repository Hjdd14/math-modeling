#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pre_tool_use_guard.py 的自测脚本（零第三方依赖）。

模拟 6 个场景，把宿主事件 JSON 从 stdin 喂给 guard，再断言 stdout /
stderr / exit code：

1. 未确认 + 写 solution.py              -> deny
2. 已确认 + 写 solution.py              -> allow（含“逐题 confirmed”兼容写法）
3. 未确认 + 写 README.md（非保护文件）  -> allow
4. 未确认 + 写 solution_tests.py        -> deny
5. MM_GATE_BYPASS=1 + 未确认 + solution.py -> allow，且 stderr 有警告
6. 缺字段 / 非法 JSON                   -> 不崩，allow（fail-open）

运行：``python hooks/selftest.py``
全部通过打印 ``6/6 passed`` 并 exit 0；否则打印失败详情并 exit 1。
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


def _write_board(workspace, payload):
    workspace.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    (workspace / "design_board.json").write_text(text, encoding="utf-8")
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


SCENARIOS = [
    (1, "未确认 + solution.py -> deny（含 Cursor/解析失败子用例）", scenario_1),
    (2, "已确认 + solution.py -> allow", scenario_2),
    (3, "未确认 + README.md -> allow", scenario_3),
    (4, "未确认 + solution_tests.py -> deny", scenario_4),
    (5, "MM_GATE_BYPASS=1 -> allow 且 stderr 警告", scenario_5),
    (6, "缺字段 / 非法 JSON -> fail-open", scenario_6),
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
                print("[%d/6] FAILED  %s" % (number, name))
                print("      %s" % str(exc).replace("\n", "\n      "))
            except Exception as exc:  # 自测脚本自身的意外错误
                failures.append((number, name, "%s: %s" % (type(exc).__name__, exc)))
                print("[%d/6] ERROR   %s" % (number, name))
                print("      %s: %s" % (type(exc).__name__, exc))
            else:
                print("[%d/6] ok      %s" % (number, name))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print("\n%d/6 passed" % (len(SCENARIOS) - len(failures)))
        return 1

    print("\n6/6 passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
