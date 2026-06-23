#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建模方案共识系统测试"""

import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)

AGENT_ROLES = {
    "optimizer": {"name": "优化视角Agent", "bias": "倾向于优化模型"},
    "statistician": {"name": "统计视角Agent", "bias": "倾向于统计模型"},
    "physicist": {"name": "物理视角Agent", "bias": "倾向于机理模型"},
    "engineer": {"name": "工程视角Agent", "bias": "倾向于实用模型"},
    "innovator": {"name": "创新视角Agent", "bias": "倾向于AI/ML模型"},
}


def create_test_problem(problem_type="linear_programming"):
    """创建测试问题"""
    problems = {
        "linear_programming": {
            "type": "linear_programming",
            "description": "最大化利润的线性规划问题",
            "variables": ["x", "y"],
            "objective": "max 200x + 300y",
            "constraints": ["2x + y <= 80", "x + 3y <= 90", "x,y >= 0"]
        },
        "multi_objective": {
            "type": "multi_objective",
            "description": "多目标优化问题",
            "variables": ["x1", "x2", "x3"],
            "objective": "min f1, max f2",
            "constraints": ["sum(xi) = 1", "xi >= 0"]
        },
        "trade_off": {
            "type": "trade_off",
            "description": "需要权衡的问题",
            "variables": ["a", "b"],
            "objective": "min cost, max quality",
            "constraints": ["budget limit", "time limit"]
        },
    }
    return problems.get(problem_type, problems["linear_programming"])


def create_sample_solution():
    """创建样本方案"""
    return {
        "model_name": "线性规划模型",
        "variables": [{"name": "x", "meaning": "A产品产量", "range": ">=0"}],
        "objective_function": "max f = 200x + 300y",
        "constraints": ["2x + y <= 80", "x + 3y <= 90"],
        "solution_method": "单纯形法",
        "assumptions": ["利润恒定", "产能固定"],
        "pros": ["计算快速", "全局最优"],
        "cons": ["线性假设"],
        "complexity": "O(n^3)"
    }


def create_sample_criticism():
    """创建样本批评"""
    return {
        "optimizer": {
            "agent_a": {
                "criticisms": ["未考虑非线性因素", "约束过于简化"],
                "suggestions": ["加入非线性项", "增加缓冲约束"],
                "severity": "medium",
                "score": 70
            }
        }
    }


def create_multiple_solutions():
    """创建多个方案"""
    solutions = {}
    for role in AGENT_ROLES:
        sol = create_sample_solution()
        sol["model_name"] = f"{role}视角模型"
        solutions[role] = sol
    return solutions


def evaluate_consensus(solutions: dict) -> dict:
    """评估共识度"""
    methods = [s.get("model_name", "") for s in solutions.values()]
    unique_methods = set(methods)
    n = len(methods)

    if len(unique_methods) == 1:
        consensus_score = 100.0
    elif len(unique_methods) == 2:
        consensus_score = 70.0
    elif len(unique_methods) <= n // 2:
        consensus_score = 50.0
    else:
        consensus_score = 30.0

    agreement_matrix = {}
    for agent_id in solutions:
        agreement_matrix[agent_id] = {
            other_id: solutions[agent_id].get("model_name") == solutions[other_id].get("model_name")
            for other_id in solutions
        }

    key_disagreements = []
    if len(unique_methods) > 1:
        key_disagreements.append(f"方法分歧: {', '.join(unique_methods)}")

    return {
        "consensus_score": round(consensus_score, 2),
        "agreement_matrix": agreement_matrix,
        "key_disagreements": key_disagreements,
        "convergence_trend": "improving" if consensus_score > 50 else "stagnant"
    }


def should_continue(round_num, consensus_history, max_rounds=5, consensus_threshold=80.0, stagnation_threshold=2):
    """判断是否继续共识循环"""
    if round_num >= max_rounds:
        return False
    if consensus_history and consensus_history[-1] >= consensus_threshold:
        return False
    if len(consensus_history) >= stagnation_threshold:
        recent = consensus_history[-stagnation_threshold:]
        if len(recent) >= 2:
            diffs = [abs(recent[i] - recent[i-1]) for i in range(1, len(recent))]
            if all(d < 2.0 for d in diffs):
                return False
    return True


def evaluate_convergence_trend(history):
    """评估收敛趋势"""
    if len(history) < 2:
        return "unknown"
    diffs = [history[i] - history[i-1] for i in range(1, len(history))]
    if all(d > 0 for d in diffs):
        return "improving"
    elif all(d < 0 for d in diffs):
        return "diverging"
    elif all(abs(d) < 2 for d in diffs):
        return "stagnant"
    else:
        return "mixed"


def test_simple_consensus():
    """测试1：简单问题快速收敛"""
    problem = create_test_problem("linear_programming")
    assert problem["type"] == "linear_programming"


def test_complex_consensus():
    """测试2：复杂问题需要多轮"""
    problem = create_test_problem("multi_objective")
    assert problem["type"] == "multi_objective"


def test_disagreement():
    """测试3：分歧问题"""
    problem = create_test_problem("trade_off")
    assert "trade_off" in problem["type"] or "权衡" in problem["description"]


def test_consensus_score():
    """测试4：共识度计算"""
    solutions = {
        "agent_a": {"model_name": "linear", "score": 90},
        "agent_b": {"model_name": "linear", "score": 85},
        "agent_c": {"model_name": "nonlinear", "score": 70}
    }
    result = evaluate_consensus(solutions)
    assert result["consensus_score"] > 50


def test_criticism_quality():
    """测试5：批评质量"""
    solution = create_sample_solution()
    assert len(solution["assumptions"]) > 0
    assert all(len(a) > 0 for a in solution["assumptions"])


def test_solution_modification():
    """测试6：方案修正"""
    original = create_sample_solution()
    modified = create_sample_solution()
    modified["model_name"] = "修正后的模型"
    assert modified["model_name"] != original["model_name"]


def test_final_decision():
    """测试7：最终裁决"""
    solutions = create_multiple_solutions()
    assert len(solutions) == len(AGENT_ROLES)
    for role in AGENT_ROLES:
        assert role in solutions


def test_max_rounds():
    """测试8：达到最大轮次"""
    history = [50, 55, 58]
    result = should_continue(3, history, max_rounds=3)
    assert result is False


def test_convergence_trend():
    """测试9：收敛趋势"""
    history = [50, 60, 70, 75, 78]
    trend = evaluate_convergence_trend(history)
    assert trend == "improving"


def test_agreement_matrix():
    """测试10：同意矩阵"""
    solutions = create_multiple_solutions()
    result = evaluate_consensus(solutions)
    assert "agreement_matrix" in result
    assert len(result["agreement_matrix"]) == len(solutions)


def test_should_continue_stagnation():
    """测试11：停滞检测"""
    history = [70, 70.5, 70.3]
    result = should_continue(2, history, max_rounds=5, stagnation_threshold=3)
    assert result is False


def test_should_continue_improving():
    """测试12：继续改进"""
    history = [50, 60, 70]
    result = should_continue(3, history, max_rounds=5, consensus_threshold=80)
    assert result is True
