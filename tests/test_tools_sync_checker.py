#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools_sync_checker 双仓库工具漂移检查测试"""

import json
from pathlib import Path

from tools import tools_sync_checker


SKILL_DIR = Path(__file__).resolve().parents[1]


def make_repo(root: Path, files: dict) -> Path:
    """在 `root/tools/` 下按 {文件名: 内容} 造一个最小仓库目录。"""
    tools_dir = root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (tools_dir / name).write_text(content, encoding="utf-8")
    return root


def test_identical_tools_pass(tmp_path):
    """两边完全一致 → passed，且 strict 模式不拦截。"""
    files = {"alpha.py": "X = 1\n", "beta.py": "Y = 2\n"}
    primary = make_repo(tmp_path / "p", dict(files))
    branch = make_repo(tmp_path / "b", dict(files))

    result = tools_sync_checker.build_result(primary, branch)

    assert result["passed"] is True
    assert result["counts"]["identical"] == 2
    assert result["counts"]["union"] == 2
    assert result["differs_unexpected"] == []
    assert result["differs_expected"] == []
    assert result["primary_only"] == []
    assert result["branch_only"] == []
    assert tools_sync_checker.exit_code_for(result, "strict") == 0


def test_unexpected_drift_warns_by_default_but_fails_strict(tmp_path):
    """不在白名单却内容不同 = 漂移：默认模式退出 0，strict 模式退出 1。"""
    primary = make_repo(tmp_path / "p", {"alpha.py": "X = 1\n"})
    branch = make_repo(tmp_path / "b", {"alpha.py": "X = 2\n"})

    result = tools_sync_checker.build_result(primary, branch)

    assert result["passed"] is False
    assert result["differs_unexpected"] == ["alpha.py"]
    assert result["differs_expected"] == []
    assert result["identical"] == []
    assert tools_sync_checker.exit_code_for(result, "default") == 0
    assert tools_sync_checker.exit_code_for(result, "strict") == 1

    # CLI 必须真的把 strict 的失败暴露成退出码，否则挂不到 CI 上。
    assert (
        tools_sync_checker.main(
            ["--primary", str(primary), "--branch", str(branch), "--mode", "strict", "--quiet"]
        )
        == 1
    )


def test_whitelisted_difference_still_passes(tmp_path):
    """白名单内的差异（doctor.py 等）属于预期差异，不算漂移。"""
    primary = make_repo(tmp_path / "p", {"doctor.py": "X = 1\n", "alpha.py": "A\n"})
    branch = make_repo(tmp_path / "b", {"doctor.py": "X = 2\n", "alpha.py": "A\n"})

    result = tools_sync_checker.build_result(primary, branch)

    assert result["passed"] is True
    assert result["differs_expected"] == ["doctor.py"]
    assert result["differs_unexpected"] == []
    assert result["identical"] == ["alpha.py"]
    assert tools_sync_checker.exit_code_for(result, "strict") == 0


def test_primary_only_design_gate_files_allowed_others_not(tmp_path):
    """只存在于主仓库的文件：设计闸门新增文件可接受，其它仍算漂移。"""
    primary = make_repo(
        tmp_path / "p",
        {"design_board.py": "D\n", "tools_sync_checker.py": "S\n", "newcomer.py": "N\n"},
    )
    branch = make_repo(tmp_path / "b", {"question_queue.py": "Q\n"})

    result = tools_sync_checker.build_result(primary, branch)

    assert result["primary_only"] == ["design_board.py", "newcomer.py", "tools_sync_checker.py"]
    assert result["branch_only"] == ["question_queue.py"]
    assert result["unexpected_primary_only"] == ["newcomer.py"]
    assert result["passed"] is False
    assert tools_sync_checker.exit_code_for(result, "strict") == 1


def test_cli_json_out_and_quiet(tmp_path):
    """`--json-out` 要落盘成可解析 JSON，供 CI 归档。"""
    files = {"alpha.py": "X = 1\n"}
    primary = make_repo(tmp_path / "p", dict(files))
    branch = make_repo(tmp_path / "b", dict(files))
    out_path = tmp_path / "reports" / "sync.json"

    code = tools_sync_checker.main(
        [
            "--primary",
            str(primary),
            "--branch",
            str(branch),
            "--json-out",
            str(out_path),
            "--quiet",
        ]
    )

    assert code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["mode"] == "default"
    assert payload["counts"]["identical"] == 1
