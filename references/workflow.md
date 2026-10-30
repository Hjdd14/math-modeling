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

## Phase 0.5: 设计板循环（用户确认闸门）

Phase 0 完成后进入本阶段。目标是让用户在写任何代码之前看到完整的建模决策、候选算法对比与真实试算数值，并由用户本人确认放行。Phase 0.5 是硬性闸门：`design_board.json` 未 `confirmed: true` 之前，不允许进入 Phase 1，也不允许创建或修改 `solution.py` / `solution.m`。

### 0.5.1 三条硬性规则

1. **AI 只写提议**：`design_board.json` 的 `questions` / `options` / `pending_decisions` 由 AI 生成，这是"提议"。
2. **用户通道写回执**：`design_rounds/round_NNN.json` 只能由用户提交后经 `ingest` 回写产生；AI 不得代写回执，也不得手写 `no_change_rounds`。
3. **只有 `confirm` 能写确认**：`confirmed` / `confirmed_at` / `confirmed_by` / `confirm_code` / `confirm_attested` 只能由 `design_board.py confirm --apply` 写入，且必须由**用户本人**执行并输入确认码。

`board_sha256` 由 `render` 计算并回写，同样不允许手写——它是"用户实际看到的这一版内容"的锚点。`.md` / `.html` / `.xlsx` 都只是视图，唯一真实来源是 `design_board.json`。

### 0.5.2 design_board.json

```json
{
  "schema_version": 1, "board_id": "b-YYYY-MM-DD-xxxx", "board_sha256": "...",
  "language": "python", "created_at": "ISO8601", "revision": 1,
  "problem_summary": {"title": "...", "questions": ["..."], "key_ambiguities": [{"id": "A1", "severity": "medium", "issue": "...", "resolution": "pending"}]},
  "mindmap": {"format": "mermaid", "source": "graph LR ..."},
  "questions": [{"id": "Q1", "goal": "...", "options": [{"id": "O1", "name": "...", "tier": "recommended", "rationale": "...", "source_ref": {"type": "method_card", "ref": "OPT-01", "tier": "tier_a", "verified": true}, "complexity": "...", "dependencies": [], "risk": "...", "mini_trial": {"sample": "...", "output": {...}, "seconds": 0.0, "feasible": true}}], "user_choice": "O1", "user_locked": true, "user_comment": "", "confirmed": false}],
  "pending_decisions": [], "no_change_rounds": 0,
  "confirmed_at": null, "confirmed_by": null, "receipt_origin": null,
  "confirm_code": null, "confirm_attested": false
}
```

字段要求（`design_board_checker.py --gate a` 逐条校验，不要自创字段）：

- `schema_version: 2`；每题必须有 `paradigm_set`（3–5 项）与 `paradigm_selection`（≥2 项，含 ≥1 个异质族）。
- 每个范式：`paradigm_id`、`name`、`family`、`source_ref`（含 `tier` 与 `verified`）、`why_explore`、`explore_cost.level ∈ {low,medium,high}` + `note`；`source_ref.verified=false` 必须补 `unverified_reason`。
- `options` **允许为空数组**（A 板不再承载模型候选）；`user_choice` 允许 `null`；`user_locked` **必须为 false**（否则 `gate_a_user_locked_forbidden`）。
- `options` 非空时按旧规则校验（`rationale`/`source_ref`/`risk`；`mini_trial` 已改为可选）。
- `confirmed: true` 时 `confirmed_at` / `confirmed_by` / `receipt_origin` / `confirm_code` / `confirm_attested` 必须齐全。

> B 板的字段见 §1.5.2。两块板共用同一套 `render/serve/ingest/status/confirm`，只是文件名与回执目录不同（`--gate a|b`）。

### 0.5.3 design_rounds/round_NNN.json

每轮回执，`ingest` 自动生成，轮次号递增：

```json
{"round": 2, "at": "ISO8601", "board_sha256": "...", "user_edited": false,
 "changes": [{"path": "questions[0].user_choice", "from": "O2", "to": "O1"}],
 "receipt_origin": "browser-submit", "nonce": "..."}
```

`user_edited` 与 `changes` 是判断"用户到底改没改"的客观依据，`ingest` 据此自动维护 `no_change_rounds`（未修改则 +1，修改则清零）。

### 0.5.4 mini_trials.json（A 板可选；B 闸门改用 perspective_trials.json）

