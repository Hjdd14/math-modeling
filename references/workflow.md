# 数学建模并行 Agent 工作流

本文件保存完整 Phase 0-5 流程。短主 `SKILL.md` 只是入口，并不削减这里的并行子 Agent 要求。所有 Python CLI 只做确定性解析、状态管理和验证，不能替代建模方案生成、批评、修正、代码实现、图表设计或审查推理。

本轮边界：本 skill 负责建模、代码、图表、结果、验证证据、合规复现和写作交接提示词；不生成正式写作正文。新流程的硬产物是 `writer_prompt.md`。

## Phase 0: 题目与数据提取、题意审计和评分策略

1. 使用 `tools/input_parser.py extract --file <题目文件>` 提取 PDF/DOCX/MD/TXT 题目文本。
2. 使用 `tools/input_parser.py brief --problem <题目文件> --data <附件...> --out problem_brief.md` 生成初版 brief。
3. 使用 `tools/state_manager.py init --workspace . --language python|matlab` 初始化状态。
4. 启动题意审计 Agent，输出 `ambiguity_register.json` 与 `assumption_ledger.md`。
5. 启动问题拆解与评分策略 Agent，输出 `scoring_strategy.md`。
6. 读取 `references/competition_sources.json`，做竞赛来源匹配：电力、电路、电磁场优先电工杯；统计调查和社会经济数据优先统计建模大赛；行业数据和大数据题优先 MathorCup；工程真实问题优先深圳杯；国际开放式表达参考 COMAP。
7. 建立 `data_schema.json` 初稿，记录附件列名、类型、单位、缺失率、异常值、主键和范围；建立 `symbol_table.json` 初稿，记录符号、单位和代码变量映射。
8. 向用户确认 `problem_brief.md` 中的题目目标、约束、附件摘要、关键歧义、评分重点、假设和编程语言。

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

### 0.2 问题拆解与评分策略 Agent

该 Agent 专门判断“真正拿分的点”，不能跳过。它读取 `problem_brief.md`、题意审计结果和附件摘要，输出 `scoring_strategy.md`：

- 题目有哪些小问，每问必须回应什么。
- 哪些地方必须给出具体数值、排名、路径、预测区间或方案。
- 哪些图表最能支撑结论。
- 哪些地方适合突出模型创新。
- 哪些要求属于格式、精度、匿名性、AI 使用披露或解释性扣分点。

## Phase 1: 并行建模共识

Phase 1 必须使用五视角建模 Agent。必须先生成 `problem_taxonomy`，再由资料库检索 Agent 读取 `references/competition_sources.json` 和 `references/award_playbook.md`，输出 `case_retrieval.json`，列出相似题型、可借鉴模型、推荐验证和不能照搬的风险。五个 Agent 并行生成方案时必须参考 `case_retrieval.json`，但不得直接套用不匹配模型。按题型最多追加 3 个动态专家 Agent，随后并行批评、并行修正，再由创新筛选 Agent 和最终裁决 Agent 选定方案。本阶段输出 `baseline_solution.json`、`case_retrieval.json`、`model_selection_audit.json`、`model_spec.json`、`solver_strategy.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`ablation_study.json`、`innovation_register.json`、`final_solution.json` 与 `model_decision.md`，不生成正式写作正文。

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

可选题型包括：优化调度、预测统计、图网络路径、随机仿真、物理机理、政策决策、多目标鲁棒、机器学习混合模型、非线性约束、网络流、博弈和聚类分类。

### 1.0b 资料库检索 Agent

该 Agent 在五视角建模 Agent 之前执行。它读取 `problem_brief.md`、`problem_taxonomy`、`competition_sources.json` 和 `award_playbook.md`，输出 `case_retrieval.json`：

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
      "validation_needed": ["物理约束检查", "小例 oracle", "敏感性分析"]
    }
  ],
  "candidate_methods": ["robust_dispatch", "scenario_analysis"],
  "cannot_copy_risks": ["公开案例只提供题型和验证启发，不复制原作品正文"]
}
```

防乱套规则：电力、电路、电磁场题的首个匹配应优先电工杯或电力相关案例；统计调查和社会经济数据题的首个匹配应优先统计建模大赛或数据洞察类案例；行业大数据题的首个匹配应优先 MathorCup 大数据或可核验行业数据案例。`tools/case_retrieval_checker.py` 会检查这些匹配关系。

### 1.1 五视角建模 Agent 并行生成方案

在同一轮中并行启动以下 Agent，并要求每个 Agent 输出 JSON。动态专家是追加，必须保留原五视角，最多追加 3 个动态专家 Agent，不能替换任何一个五视角 Agent。

