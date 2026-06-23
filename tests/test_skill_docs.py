#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKILL.md 文档一致性测试"""

import os
import re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DOC = os.path.join(SKILL_DIR, "SKILL.md")


def read_skill_doc():
    with open(SKILL_DOC, "r", encoding="utf-8") as f:
        return f.read()


def test_python_template_defines_main_before_calling_it():
    """测试：Python 模板必须定义 main 后再调用 main"""
    content = read_skill_doc()
    templates_path = os.path.join(SKILL_DIR, "references", "templates.md")
    with open(templates_path, "r", encoding="utf-8") as f:
        templates = f.read()
    assert "def main():" in templates
    assert 'if __name__ == "__main__":\n    main()' in templates


def test_parallel_phase_uses_final_solution_not_phase2_report_dependency():
    """测试：并行代码 Agent 不得依赖 Phase 2 已写出的报告作为输入"""
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    phase3_match = re.search(r"### Phase 3:[\s\S]*?### Phase 4:", workflow)
    assert phase3_match is not None
    phase3_step = phase3_match.group(0)
    assert "final_solution.json" in phase3_step
    assert "problem_brief.md" in phase3_step
    assert "不等待 Phase 2" in phase3_step
    assert "读取 Phase 2 创建的 `modeling_report.md`" not in phase3_step


def test_tool_output_docs_include_new_failure_fields():
    """测试：文档必须说明新增 JSON 字段的判定语义"""
    tools_path = os.path.join(SKILL_DIR, "references", "tools.md")
    with open(tools_path, "r", encoding="utf-8") as f:
        tools_doc = f.read()
    assert "changed_files" in tools_doc
    assert "passed_all" in tools_doc
    assert "total == 0" in tools_doc
    assert "`document` 是 `model` 的兼容别名" in tools_doc


def test_skill_doc_is_short_and_points_to_references():
    """测试：主 SKILL.md 应短而明确，详细流程放入 references"""
    content = read_skill_doc()
    assert len(content.splitlines()) <= 520
    assert "references/workflow.md" in content
    assert "references/templates.md" in content
    assert "references/tools.md" in content
    assert "references/evals.md" in content


def test_parallel_agents_are_preserved_as_phase_gates():
    """测试：并行子 Agent 机制必须保留为硬性阶段门"""
    content = read_skill_doc()
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()

    combined = content + "\n" + workflow
    required_terms = [
        "五视角建模 Agent",
        "并行生成方案",
        "并行批评",
        "并行修正",
        "文档 Agent 与代码 Agent 并行",
        "语法审查 Agent",
        "逻辑审查 Agent",
        "输出审查 Agent",
    ]
    for term in required_terms:
        assert term in combined


def test_phase1_outputs_decision_files_not_modeling_report():
    """测试：Phase 1 只输出决策产物，报告由 Phase 2 生成"""
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    phase1_match = re.search(r"## Phase 1:[\s\S]*?## Phase 2", workflow)
    assert phase1_match is not None
    phase1 = phase1_match.group(0)
    assert "final_solution.json" in phase1
    assert "model_decision.md" in phase1
    assert "不得写入 `modeling_report.md`" in phase1
