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
```

总控验证会串联 LaTeX、代码运行、图表、公式一致性、brief 核查和 evidence check。`passed == false` 时必须修正后重跑。默认 `--evidence-mode standard` 向后兼容旧工作区；难题、完整交付或正式竞赛结果使用 `--evidence-mode strict`。

## workflow_runner.py

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
python "tools/workflow_runner.py" resume --workspace "." --language python
python "tools/workflow_runner.py" verify --workspace "." --language python
```

该工具只做确定性文件状态编排，不替代并行 Agent 推理。`resume` 会扫描工作区产物并合并已有 `phases`、`tool_runs`、`agent_runs` 和 `issues`，不能抹掉并行 Agent 历史。