A 闸门阶段还没有"最终候选"，因此 `mini_trial` 由必填降为**可选**：有真实试算更好，没有不阻断。B 闸门的证据改用 §1.5.4 的 `perspective_trials.json`（只能由 `tools/perspective_trial_runner.py` 写入）。若仍要记录 A 阶段的小样本试算：

```json
{"trials": [{"question_id": "Q1", "option_id": "O1", "sample_rows": 20, "input_hash": "sha256:...",
             "output": {"objective": 1240.5, "feasible": true}, "seconds": 0.8,
             "solver": "HiGHS via scipy.optimize.milp",
             "reproduce_cmd": "python solution.py --method enum"}]}
```

数值必须是真实跑出来的，`reproduce_cmd` 必须可复跑。

### 0.5.5 收敛判据（5 条，全部满足才允许确认）

1. 存在 `design_rounds/round_NNN.json`，且最后一轮 `user_edited == false`。
2. `no_change_rounds >= 2`（连续两轮用户未修改）。
3. `board_sha256` 与当前 `design_board.json` 内容一致。
4. A 板：每题 `paradigm_selection` 非空（≥2 项，含异质族）、`user_locked` 为 false、`pending_decisions == []`；B 板：每题 `user_choice` 非空且 `pending_decisions == []`。
5. `confirm --apply` 时输入的 4 位确认码与 `render` 写入视图的确认码一致。

### 0.5.6 design_board.py 子命令

```bash
python "tools/design_board.py" render --workspace "." --format all
python "tools/design_board.py" ingest --workspace "." --from "user_submission.json"
python "tools/design_board.py" ingest --workspace "." --from "design_choices.xlsx"
python "tools/design_board.py" serve --workspace "."
python "tools/design_board.py" status --workspace "."
python "tools/design_board.py" confirm --workspace "."
python "tools/design_board.py" confirm --workspace "." --apply
```

- `render`：读 JSON 生成视图（`--format md|html|xlsx|all`），同时计算 `board_sha256` 与 4 位确认码并写回 JSON 与三份视图。`html` 为单文件零外链（内联 SVG 导图），`xlsx` 为七工作表（下拉 + 保护 + 条件格式）。缺模块或缺 `openpyxl` 时只跳过该格式，不打断其它格式。
- `ingest`：读用户提交的 JSON **或 `design_choices.xlsx`**，校验后写 `design_rounds/round_NNN.json`，自动维护 `no_change_rounds`；非法选择或哈希不符即 exit 1。
- `serve`：起本地回传服务器，用户在页面上直接选完提交即写回执。只绑 `127.0.0.1`，页面注入一次性 token 并在服务端校验 `X-MM-Token`（挡跨源表单伪造）；回执走与 `ingest` 同一套 `apply_submission()` 校验。页面在无服务器（file://）时自动降级为下载 `design_board_submission.json`。`--once` 收到第一份回执即退出。
- `status`：输出当前轮次、收敛进度、待决项与 `ready_to_confirm`。
- `confirm`：默认 dry-run，只打印收敛判据是否满足，**不写任何字段**；加 `--apply` 才写确认，并要求交互式输入确认码。
- `--skip-interactive` 是逃生口：写入 `confirmed_by: "user_non_interactive"`，checker 标 `confirm_not_attested`（warning，留痕不阻断）。
- CI 场景可设环境变量 `MM_CONFIRM_CODE`；此时 `confirmed_by: "ci"`，checker 标 `confirm_ci`（info）。

### 0.5.7 确认码机制

`render` 从 `board_sha256` 派生 4 位确认码（取前 4 位大写，如 `A7F2`），并写进 `design_board.md`、`design_board.html`、`design_choices.xlsx` 与 dry-run 输出。用户本人在视图上看到这 4 位后运行 `confirm --apply` 输入；AI 若未转述则无法猜中。**AI 不得代用户执行 `confirm --apply`，也不得代填确认码。**

### 0.5.8 写权限归属

| 字段 / 产物 | 允许的写入者 | AI 能否代写 | 理由 |
|---|---|---|---|
| `design_board.json` 的 `questions` / `options` / `pending_decisions` | AI | ✅ 应该 | 这是"提议"，AI 的职责就是提方案 |
| `board_sha256` | `design_board.py render` | ❌ 不应 | 内容快照的锚，手写等于自证 |
| `design_rounds/*.json` | 用户通道（`ingest` / serve `/submit` / Excel） | ❌ 不应 | 这是"人的输入"，AI 代写等于自问自答 |
| `no_change_rounds` | `ingest` 自动维护 | ❌ 不应 | 收敛计数器，手写 `2` 可骗过判据 |
| `confirmed` / `confirmed_at` / `confirmed_by` / `confirm_code` / `confirm_attested` | **`confirm --apply`，且需用户本人触发** | ❌ 绝对不应 | 这是闸门本身 |

