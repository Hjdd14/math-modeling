# Changelog

## 1.0.0 - 2026-06-23

正式版发布。

- 将长 `SKILL.md` 拆为短主入口和 `references/` 引用文档。
- 保留并强化 Phase 1、Phase 2/3、Phase 4 的并行 Agent gate。
- 新增 `workflow_runner.py`、`pipeline_check.py`、`input_parser.py` 和 `state_manager.py`。
- 新增可恢复 `modeling_state.json`，记录 phase、artifact、tool run、agent run 和 issues。
- 修复状态文件相对路径解析、并发写入覆盖和 `resume` 抹除历史的问题。
- 优化 `consistency_checker.py`，避免 Python AST 结构词造成误报，并支持机器可读 `passed` 字段。
- 明确 MATLAB 为正式支持分支，提供模板、夹具和可选集成测试。
- 新增 eval 文件、触发评估和开源发布文档。

## 0.2.0 - 2026-06-22

- 新增短主 skill 架构、引用文档、输入解析、状态管理、总控验证和工作流入口。
- 测试基线提升到 `99 passed, 1 skipped`。

## 0.1.0 - 2026-06-13

- 修复早期工具链假通过问题。
- 增补 LaTeX、图表、代码运行、brief 和一致性检查测试。
