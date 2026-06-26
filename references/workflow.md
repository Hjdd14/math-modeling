# 数学建模并行 Agent 工作流

本文件保存完整 Phase 0-5 流程。短主 `SKILL.md` 只是入口，并不削减这里的并行子 Agent 要求。所有 Python CLI 只做确定性解析、状态管理和验证，不能替代建模方案生成、批评、修正、文档撰写、代码实现或审查推理。

## Phase 0: 题目与数据提取和题意审计

1. 使用 `tools/input_parser.py extract --file <题目文件>` 提取 PDF/DOCX/MD/TXT 题目文本。
2. 使用 `tools/input_parser.py brief --problem <题目文件> --data <附件...> --out problem_brief.md` 生成初版 brief。
3. 使用 `tools/state_manager.py init --workspace . --language python|matlab` 初始化状态。
4. 启动题意审计 Agent，输出 `ambiguity_register.json` 与 `assumption_ledger.md`。
5. 向用户确认 `problem_brief.md` 中的题目目标、约束、附件摘要、关键歧义、假设和编程语言。

### 0.1 题意审计 Agent

题意审计 Agent 专门找“读错题会导致后续全错”的风险，不能提出正式模型。它读取 `problem_brief.md` 和附件摘要，检查：

- 目标函数和评分要求是否完整。
- 单位、量纲、时间尺度、坐标系、编号、字段含义是否明确。
- 是否存在隐藏约束、边界条件、缺失数据、异常值、重复字段或不可用附件。
- 输出格式、图表、精度、排名规则是否遗漏。
- 用户确认前不能擅自把 high severity 歧义当作已解决。

`ambiguity_register.json` 格式：

```json
{
  "items": [
    {
      "id": "A1",
      "severity": "high",
      "source": "problem_brief.md:约束条件",
      "issue": "产能约束单位未说明是每天还是整个周期",
      "impact": "会改变约束右端项和最优解",
      "resolution": "pending",
      "assumption_if_unresolved": "按整个周期处理"
    }
  ]
}
```

`assumption_ledger.md` 必须记录每条假设的来源、影响、验证方式和状态。未解决的 high severity 歧义必须同步写入 `modeling_memory.md`，不能静默进入 Phase 1。

## Phase 1: 并行建模共识

Phase 1 必须使用五视角建模 Agent。必须先生成 `problem_taxonomy`，再由五个 Agent 并行生成方案，按题型最多追加 3 个动态专家 Agent，随后并行批评、并行修正，再由最终裁决 Agent 选定方案。本阶段输出 `baseline_solution.json`、`final_solution.json` 与 `model_decision.md`，不得写入 `modeling_report.md`。

### 1.0 题型分类 problem_taxonomy

在五视角并行前，先由调度者基于 `problem_brief.md` 和题意审计结果写入 `problem_taxonomy`：

```json
{
  "primary_types": ["optimization", "multi_objective"],
  "secondary_types": ["simulation", "sensitivity_analysis"],
  "data_regime": "small_structured_table",
  "uncertainty_sources": ["missing_field_semantics", "parameter_variation"],
  "recommended_dynamic_experts": ["multi_objective_optimizer", "robustness_validator"]
}
```

可选题型包括：优化、预测、图论、随机仿真、微分方程、排队、多目标、非线性约束、空间路径规划、网络流、博弈、聚类分类和机理统计混合模型。

### 1.1 五视角建模 Agent 并行生成方案

在同一轮中并行启动以下 Agent，并要求每个 Agent 输出 JSON。动态专家是追加，必须保留原五视角，最多追加 3 个动态专家 Agent，不能替换任何一个五视角 Agent。

- `initial_optimizer`：优化视角 Agent。关注线性规划、非线性规划、整数规划、动态规划、全局最优性和计算效率。
- `initial_statistician`：统计视角 Agent。关注回归、时间序列、贝叶斯、蒙特卡洛、不确定性和置信区间。
- `initial_physicist`：物理机理 Agent。关注微分方程、动力系统、守恒定律、量纲一致性和可解释性。
- `initial_engineer`：工程实践 Agent。关注实现难度、鲁棒性、仿真、排队论和可部署性。
- `initial_innovator`：创新方法 Agent。关注机器学习、混合模型、启发式算法和创新性。

