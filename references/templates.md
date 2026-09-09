# 数学建模模板

## problem_brief.md

```markdown
# 数学建模题目简报

## 1. 题目原文

## 2. 求解目标

## 3. 已知条件与参数

## 4. 约束条件

## 5. 附件数据

## 6. 输出要求

## 7. 评分标准（如有）
```

## ambiguity_register.json

```json
{
  "items": [
    {
      "id": "A1",
      "severity": "medium",
      "source": "problem statement",
      "issue": "字段或约束含义需要确认",
      "impact": "影响模型变量或约束解释",
      "resolution": "pending",
      "assumption_if_unresolved": "明确写入 assumption_ledger.md"
    }
  ]
}
```

## assumption_ledger.md

```markdown
# 建模假设台账

| ID | 假设 | 来源 | 影响 | 验证方式 | 状态 |
|----|------|------|------|----------|------|
| H1 |  | 题目/附件/用户确认 |  | baseline/oracle/sensitivity | pending |

## 未解决高风险歧义

- 无；如有 high severity，必须同步写入 modeling_memory.md。
```

## baseline_solution.json

```json
{
  "baseline_name": "naive_feasible_solution",
  "rationale": "使用简单、可运行、可解释的方法作为下限",
  "inputs_required": ["problem_brief.md"],
  "method": "greedy / mean / last-value / enumeration / shortest-path",
  "expected_outputs": ["results/output.csv", "results/summary.json"],
  "limitations": ["不追求最优，只用于可信度对比"]
}
```

## scoring_strategy.md

```markdown
# 评分策略

| 小问 | 必答结果 | 评分重点 | 需要图表 | 创新表达 |
|------|----------|----------|----------|----------|
| 问题一 | 数值/排名/方案 | 模型合理性、结果可解释 | 是 | baseline 对比 |
```

## data_schema.json

```json
{
  "datasets": [
    {
      "path": "data.csv",
      "primary_key": ["id"],
      "fields": [
        {
          "name": "value",
          "type": "number",
          "unit": "件",
          "required": true,
          "min": 0,
          "max_missing_rate": 0.05
        }
      ]
    }
  ]
}
```

## symbol_table.json

```json
{
  "symbols": [
    {
      "symbol": "x_i",
      "meaning": "第 i 类产品产量",
      "unit": "件",
      "code_name": "x_i"
    }
  ]
}
```

## model_spec.json

```json
{
  "variables": [
    {"name": "x", "type": "decision", "unit": "件", "bounds": [0, null], "code_name": "x"}
  ],
  "objective": {"sense": "max", "expression": "profit * x"},
  "constraints": [{"name": "capacity", "expression": "x <= capacity"}],
  "parameters": [{"name": "profit", "unit": "元/件", "source": "data_schema.json"}],
  "data_fields": [{"name": "value", "dataset": "data.csv", "unit": "件"}],
  "solution_method": "enumeration / scipy / dynamic programming / simulation",
  "validation_plan": {
    "baseline": "baseline_solution.json",
    "oracle": "small brute-force case",
    "solver_cross_check": "alternate solver or enumeration",
    "sensitivity": "one-at-a-time perturbation"
  },
  "figure_plan": ["baseline_vs_final", "sensitivity"]
}
```

## solver_strategy.json

```json
{
  "primary_solver": "scipy.optimize / enumeration / dynamic_programming",
  "fallback_solvers": ["brute_force_small_case", "greedy_feasible"],
  "timeout_seconds": 300,
  "cross_validation": "small-scale enumeration",
  "failure_policy": "write failure mode and fallback result instead of silently continuing"
}
```

## model_selection_audit.json

```json
{
  "candidates": [
    {"name": "integer_programming", "score": 0.92, "evidence": ["oracle_tests", "gap=0"]},
    {"name": "greedy_baseline", "score": 0.61, "rejection_reason": "不能证明全局最优", "evidence": ["baseline_comparison"]}
  ],
  "final_selection": {
    "name": "integer_programming",
    "score": 0.92,
    "evidence": ["constraint_residuals=0", "optimality_gap=0", "solver_cross_checks"]
  }
}
```