一句话原则：`model_decision.md` 是 AI 的内部共识，`design_rounds/` 是人的外部回执；两者混用，闸门立刻失效。

### 0.5.9 时间线校验（防"先写代码、后补板"）

**双时间线**（两板各自一条）：

- `--gate a`：`solution.*` / `solution_tests.*` / `results/` 的 mtime 不得早于 **A 板** `confirmed_at`，否则 `code_written_before_gate_a`（旧板 schema<2 仍报 `code_written_before_confirm`，保持兼容）。
- `--gate b`：交付代码的 mtime 不得早于 **B 板** `confirmed_at`，否则 `code_written_before_gate_b`。
- **缺板 + 已有交付代码 = error**：板不在场时不得把这条降级为 `skipped`（旧实现会，这是最大的降级陷阱）。
- `perspective_trials/**` 属试算代码，**永不计入**交付代码时间线（它是 B 闸门之前允许存在的证据）。

容差 5 秒。原来的单闸门描述保留如下（历史口径）：若确认后确实需要一次小修，可在 `design_rounds/` 追加一条 `post_confirm_edit` 记录（说明改了什么、为何不属于方案变更），checker 见到即放行并标 warning。局限：mtime 可被 `os.utime` 伪造，这不是绝对防线，但与 `board_sha256` 绑定叠加后伪造成本显著上升。夹具目录（`tests/test_data`、`examples/solved-python`、`examples/design-board-sample`）自动豁免，或加 `--skip-timeline` 跳过。

### 0.5.10 交叉校验（板与模型选择审计对账）

对账按闸门拆开（`schema_version >= 2` 之后）：

- **A 组**：只报 `paradigm_audit_pending`（warning）并跳过候选对账——A 板确认时 `model_selection_audit.json` 还没产出，拿它来对账必然是假阴性。旧板（schema<2）仍走原三条规则，行爲不变。
- **B 组**：把 `design_board_gate_b.json` 与 `model_selection_audit.json` 对账：
  1. `user_choice` 对应 option 的 `name` 必须能匹配审计的 `final_selection.name`，否则 `board_audit_selection_mismatch`；
  2. B 板候选名与审计 `candidates[].name` 至少一对能匹配，否则 `board_audit_candidate_mismatch`；
  3. 已确认但缺审计：`excellence` 报 `board_audit_missing`（error），`standard` 报 warning；
  4. 审计 `selected_by != "user"` 或 `user_choice_id` 与板不一致 → `board_audit_selection_mismatch`（裁决 Agent 必须采用用户选择）。

匹配采用归一化后的**双向包含**比对（去括号内容、小写、去空格与连字符），避免"整数线性规划 (ILP)"与"整数规划"被误判不一致；无法匹配时不猜，直接报失败码并列出双方名称。旧工作区迁移期可加 `--no-cross-audit` 跳过这三条规则（输出标 `cross_audit: skipped`）。

### 0.5.11 旧工作区迁移（`--allow-legacy` 与迁移脚本）

设计闸门上线前就存在的项目没有 `design_board.json`，直接升级会让 excellence 变红。两条过渡路径：

1. `python "tools/migrate_workspace.py" --workspace "."`（dry-run）→ 看将生成的骨架 → `--apply` 落地。生成的板从 `problem_brief.md` / `model_selection_audit.json` 推断题目与候选，所有 `source_ref.verified = false` 并带 `unverified_reason`，**不会**伪造确认状态，用户必须自己重新走 render → confirm。
2. `python "tools/design_board_checker.py" --workspace "." --allow-legacy`：把"缺板"从 error 降为 warning（`legacy_workspace_without_board`），用于过渡期不阻塞其它检查；其它失败码严格度不变。

### 0.5.12 宿主 hook（L5 防线，可选）

前三层（产物结构 / 哈希与确认码 / 时间线）都在 skill 内部，第 4–5 层需要宿主配合：