动态专家示例：

- `graph_path_expert`：图路径、网络流、最短路、连通性。
- `forecasting_expert`：缺失数据、时间序列、holdout 验证、naive baseline。
- `stochastic_simulation_expert`：随机仿真、方差控制、置信区间。
- `multi_objective_expert`：Pareto、加权和、层次分析、约束法。
- `nonlinear_solver_expert`：非凸性、局部最优、初值敏感性。

统一 prompt：

```text
你是[角色]。请基于 problem_brief.md、ambiguity_register.json、assumption_ledger.md 和 problem_taxonomy 提出一个完整数学建模方案。
必须输出 JSON：
{
  "agent_id": "...",
  "model_name": "...",
  "problem_fit": "...",
  "variables": [{"name": "...", "meaning": "...", "range": "..."}],
  "objective_function": "...",
  "constraints": ["..."],
  "solution_method": "...",
  "assumptions": ["..."],
  "validation_plan": {
    "baseline": "...",
    "oracle_or_known_case": "...",
    "solver_cross_check": "...",
    "sensitivity_analysis": "..."
  },
  "pros": ["..."],
  "cons": ["..."],
  "complexity": "..."
}
```

### 1.2 baseline_solution.json

并行方案产生后，必须生成 `baseline_solution.json`。baseline 应简单、可运行、可解释，不追求最好，但要能作为结果可信度下限。

```json
{
  "baseline_name": "naive_feasible_solution",
  "rationale": "用贪心/均值/最短路/上一期值等简单规则构造可解释基线",
  "inputs_required": ["..."],
  "method": "...",
  "expected_outputs": ["..."],
  "limitations": ["..."]
}
```

### 1.3 并行批评

把五视角方案、动态专家方案和 `baseline_solution.json` 合并为 `all_solutions` 后，在同一轮中启动批评 Agent。每个批评 Agent 必须批评所有方案，而不只批评自己的方案。

输出 JSON：

```json
{
  "target_agent_id": {
    "criticisms": ["问题"],
    "suggestions": ["建议"],
    "score": 75,
    "severity": "medium"
  }
}
```

### 1.4 并行修正

把批评意见返回给原 Agent，并行修正方案。每个修正方案必须包含 `responses` 字段，说明接受或拒绝每条批评的理由。修正时必须补充验证计划，不能只美化措辞。

### 1.5 共识判断

记录每轮共识度：

- 五个核心 `model_name` 完全一致：100
- 两类模型：70
- 不超过半数类别：50
- 高度分散：30

达到 80 分、连续两轮变化小于 2 分，或达到 5 轮时停止。动态专家意见参与裁决，但不改变“五视角建模 Agent 是硬性 gate”的要求。

### 1.6 最终裁决

启动 `final_decision` Agent，综合全部方案、批评、修正、题意审计、baseline 和共识历史，输出：

- `final_solution.json`
- `model_decision.md`

`final_solution.json` 必须包含模型评分矩阵：

```json
{
  "selected_model": "...",
  "problem_taxonomy": {},
  "score_matrix": [
    {
      "model_name": "...",
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
    "baseline_comparison": "...",
    "oracle_tests": "...",
    "solver_cross_checks": "...",
    "sensitivity_analysis": "...",
    "invariants": ["..."]
  }
}
```

`model_decision.md` 必须包含方案对比表、模型评分矩阵、选择理由、被拒方案的不足、关键洞察和验证要点。

## Phase 2: 文档 Agent

文档 Agent 与代码 Agent 并行执行。文档 Agent 读取 `problem_brief.md`、`ambiguity_register.json`、`assumption_ledger.md`、`baseline_solution.json` 与 `final_solution.json`，生成 `modeling_report.md`。报告必须包含问题描述、模型假设、符号说明、模型建立、求解方法、baseline 对比、代入验证、敏感性分析、模型评价和改进方向。

文档生成后运行：

```bash
python "tools/latex_validator.py" validate --file "modeling_report.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage document --target "modeling_report.md"
```

### Phase 3: 代码 Agent

代码 Agent 与文档 Agent 并行执行。代码 Agent 读取 `final_solution.json`、`baseline_solution.json` 与 `problem_brief.md`，不等待 Phase 2 创建 `modeling_report.md`。代码必须根据语言选择生成 `solution.py` 或 `solution.m`，所有输出必须写入 `results/`。

