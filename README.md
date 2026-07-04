# math-modeling

正式版 1.0.0，当前 Unreleased 增强面向奖项级建模与代码交付。`math-modeling` 是一个面向数学建模竞赛/课程题目的 Codex/Claude Skill：它把题目解析、并行 Agent 建模、创新筛选、Python/MATLAB 代码实现、结果验证、模型规范、数据契约、图表证据、合规复现和写作交接提示词串成一条可审计流程。

本 skill 不生成正式写作正文。它输出 `writer_prompt.md`，把模型、代码、结果、图表、验证证据、可复现信息和合规注意事项交给后续独立写作 skill。

主入口是 `SKILL.md`。完整流程、模板、工具说明、权威竞赛来源总索引、案例方法谱系、评委组规则和 eval 规则分别放在 `references/workflow.md`、`references/templates.md`、`references/tools.md`、`references/competition_sources.json`、`references/award_playbook.md`、`references/evaluator_panel.md` 和 `references/evals.md`。主 skill 变短是为了降低上下文负担，不代表删减能力；并行 Agent 流程仍是 phase gate。

## 能力

- Phase 0：从 PDF/DOCX/Markdown/TXT 和表格附件生成 `problem_brief.md`，并根据 `competition_sources.json` 做竞赛来源匹配。
- Phase 0：题意审计 Agent 生成 `ambiguity_register.json` 与 `assumption_ledger.md`，先暴露歧义、单位和隐藏约束。
- Phase 1：五个建模 Agent 并行出方案，资料库检索 Agent 参考 `references/competition_sources.json` 和 `references/award_playbook.md` 输出 `case_retrieval.json`，按题型最多追加 3 个动态专家 Agent，再并行批评、并行修正，最后裁决生成 `baseline_solution.json`、`final_solution.json` 和 `model_decision.md`。
- Phase 1：创新筛选 Agent 生成 `innovation_register.json`，`innovation_checker.py` 要求每个创新点都有题目痛点、baseline 增益、验证证据和失败风险。
- 资料库质量：`source_registry_checker.py` 检查权威来源和 40 张方法卡，`source_freshness_checker.py` 离线检查来源年份和结构；`source_material_reader.py` 作为发布前/人工复核的可选联网深扫，抽检是否能读到优秀论文、赛题、获奖或评审等材料内容；`case_retrieval_checker.py` 防止电工、统计调查、大数据题乱套模型。
- Phase 2/3：写作交接文档 Agent 与代码 Agent 并行工作，生成 `writer_prompt.md` 与 `solution.py` 或 `solution.m`；`writer_prompt_checker.py` 检查交接提示词完整性，代码必须写出 `results/validation_summary.json`。
- Phase 4：语法审查、逻辑审查、输出审查三个 Agent 并行，同时执行独立复现 Agent，再运行 `evidence_checker.py` 和工具链验证。
- Phase 4：多评委并行审查，`judge_panel_checker.py` 要求国赛建模评委、美赛评委、代码复现评委、图表证据评委、工程/业务解释评委和 chair judge 汇总。
- 奖项级上限产物：`award_readiness_checker.py` 要求题意歧义、假设台账、评分策略、消融实验、决策建议和评委质询材料完整，防止“能跑通但不好拿高奖”的交付断层。
- Phase 5：`compliance_checker.py` 检查 AI 使用记录、匿名性、外部资料引用和复现提示。
- 卓越质量闭环：用 `problem_brief.md` 完成度、`model_selection_audit.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`data_validation.json`、`statistical_validation.json`、`model_spec.json`、`data_schema.json`、`symbol_table.json`、`solution_tests.py`、`figure_style.json`、`figure_storyboard.md`、`reproducibility_manifest.json` 和结构化 checker 把模型、数据、代码、图表与复现实验连起来。
- 出版级图表：`figure_auditor.py` 配合可视化设计 Agent 检查 `results/figure_quality_report.json`，要求每张图在 `figure_storyboard.md` 中包含 `file`、`claim`、`source_data`、`x_unit`、`y_unit` 和 `supports_question`，让图表从“能生成”升级到“能支撑结论”。
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

奖项级完整交付使用严格证据和卓越质量模式：

```powershell
python tools/pipeline_check.py --workspace runs/my_case --language python --evidence-mode strict --quality-mode excellence
```

完整测试：

```powershell
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
python tools/source_registry_checker.py --skill-root . --mode excellence
python tools/source_freshness_checker.py --workspace . --mode excellence
python tools/award_readiness_checker.py --workspace tests/test_data --mode excellence
python tools/pipeline_check.py --workspace runs/my_case --language python --evidence-mode strict --quality-mode excellence --online-source-materials
python tools/mini_benchmark_checker.py --benchmark evals/mini_contest_benchmark.json --mode strict
python tools/mini_benchmark_runner.py --benchmark evals/mini_contest_benchmark.json --mode strict
Get-ChildItem workflows -Filter *.js | ForEach-Object { node --check $_.FullName }
```

也可以先试公开合成样例：

```powershell
python tools/workflow_runner.py scaffold --workspace runs/quickstart --language python
python tools/input_parser.py brief --problem examples/quickstart/problem.md --data examples/quickstart/production_data.csv --out runs/quickstart/problem_brief.md
python tools/workflow_runner.py resume --workspace runs/quickstart --language python
```

示例说明见 `examples/quickstart/README.md`。

完整 solved example 见 `examples/solved-python/`。它展示了 `model_spec.json`、`model_selection_audit.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`data_validation.json`、`statistical_validation.json`、`data_schema.json`、`solution_tests.py`、`validation_summary.json`、`writer_prompt.md`、`innovation_register.json`、`judge_panel_review.json`、`compliance_record.json`、图表证据和复现清单的理想结构。