- `initial_optimizer`：优化视角 Agent。关注线性规划、非线性规划、整数规划、动态规划、全局最优性和计算效率。
- `initial_statistician`：统计视角 Agent。关注回归、时间序列、贝叶斯、蒙特卡洛、不确定性和置信区间。
- `initial_physicist`：物理机理 Agent。关注微分方程、动力系统、守恒定律、量纲一致性和可解释性。
- `initial_engineer`：工程实践 Agent。关注实现难度、鲁棒性、仿真、排队论和可部署性。
- `initial_innovator`：创新方法 Agent。关注混合模型、启发式算法、可验证创新和表达亮点。

动态专家示例：

- `graph_path_expert`：图路径、网络流、最短路、连通性。
- `forecasting_expert`：缺失数据、时间序列、holdout 验证、naive baseline。
- `stochastic_simulation_expert`：随机仿真、方差控制、置信区间。
- `multi_objective_expert`：Pareto、加权和、约束法和鲁棒权衡。
- `nonlinear_solver_expert`：非凸性、局部最优、初值敏感性。

统一 prompt：

```text
你是[角色]。请基于 problem_brief.md、ambiguity_register.json、assumption_ledger.md、problem_taxonomy、case_retrieval.json 和 award_playbook.md 提出一个完整数学建模方案。
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
  "candidate_innovations": ["..."],
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
  "inputs_required": ["problem_brief.md"],
  "method": "...",
  "expected_outputs": ["results/output.csv", "results/summary.json"],
  "limitations": ["不追求最优，只用于可信度对比"]
}
```

### 1.3 创新筛选 Agent

创新筛选 Agent 读取全部候选方案、baseline、`award_playbook.md` 和评分策略，输出 `innovation_register.json`。每个创新点必须说明：

- 解决的题目痛点。
- 相对 baseline 的增益，或消融/敏感性分析证据。
- 实现成本和可解释性。
- 可验证证据与失败风险。
- 进入最终方案、保留为备选或拒绝的理由。

“为了高级而高级”的方法不得进入最终模型；创新必须被 baseline、消融或敏感性分析支撑。

### 1.4 并行批评

把五视角方案、动态专家方案、`baseline_solution.json` 和 `innovation_register.json` 合并为 `all_solutions` 后，在同一轮中启动批评 Agent。每个批评 Agent 必须批评所有方案，而不只批评自己的方案。

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

### 1.5 并行修正

把批评意见返回给原 Agent，并行修正方案。每个修正方案必须包含 `responses` 字段，说明接受或拒绝每条批评的理由。修正时必须补充验证计划和创新证据，不能只美化措辞。

### 1.6 共识判断与最终裁决

记录每轮共识度：

- 五个核心 `model_name` 完全一致：100
- 两类模型：70
- 不超过半数类别：50
- 高度分散：30

达到 80 分、连续两轮变化小于 2 分，或达到 5 轮时停止。动态专家意见参与裁决，但不改变“五视角建模 Agent 是硬性 gate”的要求。

启动 `final_decision` Agent，综合全部方案、批评、修正、题意审计、baseline、创新筛选和共识历史，输出 `final_solution.json`、`model_selection_audit.json`、`model_spec.json`、`solver_strategy.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`ablation_study.json` 与 `model_decision.md`。

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

## Phase 2: 写作交接文档 Agent

文档 Agent 与代码 Agent 并行执行。文档 Agent 不写正式论文正文，只整理后续写作 skill 可直接使用的 `writer_prompt.md`。它读取 `problem_brief.md`、`scoring_strategy.md`、`ambiguity_register.json`、`assumption_ledger.md`、`case_retrieval.json`、`model_selection_audit.json`、`model_spec.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`symbol_table.json`、`baseline_solution.json`、`innovation_register.json`、`final_solution.json`，输出首轮草稿。

`figure_storyboard.md`、`results/validation_summary.json` 由并行的 Phase 3 产出，`reproducibility_manifest.json` 是 Phase 5 产物：**Phase 2 首轮允许这三项缺省**，不要为等待它们而阻塞并行；它们在 Phase 5 按本文件末尾的定稿要求补入。`writer_prompt.md` 因此是"Phase 2 草稿 + Phase 5 定稿"两段式产物。

输出内容包括：

- 模型主线和每问应答要点。
- 代码与结果文件路径。
- 图表清单、每张图支撑的结论、建议放置位置。
- baseline、oracle、solver 交叉验证、敏感性和数值鲁棒性证据摘要。
- 创新点是否进入最终模型及其证据。
- AI 使用、匿名性、外部资料引用、复现命令和 hash 提醒。
- 明确声明：本 skill 不生成正式写作正文，只生成写作交接提示词。

