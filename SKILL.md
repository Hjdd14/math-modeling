---
name: math-modeling
description: 用于数学建模竞赛或类似多阶段建模任务。触发条件：用户提供题目 PDF/DOCX/Markdown/TXT 与 Excel/CSV 附件，并要求完成建模分析、报告、Python 或 MATLAB 代码、图表、结果验证或难题可信度审查。不要用于普通单题解答、单纯表格清洗、PDF 翻译或只写一段代码的任务。执行时必须保留并行子 Agent：Phase 1 五视角建模共识，Phase 2/3 文档 Agent 与代码 Agent 并行，Phase 4 三类审查 Agent 并行。
---

# 数学建模竞赛全流程 Skill

本 skill 执行完整的数学建模工作流：题目与附件解析、并行建模共识、并行文档与代码生成、工具链验证、修正循环和最终交付。主文件只保留执行骨架；详细流程、模板和工具说明按需读取引用文档。

## 必读引用

执行前先读取这些文件：

1. `references/workflow.md`：完整 Phase 0-5 流程，包含所有并行 Agent prompt、输入、输出和汇总规则。
2. `references/templates.md`：`problem_brief.md`、`modeling_report.md`、Python/MATLAB 代码、`modeling_memory.md` 模板。
3. `references/tools.md`：所有 CLI 工具命令、JSON 字段和失败判定。
4. `references/evals.md`：本地 eval、Claude 实跑 eval、触发描述优化流程。

如果引用文档与本主文件冲突，以本主文件的核心约束为准；如果用户的显式要求更具体，以用户要求为准。

## 核心约束

1. `problem_brief.md` 是唯一真实来源；模型、报告、代码和结果都必须对照它核查。
2. 并行子 Agent 是核心能力，不能被 Python CLI、workflow runner 或引用文档替代。
3. Python CLI 只做确定性编排、状态管理和验证；不得把多 Agent 建模降级为单脚本假推理。
4. Phase 1 不得写入 `modeling_report.md`；只输出 `final_solution.json` 和 `model_decision.md`。
5. Phase 2 才生成 `modeling_report.md`。
6. Phase 3 代码只依赖 `final_solution.json` 与 `problem_brief.md`，不等待 Phase 2 先落盘。
7. 所有运行结果统一写入 `results/`。
8. 每个阶段都更新 `modeling_state.json` 和 `modeling_memory.md`。
9. 工具调用必须在对应 step 直接执行，不得跳过。
10. 验证失败时回溯到对应阶段修正，而不是在后续阶段打补丁。
11. 难题必须保留可证伪证据链：题意审计、baseline、oracle 或等价小例验证、solver 交叉验证、敏感性分析和独立复现记录。
12. 未解决的 high severity 歧义必须写入 `modeling_memory.md`，不能静默进入 Phase 1。
13. 难题或完整验证必须使用 `pipeline_check.py --evidence-mode strict`。

## 固定产物

工作区内固定维护以下文件或目录：

| 产物 | 阶段 | 说明 |
|------|------|------|
| `problem_brief.md` | Phase 0 | 题目、目标、约束、附件摘要 |
| `ambiguity_register.json` | Phase 0 | 题意歧义、单位、隐藏约束和评分要求审计 |
| `assumption_ledger.md` | Phase 0+ | 假设来源、影响和验证状态 |
| `modeling_state.json` | 全程 | 机器可读状态 |
| `modeling_memory.md` | 全程 | 人类可读过程记忆 |
| `baseline_solution.json` | Phase 1 | 简单、可运行、可解释的基线模型 |
| `final_solution.json` | Phase 1 | 最终建模方案 |
| `model_decision.md` | Phase 1 | 共识过程和裁决理由 |
| `modeling_report.md` | Phase 2 | 正式建模报告 |
| `solution.py` 或 `solution.m` | Phase 3 | 可运行代码 |
| `results/` | Phase 3+ | CSV/JSON/PNG 等输出 |
| `results/validation_summary.json` | Phase 3+ | baseline、oracle、交叉验证、敏感性和不变量证据 |

## 执行入口

首次开始：

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
```

恢复任务：

```bash
python "tools/workflow_runner.py" resume --workspace "." --language python
```

最终验证：

```bash
python "tools/pipeline_check.py" --workspace "." --language python
```

把 `python` 换成 `matlab` 即使用 MATLAB 分支。`workflow_runner.py` 只初始化、恢复和验证文件状态；并行 Agent 推理仍必须由执行者按 `references/workflow.md` 发起。

## Phase Gates

### Phase 0: 题目与数据提取

读取题目文件和附件，使用 `tools/input_parser.py` 与 `tools/data_analyzer.py` 生成 `problem_brief.md`。启动题意审计 Agent，生成 `ambiguity_register.json` 与 `assumption_ledger.md`。向用户确认题目目标、附件摘要、关键歧义和编程语言。确认后更新 `modeling_state.json` 与 `modeling_memory.md`。

### Phase 1: 并行建模共识

必须先判断 `problem_taxonomy`，再执行五视角建模 Agent。流程是：五个 Agent 并行生成方案，按题型最多追加 3 个动态专家 Agent，随后并行批评，并行修正，最后由裁决 Agent 生成 `baseline_solution.json`、`final_solution.json` 与 `model_decision.md`。本阶段不得写入 `modeling_report.md`。

五视角建模 Agent 包括：

- 优化视角 Agent
- 统计视角 Agent
- 物理机理 Agent
- 工程实践 Agent
- 创新方法 Agent

### Phase 2/3: 文档与代码并行

文档 Agent 与代码 Agent 并行执行。文档 Agent 基于 `final_solution.json`、`baseline_solution.json` 和 `problem_brief.md` 生成 `modeling_report.md`。代码 Agent 基于同样输入生成 `solution.py` 或 `solution.m`，并把所有结果和 `results/validation_summary.json` 写入 `results/`。

### Phase 4: 并行审查与工具验证

先并行启动三个审查 Agent：

- 语法审查 Agent
- 逻辑审查 Agent
- 输出审查 Agent

同时启动独立复现 Agent，只读 `problem_brief.md`、`final_solution.json` 和代码输出，独立复算核心结论，不参考报告措辞。汇总问题后，依次运行 `code_runner.py`、`figure_checker.py`、`consistency_checker.py`、`brief_validator.py`、`evidence_checker.py` 或直接运行 `pipeline_check.py`。任何失败都必须修正并重新验证。

### Phase 5: 最终交付

确认固定产物齐全，运行总控验证，归档 `modeling_memory.md`，把验证摘要写入 `modeling_state.json`。如果本 skill 自身被修改，还要更新 `audit_memory.md`。

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
python "tools/workflow_runner.py" resume --workspace "tests/test_data" --language python
```

验证结果与本次修改摘要必须追加到 `audit_memory.md`。
