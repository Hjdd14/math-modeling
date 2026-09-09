# math-modeling 缺陷修复方案

范围按你的选择：**A+B（局部 bug + 证据完整性）**，不做架构重构。所有改动都已对照 211 个通过测试做过冲突排查，标注了必须保留的字符串和字段形状。

---

## 设计前提（每条改动都受此约束）

1. **不改动产物契约**：`summarize_data_file` 仍返回 `{structure, stats, quality}`，`pipeline_check` 仍返回布尔 `passed`，`state_manager` 的 artifact 路径仍保持相对形式。新增字段只加不删。
2. **不收紧 standard 模式**：`tests/test_pipeline_check.py:26,411-413,431-434`、`tests/test_workflow_runner.py:67`、`tests/test_award_level_enhancements.py:187-192` 共 5 处断言把 standard 锁定为 warning-only，改它等于自断兼容性。改文档指向严格模式。
3. **不用"全零即占位"启发式**：`tests/test_data/results/validation_summary.json:42-65` 里 `max_abs=0.0`、`gap=0.0`、`std=0.0`、`lower==upper==12000` 都是**合法**的最优解证据。占位识别只认显式标记。
4. **不扩展 `PROFILE_REQUIREMENTS`**：`tests/test_award_level_enhancements.py:295,367` 的 fixture 恰好提供当前字段列表，加字段会破测试。
5. **不改这些字符串**：模板函数名 `run_baseline`/`run_known_case_tests`/`run_sensitivity_analysis`、`def main():`、`if __name__ == "__main__":\n    main()`、`validation_summary.json`、`MATLAB`、`results`（`tests/test_matlab_support.py:25-33`、`tests/test_skill_docs.py:23-24`）；issue code `missing_validation_profile_field` 及其 `field` 键；`ci.yml` 里被断言的 7 个子串；`CHANGELOG.md` 的字面量 `1.0.0`。

---

## 第 1 组：可复现的功能性 bug

### 1.1 `tools/state_manager.py` 阶段推断（最高优先）

现状：`:198` 在 init 时建空 `results/`，`:188-189` 见目录即判 phase4 → 全新工作区自称 phase4，同时 `workflow_runner.py` 写的 `modeling_memory.md` 说 Phase 0，自相矛盾。

改动 `:183-190`，把 phase4 的判据从"目录存在"换成"目录有真实产物"：

- 计算 `results/` 下的条目数，phase4 要求 `results/validation_summary.json` 存在**或** `results/` 内至少有一个文件。
- `artifact_info()` 对目录额外返回 `entry_count`，让状态文件自证依据（`tests/test_state_manager.py:51` 只断言 `exists`，加键安全）。

安全性：`tests/test_workflow_runner.py:55` 断言 phase4，其 fixture 从 `tests/test_data/results/` 拷了 5 个文件（含 `validation_summary.json`），仍判 phase4。`tests/test_state_manager.py:35` 走 `update_phase` 直接赋值，不经推断。**0 破坏。**

### 1.2 `tools/state_manager.py` 枚举校验与工作区越界

现状：`--phase phase99 --status bogus_status` 原样接受；`--path ../../etc/hosts` 原样记录。

- 新增 `VALID_STATUSES = {"pending","running","in_progress","completed","passed","failed","warning","skipped","blocked"}`，在 `update_phase`/`record_tool_run`/`record_agent_run` 校验；phase 校验用现成的 `PHASE_ORDER`（`:26`）。非法值 `raise ValueError`，由 `main()` 的 `except` 走既有 `error()` 出口（exit 1）。
- `resolve_workspace_path`（`:54-58`）加**包含性**检查：解析后必须落在 workspace 根内。

关键细节：必须用 `is_relative_to(workspace_root)` 而**不是**"禁止绝对路径"——`tests/test_state_manager.py:21` 传的正是 workspace 内的绝对路径，禁绝对路径会破 `:37`。同时 `:67` 断言相对路径原样保存，所以只校验不改写 `path` 字段。白名单必须含 `passed`（`tests/test_state_manager.py:74-103` 有 12 个并发子进程用 `--status passed` 并断言 `failures == []`）。**0 破坏。**

### 1.3 `tools/input_parser.py` Excel 多 sheet 评分串用

