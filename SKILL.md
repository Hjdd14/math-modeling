---
name: math-modeling
description: 用于数学建模竞赛或类似多阶段建模任务。触发条件：用户提供题目 PDF/DOCX/Markdown/TXT 与 Excel/CSV 附件，并要求完成题意审计、建模方案、Python 或 MATLAB 代码、图表、结果验证、数据契约、模型规范、写作交接提示词或奖项级可信度审查。不要用于普通单题解答、PDF 翻译、只写正式论文正文或只写一段代码的任务。
---

# 数学建模竞赛建模与代码交付 Skill

本 skill 执行数学建模竞赛中的建模与代码交付流程：题目理解、并行建模共识、创新筛选、可运行代码、结果与图表、证据验证、合规复现和写作交接提示词。它不生成正式写作正文；正式论文正文应交给后续独立写作 skill。

## 必读引用

执行前先读取这些文件：

1. `references/workflow.md`：完整 Phase 0-5 流程，包含并行 Agent prompt、输入、输出和汇总规则。
2. `references/templates.md`：固定产物模板，包括 `writer_prompt.md`、`innovation_register.json`、`judge_panel_review.json` 和 `compliance_record.json`。
3. `references/tools.md`：所有 CLI 工具命令、JSON 字段和失败判定。
4. `references/competition_sources.json`：权威竞赛来源分层、官方入口和可信度规则。
5. `references/award_playbook.md`：权威竞赛案例方法谱系和题型方法卡片。
6. `references/evaluator_panel.md`：多评委并行审查角色、评分字段和 chair judge 汇总规则。
7. `references/evals.md`：本地 eval、Claude 实跑 eval、触发描述优化流程。
8. `docs/DESIGN_GATE_PLAN.md`：**双闸门**（A 框架闸门 / B 方案择定闸门）的完整规格、确认码机制、交叉校验、双时间线与 hook 守卫分工。

如果引用文档与本主文件冲突，以本主文件的核心约束为准；如果用户的显式要求更具体，以用户要求为准。

## 核心约束

1. `problem_brief.md` 是唯一真实来源；模型、代码、结果、图表和写作交接提示词都必须对照它核查。
2. 并行子 Agent 是核心能力，不能被 Python CLI、workflow runner 或引用文档替代。
3. Python CLI 只做确定性编排、状态管理和验证；不得把多 Agent 建模降级为单脚本假推理。
4. Phase 1 不生成正式写作正文；只输出建模决策、模型规范、创新登记和验证计划。
5. Phase 2 只生成 `writer_prompt.md` 等写作交接材料，不生成正式写作正文。
6. Phase 3 代码只依赖 `final_solution.json` 与 `problem_brief.md`，不等待 Phase 2 先落盘。
7. 所有运行结果统一写入 `results/`。
8. 每个阶段都更新 `modeling_state.json` 和 `modeling_memory.md`。
9. 工具调用必须在对应 step 直接执行，不得跳过。
10. 验证失败时回溯到对应阶段修正，而不是在后续阶段打补丁。
11. 难题必须保留可证伪证据链：题意审计、baseline、oracle 或等价小例验证、solver 交叉验证、敏感性分析和独立复现记录。
12. 未解决的 high severity 歧义必须写入 `modeling_memory.md`，不能静默进入 Phase 1。
13. 难题或完整验证必须使用 `pipeline_check.py --evidence-mode strict`。
14. 奖项级交付必须使用题意完成度、模型选择审计、优化证书、不确定性预算、题型 profile、数据泄漏、统计验证、模型规范、数据契约、自动测试、数值鲁棒性、图表语义证据、多评委并行审查、创新筛选、合规复现和写作交接闭环，并运行 `pipeline_check.py --quality-mode excellence`。
15. `model_spec.json`、`model_selection_audit.json`、`validation_profile.json`、`data_schema.json`、`symbol_table.json`、`solver_strategy.json`、`innovation_register.json` 和 `writer_prompt.md` 是模型、代码、验证器和后续写作之间的对齐基准。
16. **Phase 0.5 是框架闸门（A 闸门）**：必须先生成 `design_board.json`（schema v2，每问 3-5 个 `paradigm_set` + `paradigm_selection`）并渲染，用户确认后才能进入 Phase 1 和写任何代码。A 板**不锁定模型选型**。
16b. **Phase 1.5 是方案择定闸门（B 闸门，硬性）**：Phase 1 五视角与真实试算之后，必须生成 `model_advice.json`、`perspective_trials.json` 与 `design_board_gate_b.json`，由用户在 B 板上选定模型并 `confirm`。**B 板确认前不得进入 Phase 2/3，不得创建或修改 `solution.py` / `solution.m` / `solution_tests.*`**（A 板未确认同样禁止）。
17. `design_board.py confirm --apply`（A 板与 B 板各一次）必须由用户本人执行并输入该板 4 位确认码；AI 不得代跑，也不得代填确认码，也不得用 `preauthorized` 冒充人工选择（优秀模式直接判不通过）。
18. `problem_brief.md`（根与每问）**不得**出现"已锁定选型 / 不得更换 / user_locked=true / 主模型已由…闸门"这类措辞；模型选择只能由 B 板的 `user_choice` 决定。