`writer_prompt.md` 不能包含队伍、学校、姓名等身份信息；不能复制优秀论文原文；只能抽象方法、验证方式和图表结构。

### Phase 3: 代码 Agent

代码 Agent 与文档 Agent 并行执行。代码 Agent 读取 `final_solution.json`、`baseline_solution.json`、`model_spec.json`、`solver_strategy.json` 与 `problem_brief.md`，不等待 Phase 2 创建 `writer_prompt.md` 或任何旧报告文件。代码必须根据语言选择生成 `solution.py` 或 `solution.m`，所有输出必须写入 `results/`。

代码要求：

- 先根据 `model_spec.json`、`solver_strategy.json` 和验证计划生成 `solution_tests.py` 或 `solution_tests.m`，再写正式代码。
- 契约测试必须包含输出存在、约束不变量、小规模 oracle、baseline 不劣化、随机种子复现、输出字段与单位一致。
- 生成 `results/output.csv` 或同等结构化结果。
- 生成 `results/summary.json` 或同等摘要。
- 生成 `results/validation_summary.json`，记录 baseline 对比、小规模 oracle 测试、solver 交叉验证、敏感性分析、关键不变量、失败模式、约束残差、最优性 gap、多初值不少于 3 次、随机种子不少于 3 个、bootstrap/置信区间置信水平至少 0.95 和参数扰动排名稳定性。
- 每一项证据都必须由真实计算产生。模板默认的 `status: "NOT_VALIDATED"` 与 `passed: null` 会被 `evidence_checker.py`、`robustness_checker.py` 在所有模式下判为失败，不允许照抄模板充当验证结果。
- 随机性相关要求（多初值、随机种子、bootstrap 区间、扰动排名稳定）按题型条件化：确定性精确枚举、确定性线性规划、最短路、解析解 ODE 等模型可显式声明不适用，格式为
  `{"status": "not_applicable", "rationale": "为什么不适用", "alternative_validation": "改用哪种验证替代"}`。
  两个字段缺任一即判失败；`constraint_residuals` 与 `optimality_gap` 对任何模型都可核验，不允许声明不适用。
- 生成或更新 `data_validation.json`、`statistical_validation.json`、`optimization_certificate.json` 和 `validation_profile.json`，确保预测/机器学习题无目标泄漏、时间序列不用随机切分、预处理只在训练集拟合。
- 生成 `figure_style.json` 与 `figure_storyboard.md`，再生成至少一张 `results/result_*.png` 图表。
- Python 必须包含 `def main()`、`run_baseline()`、`run_known_case_tests()`、`run_sensitivity_analysis()`、`write_validation_summary()` 和 `if __name__ == "__main__": main()`。
- MATLAB 必须创建 `results` 目录，包含 `run_baseline()`、`run_known_case_tests()`、`run_sensitivity_analysis()`，并使用 `writetable`、`writecell` 或等价函数输出结果。

### 3.1 可视化设计 Agent

可视化设计 Agent 与代码 Agent 协同，但不替代代码。它输出 `figure_storyboard.md` 与 `figure_style.json`：

- 每张图回答一个明确问题，并能在后续写作中支撑关键结论。
- `figure_storyboard.md` 中每张图必须包含 `file`、`claim`、`source_data`、`x_unit`、`y_unit` 和 `supports_question`。
- 图表标题尽量写成发现，而不是“图1”。
- 优先生成证据图组：数据质量图、模型结构图、baseline vs final 对比图、约束利用率图、敏感性图、误差/残差诊断图、不确定性区间图、Pareto 前沿图、路径规划图或仿真收敛图。
- 统一 DPI、字体、字号、线宽、色盲友好色板、黑白打印可辨性、图例位置、网格和留白。

`validation_summary.json` 最低结构：

```json
{
  "baseline_comparison": {"baseline_name": "...", "passed": true},
  "oracle_tests": [{"name": "...", "passed": true}],
  "solver_cross_checks": [{"name": "...", "passed": true}],
  "sensitivity_analysis": {"method": "...", "passed": true},
  "invariants": [{"name": "...", "passed": true}],
  "failure_modes": [{"name": "...", "mitigation": "..."}],
  "constraint_residuals": {"max_abs": 0, "tolerance": 1e-6, "passed": true},
  "optimality_gap": {"value": 0, "tolerance": 1e-4, "passed": true},
  "multi_start": {"runs": 5, "passed": true},
  "random_seed_stability": {"seeds": [1, 2, 3], "passed": true},
  "bootstrap_confidence_interval": {"level": 0.95, "lower": 0, "upper": 0, "passed": true},
  "perturbation_stability": {"ranking_changed": false, "passed": true}
}
```

