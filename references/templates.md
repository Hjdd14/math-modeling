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

## 8. 待探索范式集合（引用 A 板）

| paradigm_id | 范式 | 方法族 | 探索成本 | 来源 |
|---|---|---|---|---|
| P1 |  | statistical_inference | medium |  |
| P3 |  | mechanistic | high |  |

> 本小节的唯一来源是 `design_board.json`（A 板）的 `paradigm_selection`；改这里等于改板，必须重新 render → 重新确认。

## 9. 硬约束（不可违背）

## 10. 参考对账值

## 11. 陷阱清单
```

> **禁止**在 `problem_brief.md`（根与每问）写"锁定选型 / 已锁定 / 不得更换 / user_locked=true / 主模型已由…闸门"这类措辞。模型选择只能由 B 板的 `user_choice` 决定；`brief_completeness_checker.py` 会扫这几类字样并判 `brief_contains_locked_selection`。

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

## design_board.json

A 板的唯一真实来源：用户确认过哪些**待探索范式**、题目框架与高危假设是否接受。`design_board.md` / `.html` / `design_choices.xlsx` 只是视图。

> A 板**不承载模型候选**：`options` 允许为空，`user_choice` 允许 null，`user_locked` 必须 false。模型选择在 B 板（见下）。

```json
{
  "schema_version": 2,
  "gate": "a",
  "board_id": "b-YYYY-MM-DD-xxxx",
  "board_sha256": "<由 design_board.py render 计算写入，不要手写>",
  "language": "python",
  "created_at": "ISO8601",
  "revision": 1,
  "problem_summary": {
    "title": "...",
    "questions": ["问题一", "问题二"],
    "key_ambiguities": [{"id": "A1", "severity": "medium", "issue": "...", "resolution": "pending"}]
  },
  "mindmap": {"format": "mermaid", "source": "graph LR\n  P[题目] --> Q1[问题一]"},
  "questions": [
    {
      "id": "Q1",
      "goal": "...",
      "paradigm_set": [
        {
          "paradigm_id": "P1",
          "name": "配对差单样本 t 检验族",
          "family": "statistical_inference",
          "source_ref": {"type": "method_card", "ref": "STA-03", "tier": "tier_a", "verified": true},
          "why_explore": "题目给的是逐日配对观测，差值检验与题意最贴",
          "explore_cost": {"level": "medium", "note": "一天可完成前提检验与多重校正"}
        },
        {
          "paradigm_id": "P2",
          "name": "非参数秩检验族",
          "family": "statistical_inference",
          "source_ref": {"type": "method_card", "ref": "STA-07", "tier": "tier_b", "verified": true},
          "why_explore": "作为正态性不成立时的稳健对照",
          "explore_cost": {"level": "low", "note": "半天"}
        },
        {
          "paradigm_id": "P3",
          "name": "守恒/流入流出机理模型",
          "family": "mechanistic",
          "source_ref": {"type": "paper", "ref": "DOI:...", "tier": "tier_b", "verified": false,
                         "unverified_reason": "尚未核对原文参数适用范围"},
          "why_explore": "与统计族异质，可解释园区总量守恒约束",
          "explore_cost": {"level": "high", "note": "要建质量平衡方程"}
        }
      ],
      "paradigm_selection": ["P1", "P3"],
      "options": [],
      "user_choice": null,
      "user_locked": false,
      "user_comment": "",
      "confirmed": false
    }
  ],
  "pending_decisions": [],
  "no_change_rounds": 0,
  "confirmed_at": null,
  "confirmed_by": null,
  "receipt_origin": null,
  "confirm_code": null,
  "confirm_attested": false
}
```

硬规则（`design_board_checker.py --gate a` 逐条校验）：

- 每题 `paradigm_set` **3–5 项**；每项必须有 `paradigm_id` / `name` / `family` / `source_ref` / `why_explore` / `explore_cost`。
- 同题内至少 1 个 `family` 与其他不同（异质），否则 `paradigm_no_heterogeneous`。
- `paradigm_selection` 是 `paradigm_set` 的子集、≥2 项、且覆盖 ≥2 个方法族。
- `user_locked` 必须为 `false`；`user_choice` 必须为 `null`；`options` 允许 `[]`。
- `source_ref.verified == false` 必须同时给 `unverified_reason`。
- `confirmed: true` 时必须有 `confirmed_at` / `confirmed_by` / `receipt_origin` / `confirm_code`（4 位）/ `confirm_attested`。
- `no_change_rounds >= 2` 才允许确认。
- `board_sha256` 由 `render` 回写；手写等于自证。

## design_board_gate_b.json

B 板：用户在哪几个模型里选了哪个。与 A 板同构（`questions[] / options[]`），额外嵌入 `advice` 与 `advice_sha256`；主仓库是整题一块板，分支是每问一块板。

```json
{
  "schema_version": 2,
  "gate": "b",
  "question_scope": "problem",
  "board_id": "gb-YYYY-MM-DD-xxxx",
  "board_sha256": "<render 写入>",
  "advice_ref": "model_advice.json",
  "advice_sha256": "<model_advice.json 的字节哈希>",
  "language": "python",
  "revision": 1,
  "problem_summary": {"title": "...", "questions": ["问题一", "问题二"]},
  "questions": [
    {
      "id": "Q1",
      "goal": "...",
      "options": [
        {"id": "O1", "name": "配对差 t 检验族", "verdict": "recommended", "score": 86.5,
         "origin": "perspective:statistician", "paradigm_id": "P1"},
        {"id": "O2", "name": "Wilcoxon + Hodges-Lehmann", "verdict": "not_recommended", "score": 78.0,
         "origin": "perspective:optimizer", "paradigm_id": "P1"}
      ],
      "advice": {"is_judge_panel": false, "candidates": [], "data_comparison": {}, "scoring_rubric": {}},
      "user_choice": "O1",
      "user_locked": true,
      "user_comment": "",
      "confirmed": false
    }
  ],
  "pending_decisions": [],
  "no_change_rounds": 0,
  "confirmed_at": null,
  "confirmed_by": null,
  "receipt_origin": null,
  "confirm_code": null,
  "confirm_attested": false
}
```

硬规则（`--gate b`）：候选 5–8 个且与 `advice.candidates[].option_id` 一一对应；`advice_sha256` 必须等于建议文件字节哈希；`user_choice` 必须是某个 option 的 id；`preauthorized: true` 在 excellence 下判 error。

## model_advice.json

建议 Agent 的产物：**1 个建议 + 其余不建议 + 打分 + 多组真实数据对比**。不是评委结论（`is_judge_panel: false`）。

```json
{
  "schema_version": 2,
  "question_id": "Q1",
  "generated_at": "ISO8601",
  "is_judge_panel": false,
  "disclaimer": "本文件是选型建议，不是评委审查。评委审查在 Phase 4。",
  "scoring_rubric": {
    "dimensions": [
      {"id": "fit", "name": "题意契合度", "weight": 0.3},
      {"id": "rigor", "name": "方法严谨性", "weight": 0.25},
      {"id": "evidence", "name": "数据支持度", "weight": 0.25},
      {"id": "risk", "name": "实施与解释风险(反向)", "weight": 0.2}
    ],
    "scale": "0-100"
  },
  "candidates": [
    {
      "option_id": "O1", "origin": "perspective:statistician", "name": "...", "paradigm_id": "P1",
      "verdict": "recommended", "score": 86.5,
      "dimension_scores": {"fit": 90, "rigor": 88, "evidence": 85, "risk": 80},
      "pros": ["三口径结论一致", "可手算复核"],
      "cons": ["多重校正后偏保守"],
      "evidence_refs": ["perspective_trials.json#O1/full"]
    },
    {
      "option_id": "O2", "origin": "perspective:optimizer", "name": "...", "paradigm_id": "P1",
      "verdict": "not_recommended", "score": 78.0,
      "dimension_scores": {"fit": 70, "rigor": 85, "evidence": 82, "risk": 75},
      "pros": ["非参数，不依赖正态", "抗离群"],
      "cons": ["正态成立时过度保守", "功效略低"],
      "why_not": ["与 O1 结论相同，无增量信息", "在正态性成立时属过度保守"],
      "when_better": "若 Shapiro 拒绝正态且样本量小，O2 应升为主模型",
      "evidence_refs": ["perspective_trials.json#O2/full"]
    }
  ],
  "data_comparison": {
    "comparable_columns": ["runtime_s", "finished"],
    "rows": [
      {"slice_id": "full", "option_id": "O1", "trials_ref": "O1/full",
       "comparable": {"runtime_s": 0.91, "finished": true},
       "own": {"p_value": 0.0258}}
    ],
    "baseline_row": {"slice_id": "full", "option_id": "baseline",
                     "comparable": {"runtime_s": 0.004, "finished": true}}
  },
  "recommended_option_id": "O1",
  "aggregate_note": "为什么推荐它，剩余风险交给 Phase 4"
}
```

硬规则：候选 5–8；恰好 1 个 recommended；全部有分且维度分键齐全；pros/cons 各 ≥2；不推荐项 `why_not` ≥2 + `when_better`；`data_comparison` ≥2 slice × 全候选且每格可回溯到 `perspective_trials.json`（数值一致，不得手改）；`comparable` 跨候选同键；不得出现评委结论措辞。

## perspective_trials.json

每视角真实试算。**唯一写入口是 `tools/perspective_trial_runner.py`**，手填记录会被 checker 判 `trials_not_tool_executed`。

```json
{
  "schema_version": 2,
  "question_id": "Q1",
  "generated_by": "tools/perspective_trial_runner.py",
  "run_id": "2026-11-01T10:00:00+08:00-3f9a1c",
  "slice_axis": "data_rows",
  "slice_axis_note": "",
  "slices": [
    {"slice_id": "full", "description": "全部数据", "data_ref": "data.csv", "selector": {"rows": "all"}},
    {"slice_id": "holdout", "description": "留出 20%", "data_ref": "data.csv", "selector": {"rows": "56..70"}}
  ],
  "metric_definitions": {
    "comparable": [{"key": "runtime_s", "unit": "s"}, {"key": "finished", "unit": "bool"}],
    "own": {"O1": [{"key": "p_value", "unit": "1"}]}
  },
  "perspectives": [
    {
      "perspective": "statistician", "option_id": "O1",
      "script": "perspective_trials/statistician.py", "script_sha256": "...",
      "runs": [
        {"slice_id": "full", "executed_by": "tool", "runner_version": "1.0", "run_seq": 1,
         "exit_code": 0, "runtime_s": 0.9123, "stdout_sha256": "...", "captured_at": "ISO8601",
         "metrics": {"comparable": {"runtime_s": 0.9123, "finished": true},
                     "own": {"p_value": 0.0258}},
         "reproduce_cmd": "python tools/perspective_trial_runner.py run --perspective statistician --option-id O1 --slice full"}
      ]
    }
  ]
}
```

硬规则：slices ≥2（无数据集用 `parameter`/`scenario` 轴并写 `slice_axis_note`）；perspectives ≥5 且每个都有 `option_id`；每个 run 必须 `executed_by: "tool"` + `exit_code` + `stdout_sha256` + `captured_at`；同一 slice 下各视角 `comparable` 键集合一致。

## reopen_gate_request.json

```json
{
  "schema_version": 1,
  "question_id": "Q1",
  "raised_by": "arbitrator",
  "raised_at": "ISO8601",
  "gate": "b",
  "user_choice_id": "O1",
  "blocking_reason": "solver_infeasible",
  "evidence": ["optimization_certificate.json#status=infeasible"],
  "proposed_alternatives": ["O3"],
  "requires_user_reconfirm": true
}
```

`gate` 取 `a`（范式不成立）或 `b`（所选方案不可行）。产出后必须停下等用户重新确认，不得自行换方案。

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

> ⚠️ 本示例是**结构参考**，不是可用证据。照抄后必须把每一项换成真实计算值，并把 `status` 改为 `passed`/`failed`。
> `evidence_checker.py` 与 `robustness_checker.py` 会把仍含 `NOT_VALIDATED` 的 payload 判为失败。

```json
{
  "baseline_comparison": {
    "baseline_name": "naive_feasible_solution",
    "metric": "objective_or_error",
    "baseline_value": 0,
    "model_value": 0,
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "oracle_tests": [
    {
      "name": "small_known_case",
      "expected": 0,
      "actual": 0,
      "status": "NOT_VALIDATED",
      "passed": null
    }
  ],
  "solver_cross_checks": [
    {
      "name": "alternate_solver_or_enumeration",
      "primary": 0,
      "secondary": 0,
      "status": "NOT_VALIDATED",
      "passed": null
    }
  ],
  "sensitivity_analysis": {
    "method": "one_at_a_time",
    "max_relative_change": 0,
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "invariants": [
    {
      "name": "constraints_satisfied",
      "status": "NOT_VALIDATED",
      "passed": null
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
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "optimality_gap": {
    "value": 0,
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "multi_start": {
    "runs": 5,
    "best_values": [0, 0, 0],
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "random_seed_stability": {
    "seeds": [1, 2, 3],
    "std": 0,
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "bootstrap_confidence_interval": {
    "level": 0.95,
    "lower": 0,
    "upper": 0,
    "status": "NOT_VALIDATED",
    "passed": null
  },
  "perturbation_stability": {
    "ranking_changed": false,
    "status": "NOT_VALIDATED",
    "passed": null
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
