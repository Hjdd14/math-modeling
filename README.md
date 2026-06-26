# math-modeling

正式版 1.0.0，当前 Unreleased 增强面向 1.2.0。`math-modeling` 是一个面向数学建模竞赛/课程题目的 Codex/Claude Skill：它把题目解析、并行 Agent 建模、报告撰写、Python/MATLAB 代码实现、结果验证、模型规范、数据契约、出版级图表和可恢复状态管理串成一条可审计流程。

这个仓库的主入口是 `SKILL.md`。完整流程、模板、工具说明和 eval 规则分别放在 `references/workflow.md`、`references/templates.md`、`references/tools.md` 和 `references/evals.md`。主 skill 变短是为了降低上下文负担，不代表删减能力；并行 Agent 流程仍是 phase gate。

## 能力

- Phase 0：从 PDF/DOCX/Markdown/TXT 和表格附件生成 `problem_brief.md`。
- Phase 0：题意审计 Agent 生成 `ambiguity_register.json` 与 `assumption_ledger.md`，先暴露歧义、单位和隐藏约束。
- Phase 1：五个建模 Agent 并行出方案，按题型最多追加 3 个动态专家 Agent，再并行批评、并行修正，最后裁决生成 `baseline_solution.json`、`final_solution.json` 和 `model_decision.md`。
- Phase 2/3：文档 Agent 与代码 Agent 并行工作，生成 `modeling_report.md` 与 `solution.py` 或 `solution.m`；代码必须写出 `results/validation_summary.json`。
- Phase 4：语法审查、逻辑审查、输出审查三个 Agent 并行，同时执行独立复现 Agent，再运行工具链和 `evidence_checker.py` 验证。
- 1.2.0 卓越质量闭环：用 `model_spec.json`、`data_schema.json`、`symbol_table.json`、`solution_tests.py`、`figure_style.json`、`figure_storyboard.md`、`reproducibility_manifest.json` 和 `report_auditor.py` 把模型、数据、代码、图表、报告与复现实验连起来。
- 出版级图表：`figure_auditor.py` 配合可视化设计 Agent 检查 `results/figure_quality_report.json`，让图表从“能生成”升级到“能支撑论文论证”。
- Phase 5：更新 `modeling_state.json` 和 `modeling_memory.md`，支持中断恢复。
- MATLAB 是正式支持分支；默认测试会做静态检查，检测到本机 MATLAB 并设置 `RUN_MATLAB_TESTS=1` 后可实跑。

## 安装

```powershell
python -m pip install -r requirements.txt
```

可选依赖：

- Node.js：用于 `node --check workflows/*.js` 静态检查。
- MATLAB：用于运行 `solution.m` 和 MATLAB 集成测试。
- Claude CLI：用于 `tools/claude_eval_runner.py` 的真实对比 eval。

## 快速开始

先运行本地体检：

```powershell
python tools/doctor.py --workspace .
```

初始化一个工作区：

```powershell
python tools/workflow_runner.py scaffold --workspace runs/my_case --language python
```

解析题目：

```powershell
python tools/input_parser.py brief --problem path/to/problem.pdf --data path/to/data.xlsx --out runs/my_case/problem_brief.md
```

恢复已有工作区：

```powershell
python tools/workflow_runner.py resume --workspace runs/my_case --language python
```

总控验证：

```powershell
python tools/pipeline_check.py --workspace runs/my_case --language python
```

难题或正式交付使用严格证据模式：

```powershell
python tools/pipeline_check.py --workspace runs/my_case --language python --evidence-mode strict
```

一等奖级完整交付使用严格证据和卓越质量模式：

```powershell
python tools/pipeline_check.py --workspace runs/my_case --language python --evidence-mode strict --quality-mode excellence
```

完整测试：

```powershell
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
```

也可以先试公开合成样例：

```powershell
python tools/workflow_runner.py scaffold --workspace runs/quickstart --language python
python tools/input_parser.py brief --problem examples/quickstart/problem.md --data examples/quickstart/production_data.csv --out runs/quickstart/problem_brief.md
python tools/workflow_runner.py resume --workspace runs/quickstart --language python
```

示例说明见 `examples/quickstart/README.md`。

完整 solved example 见 `examples/solved-python/`。它展示了 `model_spec.json`、`data_schema.json`、`solution_tests.py`、`validation_summary.json`、`figure_auditor.py` 相关产物、报告和复现清单的理想结构。

## 给其他 Agent 的使用约定

1. 先读 `SKILL.md`，再按其要求读取并执行 `references/workflow.md`。
2. 不要把 `workflow_runner.py` 当成建模推理替代品；它只负责 scaffold、resume、verify 和状态文件维护。
3. 并行 Agent 步骤必须真实执行或明确记录为外部已执行步骤，并把摘要写入 `modeling_state.json`。
4. 使用 `tools/state_manager.py agent-run` 记录 Agent 运行，使用 `tools/state_manager.py tool-run` 记录工具运行。
5. Phase 1 只产出 `final_solution.json` 和 `model_decision.md`，正式报告只能在 Phase 2 生成。
6. 难题或完整交付必须保留 `validation_summary.json`、baseline、oracle/小例验证、solver 交叉验证、敏感性分析和独立复现摘要。
7. 一等奖级交付额外运行 `pipeline_check.py --quality-mode excellence`，并保留 `model_spec.json`、`data_schema.json`、`solution_tests.py`、`figure_storyboard.md`、`report_quality_report.json`、`defense_questions.md` 和 `reproducibility_manifest.json`。

## 固定产物

每个建模工作区应包含：

- `problem_brief.md`
- `ambiguity_register.json`
- `assumption_ledger.md`
- `modeling_state.json`
- `modeling_memory.md`
- `baseline_solution.json`
- `scoring_strategy.md`
- `data_schema.json`
- `symbol_table.json`
- `model_spec.json`
- `solver_strategy.json`
- `ablation_study.json`
- `final_solution.json`
- `model_decision.md`
- `modeling_report.md`
- `solution.py` 或 `solution.m`
- `solution_tests.py` 或 `solution_tests.m`
- `figure_style.json`
- `figure_storyboard.md`
- `results/`
- `results/validation_summary.json`
- `results/figure_quality_report.json`
- `report_quality_report.json`
- `decision_insights.md`
- `defense_questions.md`
- `reproducibility_manifest.json`

## 验证边界

工具链会检查 LaTeX、代码执行、图表文件、brief 对齐、文档/代码公式一致性、可信度证据、数据契约、模型规范、符号单位、数值鲁棒性、出版级图表、报告结构和可复现清单。`consistency_checker.py`、`evidence_checker.py`、`schema_checker.py`、`model_spec_checker.py`、`figure_auditor.py` 都是结构化检查，不等价于数学证明；真实任务仍需要 Phase 4 的并行审查 Agent、独立复现 Agent、评委质询 Agent 和问题级断言共同验证。

## 开源许可

本项目使用 MIT License。详见 `LICENSE`。

## 本地 GitHub 仓库

本目录可以直接添加到 GitHub Desktop。步骤见 `docs/GITHUB_DESKTOP.md`。仓库默认不配置 remote，不会自动上传。
