#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""决策板本地回传服务器（`design_board.py serve`）的测试。

服务用 `port=0` 在**进程内**起（拿随机空闲端口），不启子进程、不 sleep 猜就绪，
测试结束显式 shutdown，避免残留监听端口。

覆盖点对应设计约束：
- 只接受带正确 `X-MM-Token` 的 POST（挡跨源表单伪造回执）；
- token 只在服务端响应时注入，磁盘上的 HTML 保持占位符；
- 网页提交走与命令行 `ingest` 同一条校验路径（非法 option 被拒）；
- 提交后写入 `design_rounds/`，但**绝不**写确认字段；
- `--once` 语义：收到一份回执后服务自行停止。
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools import design_board

BOARD_ID = "b-2026-06-28-serve-test"


def make_board(option_ids=("O1", "O2", "O3")):
    """最小合法板：1 题 + N 个候选，未确认。"""
    options = []
    for index, oid in enumerate(option_ids):
        options.append(
            {
                "id": oid,
                "name": f"候选算法 {oid}",
                "tier": "recommended" if index == 0 else "alternative",
                "rationale": f"{oid} 的理由",
                "source_ref": {
                    "type": "method_card",
                    "ref": f"OPT-0{index + 1}",
                    "tier": "tier_a",
                    "verified": True,
                },
                "complexity": "O(1)",
                "dependencies": [],
                "risk": "无",
                "mini_trial": {"sample": "全量", "output": {"objective": 100 + index}, "seconds": 0.001},
            }
        )
    return {
        "schema_version": 1,
        "board_id": BOARD_ID,
        "language": "python",
        "created_at": "2026-06-28T10:00:00+00:00",
        "revision": 1,
        "problem_summary": {"title": "serve 测试题", "questions": ["问题一"], "key_ambiguities": []},
        "mindmap": {"format": "mermaid", "source": "graph LR\n  P[题目] --> Q1[问题一]"},
        "questions": [
            {
                "id": "Q1",
                "goal": "在约束内最大化总利润",
                "options": options,
                "user_choice": "O1",
                "user_locked": False,
                "user_comment": "",
                "confirmed": False,
            }
        ],
        "pending_decisions": [],
        "no_change_rounds": 0,
    }