现状 `:143-150`：`quality` 在 per-file 层绑定一次（因 pandas 默认 `sheet_name=0`，实际只是第一个 sheet），却在 per-sheet 循环里复用。实测两 sheet 工作簿，脏 sheet 真实分 85.0，简报两行都写 100.0，且脏 sheet 的列从未被 `generate_stats` 分析。

- `summarize_data_file`（`:100-105`）改为遍历 `structure["sheets"]`，对 Excel 逐 sheet 调 `generate_stats(file_path, sheet_name)` 和 `check_quality(file_path, sheet_name)`，结果放进新键 `by_sheet`；`stats`/`quality` 仍保留为第一个 sheet 的结果以保持向后兼容（`tests/test_input_parser.py:74` 依赖该形状）。
- `render_brief`（`:146-150`）改读 `by_sheet[sheet_name]["quality"]["quality_score"]`，取不到时回退 `summary["quality"]`。
- 顺带修 `tools/data_analyzer.py:168,184,196` 的 `sheet_name or "Sheet1"` 误标：Excel 且 `sheet_name is None` 时解析出真实首个 sheet 名再打标签，CSV 保持 `"Sheet1"`（与 `read_data_structure:55` 一致）。

安全性：无任何测试断言简报表格列布局或行数；两个 fixture 都是单 sheet CSV。**0 破坏。**

### 1.4 `tools/data_analyzer.py` 空数据满分

现状 `:208-209`：`total_cells == 0` 直接返回 100.0，只有表头的 CSV 实测得 100 分。

- 改为返回 `quality_score = 0.0` 并新增 `"empty_data": True` 标记与一条显式说明。
- 必须返回 `0.0` 而**不是** `None`：`tests/test_data_analyzer.py:58` 和 `tests/test_e2e_workflow.py:44` 断言 `0 <= quality_score <= 100`，`None` 会 TypeError。

安全性：`tests/test_data/empty.xlsx` 只被 `read` 动作使用（`tests/test_data_analyzer.py:61-64`），没有测试把 0 行文件喂给 `check_quality`；无测试断言 `quality_score == 100`。**0 破坏。**

### 1.5 `tools/input_parser.py` 文本编码无回退

现状 `:29-30` 是裸 `read_text(encoding="utf-8")`，GBK 题目文件直接 exit 1——而中文赛题常见 GB18030。

- 按 `utf-8` → `utf-8-sig` → `gb18030` → `big5` 顺序尝试，全失败再用 `utf-8, errors="replace"` 并置 `encoding_fallback: true`。
- `extract_text` 返回值新增 `encoding` 键，解析口径可追溯。
- 不用 `latin-1` 兜底：它永不抛错，会把中文变成静默乱码。

### 1.6 `tools/input_parser.py` PDF 空抽取静默成功

现状 `:33-43`：`or ""` 把失败页变空串，`if part` 又把空页从 join 里丢掉，页码对应关系被摧毁；扫描件返回 `char_count=0` 仍以成功退出，`render_brief:121` 直接内联空文本。

- `_read_pdf` 改为返回 `(text, page_report)`，`page_report` 记录每页 `index`/`chars`/`extracted`（它只在 `:85` 一处被调用，改签名无扩散）。
- `extract_text` 新增 `pages`、`empty_pages`、`extraction_ratio` 键；全文为空时抛出明确错误，提示可能是扫描件、需先 OCR 或换可选文本 PDF。
- 保留 `{file_name,file_type,text,char_count,line_count}` 全部原有键（`tests/test_input_parser.py:54-55`，该测试还被 `fitz` importorskip 门控）。

### 1.7 `tools/source_freshness_checker.py` 年份定时炸弹

现状：`:70-85` 唯一的新鲜度信号是 `max(years) >= current_year - 1`，`:88-95` 的参考年份在无 `checked_at` 时回落到 `date.today().year`，而注册表里没有任何 `checked_at`。实测模拟 2027 年 CUMCM 被判 stale，2028 年 14 个来源全部 stale、strict 模式 exit 1——代码和数据一行不改。

拆成两个互不混淆的维度，**不新增注册表数据**：

