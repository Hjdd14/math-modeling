# 工具命令与判定

## doctor.py

```bash
python "tools/doctor.py" --workspace "."
```

用于新用户或其他 Agent 接手前做本地体检：检查必备文件、运行依赖、可选外部工具、Git 仓库状态和公开 quickstart 示例。`summary.failed > 0` 时先修复依赖或仓库结构。

## input_parser.py

```bash
python "tools/input_parser.py" extract --file "problem.pdf"
python "tools/input_parser.py" brief --problem "problem.pdf" --data "data.xlsx" --out "problem_brief.md"
```

## state_manager.py

```bash
python "tools/state_manager.py" init --workspace "." --language python
python "tools/state_manager.py" inspect --workspace "." --language python
python "tools/state_manager.py" phase --workspace "." --phase phase1 --status completed
python "tools/state_manager.py" artifact --workspace "." --name final_solution --path final_solution.json
python "tools/state_manager.py" tool-run --workspace "." --name pipeline_check --status passed --score 100 --summary "all checks passed"
python "tools/state_manager.py" agent-run --workspace "." --phase phase1 --agent optimizer --role initial_modeling_agent --status completed --summary "generated initial solution" --output-path agent_outputs/phase1/initial_solutions.json
```

`modeling_state.json` 记录 `phase`、`artifact`、`tool_runs`、`agent_runs` 和 `issues`。

状态写入使用文件锁和原子替换；并行 Agent 或工具同时记录时，不应覆盖彼此的历史。相对 `artifact` 路径按 `--workspace` 解析，但状态文件中保留相对路径，便于迁移。

## code_runner.py

```bash
python "tools/code_runner.py" run --file "solution.py" --lang python --timeout 300
```

关键字段：

- `success == true` 才能进入后续检查。
- `generated_files` 只表示本次新增文件。
- `changed_files` 表示本次新增或覆盖更新的文件。

## figure_checker.py

```bash
python "tools/figure_checker.py" batch --dir "results" --pattern "*.png"
```

失败判定：

- `total == 0` 视为失败。
- `passed_all == false` 视为失败。
- 空白图、过低 DPI、尺寸过小都必须修复。

## latex_validator.py

```bash
python "tools/latex_validator.py" validate --file "model_decision.md"
```

`invalid > 0` 必须修复。

## consistency_checker.py

```bash
python "tools/consistency_checker.py" formula --doc "model_decision.md" --code "solution.py" --lang python
```

`mismatches` 中的符号或数字常量差异要人工审查；该工具是启发式检查，不等价于数学证明。

关键字段：

- `passed`：机器可读判定，供 `pipeline_check.py` 使用；当文档公式与代码数学表达式存在共同核心符号时，推导用常量差异会保留为 `mismatches` 供人工审查，但不直接判定失败。
- `consistency_score`：基于文档公式符号与代码数学表达式符号的启发式分数。
- `mismatches`：包括文档独有符号、代码独有符号和数字常量差异。

## evidence_checker.py

```bash
python "tools/evidence_checker.py" --workspace "." --mode standard
python "tools/evidence_checker.py" --workspace "." --mode strict
```

检查 `results/validation_summary.json` 的证据结构和显式通过状态。该工具只检查证据是否存在、结构是否合格、关键状态是否通过，不替代建模推理，也不证明数学结论正确。

关键字段：

- `exists`：是否找到 `results/validation_summary.json`。
- `passed`：机器可读总判定。
- `warning`：标准模式下缺少新证据或新字段时为 true。
- `checks`：逐项检查 baseline、oracle、solver 交叉验证、敏感性、不变量和失败模式。
- `evidence_items`：轻量证据名称摘要，便于 reviewer 和 CI 定位。
- `issues`：warning/error 列表。

失败判定：

- `--mode standard`：旧工作区缺少 `validation_summary.json` 或新增证据项时给 warning，不直接失败。
- `--mode strict`：难题或完整交付模式；缺少 baseline、oracle、solver 交叉验证、敏感性、不变量或失败模式即失败。
- 如果证据文件存在但 JSON 无效，或任一证据项显式 `passed=false` / `status=failed`，所有模式都失败。

## schema_checker.py

```bash
python "tools/schema_checker.py" --workspace "." --mode standard
python "tools/schema_checker.py" --workspace "." --mode excellence
```

检查 `data_schema.json` 与附件数据是否一致：字段存在、类型、单位、缺失率、主键重复和数值范围。`standard` 模式缺少 `data_schema.json` 仅 warning；`strict`/`excellence` 缺少或字段错误失败。

关键字段：`passed`、`warning`、`datasets_checked`、`checks`、`issues`。

## brief_completeness_checker.py