## 固定产物

工作区内固定维护以下文件或目录：

| 产物 | 阶段 | 说明 |
|------|------|------|
| `problem_brief.md` | Phase 0 | 题目、目标、约束、附件摘要 |
| `design_board.json` | Phase 0.5 | **A 板**：题意框架 + 每问 `paradigm_set` / `paradigm_selection`（schema v2）；不锁定模型 |
| `design_rounds/round_NNN.json` | Phase 0.5 | A 板回执：用户改了什么、回传来源与 nonce |
| `design_board.md` | Phase 0.5 | A 板渲染视图（Mermaid 导图 + 范式表 + 确认码） |
| `mini_trials.json` | Phase 0.5 | 候选在小样本上的真实试算（A 板可选用；B 闸门改用 `perspective_trials.json`） |
| `design_board_gate_b.json` | Phase 1.5 | **B 板**：每问候选分数/优缺点/数据对比/用户选择/确认状态 |
| `design_rounds_gate_b/round_NNN.json` | Phase 1.5 | B 板回执 |
| `design_board_gate_b.md/.html/.xlsx` | Phase 1.5 | B 板渲染视图（含 4 位确认码） |
| `model_advice.json` | Phase 1.5 | 建议 Agent 产出：1 建议 + 其余不建议 + 打分 + 多组数据对比 |
| `perspective_trials.json` | Phase 1.5 | 每视角真实试算（**只能由 `tools/perspective_trial_runner.py` 写入**） |
| `reopen_gate_request.json` | Phase 1.5+ | 重开闸门申请（范式不成立或所选方案不可行），可选 |
| `ambiguity_register.json` | Phase 0 | 题意歧义、单位、隐藏约束和评分要求审计 |
| `assumption_ledger.md` | Phase 0+ | 假设来源、影响和验证状态 |
| `scoring_strategy.md` | Phase 0/1 | 题目小问、评分点、数值答案和图表支撑策略 |
| `data_schema.json` | Phase 0/3 | 附件字段、类型、单位、缺失率、范围和主键契约 |
| `symbol_table.json` | Phase 1/2 | 符号、单位和代码变量映射 |
| `modeling_state.json` | 全程 | 机器可读状态 |
| `modeling_memory.md` | 全程 | 人类可读过程记忆 |
| `baseline_solution.json` | Phase 1 | 简单、可运行、可解释的基线模型 |
| `case_retrieval.json` | Phase 1 | 相似题型、可借鉴方法、不能照搬的风险和推荐验证 |
| `model_spec.json` | Phase 1+ | 变量、目标函数、约束、参数、单位、数据映射和验证计划 |
| `model_selection_audit.json` | Phase 1 | 候选模型、评分、拒绝理由和最终选择证据 |
| `optimization_certificate.json` | Phase 1/3 | 可行性残差、上下界、gap、替代求解器或枚举 oracle |
| `uncertainty_budget.json` | Phase 1/4 | 数据、参数、模型和随机误差预算及影响 |
| `validation_profile.json` | Phase 1/4 | 按题型记录优化、预测、图网络、仿真、机理或政策验证证据 |
| `data_validation.json` | Phase 0/3 | 数据切分、目标泄漏和训练集拟合预处理记录 |
| `statistical_validation.json` | Phase 3/4 | 指标、残差、区间、稳健性和过拟合风险 |
| `solver_strategy.json` | Phase 1/3 | 首选求解器、备选求解器、fallback、超时和交叉验证 |
| `ablation_study.json` | Phase 1/3 | baseline、简化模型、完整模型和约束/权重消融实验 |
| `innovation_register.json` | Phase 1 | 创新点、题目痛点、baseline 增益、证据和风险 |
| `final_solution.json` | Phase 1 | 最终建模方案 |
| `model_decision.md` | Phase 1 | 共识过程和裁决理由 |
| `writer_prompt.md` | Phase 2/5 | 给后续写作 skill 的交接提示词 |
| `solution.py` 或 `solution.m` | Phase 3 | 可运行代码 |
| `solution_tests.py` 或 `solution_tests.m` | Phase 3 | 代码 Agent 先写的契约测试 |
| `figure_style.json` | Phase 3 | 图表风格规范 |
| `figure_storyboard.md` | Phase 3 | 图表叙事板，每张图包含 file、claim、source_data、x_unit、y_unit 和 supports_question |
| `results/` | Phase 3+ | CSV/JSON/PNG 等输出 |
| `results/validation_summary.json` | Phase 3+ | baseline、oracle、交叉验证、敏感性和不变量证据 |
| `results/figure_quality_report.json` | Phase 4 | 图表清晰度、叙事支撑和出版级质量审计 |
| `judge_panel_review.json` | Phase 4 | 多评委并行审查和 chair judge 汇总 |
| `decision_insights.md` | Phase 4/5 | 结果解释、工程/管理含义、风险提示和可执行策略 |
| `defense_questions.md` | Phase 4/5 | 评委质询 Agent 问题和修正建议 |
| `compliance_record.json` | Phase 5 | AI 使用、匿名性、资料引用、官方规则和最终提交约束 |
| `reproducibility_manifest.json` | Phase 5 | OS、Python/MATLAB、求解器、依赖、随机库、耗时、输入/输出 hash |

