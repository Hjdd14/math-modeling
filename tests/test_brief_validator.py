#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brief_validator 工具测试"""

import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL_DIR, "tools", "brief_validator.py")
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def run_tool(*args):
    """运行工具并返回解析后的 JSON。

    子进程统一按 UTF-8 解码：Windows 默认用 GBK 解 stdout，而工具输出的是 UTF-8
    JSON（尤其当调用方导出了 PYTHONIOENCODING=utf-8 时），不指定编码会直接
    把 stdout 解成 None，测试随即 TypeError。
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, TOOL] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=SKILL_DIR,
        env=env,
    )
    assert result.returncode == 0, f"Error (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_extract_structure():
    """测试1：提取结构化信息"""
    result = run_tool("extract", "--brief", os.path.join(TEST_DATA, "problem_brief.md"))
    assert len(result["solve_targets"]) > 0
    assert len(result["known_conditions"]) > 0
    assert len(result["constraints"]) > 0


def test_validate_model():
    """测试2：验证建模结果"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    assert "passed" in result
    assert len(result["checks"]) > 0


def test_validate_document_alias_matches_model():
    """测试：document 阶段必须执行与 model 阶段相同的非空检查"""
    model_result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                            "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    document_result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                               "--stage", "document", "--target", os.path.join(TEST_DATA, "model_decision.md"))

    assert len(document_result["checks"]) > 0
    assert document_result["checks"] == model_result["checks"]
    assert document_result["score"] == model_result["score"]
    assert document_result["passed"] == model_result["passed"]


def test_validate_document_alias_does_not_pass_empty_checks(tmp_path):
    """测试：document 阶段不能因空检查列表直接 100 分通过"""
    sparse_doc = tmp_path / "sparse_report.md"
    sparse_doc.write_text("# 空报告\n\n没有覆盖题目目标。\n", encoding="utf-8")

    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "document", "--target", str(sparse_doc))

    assert len(result["checks"]) > 0
    assert result["score"] < 100


def test_validate_code():
    """测试3：验证代码实现"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "code", "--target", os.path.join(TEST_DATA, "solution.py"))
    assert all(check["status"] in ["pass", "fail", "warning"] for check in result["checks"])


def test_validate_output():
    """测试4：验证输出完整性"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "output", "--target", os.path.join(TEST_DATA, "results"))
    assert any("目标" in check["item"] or "求解" in check["item"] for check in result["checks"])


def test_report_generation():
    """测试5：报告生成"""
    files_json = json.dumps({"model": os.path.join(TEST_DATA, "model_decision.md")})
    result = run_tool("report", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--files", files_json)
    assert "checks" in result
    assert "overall_score" in result


def test_missing_brief():
    """测试6：缺失brief文件"""
    result = subprocess.run(
        [sys.executable, TOOL, "extract", "--brief", "nonexistent.md"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=SKILL_DIR,
    )
    assert result.returncode != 0


def test_score_range():
    """测试7：评分范围"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    assert 0 <= result["score"] <= 100


def test_check_details():
    """测试8：检查项详情"""
    result = run_tool("validate", "--brief", os.path.join(TEST_DATA, "problem_brief.md"),
                      "--stage", "model", "--target", os.path.join(TEST_DATA, "model_decision.md"))
    for check in result["checks"]:
        assert "item" in check
        assert "status" in check
        assert "detail" in check

# ---------------------------------------------------------------------------
# problem_brief.md 选型锁定扫描（brief_completeness_checker）
# 闸门 A 只确认框架与待探索范式；"已锁定 / 不得推翻 / user_locked=true" 是
# 选型锁定措辞，必须被抓住，否则 Phase 1 五视角会照抄成"只用这一个模型"。
# ---------------------------------------------------------------------------

BRIEF_TOOL = os.path.join(SKILL_DIR, "tools", "brief_completeness_checker.py")

COMPLETE_BRIEF = (
    "# 题目\n\n"
    "## 目标\n求最优产量。\n\n"
    "## 约束\n线性产能上限。\n\n"
    "## 输出\n方案与数字结果。\n"
)


def run_brief_tool(*args):
    """运行 brief_completeness_checker；返回 (exit_code, 解析后的 JSON)。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, BRIEF_TOOL] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=SKILL_DIR,
        env=env,
    )
    return result.returncode, json.loads(result.stdout)


def _brief_issue_codes(payload):
    return {issue["code"] for issue in payload["issues"]}


