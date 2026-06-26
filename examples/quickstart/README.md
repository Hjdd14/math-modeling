# Quickstart Example

这是一个可公开上传的合成小题，用来验证 `math-modeling` 的基础体验。它只包含输入文件，不包含本地运行产物。

## 运行

```powershell
python tools/workflow_runner.py scaffold --workspace runs/quickstart --language python
python tools/input_parser.py brief --problem examples/quickstart/problem.md --data examples/quickstart/production_data.csv --out runs/quickstart/problem_brief.md
python tools/workflow_runner.py resume --workspace runs/quickstart --language python
```

接下来由 Agent 按 `SKILL.md` 和 `references/workflow.md` 执行并行建模、文档、代码和审查流程。

## 文件

- `problem.md`：合成数学建模题目。
- `production_data.csv`：题目附件数据。
