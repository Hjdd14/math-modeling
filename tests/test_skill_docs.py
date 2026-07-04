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
    """测试：并行代码 Agent 不得依赖 Phase 2 写作交接作为输入"""
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    phase3_match = re.search(r"### Phase 3:[\s\S]*?### Phase 4:", workflow)
    assert phase3_match is not None
    phase3_step = phase3_match.group(0)
    assert "final_solution.json" in phase3_step
    assert "problem_brief.md" in phase3_step
    assert "不等待 Phase 2" in phase3_step
    assert "正式写作正文" not in phase3_step


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
    assert "references/competition_sources.json" in content
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


def test_hard_problem_evidence_gates_are_documented():
    """测试：难题准确性增强 gate 必须写入主入口和工作流"""
    content = read_skill_doc()
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    combined = content + "\n" + workflow

    required_terms = [
        "ambiguity_register.json",
        "assumption_ledger.md",
        "题意审计 Agent",
        "problem_taxonomy",
        "动态专家 Agent",
        "baseline_solution.json",
        "模型评分矩阵",
        "validation_summary.json",
        "独立复现 Agent",
        "evidence_checker.py",
    ]
    for term in required_terms:
        assert term in combined


def test_dynamic_experts_are_additive_not_replacements():
    """测试：动态专家只能追加，不能替换五视角 Agent"""
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()

    assert "保留原五视角" in workflow
    assert "最多追加 3 个动态专家 Agent" in workflow
    assert "不能替换" in workflow


def test_phase1_outputs_decision_files_not_formal_body():
    """测试：Phase 1 只输出决策产物，不生成正式写作正文"""
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    phase1_match = re.search(r"## Phase 1:[\s\S]*?## Phase 2", workflow)
    assert phase1_match is not None
    phase1 = phase1_match.group(0)
    assert "final_solution.json" in phase1
    assert "model_decision.md" in phase1
    assert "不生成正式写作正文" in phase1


def test_1_2_excellence_delivery_gates_are_documented():
    """测试：1.2.0 一等奖级交付增强必须被主入口和工作流引用"""
    content = read_skill_doc()
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    templates_path = os.path.join(SKILL_DIR, "references", "templates.md")
    tools_path = os.path.join(SKILL_DIR, "references", "tools.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    with open(templates_path, "r", encoding="utf-8") as f:
        templates = f.read()
    with open(tools_path, "r", encoding="utf-8") as f:
        tools_doc = f.read()
    combined = "\n".join([content, workflow, templates, tools_doc])

    required_terms = [
        "model_spec.json",
        "data_schema.json",
        "schema_checker.py",
        "solution_tests.py",
        "symbol_table.json",
        "unit_checker.py",
        "solver_strategy.json",
        "reproducibility_manifest.json",
        "figure_style.json",
        "figure_auditor.py",
        "figure_storyboard.md",
        "writer_prompt.md",
        "case_retrieval.json",
        "innovation_register.json",
        "judge_panel_review.json",
        "compliance_record.json",
        "source_registry_checker.py",
        "case_retrieval_checker.py",
        "award_readiness_checker.py",
        "writer_prompt_checker.py",
        "innovation_checker.py",
        "judge_panel_checker.py",
        "compliance_checker.py",
        "scoring_strategy.md",
        "ablation_study.json",
        "decision_insights.md",
        "defense_questions.md",
        "可视化设计 Agent",
        "多评委并行审查",
        "评委质询 Agent",
        "--quality-mode",
    ]
    for term in required_terms:
        assert term in combined


def test_skill_boundary_outputs_writer_prompt_not_formal_report_body():
    """测试：skill 边界必须转向建模代码交付与写作交接提示词"""
    content = read_skill_doc()
    workflow_path = os.path.join(SKILL_DIR, "references", "workflow.md")
    templates_path = os.path.join(SKILL_DIR, "references", "templates.md")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = f.read()
    with open(templates_path, "r", encoding="utf-8") as f:
        templates = f.read()
    combined = "\n".join([content, workflow, templates])

    assert "writer_prompt.md" in combined
    assert "不生成正式写作正文" in combined
    assert "写作交接提示词" in combined

    fixed_product_match = re.search(r"## 固定产物[\s\S]*?## 执行入口", content)
    assert fixed_product_match is not None
    fixed_products = fixed_product_match.group(0)
    assert "writer_prompt.md" in fixed_products
    assert "modeling_report.md" not in fixed_products


def test_award_playbook_and_evaluator_panel_references_exist():
    """测试：奖项级方法谱系与评委组参考必须可发现"""
    sources_path = os.path.join(SKILL_DIR, "references", "competition_sources.json")
    award_path = os.path.join(SKILL_DIR, "references", "award_playbook.md")
    panel_path = os.path.join(SKILL_DIR, "references", "evaluator_panel.md")
    assert os.path.exists(sources_path)
    assert os.path.exists(award_path)
    assert os.path.exists(panel_path)

    with open(award_path, "r", encoding="utf-8") as f:
        award = f.read()
    with open(panel_path, "r", encoding="utf-8") as f:
        panel = f.read()

    for phrase in ["2012-2025", "2018-2026", "国赛展示", "COMAP"]:
        assert phrase in award
    for problem_type in ["优化调度", "预测统计", "图网络路径", "随机仿真", "物理机理", "政策决策", "多目标鲁棒", "机器学习混合"]:
        assert problem_type in award
    for judge in ["国赛建模评委", "美赛评委", "代码复现评委", "图表证据评委", "工程/业务解释评委", "chair judge"]:
        assert judge in panel
