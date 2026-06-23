# Contributing

欢迎贡献 `math-modeling`。这个仓库的核心原则是：短主 skill 降低上下文负担，但不能削弱并行 Agent 工作流和可验证交付。

## 开发流程

1. 先阅读 `SKILL.md`、`references/workflow.md` 和 `references/tools.md`。
2. 修改工具前先补测试，优先覆盖真实任务风险和已发现回归。
3. 不要用脚本替代建模 Agent 推理；CLI 只做确定性编排、状态管理和验证。
4. 修改输出产物边界时，同步更新 `SKILL.md`、`references/` 和测试。
5. 涉及 MATLAB 的改动必须至少通过静态测试；能访问 MATLAB 时再设置 `RUN_MATLAB_TESTS=1` 跑集成测试。

## 本地验证

```powershell
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
python tools/pipeline_check.py --workspace tests/test_data --language python
python tools/workflow_runner.py resume --workspace tests/test_data --language python
```

可选：

```powershell
node --check workflows/*.js
$env:RUN_MATLAB_TESTS = "1"; python -m pytest tests/test_matlab_support.py -q
```

## 文档要求

- 新增工具需要写入 `references/tools.md`。
- 新增流程或 Agent gate 需要写入 `references/workflow.md`。
- 新增模板需要写入 `references/templates.md`。
- 新增 eval 需要更新 `evals/` 和 `references/evals.md`。

## Pull Request 建议

- 说明改动动机和影响范围。
- 列出已运行的验证命令。
- 明确是否影响并行 Agent 机制、固定产物、MATLAB 支持或恢复语义。
