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
python "tools/latex_validator.py" validate --file "modeling_report.md"
```

`invalid > 0` 必须修复。

## consistency_checker.py

```bash
python "tools/consistency_checker.py" formula --doc "modeling_report.md" --code "solution.py" --lang python
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

## model_spec_checker.py

```bash
python "tools/model_spec_checker.py" --workspace "." --mode excellence
```

检查 `model_spec.json` 是否包含变量、目标函数、约束、参数、数据字段和验证计划，并尽量核对变量是否进入报告和代码。它不证明公式语义正确，但能减少“报告一个模型，代码另一个模型”的断层。

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

检查 `results/validation_summary.json` 中的数值鲁棒性证据：约束残差、最优性 gap、多初值、随机种子稳定性、bootstrap/置信区间和参数扰动排名稳定性。`standard` 模式缺新字段 warning；`excellence` 模式缺字段失败；任一字段显式 `passed=false` 所有模式失败。

## figure_auditor.py

```bash
python "tools/figure_auditor.py" --workspace "." --mode excellence
```

在 `figure_checker.py` 基础上审计论文级图表质量，读取 `figure_style.json` 与 `figure_storyboard.md`，检查图表是否存在、非空、清晰、比例合理、是否有叙事板引用，并输出 `results/figure_quality_report.json`。机器无法可靠识别所有标题和坐标轴语义，因此语义性图表判断仍由可视化设计 Agent 和报告审查完成。

## report_auditor.py

```bash
python "tools/report_auditor.py" --workspace "." --mode excellence
```

检查 `modeling_report.md` 是否具有高分数模论文结构：摘要、问题重述、假设、符号、模型建立、求解、验证、敏感性、评价和结论；同时检查正文是否引用图表、摘要是否包含结果、是否存在明显过度承诺。输出 `report_quality_report.json`。

## manifest_checker.py

```bash
python "tools/manifest_checker.py" --workspace "." --mode excellence
```

检查 `reproducibility_manifest.json`：Python/MATLAB 版本、依赖、随机种子、输入 hash 和输出 hash。hash 不匹配或文件缺失失败。

## brief_validator.py

```bash
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage model --target "modeling_report.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage document --target "modeling_report.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage code --target "solution.py"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage output --target "results"
```

`document` 是 `model` 的兼容别名，不是空检查阶段。

## pipeline_check.py

```bash
python "tools/pipeline_check.py" --workspace "." --language python
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict
python "tools/pipeline_check.py" --workspace "." --language python --evidence-mode strict --quality-mode excellence
```

总控验证会串联 LaTeX、代码运行、图表、公式一致性、brief 核查、evidence check 和 1.2.0 质量闭环检查。`passed == false` 时必须修正后重跑。默认 `--evidence-mode standard` 与 `--quality-mode standard` 向后兼容旧工作区；难题、完整交付或正式竞赛结果使用 `--evidence-mode strict`；一等奖级交付使用 `--quality-mode excellence`。

## workflow_runner.py

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
python "tools/workflow_runner.py" resume --workspace "." --language python
python "tools/workflow_runner.py" verify --workspace "." --language python
```

该工具只做确定性文件状态编排，不替代并行 Agent 推理。`resume` 会扫描工作区产物并合并已有 `phases`、`tool_runs`、`agent_runs` 和 `issues`，不能抹掉并行 Agent 历史。
