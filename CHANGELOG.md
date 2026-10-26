# Changelog

## Unreleased

- 新增 Phase 0.5「设计板循环」闸门：`design_board.json`（每题多候选 + 推荐理由 + 真实试算）、`design_rounds/round_NNN.json`（每轮回执）、`mini_trials.json`（试算证据）与 `design_board.md`（Mermaid 导图 + 对比表 + 4 位确认码）。用户可改选择、写批注、调权重；连续两轮无修改后才可确认。
- 新增 `tools/design_board.py`（render / ingest / status / confirm，主流程零第三方依赖）与 `tools/design_board_checker.py`。`confirm --apply` 必须由用户本人输入 4 位确认码，AI 不得代跑；`confirm_attested=false` 时 checker 标 warning。
- 新增三种决策板视图：`render --format md|html|xlsx|all`。HTML 为单文件离线（内联 SVG 思维导图、零外链、深浅色自适应、可打印）；Excel 为 7 工作表（总览 / 待决策 / 权重 / 打分 / 来源 / 批注 / 说明，含下拉、单元格保护、条件格式、加权公式）。缺少对应模块或 `openpyxl` 时只跳过该格式并在 `skipped` 说明，不中断其余格式。
- 新增从 Excel 回读：`ingest --from design_choices.xlsx` 按表头定位「题号 / 当前选择 / 批注」列转成回执，与 JSON 回执走同一套校验与落盘逻辑。
- 新增 `design_board.py serve` 本地回传服务器：用户在 HTML 页面上直接选完点提交即写 `design_rounds/`。只监听 `127.0.0.1`，页面注入一次性 token 并在服务端校验 `X-MM-Token`（挡住跨源表单伪造回执）；回执走与 `ingest` 相同的 `apply_submission()` 校验路径；无服务器（file://）时自动降级为下载 `design_board_submission.json`；选择即时存 `localStorage`；`--once` 收到第一份回执即退出。
- 新增 `tools/mini_trial.py`：跑真实试算并落 `mini_trials.json`（测耗时、解析 stdout JSON、追加写盘、超时用 `Popen` + `taskkill /T` / `killpg` 回收整棵进程树）。
- 新增 `tools/migrate_workspace.py` 与 `design_board_checker --allow-legacy`：给设计闸门上线前的旧工作区补最小可用 `design_board.json` 骨架（默认 dry-run，从不覆盖、从不伪造确认），或把"缺板"降级为 warning 以渡过过渡期。
- 新增 `hooks/`：宿主侧 `PreToolUse` 守卫（Claude Code JSON deny / Cursor exit 2），未确认时拦写 `solution.*`；`MM_GATE_BYPASS=1` 可旁路并留 warning。附 `selftest.py`（6 场景）与两种宿主的配置片段。
- 新增 `tools/tools_sync_checker.py`：比对主仓库与按小问分支仓库的工具哈希，`--mode strict` 下未声明漂移即 exit 1；当前 `differs_unexpected` 为 0。
- 加固人工确认判据（由对抗演练实测驱动）：`confirm_code` 必须由 `board_sha256` 派生（手写值判 `confirm_code_mismatch`）；`confirmed_by="ci"` 与 `user_non_interactive` 在 standard 仅留痕、**excellence 判 error**；交互式 `confirm` **要求真实终端**，`echo <码> | confirm --apply` 不再能冒充人工确认（非 TTY 直接拒绝，提示改用 `--skip-interactive` 并留痕）。
- 新增 `docs/DESIGN_GATE_PLAN.md` §20.7 对抗性演练记录：12 个"抄近路"场景的实测结果、3 处加固的前后对比，以及**残余缺口的诚实说明**（完整手写全部确认字段在 skill 内不可证伪，真正强制需装 L5 宿主 hook）。
- 新增两道反伪造校验：**时间线校验**（代码/结果 mtime 早于 `confirmed_at` 判 `code_written_before_confirm`）与**交叉校验**（板与 `model_selection_audit.json` 的候选必须能对账，判 `board_audit_*`）。
- 修正 `judge_panel_checker.py`：新增最低分阈值（60）与 `chair_summary.decision` 枚举校验，此前 `score: 0` 也能通过。
- 修正 `code_runner.py`：给子进程显式注入 `PYTHONIOENCODING=utf-8`/`PYTHONUTF8=1` 并按 `encoding="utf-8", errors="replace"` 解码，此前环境里设了 `PYTHONIOENCODING=utf-8` 时中文输出会触发 `UnicodeDecodeError`，让 `code_runner` 误判失败、excellence 无故变红。
- 修正 `pipeline_check.py`：`final_solution.json` / `model_decision.md` 从软推荐升为硬门（`missing_decision_artifact`，standard 只 warning），此前删掉它们 excellence 仍能全绿。
- 扩充 `references/award_playbook.md` 与 `source_registry_checker.py`：40 张方法卡从 7 个必填标签扩到 11 个（追加「推荐理由 / 计算复杂度 / 实现依赖 / 对标 baseline」），两处锁定同步。
- 修正 `references/templates.md` 的 `validation_summary.json` 示例：全部 `passed: true` 改为 `status: "NOT_VALIDATED"` + `passed: null`，照抄模板不再能通过 `evidence_checker` / `robustness_checker`。
- 修正 `examples/solved-python` 的两处数值矛盾：`optimization_certificate.json` 的 `bounds` 由 2050 改为真实最优值 2175，审计的 `oracle_value` 同步；`model_selection_audit.json` 的候选名与决策板对齐。

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