```bash
python "tools/brief_completeness_checker.py" --workspace "." --mode excellence
```

检查 `problem_brief.md` 是否仍残留占位符，并确认目标、约束和输出要求已提取。该工具只检查题意审计是否完整，不替代人工理解原题。

## model_selection_checker.py

```bash
python "tools/model_selection_checker.py" --workspace "." --mode excellence
```

检查 `model_selection_audit.json` 是否列出至少两个候选模型、评分、拒绝理由和最终选择证据。用于防止“只写最终模型、不解释为什么”的断层。

## optimization_certificate_checker.py

```bash
python "tools/optimization_certificate_checker.py" --workspace "." --mode excellence
```

检查 `optimization_certificate.json` 中的可行性残差、上下界、最优性 gap 和 oracle/替代求解器证据。该工具验证证据结构和阈值，不等价于完整数学证明。

## uncertainty_budget_checker.py

```bash
python "tools/uncertainty_budget_checker.py" --workspace "." --mode excellence
```

检查 `uncertainty_budget.json` 是否覆盖数据、参数、模型和随机误差来源，并记录 mitigation、sensitivity 或 evidence。

## validation_profile_checker.py

```bash
python "tools/validation_profile_checker.py" --workspace "." --mode excellence
```

检查 `validation_profile.json` 中题型专属验证证据。优化题要求 baseline、oracle、gap、residuals、sensitivity；预测题要求 holdout/CV、核心指标、残差和区间覆盖；图网络、随机仿真、物理机理和政策决策题也有对应字段。

## data_leakage_checker.py

```bash
python "tools/data_leakage_checker.py" --workspace "." --mode excellence
```

检查 `data_validation.json` 是否存在目标字段进入特征、时间序列随机切分、预处理在全量数据拟合等泄漏风险。

## statistical_validation_checker.py

```bash
python "tools/statistical_validation_checker.py" --workspace "." --mode excellence
```

检查 `statistical_validation.json` 是否记录 holdout/CV、常用指标、残差、区间、稳健性和过拟合风险。预测、统计调查和机器学习混合模型应优先补齐该文件。

## model_spec_checker.py

```bash
python "tools/model_spec_checker.py" --workspace "." --mode excellence
```

检查 `model_spec.json` 是否包含变量、目标函数、约束、参数、数据字段和验证计划，并尽量核对变量是否进入写作交接材料和代码。它不证明公式语义正确，但能减少“方案一个模型，代码另一个模型”的断层。

## unit_checker.py

```bash
python "tools/unit_checker.py" --workspace "." --mode excellence
```

检查 `symbol_table.json` 中符号、含义、单位和代码变量映射是否完整，并与 `model_spec.json` 做轻量覆盖核查。

## solution_test_generator.py

```bash
python "tools/solution_test_generator.py" --workspace "." --language python
python "tools/solution_test_generator.py" --workspace "." --language matlab
```

生成 `solution_tests.py` 或 `solution_tests.m` 契约测试骨架。该工具只生成测试文件，不替代代码 Agent 推理；正式代码仍由代码 Agent 根据 `model_spec.json` 和 `solver_strategy.json` 编写。

## robustness_checker.py

```bash
python "tools/robustness_checker.py" --workspace "." --mode excellence
```

检查 `results/validation_summary.json` 中的数值鲁棒性证据：约束残差、最优性 gap、多初值不少于 3 次、随机种子不少于 3 个、bootstrap/置信区间置信水平至少 0.95 和参数扰动排名稳定性。`standard` 模式缺新字段 warning；`excellence` 模式缺字段失败；任一字段显式 `passed=false` 所有模式失败。

两条与"声明式通过"直接相关的判定：

- **占位证据一律失败**：条目仍带 `status: "NOT_VALIDATED"`/`TODO`/`REPLACE_ME` 或 `passed: null` 时，所有模式都报 `placeholder_evidence` 错误。模板默认值不是证据，照抄模板不做替换会在此处被拦下。
- **按题型可声明不适用**：确定性模型可对 `multi_start`、`random_seed_stability`、`bootstrap_confidence_interval`、`perturbation_stability` 写
  `{"status": "not_applicable", "rationale": "...", "alternative_validation": "..."}`；缺 `rationale` 或 `alternative_validation` 报 `not_applicable_without_justification`。`constraint_residuals` 与 `optimality_gap` 对任何模型都可核验，声明不适用会报 `not_applicable_not_allowed`。

## figure_auditor.py

```bash
python "tools/figure_auditor.py" --workspace "." --mode excellence
```