## 执行入口

首次开始：

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
```

恢复任务：

```bash
python "tools/workflow_runner.py" resume --workspace "." --language python
```

快速自检（兼容旧工作区，warning-only，通过不代表产物齐全）：

```bash
python "tools/pipeline_check.py" --workspace "." --language python
```

最终交付验证（难题、完整交付、竞赛正式结果必须使用）：

```bash
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict --quality-mode excellence
```

标准模式只做结构自检，缺失的质量闭环产物只报 warning；`passed: true` 仅表示没有硬性错误，
产物齐备情况见返回值中的 `artifact_completeness` 与 `status` 字段。最终交付一律以严格/卓越模式为准。

把 `python` 换成 `matlab` 即使用 MATLAB 分支。`workflow_runner.py` 只初始化、恢复和验证文件状态；并行 Agent 推理仍必须由执行者按 `references/workflow.md` 发起。

## Phase Gates

### Phase 0: 题目与数据提取

读取题目文件和附件，使用 `tools/input_parser.py` 与 `tools/data_analyzer.py` 生成 `problem_brief.md`。启动题意审计 Agent、问题拆解与评分策略 Agent，并根据题目领域和数据类型读取 `references/competition_sources.json` 完成竞赛来源匹配：电力、电路、电磁场优先参考电工杯；统计调查和社会经济数据优先参考统计建模大赛；行业数据和大数据题优先参考 MathorCup；工程真实问题优先参考深圳杯。生成 `ambiguity_register.json`、`assumption_ledger.md` 与 `scoring_strategy.md`。建立 `data_schema.json` 初稿，向用户确认题目目标、附件摘要、关键歧义、评分重点和编程语言。确认后更新 `modeling_state.json` 与 `modeling_memory.md`。

### Phase 0.5: 框架与探索边界闸门（A 闸门）

Phase 0 完成后进入本阶段。目标是让用户在写任何代码前确认三件事：**题目读对了吗、高危假设接不接受、这一题要探索哪些方法范式**，并由用户本人确认。**本阶段不选模型**——选模型在 Phase 1.5 的 B 闸门。

1. 生成 `design_board.json`（`schema_version: 2`）：每题给 **3-5 个 `paradigm_set`**，每项含 `paradigm_id`、`name`、`family`（方法族）、`source_ref`（含 tier 与 verified，未核实必须写 `unverified_reason`）、`why_explore`、`explore_cost`（`{"level": "low|medium|high", "note": ...}`）。同一题内**至少 1 个范式与其他范式异质**（`family` 不同），否则五视角仍会互抄。
2. 每题写 `paradigm_selection`（用户确认要探索的范式子集，≥2 项且至少含 1 个异质族）、`options: []`、`user_choice: null`、`user_locked: false`。**A 板不承载模型候选**；`mini_trial` 在本阶段变为可选（有真实试算更好，没有不阻断）。
3. 运行 `python "tools/design_board.py" render --workspace "." --format all`（默认 `--gate a`）生成 `design_board.md` / `.html` / `design_choices.xlsx`（Mermaid 导图 + 范式表 + 4 位确认码）。HTML 单文件零外链。
4. 把 A 板交给用户修改（增删范式、调整要探索的集合、写批注）。三条通道任选其一，语义等价：
   - **页面直选**：`python "tools/design_board.py" serve --workspace "."` 起本地回传服务器（只绑 `127.0.0.1`，带一次性 token），提交后直接写 `design_rounds/`；
   - **Excel**：用户改 `design_choices.xlsx` 后 `ingest --from design_choices.xlsx`；
   - **下载 JSON**：离线页面点「下载回执 JSON」，再 `ingest --from design_board_submission.json`。
5. 重复第 3–4 步，直到连续 2 轮无修改（`no_change_rounds >= 2`）、无待决项、且 `board_sha256` 与内容一致。
6. **由用户本人**运行 `python "tools/design_board.py" confirm --workspace "." --apply` 并输入 `design_board.md` 顶部的 4 位确认码。AI 不得代跑、不得代填。
7. 运行 `python "tools/design_board_checker.py" --workspace "." --gate a --mode excellence`：校验范式集合、异质性、选择子集、确认回执与时间线（代码不得早于 A 板确认）。
8. 确认通过后才允许进入 Phase 1。五视角建模 Agent 以 `paradigm_selection` 为**探索边界**，各自在边界内提出最优方案；**任何预设选型都不得注入简报**，范式不成立时走 `reopen_gate_request.json`（`gate: "a"`）。

> 旧项目（Phase 0.5 之前就存在的 workspace）没有 `design_board.json`：先跑 `python "tools/migrate_workspace.py" --workspace "."`（dry-run）看将生成什么，再 `--apply` 落地骨架；迁移生成的板**必须**由用户重新走一遍 render → 确认，不允许跳过。
> 若宿主支持 hook，装 `hooks/pre_tool_use_guard.py`（见 `hooks/README.md`）可在 AI 试图写 `solution.py` 时硬拦——A 板未确认拦一次，B 板未确认再拦一次（L5 防线）。

### Phase 1: 并行建模共识

必须先判断 `problem_taxonomy`，再执行五视角建模 Agent。流程是：资料库检索 Agent 先读取 `competition_sources.json` 和 `award_playbook.md`，输出 `case_retrieval.json`，列出相似题型、可借鉴模型和不能照搬的风险；五个 Agent 并行生成方案并参考这些卡片，但不得直接套用不匹配模型。**五视角以 A 板的 `paradigm_selection` 为探索边界，各自独立提出该边界内的最优方案；不得被任何预设选型锁定，发现范式本身不成立时走 `reopen_gate_request.json`（`gate: "a"`）。** 按题型最多追加 3 个动态专家 Agent，随后并行批评、并行修正，创新筛选 Agent 生成 `innovation_register.json`。修正完成后**先进入 Phase 1.5（B 闸门）**；裁决 Agent 只在 B 板确认后按用户的 `user_choice` 生成 `baseline_solution.json`、`model_spec.json`、`solver_strategy.json`、`ablation_study.json`、`final_solution.json` 与 `model_decision.md`。本阶段不生成正式写作正文。

五视角建模 Agent 包括：

- 优化视角 Agent
- 统计视角 Agent
- 物理机理 Agent
- 工程实践 Agent
- 创新方法 Agent

### Phase 1.5: 方案择定闸门（B 闸门）

Phase 1 的五视角并行、批评与修正完成后进入本阶段。**主仓库形态是一块 B 板覆盖全部小问、一次确认**（分支形态是每问一块板，逐问确认）。本阶段回答一个问题：**这一题用哪个模型**。

1. 每视角产出可跑试算脚本 `perspective_trials/<perspective>.py`（打印一个 JSON 对象作为 metrics）。
2. 用 `python "tools/perspective_trial_runner.py" open --workspace "." --slices slices.json` 初始化，再逐格 `run --perspective <名> --option-id <O?> --slice <id>` 真跑 **≥2 组数据切片**（无数据集的小问用 `--axis parameter|scenario` 的参数/场景切片）。**禁止手填**：`perspective_trials.json` 只能由该 runner 写入（`executed_by: "tool"` + `exit_code` + `stdout_sha256`）。
3. 建议 Agent 读 `revised_*.json` / `critique_*.json` / `perspective_trials.json`，写 `model_advice.json`：**恰好 1 个 `recommended` + 其余 `not_recommended`**；候选 5-8 个（baseline 只作参照行）；每个候选 `pros`/`cons` 各 ≥2 条；不推荐项要 `why_not` ≥2 条 + `when_better`；`data_comparison` 覆盖 ≥2 个 slice × 全部候选，**数值必须回溯到 trials**（可比层 `comparable` 同键，专属层 `own` 各自指标）；`is_judge_panel: false` + `disclaimer`，不得出现评委结论措辞。
4. `python "tools/model_advice_builder.py" assemble --workspace "."` 生成骨架（数值由工具回填），Agent 只填分数/优缺点/推荐；再 `validate --workspace "." --mode excellence`，必须 `passed: true`。
5. 生成 B 板并渲染：`python "tools/design_board.py" render --gate b --workspace "." --format all`，产出 `design_board_gate_b.{md,html,xlsx}`（分数、优缺点、数据对比表、推荐/不建议理由、baseline 参照行、4 位确认码）。
6. 用户用同一套通道（serve / Excel / JSON）在 B 板上选定模型；`ingest --gate b` 写 `design_rounds_gate_b/`。
7. **由用户本人**运行 `python "tools/design_board.py" confirm --gate b --workspace "." --apply` 并输入 B 板确认码。
8. `python "tools/design_board_checker.py" --gate b --workspace "." --mode excellence`：校验建议 8 条规则、trials 工具执行与数值一致、`user_choice`、确认回执，以及**双时间线**（`solution.*` 不得早于 B 板确认）。
9. 裁决 Agent 读 B 板 `user_choice`，**无条件采用用户所选方案**，产出 `model_selection_audit.json`（`selected_by: "user"`、`user_choice_id`、`advice_recommended_id`、`diverged_from_advice`）、`model_spec.json`、`solver_strategy.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`ablation_study.json`、`innovation_register.json`、`final_solution.json`、`model_decision.md`。
10. 若所选方案在推进中不可行（求解器无解、约束矛盾），**不得自行换方案**：产出 `reopen_gate_request.json`（`gate: "b"`）并停下等用户重新确认。

