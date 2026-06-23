# Portability Guide

`math-modeling` 设计目标是让不同 Agent 在同一套产物、状态和工具约束下协作。只要对方能读取本仓库文件、运行 Python CLI，并能按文档执行外部并行 Agent 步骤，就可以使用。

## 最低能力要求

Agent 或宿主环境需要具备：

- 能读取 `SKILL.md` 和 `references/`。
- 能运行 Python 3.10+。
- 能写入建模工作区文件。
- 能并行或模拟并行地派发多个 Agent 任务，并保留每个 Agent 的输出摘要。
- 能运行 `tools/workflow_runner.py`、`tools/state_manager.py` 和 `tools/pipeline_check.py`。

可选能力：

- MATLAB：运行 `solution.m`。
- Node.js：检查 `workflows/*.js` 模板语法。
- Claude CLI：运行 `tools/claude_eval_runner.py`。

## 关键约束

`workflow_runner.py` 不是 orchestrator Agent，也不是建模推理引擎。它只负责：

- `scaffold`：创建状态、记忆和结果目录。
- `resume`：扫描工作区并合并状态，不覆盖并行 Agent 历史。
- `verify`：调用总控验证。

并行 Agent 仍必须由宿主 Agent 系统执行：

- Phase 1：五个建模 Agent、五个批评 Agent、五个修正 Agent、最终裁决。
- Phase 2/3：文档 Agent 与代码 Agent 并行。
- Phase 4：语法审查、逻辑审查、输出审查 Agent 并行。

## 推荐记录方式

记录工具运行：

```powershell
python tools/state_manager.py tool-run --workspace runs/my_case --name pipeline_check --status passed --score 100 --summary "all checks passed"
```

记录 Agent 运行：

```powershell
python tools/state_manager.py agent-run --workspace runs/my_case --phase phase1 --agent optimizer --role initial_modeling_agent --status completed --summary "linear programming model" --output-path agent_outputs/phase1/initial_solutions.json
```

恢复状态：

```powershell
python tools/workflow_runner.py resume --workspace runs/my_case --language python
```

## 已知边界

- `consistency_checker.py` 是启发式一致性检查，不能替代数学证明。
- `workflows/*.js` 是宿主 workflow 模板，默认只保证语法可检查。
- 如果宿主 Agent 不支持真正并行执行，也必须保留各 Agent 独立输入、输出和审查记录，不能合并成一个单 Agent 口头过程。
