# Changelog

## Unreleased

- 规划为 `1.2.0`：新增一等奖级交付质量闭环，包括 `model_spec.json`、`data_schema.json`、`symbol_table.json`、`solver_strategy.json`、`solution_tests.py`、`figure_style.json`、`figure_storyboard.md`、`report_quality_report.json`、`decision_insights.md`、`defense_questions.md` 和 `reproducibility_manifest.json`。
- 新增 `tools/schema_checker.py`、`tools/model_spec_checker.py`、`tools/unit_checker.py`、`tools/robustness_checker.py`、`tools/figure_auditor.py`、`tools/report_auditor.py`、`tools/manifest_checker.py` 和 `tools/solution_test_generator.py`。
- `tools/pipeline_check.py` 新增 `--quality-mode standard|strict|hard|complete|full|excellence`，默认 standard 兼容旧工作区，excellence 要求完整模型、数据、代码、图表、报告和复现证据链。
- 新增 `examples/solved-python/`，展示完整合成样例的理想产物结构，方便其他 Agent 和开源用户对齐输出。
- 工作流新增问题拆解与评分策略 Agent、可视化设计 Agent、竞赛论文表现力 Agent、结果解释与决策建议 Agent、评委质询 Agent。
- 规划为 `1.1.0`：新增难题准确性增强链路，包括题意审计、假设台账、题型分类、动态专家 Agent、baseline、模型评分矩阵、`validation_summary.json` 和独立复现 gate。
- 新增 `tools/evidence_checker.py`，并在 `pipeline_check.py` 中集成 `--evidence-mode standard|strict`；普通旧工作区缺证据给 warning，难题/完整模式缺证据失败。
- Python 与 MATLAB 模板补齐 `run_baseline()`、`run_known_case_tests()`、`run_sensitivity_analysis()` 和 `write_validation_summary()` / 等价 JSON 输出。
- eval 覆盖多目标优化、缺失数据预测、图路径规划、随机仿真和非线性约束等难题场景。
- 新增 `tools/doctor.py`，用于本地依赖、仓库结构、可选工具和 quickstart 示例体检。
- 新增 `examples/quickstart/` 合成公开样例，帮助新用户先跑通题目解析和状态恢复。
- 修正 README 中 `input_parser.py` 的错误 quickstart 命令。
- 补齐 `requirements.txt` 与 `pyproject.toml` 的运行依赖：`matplotlib`、`scipy`、`Pillow`。
- 降低 `consistency_checker.py` 对 Python 容器/函数长变量名的 `code_only_symbol` 噪声。
- CI 增加 doctor 检查。

## 1.0.0 - 2026-06-23

正式版发布。

- 将长 `SKILL.md` 拆为短主入口和 `references/` 引用文档。
- 保留并强化 Phase 1、Phase 2/3、Phase 4 的并行 Agent gate。
- 新增 `workflow_runner.py`、`pipeline_check.py`、`input_parser.py` 和 `state_manager.py`。
- 新增可恢复 `modeling_state.json`，记录 phase、artifact、tool run、agent run 和 issues。
- 修复状态文件相对路径解析、并发写入覆盖和 `resume` 抹除历史的问题。
- 优化 `consistency_checker.py`，避免 Python AST 结构词造成误报，并支持机器可读 `passed` 字段。
- 明确 MATLAB 为正式支持分支，提供模板、夹具和可选集成测试。
- 新增 eval 文件、触发评估和开源发布文档。

## 0.2.0 - 2026-06-22

- 新增短主 skill 架构、引用文档、输入解析、状态管理、总控验证和工作流入口。
- 测试基线提升到 `99 passed, 1 skipped`。

## 0.1.0 - 2026-06-13

- 修复早期工具链假通过问题。
- 增补 LaTeX、图表、代码运行、brief 和一致性检查测试。