> B 闸门的"建议 Agent 打分"不是评委结论；多评委审查仍在 Phase 4。二者不得混淆。

### Phase 2/3: 写作交接文档 Agent 与代码 Agent 并行

> **前置条件**：B 板已确认（`design_board_gate_b.json` 的 `confirmed: true` 且该问 `user_choice` 非空）。未确认前不得创建或修改 `solution.py` / `solution.m` / `solution_tests.*`；hook 守卫与 checker 会同时拦。

文档 Agent 与代码 Agent 并行执行，但文档 Agent 只生成写作交接提示词，不生成正式写作正文。文档 Agent 基于 `problem_brief.md`、`scoring_strategy.md`、`final_solution.json`、`model_spec.json`、`innovation_register.json` 生成 `writer_prompt.md` 首轮草稿；`results/validation_summary.json`、图表叙事板和复现清单由 Phase 3/5 产出，Phase 2 首轮可缺省，在 Phase 5 定稿时补入。代码 Agent 先生成 `solution_tests.py` 或 `solution_tests.m`，再生成 `solution.py` 或 `solution.m`，并把所有结果和 `results/validation_summary.json` 写入 `results/`。可视化设计 Agent 生成 `figure_storyboard.md`、`figure_style.json` 和证据图组。

验证证据必须由真实计算产生。模板默认的 `status: "NOT_VALIDATED"` 与 `passed: null` 会被 `evidence_checker.py` 和 `robustness_checker.py` 判为失败；确定性模型可对随机性相关条目声明 `{"status": "not_applicable", "rationale": ..., "alternative_validation": ...}`，但必须同时给出理由和替代验证方式。