- `_reference_year` 优先读 `references/competition_sources.json` 已有的顶层 `version: "2026-06-27"`，其次 `checked_at`，最后才是系统时钟。年份覆盖与"注册表维护时点"比较，而不是与墙上时钟比较——时间炸弹从根上消失。
- 原 `stale_source_years`（strict 下 error）拆为：`missing_year_coverage`（`years`/`years_covered` 缺失或不可解析，strict 下 error，属真实结构缺陷）与 `source_years_behind_registry_version`（覆盖落后于注册表版本，**始终 warning**）。

安全性：`tests/test_award_level_enhancements.py:499,529` 断言 `passed is True`，其 fixture 的 `checked_at` 是 2026-06-28 且只会越来越旧，所以维护时点相关判定必须是 warning；`:671-674` 和 `tests/test_pipeline_check.py:472` 走真实注册表（无 `checked_at`），所以"缺 `checked_at`"也不能是 error。两条都已按此设计。无任何测试断言 `stale_source_years`。**0 破坏。**

### 1.8 `tools/pipeline_check.py` 死导入与 LaTeX 未校验

`validate_latex_file` 在 `:22`/`:51` 导入却从未调用，全仓库无其他调用点。

- 移除死导入。
- 新增一个**永不置 `passed=False`** 的 `latex_check`：对存在的 `model_decision.md` 调 `validate_latex_file`，只产出 warning。必须自带 try/except 包装而不走 `_safe()`——`_safe()` 在异常时返回 `{"passed": False}` 会翻转总控结论。

安全性：`tests/test_pipeline_check.py:459-481` 只断言 20 个指定键通过，加第 21 个键不受断言；必须缺席的只有 `report_auditor` 和关闭开关时的 `source_material_reader`。**0 破坏。**

---

## 第 2 组：证据完整性（最严重问题的正面修复）

核心事实：`references/templates.md:633-698`（Python）与 `:756-793`（MATLAB）的 `run_baseline` 等函数硬编码 `passed: True` 且数值全 0，实测该输出原封不动通过 `evidence_checker --mode strict` 与 `robustness_checker --mode strict`，零 issue。这是一条零成本伪造证据路径。

### 2.1 模板默认状态改为未验证

改 `references/templates.md` 两处代码块，**函数名一个都不改**：

- `baseline_value`/`model_value`/`expected`/`actual` 等占位数值由 `0.0` 改为 `None`。
- 每个返回值把 `"passed": True` 换成 `"status": "NOT_VALIDATED"` + `"passed": None`。
- 加 `# TODO(必填)` 注释说明必须用真实计算替换、并把 status 改为 `passed`/`failed`。
- 模板仍可运行（不抛异常），符合 Phase 3 对可运行代码的要求；但产出的证据会被 checker 拦住。

这一步本身就复用了 `evidence_checker` 已有的正确逻辑：`_section_check:81-88` 的 `require_positive_pass` 分支在 strict 模式下对"无显式 passed"判 error，而 `NOT_VALIDATED` 既不算失败也不算通过，会正确落进该分支。

### 2.2 checker 显式拒绝占位证据

在 `tools/evidence_checker.py` 与 `tools/robustness_checker.py` 各加一个约 15 行的本地扫描（与仓库现有风格一致，38 个工具都各自定义 `output`，本轮不引入共享模块）：

- 扫描 payload 文本中的 `NOT_VALIDATED`、`UNVALIDATED`、`TODO`、`FIXME`、`REPLACE_ME` 标记以及 `passed is None`，命中即产出 `placeholder_evidence` 级别 error（占位证据在任何模式下都不是合法证据）。
- **实施前先 grep 一遍 `tests/` 全部 fixture 确认无这些标记再启用 error 级别**——审计结论是 0 命中，但这是唯一会静默破坏多个测试的风险点，值得复核。

明确不做：任何基于"数值全为 0"或"`lower == upper`"的判定。审计确认这类规则会破坏 `tests/test_quality_tools.py:193`、`tests/test_pipeline_check.py:26,30,422,458,520,532,576`、`tests/test_completion_gaps.py:59`、`tests/test_award_level_enhancements.py:662` 共 8+ 处，因为最优解的残差和 gap 本来就该是 0。

### 2.3 `evidence_checker` 的 `excellence` 漂移

`:18` 的 `STRICT_MODES` 漏了 `"excellence"`，导致 `--evidence-mode excellence` 下缺证据只降级为 warning，与其余 24 个 checker 行为不一致。

- 补进集合，同时补进 `:237` 的 argparse choices 与 `:148-149` 的 docstring。

