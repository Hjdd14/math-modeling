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

## modeling_report.md

```markdown
# [问题标题] 数学建模报告

## 1. 问题描述

## 2. 题意审计与假设

## 3. 符号说明

## 4. 模型建立

## 5. 模型求解

## 6. baseline 与结果验证

## 7. 敏感性分析

## 8. 模型评价
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
  ]
}
```

## Python solution.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模 Python 实现"""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd


RESULTS_DIR = Path("results")


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def run_baseline():
    return {
        "baseline_name": "naive_feasible_solution",
        "metric": "objective",
        "baseline_value": 0.0,
        "model_value": 0.0,
        "passed": True,
    }


def run_known_case_tests():
    return [
        {
            "name": "small_known_case",
            "expected": 0.0,
            "actual": 0.0,
            "passed": True,
        }
    ]


def run_solver_cross_checks():
    return [
        {
            "name": "primary_vs_enumeration",
            "primary": 0.0,
            "secondary": 0.0,
            "passed": True,
        }
    ]


def run_sensitivity_analysis():
    return {
        "method": "one_at_a_time",
        "max_relative_change": 0.0,
        "passed": True,
    }


def write_validation_summary():
    summary = {
        "baseline_comparison": run_baseline(),
        "oracle_tests": run_known_case_tests(),
        "solver_cross_checks": run_solver_cross_checks(),
        "sensitivity_analysis": run_sensitivity_analysis(),
        "invariants": [{"name": "constraints_satisfied", "passed": True}],
        "failure_modes": [
            {"name": "missing_or_invalid_input", "mitigation": "stop with explicit error"}
        ],
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
validation = struct();
validation.baseline_comparison = run_baseline();
validation.oracle_tests = run_known_case_tests();
validation.solver_cross_checks = struct("name", "primary_vs_enumeration", "primary", 0, "secondary", 0, "passed", true);
validation.sensitivity_analysis = run_sensitivity_analysis();
validation.invariants = struct("name", "constraints_satisfied", "passed", true);
validation.failure_modes = struct("name", "missing_or_invalid_input", "mitigation", "stop with explicit error");
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
baseline = struct("baseline_name", "naive_feasible_solution", "metric", "objective", ...
    "baseline_value", 0, "model_value", 0, "passed", true);
end

function tests = run_known_case_tests()
tests = struct("name", "small_known_case", "expected", 0, "actual", 0, "passed", true);
end

function sensitivity = run_sensitivity_analysis()
sensitivity = struct("method", "one_at_a_time", "max_relative_change", 0, "passed", true);
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

## Phase 2/3: 并行文档与代码

## Phase 4: 并行审查、独立复现与验证
- validation_summary.json：
- 独立复现 Agent：

## Phase 5: 归档

## 更新日志
```