### Phase 4: 多评委并行审查、独立复现与工具验证

先并行启动技术审查组：

- 语法审查 Agent
- 逻辑审查 Agent
- 输出审查 Agent

同时启动独立复现 Agent，只读 `problem_brief.md`、`baseline_solution.json`、`final_solution.json` 和代码输出，独立复算核心结论，不参考任何正式写作措辞。

再启动评委组并行审查：国赛建模评委、美赛评委、代码复现评委、图表证据评委、工程/业务解释评委。每个评委独立输出结构化评分和问题清单，再由 chair judge 汇总为 `judge_panel_review.json`。审查范围只覆盖建模、代码、结果、图表和验证证据，不审查正式写作正文。

汇总问题后运行 `pipeline_check.py`，或按需分别运行 `innovation_checker.py`、`judge_panel_checker.py`、`compliance_checker.py`、`evidence_checker.py`、`robustness_checker.py`、`figure_auditor.py`、`manifest_checker.py` 等工具。任何失败都必须修正并重新验证。

### Phase 5: 最终交付

确认固定产物齐全，生成或更新 `writer_prompt.md`、`compliance_record.json` 与 `reproducibility_manifest.json`，运行总控验证，归档 `modeling_memory.md`，把验证摘要写入 `modeling_state.json`。如果本 skill 自身被修改，还要更新 `audit_memory.md`。