安全性：`tests/` 中 `excellence` 与 evidence_checker 零交集；`pipeline_check:183` 的 `--evidence-mode` choices 本来就不含 `excellence`，所有 `quality_mode="excellence"` 的测试传给 `check_evidence` 的仍是 `standard`/`strict`。**0 破坏。**

### 2.4 验证要求按题型可声明不适用

`references/workflow.md:265` 无条件要求"多初值≥3、随机种子≥3、bootstrap≥0.95、扰动排名稳定"，对确定性线性规划、最短路、精确枚举、解析 ODE 并不自然，反而诱导编造。全仓库 `not_applicable` 零命中。

- `tools/validation_profile_checker.py:137-151`：字段值形如 `{"status":"not_applicable","rationale":"...","alternative_validation":"..."}` 时视为通过，但 `rationale` 与 `alternative_validation` **两者都必须非空**；缺任一则产出新 issue code `not_applicable_without_justification`。
- `tools/robustness_checker.py` 的 multi_start / 随机种子 / bootstrap 条目加同一逃逸口。
- 保留 `missing_validation_profile_field` 及其 `field` 键：字段真缺失仍是错误，只有显式声明才放行（`tests/test_award_level_enhancements.py:302-303,373-377` 依赖此区分）。
- 不扩展 `PROFILE_REQUIREMENTS`。
- 同步在 `references/workflow.md:265`、`references/templates.md` 的 `validation_summary` 结构说明里写清这个逃逸口及其举证义务。

安全性：逃逸口只在显式 status 命中时触发，`tests/test_award_level_enhancements.py:209-212`（期望 `passed is False`）不受影响。**0 破坏。**

### 2.5 `tools/code_runner.py` 超时不杀进程树 + MATLAB 引号拼接

`:75-81` 的 `subprocess.run` 超时只终止直接子进程，孙进程会遗留；`:69` 的 `f"cd('{workdir}')"` 在路径含单引号时会失败。

- 换成 `Popen` + `communicate(timeout=)`，超时后 POSIX 走 `start_new_session=True` + `killpg`，Windows 走 `taskkill /F /T /PID`，确保整棵进程树被回收。
- MATLAB 改用 `-sd <workdir>` 传工作目录；若 `tests/test_code_runner.py` 或 `tests/test_matlab_support.py` 断言了现有 `cd('...')` 命令形态（实施时先 grep 确认），则退回保留 `cd()` 但对单引号做加倍转义。
- **不做**资源限制/网络隔离/临时沙箱/`--unsafe` 开关——那属于 C 层加固，你已选择不纳入本轮；这两项只修"超时承诺没兑现"和"拼接会炸"两个确定性缺陷。

---

## 第 3 组：边界与文档一致性

### 3.1 workflows/*.js 标注为 demo 并删除越界步骤

`modeling_workflow.js` 全文 191 行，只做"数据分析 → 5 Agent → 批评循环 → 裁决 → 3 项审查 → 一次 brief_validator"，缺 `problem_brief` 生成、歧义登记、题型分类、baseline、案例检索、固定 JSON 产物、契约测试、独立复现、五类评委、状态持久化；且 `:159` 要求文档 Agent 生成 LaTeX 文档，与 `SKILL.md:30`（Phase 2 只生成写作交接材料）直接冲突。

- 7 个 JS 文件头部统一加显著 banner：仅为并行派发骨架示例，不实现 Phase 0-5 完整流程与固定产物，不得作为交付依据，完整流程见 `references/workflow.md`。
- `modeling_workflow.js:157-166` 的文档 Agent 提示词由"生成 LaTeX 文档"改为"生成 `writer_prompt.md` 写作交接材料"，消除边界冲突；`phase2_3_parallel.js` 同样排查并修正。
- `README.md:311,399` 与 `docs/PORTABILITY.md:58` 的措辞由"宿主 workflow 模板"改为"并行派发示例（demo，非完整流程）"。
- 保留 `node --check` CI 步骤（`tests/test_award_level_enhancements.py:685-694` 断言其存在）。

### 3.2 标准模式的定位改文档 + 新增只读完整度字段

standard 判定保持 warning-only（测试锁定），但要让"过了不等于齐了"这件事显式可见：

