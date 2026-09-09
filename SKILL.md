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

## 固定产物

工作区内固定维护以下文件或目录：

| 产物 | 阶段 | 说明 |
|------|------|------|
| `problem_brief.md` | Phase 0 | 题目、目标、约束、附件摘要 |
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

### Phase 1: 并行建模共识

必须先判断 `problem_taxonomy`，再执行五视角建模 Agent。流程是：资料库检索 Agent 先读取 `competition_sources.json` 和 `award_playbook.md`，输出 `case_retrieval.json`，列出相似题型、可借鉴模型和不能照搬的风险；五个 Agent 并行生成方案并参考这些卡片，但不得直接套用不匹配模型。按题型最多追加 3 个动态专家 Agent，随后并行批评、并行修正，创新筛选 Agent 生成 `innovation_register.json`，最后由裁决 Agent 生成 `baseline_solution.json`、`model_spec.json`、`solver_strategy.json`、`ablation_study.json`、`final_solution.json` 与 `model_decision.md`。本阶段不生成正式写作正文。

五视角建模 Agent 包括：

- 优化视角 Agent
- 统计视角 Agent
- 物理机理 Agent
- 工程实践 Agent
- 创新方法 Agent

### Phase 2/3: 写作交接文档 Agent 与代码 Agent 并行

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
