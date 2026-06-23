# Eval 与触发描述优化

## 本地 eval

本地 eval 使用 `evals/evals.json` 描述真实任务场景，并用 pytest 校验：

- 固定产物是否存在。
- `modeling_state.json` 是否记录工具和 Agent 运行摘要。
- `results/` 是否包含结构化结果和图表。
- 并行 Agent phase gate 是否在输出中被执行或明确记录。

## Claude 实跑 eval

可选命令：

```bash
python "tools/claude_eval_runner.py" --evals "evals/evals.json" --skill-path "." --workspace "..\math-modeling-workspace\iteration-1"
```

如需不调用 Claude，只验证 runner 结构：

```bash
python "tools/claude_eval_runner.py" --evals "evals/evals.json" --skill-path "." --workspace "..\math-modeling-workspace\dry-run" --dry-run
```

生成的输出可交给 skill-creator 的 `eval-viewer/generate_review.py` 做人工审阅。

## 触发描述 eval

`evals/trigger_eval.json` 包含 20 条 should-trigger / should-not-trigger 查询。优化描述时使用 skill-creator 的 `scripts/run_loop.py`，但只有在 skill 主体稳定后再运行。

正例应覆盖：

- 数学建模竞赛题。
- PDF/DOCX 题目加 Excel/CSV 附件。
- 需要建模报告、代码、图表、结果验证。
- Python 或 MATLAB 实现。

反例应覆盖：

- 普通数学题求解。
- 单纯 Excel 清洗。
- PDF 翻译。
- 只要求写一段代码。
- 普通论文润色或排版。