## optimization_certificate.json

```json
{
  "feasibility_residual": {"max_abs": 0.0, "tolerance": 1e-6},
  "bounds": {"lower": 0, "upper": 0},
  "optimality_gap": {"value": 0.0, "tolerance": 1e-4},
  "alternative_solver": {"name": "enumeration_or_second_solver", "value": 0, "passed": true}
}
```

## uncertainty_budget.json

```json
{
  "data": {"impact": "medium", "mitigation": "schema/hash/missingness checks"},
  "parameter": {"impact": "medium", "sensitivity": "关键参数正负扰动"},
  "model": {"impact": "medium", "evidence": "baseline、oracle、消融和评委审查"},
  "random": {"impact": "low", "mitigation": "固定随机种子并记录 3 个以上 seeds"}
}
```

## validation_profile.json

```json
{
  "profile": "optimization",
  "evidence": {
    "baseline": {"passed": true},
    "oracle": {"passed": true},
    "gap": {"value": 0.0, "passed": true},
    "residuals": {"max_abs": 0.0, "passed": true},
    "sensitivity": {"passed": true}
  }
}
```

## data_validation.json

```json
{
  "task_type": "forecasting",
  "target": "target_column",
  "features": ["feature_1", "feature_2"],
  "split": {"type": "time_series", "train_end": "YYYY-MM-DD", "holdout_start": "YYYY-MM-DD"},
  "preprocessing": [
    {"name": "standard_scaler", "fit_on": "train"}
  ]
}
```

## statistical_validation.json

```json
{
  "holdout": {"method": "time_split", "passed": true},
  "metrics": {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0},
  "residuals": {"checked": true},
  "intervals": {"level": 0.95, "coverage": 0.95},
  "robustness": {"passed": true},
  "overfitting_risk": {"level": "low", "evidence": "holdout/CV gap acceptable"}
}
```

## ablation_study.json

```json
{
  "experiments": [
    {
      "name": "without_capacity_constraint",
      "changed_component": "capacity constraint",
      "metric_delta": 0,
      "interpretation": "说明该约束对结果的影响",
      "passed": true
    }
  ]
}
```

## final_solution.json 关键字段

```json
{
  "selected_model": "final_model_name",
  "problem_taxonomy": {
    "primary_types": ["optimization"],
    "secondary_types": ["sensitivity_analysis"]
  },
  "score_matrix": [
    {
      "model_name": "candidate",
      "problem_fit": 90,
      "interpretability": 85,
      "computability": 80,
      "data_requirement": 75,
      "robustness": 80,
      "validation_difficulty": 40,
      "paper_presentation": 88,
      "decision": "selected"
    }
  ],
  "validation_plan": {
    "baseline_comparison": "compare final model against baseline_solution.json",
    "oracle_tests": "small known case or brute-force enumeration",
    "solver_cross_checks": "alternate implementation or solver",
    "sensitivity_analysis": "parameter perturbation",
    "invariants": ["constraints remain satisfied"]
  }
}
```

## case_retrieval.json

```json
{
  "problem_domain": "电力调度",
  "matched_problem_types": ["电力电工", "优化调度"],
  "matched_cases": [
    {
      "rank": 1,
      "source_competition": "中国电机工程学会杯全国大学生电工数学建模竞赛",
      "year": "2026",
      "problem_id": "A/B",
      "problem_type": "电力电工",
      "similarity_reason": "题目领域、数据结构和约束形式相近",
      "borrowable_methods": ["负荷预测", "潮流约束", "鲁棒调度"],
      "cannot_copy_risks": ["工况、电网拓扑和参数口径不同，不能照搬变量定义"],
      "validation_needed": ["小例 oracle", "物理约束检查", "敏感性分析"]
    }
  ],
  "candidate_methods": ["robust_dispatch", "scenario_analysis"],
  "cannot_copy_risks": ["公开案例只提供题型和验证启发，不复制原作品正文"]
}
```

## innovation_register.json