- `pipeline_check.run_checks` 返回值新增 `artifact_completeness`（required/recommended 各自的 present 与 missing 列表，recommended 清单取自 `references/workflow.md:350-384` 的 Phase 5 固定产物表）与顶层 `status`（`pass`/`pass_with_warnings`/`fail`）。
- **布尔 `passed` 语义与 `:209` 的退出码完全不变**（3 个 CI 步骤依赖它）。
- `SKILL.md:98-108`：把当前标为"最终验证"的 standard 命令改称"快速自检/兼容旧工作区"，并把 `--evidence-mode strict --quality-mode excellence` 明确为最终交付验证。`references/tools.md` 同步。
- 不新增第四档模式（现有已 6 档，再加只增认知负担）。

安全性：所有断言读的是 `result["passed"]` 或 `checks[name]["passed"]/["warning"]`，加新键安全；无测试断言 pipeline_check 自身退出码。需保留 `required_files.missing` 为路径字符串列表（`tests/test_pipeline_check.py:615`）。**0 破坏。**

### 3.3 Phase 2 输入清单的循环依赖标注

`references/workflow.md:243` 要求文档 Agent 读 `results/validation_summary.json` 和 `reproducibility_manifest.json`，前者由并行的 Phase 3 产出、后者是 Phase 5 产物。同文件 `:388` 其实已规定 Phase 5 最终更新一次——机制在，只是 `:243` 没说清。

- 在 `:243` 的输入清单里把这几项标注为"Phase 5 补入，Phase 2 首轮可缺省"，并说明 Phase 2 产出的是草稿、Phase 5 定稿。`SKILL.md:132` 同步一句。
- 不改并行结构本身，不动 `SKILL.md:31`（Phase 3 不等 Phase 2）。

---

## 第 4 组：工程清理（低风险，全部无测试依赖）

- **`install.sh:145-153`**：`:145` 的 `SKILLS_DIR=""` 先把继承来的环境变量清空，`:151` 的守卫 `[ -z "$SKILLS_DIR" ] && [ -n "${SKILLS_DIR:-}" ]` 要求同一变量同时为空和非空，逻辑不可达，`:152` 是自赋值空操作 → 环境变量**必然失效**，与 `install.sh:13` 和 `README.md:191` 的承诺相反。改法：在参数解析**之前**把环境值存入 `SKILLS_DIR_ENV`，再按 CLI 参数 → 环境变量 → 自动探测三级回退。
- **`install.sh:217`**：假链接 `https://github.com/issues` 改为 `https://github.com/Hjdd14/math-modeling/issues`。
- **`install.ps1:180-187`**：`cmd /c mklink /J` 改用原生 `New-Item -ItemType Junction`，并用异常/`$LASTEXITCODE` 判定成败（现在靠 `Test-Path` 间接判断）。
- **`README.md`**：7 处 `<owner>`（`:88,99,109,136,143,161,171`）改为 `Hjdd14`；`:66,304,398` 的"21+ checker"改为准确口径——`tools/` 共 39 个 CLI 工具，其中 24 个 `*_checker.py`（`:304` 现在把整个 39 文件目录都标成 checker）。需保留 `tests/test_open_source_readiness.py:40-77` 断言的 32 个短语。
- **版本叙述**：`references/tools.md:346` 与 `tools/pipeline_check.py:190`（该字符串会打进 `--help`）里的裸 `1.2.0` 去掉版本号，改称"质量闭环产物"，与 `VERSION`/`pyproject.toml`/`README` 的 1.0.0 不再冲突。`CHANGELOG.md` 不动（`tests/test_open_source_readiness.py:85` 要求保留字面量 `1.0.0`）。
- **`.github/workflows/ci.yml:13`**：矩阵补 `"3.10"`（`pyproject.toml:6` 声明 `>=3.10` 却从未验证）。已排查无 3.10 不兼容语法：`state_manager.py:169` 的 `dict | None` 在 3.10 合法，无 `match`/`tomllib`/`itertools.batched`。
- **`tests/run_all_tests.py:15-41`**：25 条硬编码清单改为 `sorted(TESTS_DIR.glob("test_*.py"))`，消除"新增测试被编排器静默跳过"的隐患（当前恰好一致，但无任何测试守护同步）。CI 双跑（`ci.yml:33-37` 先整套 pytest 再跑编排器）保持不动，避免动 CI 结构。

