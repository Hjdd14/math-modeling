# 工具命令与判定

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
```

总控验证会串联 LaTeX、代码运行、图表、公式一致性和 brief 核查。`passed == false` 时必须修正后重跑。

## workflow_runner.py

```bash
python "tools/workflow_runner.py" scaffold --workspace "." --language python
python "tools/workflow_runner.py" resume --workspace "." --language python
python "tools/workflow_runner.py" verify --workspace "." --language python
```

该工具只做确定性文件状态编排，不替代并行 Agent 推理。`resume` 会扫描工作区产物并合并已有 `phases`、`tool_runs`、`agent_runs` 和 `issues`，不能抹掉并行 Agent 历史。