```json
{
  "innovations": [
    {
      "id": "I1",
      "claim": "用 Pareto 前沿解释多目标权衡",
      "problem_pain_point": "单一加权和会掩盖目标冲突",
      "baseline_gain": {
        "metric": "profit_per_emission",
        "delta": 0.12,
        "evidence": "ablation_study.json"
      },
      "implementation_cost": "medium",
      "interpretability": "通过权衡图和敏感性分析解释",
      "verification_evidence": ["baseline_comparison", "ablation_study", "sensitivity_analysis"],
      "failure_risk": "数据规模过小时前沿可能不稳定",
      "decision": "accepted"
    }
  ]
}
```

## writer_prompt.md

```markdown
# 写作交接提示词

本 skill 已完成建模、代码、图表和验证证据，不生成正式写作正文。请后续写作 skill 基于下列材料写作，并保持匿名性与合规披露。

## 1. 题目与小问

- 来源：problem_brief.md
- 必答结果：
- 评分重点：
- 竞赛来源匹配：case_retrieval.json

## 2. 模型主线

- 来源：final_solution.json / model_spec.json / model_decision.md
- 选择理由：
- 被拒方案：

## 3. 创新与证据

- 来源：case_retrieval.json / innovation_register.json / ablation_study.json
- 创新点：
- baseline 增益：
- 敏感性或消融证据：

## 4. 代码与结果

- 代码：solution.py 或 solution.m
- 结果：results/output.csv、results/summary.json、results/validation_summary.json
- 复现：reproducibility_manifest.json

## 5. 图表交接

- 来源：figure_storyboard.md / figure_style.json / results/figure_quality_report.json
- 每张图支撑的结论：

## 6. 评委组审查与风险

- 多评委审查：judge_panel_review.json
- high severity 是否全部解决：
- 风险提示：

## 7. 合规提示

- AI 使用记录：compliance_record.json
- 外部资料引用：
- 匿名性检查：
- 复现清单：reproducibility_manifest.json

## 8. 后续写作/提交复核清单

- 匿名：
- 引用：
- AI 披露：
- 页数/格式：
- 附件：
- 代码提交：
```

## judge_panel_review.json

```json
{
  "judges": [
    {"judge_type": "national_modeling_judge", "score": 88, "issues": [], "passed": true},
    {"judge_type": "comap_judge", "score": 86, "issues": [], "passed": true},
    {"judge_type": "code_reproducibility_judge", "score": 91, "issues": [], "passed": true},
    {"judge_type": "figure_evidence_judge", "score": 84, "issues": [], "passed": true},
    {"judge_type": "engineering_business_judge", "score": 87, "issues": [], "passed": true}
  ],
  "chair_summary": {
    "overall_score": 87,
    "decision": "pass",
    "required_fixes": [],
    "summary": "模型、代码、图表和验证证据可以交给写作阶段。"
  }
}
```

## compliance_record.json

```json
{
  "ai_usage": {
    "used": true,
    "tools": [{"name": "Codex", "version": "GPT-5", "purpose": "建模代码与验证辅助"}],
    "disclosure_required": true,
    "human_reviewed": true
  },
  "anonymity": {"checked": true, "identity_terms_found": []},
  "external_sources": [
    {"source": "COMAP instructions", "citation_location": "writer_prompt.md#合规提示"}
  ],
  "reproducibility": {
    "manifest": "reproducibility_manifest.json",
    "commands": ["python solution.py", "python tools/pipeline_check.py --quality-mode excellence"],
    "input_hashes_recorded": true,
    "output_hashes_recorded": true
  },
  "final_submission": {
    "anonymity": true,
    "ai_disclosure": true,
    "citation_check": true,
    "page_limit_checked": true,
    "attachment_check": true,
    "code_submission_note": "提交前复跑代码并确认环境说明。",
    "official_rules_reviewed": true
  }
}
```

## validation_summary.json