在 `figure_checker.py` 基础上审计论文级图表质量，读取 `figure_style.json` 与 `figure_storyboard.md`，检查图表是否存在、非空、清晰、比例合理、是否有结构化叙事板引用，并输出 `results/figure_quality_report.json`。`figure_storyboard.md` 中每张图必须包含 `file`、`claim`、`source_data`、`x_unit`、`y_unit` 和 `supports_question`。机器无法可靠识别所有标题和坐标轴语义，因此语义性图表判断仍由可视化设计 Agent、写作交接 Agent 和评委组共同完成。

## source_registry_checker.py

```bash
python "tools/source_registry_checker.py" --skill-root "." --mode excellence
```

检查 `references/competition_sources.json` 与 `references/award_playbook.md`。`excellence` 模式要求至少 7 个 `tier_a` 来源、7 个 `tier_b` 来源，所有来源都有 `name`、`tier`、`organizer`、`official_url`、`years_covered`、`case_material_type` 和 `trust_notes`。同时检查 `award_playbook.md` 至少覆盖 10 类题型和 40 张方法卡；任何方法卡缺少来源链接都会失败。

关键字段：

- `tier_counts`：各层来源数量。
- `problem_types_checked`：命中的题型维度数量。
- `method_cards_checked`：方法卡数量。
- `issues`：`missing_source_field`、`unsourced_method_card` 等失败原因。

## source_freshness_checker.py

```bash
python "tools/source_freshness_checker.py" --workspace "." --mode excellence
python "tools/source_freshness_checker.py" --workspace "." --mode excellence --online
```

离线模式检查 `source_registry.json` 或 `references/competition_sources.json` 的来源结构、URL 字段和年份覆盖；`--online` 会先访问 official URL，失败时继续尝试 `secondary_urls`。若 official URL 因证书或网络异常失败但备用 URL 可达，严格模式记录 warning 而不把整个来源判死；若全部不可达则失败。CI 默认使用离线模式，避免因临时网络或证书问题误伤。

## source_material_reader.py

```bash
python "tools/source_material_reader.py" --skill-root "." --mode excellence --sample-documents 2
```

联网抽检 `references/competition_sources.json` 中每个竞赛来源是否能读到优秀论文、赛题、获奖、评审或 Outstanding Papers 等材料内容。工具会读取 official/secondary/material probe URL，识别 HTML 材料关键词、PDF/DOC/DOCX/ZIP/RAR 链接，并对 PDF/DOCX 或归档包做少量抽样读取。该工具会用未验证 TLS 读取材料并在输出中标记 `tls_verified: false`，适合发布前/人工复核前显式运行，不作为普通 CI 默认硬 gate。若某比赛没有稳定公开优秀论文 PDF，结果会以 HTML 材料页、归档包或材料信号记录，而不是把第三方搬运当作权威全文。

## case_retrieval_checker.py

```bash
python "tools/case_retrieval_checker.py" --workspace "." --mode excellence
```

检查 `case_retrieval.json` 是否记录相似题型、可借鉴方法、不能照搬风险和推荐验证。电力、电路、电磁场题的首个匹配必须优先电工杯或电力相关案例；统计调查和社会经济数据题必须优先统计建模大赛或数据洞察类案例；行业大数据题必须优先 MathorCup 大数据或可核验行业数据案例。

关键字段：

- `top_match`：按 rank 排序后的首个匹配案例。
- `cases_checked`：检查的匹配案例数。
- `issues`：`domain_source_mismatch`、`missing_case_field` 等失败原因。

## award_readiness_checker.py

```bash
python "tools/award_readiness_checker.py" --workspace "." --mode excellence
```

检查奖项级“上限产物”是否完整可复核：`ambiguity_register.json`、`assumption_ledger.md`、`scoring_strategy.md`、`ablation_study.json`、`decision_insights.md` 和 `defense_questions.md`。`excellence` 模式下缺任一文件会失败；high severity 题意歧义不得保持 pending/unresolved；消融实验必须说明变更组件、指标变化、解释和通过状态；决策建议必须包含关键结论、工程/业务/决策含义、风险提示和可执行策略；质询材料至少包含两个评委可能追问的问题及回答要点。

关键字段：

- `required_award_artifacts`：六类上限产物是否齐全。
- `unresolved_high_ambiguity`：高风险歧义未解决时失败。
- `missing_ablation_field`：消融证据缺字段时失败。
- `incomplete_decision_insights` / `incomplete_defense_questions`：决策解释或答辩准备不足时失败。

## innovation_checker.py

```bash
python "tools/innovation_checker.py" --workspace "." --mode excellence
```

检查 `innovation_register.json`。每个创新点必须包含题目痛点、baseline 增益或消融证据、实现成本、可解释性、验证证据和失败风险。`standard` 模式缺文件给 warning；`strict`/`excellence` 缺文件、空泛创新或缺证据失败。