### Phase 4: 多评委并行审查、独立复现与工具验证

Phase 4 必须先并行启动技术审查组：

- 语法审查 Agent：检查语法错误、缩进、变量命名、依赖导入、主入口。
- 逻辑审查 Agent：检查公式、约束、数据引用、算法逻辑是否与 `problem_brief.md` 和模型规范一致。
- 输出审查 Agent：检查输出是否覆盖所有目标、图表是否生成、结果是否合理。

同时启动独立复现 Agent：

- 只读取 `problem_brief.md`、`baseline_solution.json`、`final_solution.json` 和代码输出。
- 不读取正式写作措辞。
- 独立复算核心结论、关键约束和至少一个小规模 oracle/known case。
- 输出 `agent_outputs/phase4/independent_reproduction.json` 或写入状态中的 Agent run 摘要。

再启动多评委并行审查，至少包含：

- 国赛建模评委
- 美赛评委
- 代码复现评委
- 图表证据评委
- 行业评委或工程/业务解释评委

每个评委独立输出结构化评分、high/medium/low 问题清单和是否通过；chair judge 汇总为 `judge_panel_review.json`。任一 high severity 未解决，必须回溯修正。

再启动结果解释与决策建议 Agent，输出 `decision_insights.md`。再启动评委质询 Agent，输出 `defense_questions.md`。

汇总问题后运行：

```bash
python "tools/pipeline_check.py" --workspace "." --language python
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict --quality-mode excellence
```

普通旧工作区可先使用标准模式；难题、完整交付或竞赛正式结果必须使用 `--evidence-mode strict`；奖项级交付使用 `--quality-mode excellence`。

## Phase 4: 修正循环

1. 修正 high severity 题意歧义、模型逻辑、代码错误、创新证据和合规问题。
2. 重新运行相关工具。
3. 修正 medium severity 问题。
4. 重新运行 `pipeline_check.py`，难题使用 `--evidence-mode strict`。
5. 奖项级交付额外运行 `source_registry_checker.py`、`source_freshness_checker.py`、`case_retrieval_checker.py`、`brief_completeness_checker.py`、`model_selection_checker.py`、`optimization_certificate_checker.py`、`uncertainty_budget_checker.py`、`validation_profile_checker.py`、`data_leakage_checker.py`、`statistical_validation_checker.py`、`schema_checker.py`、`model_spec_checker.py`、`unit_checker.py`、`robustness_checker.py`、`figure_auditor.py`、`innovation_checker.py`、`judge_panel_checker.py`、`compliance_checker.py`、`writer_prompt_checker.py`、`manifest_checker.py` 或总控 `--quality-mode excellence`。
6. 直到所有关键检查通过。

## Phase 5: 归档与交付

最终交付前确认固定产物：

- `problem_brief.md`
- `ambiguity_register.json`
- `assumption_ledger.md`
- `scoring_strategy.md`
- `data_schema.json`
- `symbol_table.json`
- `modeling_state.json`
- `modeling_memory.md`
- `baseline_solution.json`
- `case_retrieval.json`
- `model_selection_audit.json`
- `model_spec.json`
- `optimization_certificate.json`
- `uncertainty_budget.json`
- `validation_profile.json`
- `data_validation.json`
- `statistical_validation.json`
- `solver_strategy.json`
- `ablation_study.json`
- `innovation_register.json`
- `final_solution.json`
- `model_decision.md`
- `writer_prompt.md`
- `solution.py` 或 `solution.m`
- `solution_tests.py` 或 `solution_tests.m`
- `figure_style.json`
- `figure_storyboard.md`
- `results/`
- `results/validation_summary.json`
- `results/figure_quality_report.json`
- `judge_panel_review.json`
- `decision_insights.md`
- `defense_questions.md`
- `compliance_record.json`
- `reproducibility_manifest.json`

运行总控验证并把结果写入 `modeling_memory.md` 和 `modeling_state.json`。最终摘要必须说明 baseline 对比、oracle 或等价小例验证、solver 交叉验证、敏感性分析、不变量、数值鲁棒性、图表审计、创新筛选、评委组审查、合规复现和独立复现是否通过。

`writer_prompt.md` 在 Phase 5 必须最终更新一次，补入 `case_retrieval.json`、`judge_panel_review.json`、`compliance_record.json` 和 `reproducibility_manifest.json` 的摘要路径，确保后续写作 skill 能看到来源匹配、评委组审查、风险提示和合规提示。