```json
{
  "baseline_comparison": {
    "baseline_name": "naive_feasible_solution",
    "metric": "objective_or_error",
    "baseline_value": 0,
    "model_value": 0,
    "passed": true
  },
  "oracle_tests": [
    {
      "name": "small_known_case",
      "expected": 0,
      "actual": 0,
      "passed": true
    }
  ],
  "solver_cross_checks": [
    {
      "name": "alternate_solver_or_enumeration",
      "primary": 0,
      "secondary": 0,
      "passed": true
    }
  ],
  "sensitivity_analysis": {
    "method": "one_at_a_time",
    "max_relative_change": 0,
    "passed": true
  },
  "invariants": [
    {
      "name": "constraints_satisfied",
      "passed": true
    }
  ],
  "failure_modes": [
    {
      "name": "missing_or_invalid_input",
      "mitigation": "stop with explicit error"
    }
  ],
  "constraint_residuals": {
    "max_abs": 0,
    "passed": true
  },
  "optimality_gap": {
    "value": 0,
    "passed": true
  },
  "multi_start": {
    "runs": 5,
    "best_values": [0, 0, 0],
    "passed": true
  },
  "random_seed_stability": {
    "seeds": [1, 2, 3],
    "std": 0,
    "passed": true
  },
  "bootstrap_confidence_interval": {
    "level": 0.95,
    "lower": 0,
    "upper": 0,
    "passed": true
  },
  "perturbation_stability": {
    "ranking_changed": false,
    "passed": true
  }
}
```

## solution_tests.py

```python
"""代码 Agent 先生成的契约测试。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_required_outputs_exist():
    for path in ["results/output.csv", "results/summary.json", "results/validation_summary.json"]:
        assert (ROOT / path).exists()


def test_validation_summary_fields():
    data = json.loads((ROOT / "results/validation_summary.json").read_text(encoding="utf-8"))
    for key in [
        "baseline_comparison",
        "oracle_tests",
        "solver_cross_checks",
        "sensitivity_analysis",
        "constraint_residuals",
        "optimality_gap",
    ]:
        assert key in data
```

## figure_style.json

```json
{
  "dpi": 300,
  "export_dpi": 600,
  "font_family": "DejaVu Sans",
  "font_size": 10,
  "line_width": 1.8,
  "colorblind_safe": true,
  "print_friendly": true,
  "formats": ["png", "pdf", "svg"]
}
```

## figure_storyboard.md

```markdown
# Figure Storyboard

- file: result_baseline_vs_final.png
  claim: 完整模型相对 baseline 提升明显
  source_data: results/output.csv
  x_unit: 情景
  y_unit: 指标值
  supports_question: Q1
  report_position: 模型求解
```

## decision_insights.md

```markdown
# 决策建议

- 关键结论：
- 工程/管理含义：
- 风险提示：
- 可执行策略：
- 不同情景建议：
```

## defense_questions.md

```markdown
# 评委质询模拟

| 问题 | 风险 | 回答要点 | 是否需要修正 |
|------|------|----------|--------------|
| 为什么选择该模型？ | 模型选择依据不足 | 引用 score_matrix 与消融实验 | 否 |
```

## reproducibility_manifest.json

```json
{
  "os": {"name": "Windows/Linux/macOS", "version": "..."},
  "python_version": "3.x",
  "matlab_version": null,
  "solvers": [{"name": "scipy.optimize.linprog", "version": "..."}],
  "dependencies": {"numpy": "version", "pandas": "version"},
  "random_libraries": [{"name": "numpy.random", "seed": 42}],
  "execution": {"seconds": 0.0},
  "random_seed": 42,
  "input_hashes": [{"path": "data.csv", "sha256": "..."}],
  "output_hashes": [{"path": "results/output.csv", "sha256": "..."}]
}
```

## Python solution.py

模板里的验证函数默认返回 `status: "NOT_VALIDATED"` 与 `passed: null`，这是**故意的**：占位证据不是证据。
必须用真实计算替换每个 `TODO(必填)` 处的返回值，并把 `status` 改为 `passed` 或 `failed`。
`evidence_checker.py` 与 `robustness_checker.py` 会拒绝仍含占位标记的 `validation_summary.json`，
所以照抄模板不做替换会在验证阶段直接失败，而不是伪装成通过。