关键字段：

- `innovations_checked`：检查的创新点数量。
- `checks`：必要字段与证据检查。
- `issues`：`missing_innovation_evidence`、`vague_innovation_claim` 等失败原因。

## judge_panel_checker.py

```bash
python "tools/judge_panel_checker.py" --workspace "." --mode excellence
```

检查 `judge_panel_review.json`。评委组至少包含国赛建模评委、美赛评委、代码复现评委、图表证据评委和工程/业务解释评委。每个评委独立给分和列问题，chair judge 必须给出总评和修复清单。任一 high severity 问题未 resolved/fixed/closed 即失败。

## compliance_checker.py

```bash
python "tools/compliance_checker.py" --workspace "." --mode excellence
```

检查 `compliance_record.json` 中的 AI 使用记录、匿名性检查、外部资料引用、复现信息和最终提交约束清单。`final_submission` 应覆盖匿名、AI 披露、引用、页数/格式、附件、代码提交提示和官方规则复核。该工具不替代正式提交系统的合规表单，只负责给后续写作/提交步骤提供可审计提示。

## writer_prompt_checker.py

```bash
python "tools/writer_prompt_checker.py" --workspace "." --mode excellence
```

检查 `writer_prompt.md` 是否是写作交接提示词，而不是正式论文正文。`excellence` 模式要求它引用 `problem_brief.md`、`final_solution.json`、`results/validation_summary.json`、图表材料、`judge_panel_review.json`、`compliance_record.json` 和 `reproducibility_manifest.json`，交接每张图支撑的结论，并包含“后续写作/提交复核清单”。它必须明确说明本 skill 不生成正式写作正文，只交接建模、代码、结果、图表、验证证据、风险提示和合规提示。

## mini_benchmark_runner.py

```bash
python "tools/mini_benchmark_runner.py" --benchmark "evals/mini_contest_benchmark.json" --mode strict
```

实跑 mini contest benchmark 的 6 个小型 oracle 案例，生成临时工作区、运行生成的参考 `solution.py`，并检查期望输出、oracle 值、不变量、图表和 `writer_prompt.md`。它用于验证工具链能跑通小型可核验案例，不替代真实竞赛题求解。

## manifest_checker.py

```bash
python "tools/manifest_checker.py" --workspace "." --mode excellence
```

检查 `reproducibility_manifest.json`：OS、Python/MATLAB 版本、求解器、依赖、随机库、运行耗时、随机种子、输入 hash 和输出 hash。hash 不匹配或文件缺失失败。

## brief_validator.py

```bash
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage model --target "model_decision.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage document --target "writer_prompt.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage code --target "solution.py"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage output --target "results"
```

`document` 是 `model` 的兼容别名，不是空检查阶段。

## pipeline_check.py

```bash
python "tools/pipeline_check.py" --workspace "." --language python
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict --quality-mode excellence
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict --quality-mode excellence --online-source-materials
```

总控验证会串联代码运行、图表、brief 核查、evidence check、来源总索引、离线来源新鲜度、案例检索、奖项级上限产物、模型选择、优化证书、不确定性预算、题型验证 profile、数据泄漏、统计验证、质量闭环产物、writer prompt、创新筛选、评委组审查和合规检查，并对 `model_decision.md` 中的 LaTeX 公式做提示性检查（`latex_advisory`，只产出 warning，永不翻转 `passed`；需要判失败请单独运行 `tools/latex_validator.py`）。加 `--online-source-materials` 时额外运行资料内容读取联网深扫。新正式流程不把正式写作正文作为必需产物。`passed == false` 时必须修正后重跑。

默认 `--evidence-mode standard` 与 `--quality-mode standard` 只做兼容旧工作区的结构自检：缺失的质量闭环产物只报 warning，`passed: true` 仅表示没有硬性错误，**不代表产物齐全**。产物齐备情况读返回值中的 `artifact_completeness`（`recommended_missing` 列出缺哪些固定产物、`required_missing` 列出硬性缺失）与 `status`（`pass` / `pass_with_warnings` / `fail`）；`warned_checks` 列出所有产生 warning 的检查项。难题、完整交付或正式竞赛结果使用 `--evidence-mode strict`；奖项级最终交付使用 `--quality-mode excellence`。

## workflow_runner.py

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
python "tools/workflow_runner.py" resume --workspace "." --language python
python "tools/workflow_runner.py" verify --workspace "." --language python
```

该工具只做确定性文件状态编排，不替代并行 Agent 推理。`resume` 会扫描工作区产物并合并已有 `phases`、`tool_runs`、`agent_runs` 和 `issues`，不能抹掉并行 Agent 历史。