- `hooks/pre_tool_use_guard.py`：在宿主调用写文件工具时拦截。判定顺序：
  1. 目标在 `perspective_trials/` 下 → 放行（试算代码不是交付代码）；
  2. 目标是交付代码且路径含 `questions/<qid>/` → 必须有该问已确认的 `design_board_gate_b.json`；
  3. 其余交付代码（工作区根）→ A 板必须确认；若 A 板 `schema_version >= 2`，还要求同级 `design_board_gate_b.json` 已确认；
  4. legacy（A 板 schema<2 且无 B 板）→ 放行 + warning。
  支持 Claude Code（JSON `deny`）与 Cursor（exit 2）两种协议；`MM_GATE_BYPASS=1` 可旁路并留 warning。
- 安装方式见 `hooks/README.md`。**它拦不住**用 shell 重定向写文件、用户自己手写、或宿主不支持 hook——所以它是"提高伪造成本 + 留痕"，不是"证明人确认过"。

## Phase 1: 并行建模共识

Phase 1 的输入除 `problem_brief.md` 与题意审计产物外，还必须包含 Phase 0.5 产出的 `design_board.json`：五个建模 Agent 的 prompt 中只注入**探索边界**（每题 `paradigm_selection` 与各范式 `family`），**不得注入任何模型选择**——A 板不再承载选型，`user_locked` 恒为 false。若某视角认为该范式集合本身不成立，走 `reopen_gate_request.json`（`gate: "a"`）回到 Phase 0.5 重开，而不是就地换框架。

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

## Phase 1.5: 方案择定闸门（B 闸门）

Phase 1 的五视角并行、批评、修正完成后进入本阶段。**主仓库形态是一块 B 板覆盖全部小问、一次确认**（分支 `math-modeling-per-question` 是每问一块板、逐问确认，字段与命令完全同构）。本阶段只回答一个问题：**这一题用哪个模型**。

> 两件事不要混：B 闸门的"建议 Agent 打分"是选型建议（`is_judge_panel: false`）；多评委审查在 Phase 4，审的是代码与结果。

### 1.5.1 建议 Agent（1 建议 + 其余不建议）

**输入**：`agent_outputs/initial_*.json`、`revised_*.json`、`critique_*.json`、`baseline_solution.json`、`case_retrieval.json`、`problem_taxonomy.json`、`innovation_register.json`、**`perspective_trials.json`（唯一数值来源）**。

**输出**：`model_advice.json`（schema 2，格式见 `references/templates.md`）。

硬性规则（逐条对应 checker issue code）：

1. `advice_one_recommended`：恰好 1 个 `verdict: "recommended"`，其余全部 `not_recommended`，且 `recommended_option_id` 与之一致。
2. `advice_candidates_count`：候选 5–8 个（五视角至少 5 个；追加动态专家最多 8 个）；baseline 只作参照行，不占名额。
3. `advice_scores_complete`：全部候选都有 0–100 的 `score`，`dimension_scores` 的键集合与 `scoring_rubric.dimensions[].id` 一致。
4. `advice_pros_cons`：每个候选 `pros`/`cons` 各 ≥2 条。
5. `advice_why_not_when_better`：每个不推荐项 `why_not` ≥2 条 + `when_better` 非空（"什么条件下它反而更好"）。
6. `advice_data_comparison`：≥2 个 slice，每个 slice 覆盖**全部候选**；`comparable` 键跨候选一致。
7. `advice_trials_ref_valid` + `advice_number_mismatch`：每一行数据都能按 `(option_id, slice_id)` 回溯到 `perspective_trials.json` 的某次 run，且数值一致（容差 1e-9）。**数字不得手改。**
8. `advice_is_not_judge_panel` + `advice_no_judge_wording`：必须 `is_judge_panel: false` + `disclaimer`，且不得出现"评委通过/评审结论"类措辞。

建议 Agent **不得**替用户选择：`user_choice` 只能由 `ingest` 写入。

### 1.5.2 B 板（design_board_gate_b.json）

B 板复用 A 板 `questions[] / options[]` 形状，额外带 `advice` 与 `advice_sha256`：

```json
{
  "schema_version": 2, "gate": "b", "question_scope": "problem",
  "board_id": "gb-YYYY-MM-DD-xxxx", "board_sha256": "...",
  "advice_ref": "model_advice.json", "advice_sha256": "...",
  "questions": [{
    "id": "Q1", "goal": "...",
    "options": [{"id": "O1", "name": "...", "verdict": "recommended", "score": 86.5,
                 "origin": "perspective:statistician", "paradigm_id": "P1"}],
    "advice": {"candidates": [], "data_comparison": {}, "scoring_rubric": {}},
    "user_choice": "O1", "user_locked": true, "user_comment": "", "confirmed": false
  }],
  "pending_decisions": [], "no_change_rounds": 0
}
```