对确定性模型（精确枚举、确定性线性规划、最短路、解析解 ODE），随机性相关条目
（`multi_start`、`random_seed_stability`、`bootstrap_confidence_interval`、`perturbation_stability`）
可以显式声明不适用，但必须同时给出理由和替代验证方式：

```json
{"status": "not_applicable", "rationale": "模型为确定性精确枚举，不涉及随机初始化", "alternative_validation": "全枚举穷举验证 + 约束残差检查"}
```

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模 Python 实现"""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd


RESULTS_DIR = Path("results")
# 占位状态：未经真实计算的证据一律标记为 NOT_VALIDATED，交给 checker 拦截。
NOT_VALIDATED = "NOT_VALIDATED"


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def run_baseline():
    # TODO(必填): 实际运行 baseline 与最终模型，填入真实数值，并把 status 改为 passed/failed
    return {
        "baseline_name": "naive_feasible_solution",
        "metric": "objective",
        "baseline_value": None,
        "model_value": None,
        "status": NOT_VALIDATED,
        "passed": None,
    }


def run_known_case_tests():
    # TODO(必填): 用可手算的小规模已知解替换 expected/actual
    return [
        {
            "name": "small_known_case",
            "expected": None,
            "actual": None,
            "status": NOT_VALIDATED,
            "passed": None,
        }
    ]


def run_solver_cross_checks():
    # TODO(必填): 用第二个求解器或穷举结果交叉验证主求解器
    return [
        {
            "name": "primary_vs_enumeration",
            "primary": None,
            "secondary": None,
            "status": NOT_VALIDATED,
            "passed": None,
        }
    ]


def run_sensitivity_analysis():
    # TODO(必填): 实际扰动关键参数并记录最大相对变化
    return {
        "method": "one_at_a_time",
        "max_relative_change": None,
        "status": NOT_VALIDATED,
        "passed": None,
    }


def write_validation_summary():
    # TODO(必填): 下列每一项都必须由真实计算产生；
    # 不适用的随机性条目请写成 {"status": "not_applicable", "rationale": ..., "alternative_validation": ...}
    summary = {
        "baseline_comparison": run_baseline(),
        "oracle_tests": run_known_case_tests(),
        "solver_cross_checks": run_solver_cross_checks(),
        "sensitivity_analysis": run_sensitivity_analysis(),
        "invariants": [{"name": "constraints_satisfied", "status": NOT_VALIDATED, "passed": None}],
        "failure_modes": [
            {"name": "missing_or_invalid_input", "mitigation": "stop with explicit error"}
        ],
        "constraint_residuals": {"max_abs": None, "tolerance": 1e-6, "status": NOT_VALIDATED, "passed": None},
        "optimality_gap": {"value": None, "tolerance": 1e-4, "status": NOT_VALIDATED, "passed": None},
        "multi_start": {"runs": 0, "best_values": [], "status": NOT_VALIDATED, "passed": None},
        "random_seed_stability": {"seeds": [], "std": None, "status": NOT_VALIDATED, "passed": None},
        "bootstrap_confidence_interval": {
            "level": 0.95,
            "lower": None,
            "upper": None,
            "status": NOT_VALIDATED,
            "passed": None,
        },
        "perturbation_stability": {"ranking_changed": None, "status": NOT_VALIDATED, "passed": None},
    }
    (RESULTS_DIR / "validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    ensure_results_dir()
    # 1. 参数设置
    # 2. 数据输入
    # 3. 模型构建
    # 4. 求解计算
    # 5. 结果输出
    result = pd.DataFrame([{"item": "objective", "value": 0.0}])
    result.to_csv(RESULTS_DIR / "output.csv", index=False, encoding="utf-8-sig")
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps({"status": "ok"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_validation_summary()

    # 6. 可视化
    plt.figure(figsize=(6, 4), dpi=300)
    plt.plot([0, 1], [0, 1])
    plt.xlabel("x")
    plt.ylabel("value")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "result_main.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
```

## MATLAB solution.m

```matlab
%% 数学建模 MATLAB 实现
clear; clc; close all;

resultsDir = "results";
if ~exist(resultsDir, "dir")
    mkdir(resultsDir);
end

% 1. 参数设置
item = ["objective"]';
value = [0]';

% 2. 结果输出
T = table(item, value);
writetable(T, fullfile(resultsDir, "output.csv"));

% 3. 摘要输出
summaryFile = fullfile(resultsDir, "summary.json");
fid = fopen(summaryFile, "w");
fprintf(fid, '{"status":"ok"}');
fclose(fid);

% 4. 可信度证据
% TODO(必填): 下列每一项都必须由真实计算产生；status 仍为 NOT_VALIDATED 时 checker 会判失败。
% 不适用的随机性条目请写成 struct("status","not_applicable","rationale",...,"alternative_validation",...)
NOT_VALIDATED = "NOT_VALIDATED";
validation = struct();
validation.baseline_comparison = run_baseline();
validation.oracle_tests = run_known_case_tests();
validation.solver_cross_checks = struct("name", "primary_vs_enumeration", "primary", [], "secondary", [], "status", NOT_VALIDATED);
validation.sensitivity_analysis = run_sensitivity_analysis();
validation.invariants = struct("name", "constraints_satisfied", "status", NOT_VALIDATED);
validation.failure_modes = struct("name", "missing_or_invalid_input", "mitigation", "stop with explicit error");
validation.constraint_residuals = struct("max_abs", [], "tolerance", 1e-6, "status", NOT_VALIDATED);
validation.optimality_gap = struct("value", [], "tolerance", 1e-4, "status", NOT_VALIDATED);
validation.multi_start = struct("runs", 0, "best_values", [], "status", NOT_VALIDATED);
validation.random_seed_stability = struct("seeds", [], "std", [], "status", NOT_VALIDATED);
validation.bootstrap_confidence_interval = struct("level", 0.95, "lower", [], "upper", [], "status", NOT_VALIDATED);
validation.perturbation_stability = struct("ranking_changed", [], "status", NOT_VALIDATED);
fid = fopen(fullfile(resultsDir, "validation_summary.json"), "w");
fprintf(fid, "%s", jsonencode(validation));
fclose(fid);

% 5. 可视化
fig = figure("Visible", "off");
plot([0 1], [0 1], "LineWidth", 2);
xlabel("x");
ylabel("value");
grid on;
exportgraphics(fig, fullfile(resultsDir, "result_main.png"), "Resolution", 300);
close(fig);

function baseline = run_baseline()
% TODO(必填): 实际运行 baseline 与最终模型，填入真实数值，并把 status 改为 passed/failed
baseline = struct("baseline_name", "naive_feasible_solution", "metric", "objective", ...
    "baseline_value", [], "model_value", [], "status", "NOT_VALIDATED");
end

function tests = run_known_case_tests()
% TODO(必填): 用可手算的小规模已知解替换 expected/actual
tests = struct("name", "small_known_case", "expected", [], "actual", [], "status", "NOT_VALIDATED");
end

function sensitivity = run_sensitivity_analysis()
% TODO(必填): 实际扰动关键参数并记录最大相对变化
sensitivity = struct("method", "one_at_a_time", "max_relative_change", [], "status", "NOT_VALIDATED");
end
```

## modeling_memory.md

```markdown
# 数学建模过程记忆文档

## 基本信息
- 当前阶段：
- 编程语言：

## Phase 0: 题目与数据提取

### 题意审计
- ambiguity_register.json：
- unresolved high severity：

## Phase 1: 并行建模共识
- problem_taxonomy：
- baseline_solution.json：
- 动态专家 Agent：

## Phase 2/3: 写作交接文档与代码并行

## Phase 4: 并行审查、独立复现与验证
- validation_summary.json：
- 独立复现 Agent：
- judge_panel_review.json：

## Phase 5: 归档
- writer_prompt.md：
- compliance_record.json：

## 更新日志
```
