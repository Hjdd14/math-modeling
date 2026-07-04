# Changelog

## Unreleased

- 新增 `award_readiness_checker.py` 并接入 excellence pipeline，用于硬审计 `ambiguity_register.json`、`assumption_ledger.md`、`scoring_strategy.md`、`ablation_study.json`、`decision_insights.md` 和 `defense_questions.md`，防止高风险歧义、评分策略、消融证据、决策解释或评委质询准备缺失时仍被放行。
- 新增奖项级 excellence gate：`brief_completeness_checker.py`、`model_selection_checker.py`、`optimization_certificate_checker.py`、`uncertainty_budget_checker.py`、`validation_profile_checker.py`、`data_leakage_checker.py`、`statistical_validation_checker.py`、`source_freshness_checker.py` 和 `mini_benchmark_runner.py`，并接入 `pipeline_check.py --quality-mode excellence`、CI 与 release checklist。
- 强化图表、合规和复现：`figure_storyboard.md` 每图必须含 `file`、`claim`、`source_data`、`x_unit`、`y_unit`、`supports_question`；`writer_prompt.md` 必须交接每图结论和提交复核清单；`compliance_record.json` 检查匿名、AI 披露、引用、页数、附件、代码提交和官方规则；`reproducibility_manifest.json` 增加 OS、求解器、随机库、耗时和输入/输出 hash。
- `solution_test_generator.py` 与 `robustness_checker.py` 统一奖项级阈值：随机种子至少 3 个、多初值至少 3 次、bootstrap/置信区间置信水平至少 0.95；`code_runner.py` 改为递归追踪结果文件和 sha256。
- 新增 `references/competition_sources.json`，把资料库扩展为权威竞赛来源分层索引，首版覆盖 7 个 tier_a 来源和 7 个 tier_b 来源，并记录官方入口、年份范围、材料类型和可信度说明。
- 扩容 `references/award_playbook.md`，按比赛维度和 10 类题型沉淀 40 张方法卡；每张方法卡标注来源比赛、年份、题号、适用条件、误用风险、推荐验证和来源链接。
- 新增 `tools/source_registry_checker.py`、`tools/case_retrieval_checker.py` 和 `tools/writer_prompt_checker.py`，并在 `pipeline_check.py --quality-mode excellence` 中纳入来源库、案例检索和写作交接提示词检查。
- 新增 `case_retrieval.json` 为固定产物，用于记录相似题型、可借鉴模型、不能照搬风险和推荐验证；电工、统计调查、大数据题会检查首选来源是否匹配。
- Eval 扩展覆盖 MathorCup 大数据题、电工杯电力题、统计建模社会经济题、深圳杯工程题、研究生赛工业题、APMCM 综合题和五一杯规划题。
- 规划为奖项级建模与代码交付增强：正式流程不再生成正式写作正文，改为输出 `writer_prompt.md`，把模型、代码、结果、图表、验证证据、复现信息和合规注意事项交给后续写作 skill。
- 新增 `references/award_playbook.md` 和 `references/evaluator_panel.md`，沉淀国赛/美赛题型方法谱系、验证方式、图表证据和多评委并行审查规则。
- 新增 `tools/innovation_checker.py`、`tools/judge_panel_checker.py` 和 `tools/compliance_checker.py`，并在 `pipeline_check.py --quality-mode excellence` 中纳入创新筛选、多评委审查、合规记录和 `writer_prompt.md` 检查。
- `tools/solution_test_generator.py` 生成的契约测试增加约束不变量、oracle、baseline 和随机种子稳定性检查。
- `tools/robustness_checker.py` 在严格/卓越模式下检查约束残差、最优性 gap、多初值、随机种子数量、置信区间和扰动稳定性阈值，不再只信任 `passed=true`。
- 规划为 `1.2.0`：新增奖项级交付质量闭环，包括 `model_spec.json`、`data_schema.json`、`symbol_table.json`、`solver_strategy.json`、`solution_tests.py`、`figure_style.json`、`figure_storyboard.md`、`writer_prompt.md`、`decision_insights.md`、`defense_questions.md` 和 `reproducibility_manifest.json`。
- 新增 `tools/schema_checker.py`、`tools/model_spec_checker.py`、`tools/unit_checker.py`、`tools/robustness_checker.py`、`tools/figure_auditor.py`、`tools/manifest_checker.py` 和 `tools/solution_test_generator.py`。
- `tools/pipeline_check.py` 新增 `--quality-mode standard|strict|hard|complete|full|excellence`，默认 standard 兼容增量工作区，excellence 要求完整模型、数据、代码、图表、写作交接和复现证据链。
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