## MATLAB 支持等级

MATLAB 是正式支持分支。使用 MATLAB 时：

- 代码文件为 `solution.m`。
- 所有输出仍写入 `results/`。
- 图表保存为 PNG。
- 能检测到 MATLAB 且启用运行测试时，可用 `tools/code_runner.py --lang matlab` 实测；否则执行静态模板和产物检查。

## 验证清单

完成前必须至少运行：

```bash
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
python "tools/pipeline_check.py" --workspace "tests/test_data" --language python
python "tools/design_board.py" status --workspace "tests/test_data"
python "tools/design_board.py" status --gate b --workspace "tests/test_data"
python "tools/design_board_checker.py" --workspace "tests/test_data" --gate a --mode excellence
python "tools/design_board_checker.py" --workspace "tests/test_data" --gate b --mode excellence
python "tools/perspective_trial_runner.py" status --workspace "tests/test_data"
python "tools/model_advice_builder.py" validate --workspace "tests/test_data" --mode excellence
python "tools/mini_trial.py" status --workspace "tests/test_data"
python "tools/migrate_workspace.py" --workspace "tests/test_data"
python "tools/tools_sync_checker.py" --primary "." --branch "../math-modeling-per-question"
python "hooks/selftest.py"
python "tools/pipeline_check.py" --workspace "tests/test_data" --language python --evidence-mode strict --quality-mode excellence
python "tools/source_registry_checker.py" --skill-root "." --mode excellence
python "tools/source_freshness_checker.py" --workspace "." --mode excellence
python "tools/award_readiness_checker.py" --workspace "tests/test_data" --mode excellence
python "tools/mini_benchmark_checker.py" --benchmark "evals/mini_contest_benchmark.json" --mode strict
python "tools/mini_benchmark_runner.py" --benchmark "evals/mini_contest_benchmark.json" --mode strict
python "tools/workflow_runner.py" resume --workspace "tests/test_data" --language python
Get-ChildItem workflows -Filter *.js | ForEach-Object { node --check $_.FullName }
```

验证结果与本次修改摘要必须追加到 `audit_memory.md`。