代码要求：

- 包含参数设置、数据输入、模型构建、求解计算、结果输出和可视化。
- 生成 `results/output.csv` 或同等结构化结果。
- 生成 `results/summary.json` 或同等摘要。
- 生成 `results/validation_summary.json`，记录 baseline 对比、小规模 oracle 测试、solver 交叉验证、敏感性分析、关键不变量和失败模式。
- 生成至少一张 `results/result_*.png` 图表。
- Python 必须包含 `def main()`、`run_baseline()`、`run_known_case_tests()`、`run_sensitivity_analysis()`、`write_validation_summary()` 和 `if __name__ == "__main__": main()`。
- MATLAB 必须创建 `results` 目录，包含 `run_baseline()`、`run_known_case_tests()`、`run_sensitivity_analysis()`，并使用 `writetable`、`writecell` 或等价函数输出结果。

`validation_summary.json` 最低结构：

```json
{
  "baseline_comparison": {"baseline_name": "...", "passed": true},
  "oracle_tests": [{"name": "...", "passed": true}],
  "solver_cross_checks": [{"name": "...", "passed": true}],
  "sensitivity_analysis": {"method": "...", "passed": true},
  "invariants": [{"name": "...", "passed": true}],
  "failure_modes": [{"name": "...", "mitigation": "..."}]
}
```

文档与代码都落盘后运行：

```bash
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage code --target "solution.py"
python "tools/consistency_checker.py" formula --doc "modeling_report.md" --code "solution.py" --lang python
```

### Phase 4: 并行审查、独立复现与工具验证

Phase 4 必须先并行启动三个审查 Agent：

- 语法审查 Agent：检查语法错误、缩进、变量命名、依赖导入、主入口。
- 逻辑审查 Agent：检查公式、约束、数据引用、算法逻辑是否与 `problem_brief.md` 和 `modeling_report.md` 一致。
- 输出审查 Agent：检查输出是否覆盖所有目标、图表是否生成、结果是否合理。

同时启动独立复现 Agent：

- 只读取 `problem_brief.md`、`baseline_solution.json`、`final_solution.json` 和代码输出。
- 不读取 `modeling_report.md` 的解释性措辞。
- 独立复算核心结论、关键约束和至少一个小规模 oracle/known case。
- 输出 `agent_outputs/phase4/independent_reproduction.json` 或写入状态中的 Agent run 摘要。

每个审查 Agent 输出：

```json
{
  "issues": [{"severity": "high", "location": "...", "description": "...", "fix": "..."}],
  "passed": false,
  "summary": "..."
}
```

独立复现 Agent 输出：

```json
{
  "recomputed_claims": [{"claim": "...", "method": "...", "matches": true}],
  "oracle_check": {"name": "...", "passed": true},
  "issues": [],
  "passed": true
}
```

汇总问题后运行：

```bash
python "tools/pipeline_check.py" --workspace "." --language python
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict
```

普通旧工作区可先使用标准模式；难题、完整交付或竞赛正式结果必须使用 `--evidence-mode strict`。如果失败，按问题类型回溯到 Phase 0、1、2 或 3 修正，重新执行 Phase 4。

## Phase 4: 修正循环

1. 修正 high severity 题意歧义、模型逻辑、代码错误和证据失败。
2. 重新运行相关工具。
3. 修正 medium severity 问题。
4. 重新运行 `pipeline_check.py`，难题使用 `--evidence-mode strict`。
5. 直到所有关键检查通过。

## Phase 5: 归档与交付

最终交付前确认固定产物：

- `problem_brief.md`
- `ambiguity_register.json`
- `assumption_ledger.md`
- `modeling_state.json`
- `modeling_memory.md`
- `baseline_solution.json`
- `final_solution.json`
- `model_decision.md`
- `modeling_report.md`
- `solution.py` 或 `solution.m`
- `results/`
- `results/validation_summary.json`

运行总控验证并把结果写入 `modeling_memory.md` 和 `modeling_state.json`。最终摘要必须说明 baseline 对比、oracle 或等价小例验证、solver 交叉验证、敏感性分析、不变量和独立复现是否通过。