## 给其他 Agent 的使用约定

1. 先读 `SKILL.md`，再按其要求读取并执行 `references/workflow.md`。
2. 不要把 `workflow_runner.py` 当成建模推理替代品；它只负责 scaffold、resume、verify 和状态文件维护。
3. 并行 Agent 步骤必须真实执行或明确记录为外部已执行步骤，并把摘要写入 `modeling_state.json`。
4. 使用 `tools/state_manager.py agent-run` 记录 Agent 运行，使用 `tools/state_manager.py tool-run` 记录工具运行。
5. Phase 1 只产出建模决策和方案产物，不生成正式写作正文。
6. 难题或完整交付必须保留 `validation_summary.json`、baseline、oracle/小例验证、solver 交叉验证、敏感性分析和独立复现摘要。
7. 奖项级交付额外运行 `pipeline_check.py --quality-mode excellence`，并保留 `ambiguity_register.json`、`assumption_ledger.md`、`scoring_strategy.md`、`ablation_study.json`、`decision_insights.md`、`defense_questions.md`、`case_retrieval.json`、`model_selection_audit.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`data_validation.json`、`statistical_validation.json`、`model_spec.json`、`data_schema.json`、`solution_tests.py`、`figure_storyboard.md`、`writer_prompt.md`、`innovation_register.json`、`judge_panel_review.json`、`compliance_record.json` 和 `reproducibility_manifest.json`。

## 固定产物

每个建模工作区应包含：

- `problem_brief.md`
- `ambiguity_register.json`
- `assumption_ledger.md`
- `modeling_state.json`
- `modeling_memory.md`
- `baseline_solution.json`
- `case_retrieval.json`
- `scoring_strategy.md`
- `data_schema.json`
- `symbol_table.json`
- `model_spec.json`
- `solver_strategy.json`
- `ablation_study.json`
- `innovation_register.json`
- `final_solution.json`
- `model_decision.md`
- `model_selection_audit.json`
- `optimization_certificate.json`
- `uncertainty_budget.json`
- `validation_profile.json`
- `data_validation.json`
- `statistical_validation.json`
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

正式正文由后续独立写作 skill 基于 `writer_prompt.md` 生成；本 skill 的验收面聚焦模型、代码、图表、验证证据、复现和合规交接。

## 验证边界

默认工具链会检查代码执行、图表文件、brief 对齐、可信度证据、权威来源索引、离线来源新鲜度、案例检索、奖项级上限产物、模型选择、优化证书、不确定性预算、题型验证 profile、数据泄漏、统计验证、数据契约、模型规范、符号单位、数值鲁棒性、图表证据、创新筛选、评委组审查、合规记录、写作交接提示词和可复现清单。资料内容读取需显式运行 `source_material_reader.py`，或在总控中加 `--online-source-materials` 做发布前联网深扫。`consistency_checker.py`、`evidence_checker.py`、`source_registry_checker.py`、`source_freshness_checker.py`、`source_material_reader.py`、`case_retrieval_checker.py`、`award_readiness_checker.py`、`model_selection_checker.py`、`optimization_certificate_checker.py`、`uncertainty_budget_checker.py`、`validation_profile_checker.py`、`data_leakage_checker.py`、`statistical_validation_checker.py`、`schema_checker.py`、`model_spec_checker.py`、`figure_auditor.py`、`innovation_checker.py`、`judge_panel_checker.py`、`writer_prompt_checker.py` 和 `compliance_checker.py` 都是结构化检查，不等价于数学证明；真实任务仍需要 Phase 4 的并行审查 Agent、独立复现 Agent、评委质询 Agent 和问题级断言共同验证。

## 开源许可

本项目使用 MIT License。详见 `LICENSE`。

## 本地 GitHub 仓库

本目录可以直接添加到 GitHub Desktop。步骤见 `docs/GITHUB_DESKTOP.md`。仓库默认不配置 remote，不会自动上传。