---

## 明确不纳入本轮（附理由）

- **统一 `artifact_manifest.json` + `pipeline_check` 三态化**：需要重排全部 checker 的返回契约，是你排除的架构层改动。第 3.2 的 `artifact_completeness` 字段以零破坏方式先满足"缺什么要看得见"这个核心诉求。
- **`workflows/*.js` 重写为完整 DAG**：没有宿主 API 可测，写完仍无法验证行为，收益低于风险。
- **`code_runner` 沙箱（资源/网络/文件系统隔离、`--unsafe`）**：属 C 层加固。
- **`agent_runs` 补 run_id/起止时间/prompt hash/重试次数**、**Phase 0 用户确认状态字段**、**`mini_benchmark_runner` 与 `claude_eval_runner --dry-run` 的自证通过改造**：均属 C 层，需新增字段与文档同步。这几条是确认存在的真实缺口（`claude_eval_runner.py:46-47` 直接把 `PARALLEL_MARKERS` 拼成输出再做子串匹配、必然通过；`mini_benchmark_runner.py:64-72` 把 oracle 答案抄进待评解答），本轮会在 `audit_memory.md` 记录为待办，不静默放过。
- **25 个工具各自定义 `STRICT_MODES` 的去重**：本轮只修其中已产生真实后果的 `evidence_checker` 漂移（2.3），不做提取公共模块的重构。

---

## 验证方案

先跑基线，改完逐项复核，最后整体回归。

**回归门（必须与改前一致）**
```
python -m compileall tools
python -m pytest tests -q                  # 期望仍为 211 passed, 1 skipped
python tests/run_all_tests.py
python tools/pipeline_check.py --workspace tests/test_data --language python
python tools/pipeline_check.py --workspace tests/test_data --language python --evidence-mode strict --quality-mode excellence
python tools/source_registry_checker.py --skill-root . --mode excellence
python tools/source_freshness_checker.py --workspace . --mode excellence
python tools/award_readiness_checker.py --workspace tests/test_data --mode excellence
python tools/mini_benchmark_checker.py --benchmark evals/mini_contest_benchmark.json --mode strict
python tools/mini_benchmark_runner.py --benchmark evals/mini_contest_benchmark.json --mode strict
python tools/workflow_runner.py resume --workspace tests/test_data --language python
node --check workflows/*.js
```

**行为门（我之前用来确认缺陷的探针，改后必须翻转）**

| 探针 | 改前 | 改后期望 |
|---|---|---|
| 全新工作区 `state_manager init` | `phase4` | `phase0` |
| `phase --phase phase99 --status bogus` | 接受 | exit 1 |
| `artifact --path ../../etc/hosts` | 记录 | exit 1 |
| 模板原样产出的 `validation_summary.json` 跑 `evidence_checker --mode strict` | `passed=True`, 0 issue | `passed=False`，命中 placeholder |
| 同上跑 `robustness_checker --mode strict` | `passed=True`, 0 issue | `passed=False` |
| 两 sheet 工作簿（干净 + 90% 缺失）生成简报 | 两行都 100.0 | 分别 100.0 / 85.0，且两 sheet 都被统计 |
| 仅表头 CSV 跑 `check_quality` | 100.0 | 0.0 且 `empty_data: true` |
| GBK 编码题目文件 `extract` | exit 1 | 成功并回报 `encoding` |
| 打补丁模拟 2028 年跑 `source_freshness --mode excellence` | 14 个来源全 stale、exit 1 | 通过（覆盖落后只报 warning） |
| 空壳工作区（占位 brief + stub 脚本 + 1 图）standard 模式 | `passed=true`，无提示 | `passed=true` 但 `artifact_completeness` 列出缺失项、`status=pass_with_warnings` |
| 同上 excellence 模式 | 20 个 checker 失败 | 保持失败 |

**收尾**：按 `SKILL.md:180` 要求，把本轮改动摘要与全部验证结果追加到 `audit_memory.md`，并把不纳入本轮的 C 层缺口（agent 运行证据、benchmark 自证、Phase 0 确认状态、code_runner 沙箱）作为待办明确记录。

改动涉及 12 个代码文件、5 个文档文件、2 个安装脚本、1 个 CI 配置、1 个测试编排脚本；无新增依赖，无删除文件，无产物契约变更。