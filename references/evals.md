# Eval 与触发描述优化

## 本地 eval

本地 eval 使用 `evals/evals.json` 描述真实任务场景，并用 pytest 校验：

- 固定产物是否存在。
- `modeling_state.json` 是否记录工具和 Agent 运行摘要。
- `results/` 是否包含结构化结果和图表。
- 并行 Agent phase gate 是否在输出中被执行或明确记录。
- 难题场景是否包含题意审计、baseline、动态专家、`validation_summary.json`、oracle/小例验证、敏感性分析和独立复现摘要。
- 奖项级场景是否包含 `writer_prompt.md`、`innovation_register.json`、`judge_panel_review.json`、`compliance_record.json`，并明确不生成正式写作正文。
- 权威竞赛资料库场景是否覆盖 MathorCup 大数据题、电工杯电力题、统计建模社会经济题、深圳杯工程题、研究生赛工业题、APMCM 综合题和五一杯规划题。
- 每个资料库扩展 eval 必须检查：资料库检索、`case_retrieval.json`、模型选择、代码验证、图表证据和多评委审查。

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
- 需要建模方案、代码、图表、结果验证和写作交接提示词。
- Python 或 MATLAB 实现。

反例应覆盖：

- 普通数学题求解。
- 单纯 Excel 清洗。
- PDF 翻译。
- 只要求写一段代码。
- 普通论文润色、排版或只要求写正式论文正文。