def test_brief_lock_scan_flags_root_brief(tmp_path):
    """根 problem_brief.md 写了"已锁定 / 不得更换" -> excellence 判 error。"""
    (tmp_path / "problem_brief.md").write_text(
        COMPLETE_BRIEF + "\n## 6. 已锁定的模型选型（O1，不得更换）\n",
        encoding="utf-8",
    )

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "excellence")

    assert code == 1
    assert payload["passed"] is False
    assert "brief_contains_locked_selection" in _brief_issue_codes(payload)
    issue = next(i for i in payload["issues"] if i["code"] == "brief_contains_locked_selection")
    assert issue["severity"] == "error"
    assert issue["file"] == "problem_brief.md"
    assert issue["line"] >= 1


def test_brief_lock_scan_flags_question_brief(tmp_path):
    """questions/q1/problem_brief.md 的锁定措辞同样必须被抓（v1 只查根简报）。"""
    (tmp_path / "problem_brief.md").write_text(COMPLETE_BRIEF, encoding="utf-8")
    question_dir = tmp_path / "questions" / "q1"
    question_dir.mkdir(parents=True)
    (question_dir / "problem_brief.md").write_text(
        COMPLETE_BRIEF + "\n主模型已由 Phase 0.5 设计闸门锁定为 O1，user_locked = true。\n",
        encoding="utf-8",
    )

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "excellence")

    assert code == 1
    codes = _brief_issue_codes(payload)
    assert "brief_contains_locked_selection" in codes
    files = {i["file"] for i in payload["issues"] if i["code"] == "brief_contains_locked_selection"}
    assert "questions/q1/problem_brief.md" in files
    assert "problem_brief.md" not in files


def test_brief_lock_scan_is_warning_in_standard_mode(tmp_path):
    """standard 只 warning（旧工作区不被一刀切判死），但必须留下待办。"""
    (tmp_path / "problem_brief.md").write_text(
        COMPLETE_BRIEF + "\n## 五、已锁定（AI 不得推翻）\n",
        encoding="utf-8",
    )

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "standard")

    assert code == 0
    assert payload["passed"] is True
    assert payload["warning"] is True
    severities = {
        i["severity"] for i in payload["issues"] if i["code"] == "brief_contains_locked_selection"
    }
    assert severities == {"warning"}


def test_brief_lock_scan_passes_clean_multiquestion_workspace(tmp_path):
    """干净的多问工作区：根 + 每问简报都没有锁定措辞 -> 检查项全过。"""
    (tmp_path / "problem_brief.md").write_text(
        COMPLETE_BRIEF + "\n## 待探索范式集合\n见 design_board.json 的 paradigm_selection。\n",
        encoding="utf-8",
    )
    for name in ("q1", "q2"):
        question_dir = tmp_path / "questions" / name
        question_dir.mkdir(parents=True, exist_ok=True)
        (question_dir / "problem_brief.md").write_text(COMPLETE_BRIEF, encoding="utf-8")

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "excellence")

    assert code == 0
    assert payload["passed"] is True
    assert "brief_contains_locked_selection" not in _brief_issue_codes(payload)
    lock_checks = [c for c in payload["checks"] if c["name"] == "no_locked_selection"]
    assert {c["file"] for c in lock_checks} == {
        "problem_brief.md",
        "questions/q1/problem_brief.md",
        "questions/q2/problem_brief.md",
    }
    assert all(c["passed"] for c in lock_checks)

def test_brief_lock_scan_catches_user_locked_true_alone(tmp_path):
    """只写 user_locked = true（不带其它锁定措辞）也必须被抓。"""
    (tmp_path / "problem_brief.md").write_text(
        COMPLETE_BRIEF + "\n模型：O1（user_locked = true）\n",
        encoding="utf-8",
    )

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "excellence")

    assert code == 1
    matches = [
        issue.get("match", "")
        for issue in payload["issues"]
        if issue["code"] == "brief_contains_locked_selection"
    ]
    assert any("user_locked" in match for match in matches), matches


def test_brief_lock_scan_allows_negated_paradigm_wording(tmp_path):
    """正确写法「A 闸门不锁定选型」「由 B 闸门 user_choice 决定」不得误报。"""
    (tmp_path / "problem_brief.md").write_text(
        COMPLETE_BRIEF
        + "\n## 范式说明\n闸门 A 不锁定选型，只确认待探索范式集合；"
        "模型由 B 闸门的 user_choice 决定。\n",
        encoding="utf-8",
    )

    code, payload = run_brief_tool("--workspace", str(tmp_path), "--mode", "excellence")

    assert code == 0, payload
    assert payload["passed"] is True
    assert "brief_contains_locked_selection" not in _brief_issue_codes(payload)