- `options` 5–8 个，与 `advice.candidates[].option_id` 一一对应；
- `advice_sha256` 必须等于 `model_advice.json` 的字节哈希（不一致 → `advice_board_mismatch`）；
- `user_choice` 必须是某个 option 的 `id`；未选 → `user_choice_present`（excellence error）；
- `preauthorized: true`（按建议自动执行）在 excellence 下判 `preauthorized_not_attested`（error），standard 仅留痕。

### 1.5.3 指标分层（可比层 / 专属层）

不同方法族没有共同指标，因此对比表分两层：

| 层 | 例子 | 要求 |
|---|---|---|
| `comparable` | `runtime_s`、`finished` | **跨全部候选必须同键同量纲**；这是唯一允许横向比较的层 |
| `own` | `p_value`、`objective`、`rmse` | 只要求同一候选跨 slice 同键，**不要求跨候选一致** |

baseline 只出现在可比层。

### 1.5.4 perspective_trials.json（只能由 runner 写）

每视角产出 `perspective_trials/<perspective>.py`，打印一个 JSON 对象作为 metrics；然后用工具真跑：

```bash
python "tools/perspective_trial_runner.py" open --workspace "." --slices slices.json
python "tools/perspective_trial_runner.py" run --workspace "." --perspective statistician --option-id O1 --slice full
python "tools/perspective_trial_runner.py" status --workspace "."
python "tools/perspective_trial_runner.py" verify --workspace "."
```

- `slices` ≥2；无数据集的小问用 `--axis parameter|scenario`（参数/场景切片），`data_ref` 可为 null 但必须写 `slice_axis_note`；
- 每个 run 必须 `executed_by: "tool"`、有 `exit_code`、`stdout_sha256`、`captured_at`、`script_sha256`；
- 手填记录判 `trials_not_tool_executed`；脚本改了没重跑，`verify` 标 `stale`。

### 1.5.5 渲染、回传与确认

```bash
python "tools/design_board.py" render --gate b --workspace "." --format all
python "tools/design_board.py" serve  --gate b --workspace "."
python "tools/design_board.py" ingest --gate b --workspace "." --from design_choices_gate_b.xlsx
python "tools/design_board.py" status --gate b --workspace "."
python "tools/design_board.py" confirm --gate b --workspace "." --apply
python "tools/design_board_checker.py" --gate b --workspace "." --mode excellence
```

B 板渲染必须包含：候选分数与维度分、每模型 pros/cons、多组数据对比表（可比层 + 专属层）、推荐/不建议理由与 `when_better`、baseline 参照行、4 位确认码。页头醒目标注"这是 B 闸门"。

确认码由 B 板 `board_sha256` 派生；改板必须重新 render + 重新 confirm。`--gate` 决定四件套文件名与回执目录（见 `references/tools.md`）。

### 1.5.6 裁决 Agent（B 板确认之后才出场）

1. 读 `model_advice.json` + B 板 `user_choice`（`user_locked: true`）。
2. **无条件采用用户选择**：`model_selection_audit.json` 写 `selected_by: "user"`、`user_choice_id`、`advice_recommended_id`、`diverged_from_advice`；候选与拒绝理由引用建议文件，不重新打分。
3. `model_decision.md` 记录：用户选了什么、建议 Agent 原本推荐什么、若不一致为何按用户选择执行。
4. 产出 Phase 1 的全部规范产物（`model_spec.json`、`solver_strategy.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`ablation_study.json`、`innovation_register.json`、`final_solution.json`、`model_decision.md`）。
5. **不得**把用户选择"技术性修正"成自己偏好的方案。

### 1.5.7 重开 B 闸门

若推进中发现用户所选方案不可行（求解器无解、约束自相矛盾、数据不足以支撑）：

```json
{"schema_version": 1, "question_id": "Q1", "raised_by": "arbitrator",
 "raised_at": "ISO8601", "gate": "b", "user_choice_id": "O1",
 "blocking_reason": "solver_infeasible",
 "evidence": ["optimization_certificate.json#status=infeasible"],
 "proposed_alternatives": ["O3"], "requires_user_reconfirm": true}
```

产出 `reopen_gate_request.json` 并**停下**等用户重新走 B 闸门；不得自行换方案，也不得绕过确认写码。

---

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