@pytest.fixture()
def served(tmp_path):
    """起一个进程内服务器，yield (base_url, token, workspace, state)。"""
    workspace = tmp_path
    (workspace / "design_board.json").write_text(
        json.dumps(make_board(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    token = "unit-test-token-0123456789"
    state = {"stopped": False, "submissions": 0, "last_result": None}
    server, _handler, url = design_board.build_serve_server(workspace, token, state, port=0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
    )
    thread.start()
    try:
        yield url.rstrip("/"), token, workspace, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.read().decode("utf-8")


def _post(url: str, payload, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if token is not None:
        request.add_header("X-MM-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _envelope(**overrides):
    payload = {
        "board_id": BOARD_ID,
        "at": "2026-06-28T12:00:00+00:00",
        "receipt_origin": "browser-submit",
        "nonce": "test-nonce",
        "user_edited": True,
        "decisions": [{"question_id": "Q1", "option_id": "O2"}],
        "comments": [{"question_id": "Q1", "text": "网页上选的"}],
    }
    payload.update(overrides)
    return payload


def test_ping_reports_board_identity(served):
    base, _token, _workspace, _state = served

    status, body = _get(base + "/api/ping")

    assert status == 200
    payload = json.loads(body)
    assert payload["ok"] is True
    assert payload["board_id"] == BOARD_ID
    assert payload["confirmed"] is False


def test_page_injects_token_without_writing_it_to_disk(served):
    base, token, workspace, _state = served

    status, page = _get(base + "/")

    assert status == 200
    assert "提交选择" in page
    match = re.search(r'data-token="([^"]+)"', page)
    assert match is not None, "页面必须带 data-token"
    assert match.group(1) == token
    # 磁盘上的 HTML 不该含真 token（render 落盘时是占位符或不含 token）
    on_disk = (workspace / "design_board.html")
    if on_disk.exists():
        assert token not in on_disk.read_text(encoding="utf-8")


def test_submit_requires_token(served):
    base, token, _workspace, _state = served

    status_without, payload_without = _post(base + "/api/submit", _envelope())
    status_wrong, payload_wrong = _post(base + "/api/submit", _envelope(), token="wrong-token")

    assert status_without == 403
    assert status_wrong == 403
    assert payload_without["ok"] is False
    assert "X-MM-Token" in payload_wrong["error"]
    # 被拒的请求不能写任何轮次
    assert not (_workspace / "design_rounds").exists() or not list(
        (_workspace / "design_rounds").glob("round_*.json")
    )


def test_valid_submit_writes_round_and_left_unconfirmed(served):
    base, token, workspace, state = served

    status, payload = _post(base + "/api/submit", _envelope(), token=token)

    assert status == 200
    assert payload["ok"] is True
    result = payload["result"]
    assert result["round"] == 1
    assert result["user_edited"] is True
    assert result["no_change_rounds"] == 0
    assert result["receipt_origin"] == "browser-submit"
    assert state["submissions"] == 1

    round_file = workspace / "design_rounds" / "round_001.json"
    assert round_file.is_file()
    round_payload = json.loads(round_file.read_text(encoding="utf-8"))
    assert round_payload["receipt_origin"] == "browser-submit"
    assert round_payload["changes"][0]["to"] == "O2"

    board = json.loads((workspace / "design_board.json").read_text(encoding="utf-8"))
    assert board["questions"][0]["user_choice"] == "O2"
    assert board["questions"][0]["user_comment"] == "网页上选的"
    # 网页提交绝不能写确认字段
    assert board.get("confirmed") is not True
    assert board.get("confirm_attested") is not True
    assert board.get("confirm_code") in (None, "")


def test_submit_rejects_unknown_option(served):
    base, token, workspace, _state = served

    status, payload = _post(
        base + "/api/submit",
        _envelope(decisions=[{"question_id": "Q1", "option_id": "O99"}]),
        token=token,
    )

    assert status == 400
    assert payload["ok"] is False
    assert "O99" in payload["error"]
    assert not (workspace / "design_rounds").exists() or not list(
        (workspace / "design_rounds").glob("round_*.json")
    )


def test_submit_rejects_malformed_body(served):
    base, token, _workspace, _state = served

    status, payload = _post(base + "/api/submit", {"decisions": "not-a-list"}, token=token)

    assert status == 400
    assert payload["ok"] is False


def test_unknown_route_returns_404(served):
    base, token, _workspace, _state = served

    status, payload = _post(base + "/api/nope", {}, token=token)
    assert status == 404

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(base + "/api/nope")
    assert excinfo.value.code == 404


def test_two_submissions_increment_rounds(served):
    base, token, workspace, _state = served

    first_status, first = _post(base + "/api/submit", _envelope(), token=token)
    # 第二次不改选择 → user_edited False，no_change_rounds 递增
    second_status, second = _post(
        base + "/api/submit", _envelope(decisions=[{"question_id": "Q1", "option_id": "O2"}]), token=token
    )

    assert first_status == 200 and second_status == 200
    assert first["result"]["round"] == 1
    assert second["result"]["round"] == 2
    assert second["result"]["user_edited"] is False
    assert second["result"]["no_change_rounds"] == 1
    assert (workspace / "design_rounds" / "round_002.json").is_file()


def test_once_mode_stops_after_first_submission(tmp_path):
    workspace = tmp_path
    (workspace / "design_board.json").write_text(
        json.dumps(make_board(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    token = "once-mode-token"
    state = {"stopped": False, "submissions": 0, "last_result": None}
    server, _handler, url = design_board.build_serve_server(
        workspace, token, state, port=0, once=True
    )
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
    )
    thread.start()
    try:
        status, payload = _post(url.rstrip("/") + "/api/submit", _envelope(), token=token)
        assert status == 200 and payload["ok"] is True
        thread.join(timeout=5)
        assert not thread.is_alive(), "once 模式必须在第一份回执后停止服务"
        assert state["stopped"] is True
    finally:
        server.server_close()


def test_serving_missing_board_fails_fast(tmp_path):
    state = {"stopped": False, "submissions": 0, "last_result": None}
    with pytest.raises(ValueError):
        design_board.build_serve_server(tmp_path, "token", state, port=0)
