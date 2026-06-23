# 数学建模并行 Agent 工作流

本文件保存完整 Phase 0-5 流程。短主 `SKILL.md` 只是入口，并不削减这里的并行子 Agent 要求。

## Phase 0: 题目与数据提取

1. 使用 `tools/input_parser.py extract --file <题目文件>` 提取 PDF/DOCX/MD/TXT 题目文本。
2. 使用 `tools/input_parser.py brief --problem <题目文件> --data <附件...> --out problem_brief.md` 生成初版 brief。
3. 使用 `tools/state_manager.py init --workspace . --language python|matlab` 初始化状态。
4. 向用户确认 `problem_brief.md` 中的题目目标、约束、附件摘要和编程语言。

## Phase 1: 并行建模共识

Phase 1 必须使用五视角建模 Agent。必须并行生成方案、并行批评、并行修正，再由最终裁决 Agent 选定方案。本阶段输出 `final_solution.json` 与 `model_decision.md`，不得写入 `modeling_report.md`。

### 1.1 五视角建模 Agent 并行生成方案

在同一轮中并行启动以下 Agent，并要求每个 Agent 输出 JSON：

- `initial_optimizer`：优化视角 Agent。关注线性规划、非线性规划、整数规划、动态规划、全局最优性和计算效率。
- `initial_statistician`：统计视角 Agent。关注回归、时间序列、贝叶斯、蒙特卡洛、不确定性和置信区间。
- `initial_physicist`：物理机理 Agent。关注微分方程、动力系统、守恒定律、量纲一致性和可解释性。
- `initial_engineer`：工程实践 Agent。关注实现难度、鲁棒性、仿真、排队论和可部署性。
- `initial_innovator`：创新方法 Agent。关注机器学习、混合模型、启发式算法和创新性。

统一 prompt：

```text
你是[角色]。请基于 problem_brief.md 提出一个完整数学建模方案。
必须输出 JSON：
{
  "model_name": "...",
  "variables": [{"name": "...", "meaning": "...", "range": "..."}],
  "objective_function": "...",
  "constraints": ["..."],
  "solution_method": "...",
  "assumptions": ["..."],
  "pros": ["..."],
  "cons": ["..."],
  "complexity": "..."
}
```

### 1.2 并行批评

把五个方案合并为 `all_solutions` 后，在同一轮中启动五个批评 Agent。每个 Agent 必须批评所有方案，而不只批评自己的方案。

输出 JSON：

```json
{
  "target_agent_id": {
    "criticisms": ["问题"],
    "suggestions": ["建议"],
    "score": 75,
    "severity": "medium"
  }
}
```

### 1.3 并行修正

把批评意见返回给五个原 Agent，并行修正方案。每个修正方案必须包含 `responses` 字段，说明接受或拒绝每条批评的理由。

### 1.4 共识判断

记录每轮共识度：

- 五个 `model_name` 完全一致：100
- 两类模型：70
- 不超过半数类别：50
- 高度分散：30

达到 80 分、连续两轮变化小于 2 分，或达到 5 轮时停止。

### 1.5 最终裁决

启动 `final_decision` Agent，综合全部方案、批评、修正和共识历史，输出：

- `final_solution.json`
- `model_decision.md`

`model_decision.md` 必须包含方案对比表、选择理由、被拒方案的不足、关键洞察和验证要点。

## Phase 2: 文档 Agent

文档 Agent 与代码 Agent 并行执行。文档 Agent 读取 `final_solution.json` 与 `problem_brief.md`，生成 `modeling_report.md`。报告必须包含问题描述、模型假设、符号说明、模型建立、求解方法、代入验证、模型评价和改进方向。

文档生成后运行：

```bash
python "tools/latex_validator.py" validate --file "modeling_report.md"
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage document --target "modeling_report.md"
```

### Phase 3: 代码 Agent

代码 Agent 与文档 Agent 并行执行。代码 Agent 读取 `final_solution.json` 与 `problem_brief.md`，不等待 Phase 2 创建 `modeling_report.md`。代码必须根据语言选择生成 `solution.py` 或 `solution.m`，所有输出必须写入 `results/`。

代码要求：

- 包含参数设置、数据输入、模型构建、求解计算、结果输出和可视化。
- 生成 `results/output.csv` 或同等结构化结果。
- 生成 `results/summary.json` 或同等摘要。
- 生成至少一张 `results/result_*.png` 图表。
- Python 必须包含 `def main()` 和 `if __name__ == "__main__": main()`。
- MATLAB 必须创建 `results` 目录并使用 `writetable`、`writecell` 或等价函数输出结果。

文档与代码都落盘后运行：

```bash
python "tools/brief_validator.py" validate --brief "problem_brief.md" --stage code --target "solution.py"
python "tools/consistency_checker.py" formula --doc "modeling_report.md" --code "solution.py" --lang python
```

### Phase 4: 并行审查与工具验证

Phase 4 必须先并行启动三个审查 Agent：

- 语法审查 Agent：检查语法错误、缩进、变量命名、依赖导入、主入口。
- 逻辑审查 Agent：检查公式、约束、数据引用、算法逻辑是否与 `problem_brief.md` 和 `modeling_report.md` 一致。
- 输出审查 Agent：检查输出是否覆盖所有目标、图表是否生成、结果是否合理。

每个审查 Agent 输出：

```json
{
  "issues": [{"severity": "high", "location": "...", "description": "...", "fix": "..."}],
  "passed": false,
  "summary": "..."
}
```

汇总问题后运行：

```bash
python "tools/pipeline_check.py" --workspace "." --language python
```

如果失败，按问题类型回溯到 Phase 1、2 或 3 修正，重新执行 Phase 4。

### Phase 4: 修正循环

1. 修正 high severity 问题。
2. 重新运行相关工具。
3. 修正 medium severity 问题。
4. 重新运行 `pipeline_check.py`。
5. 直到所有关键检查通过。

## Phase 5: 归档与交付

最终交付前确认固定产物：

- `problem_brief.md`
- `modeling_state.json`
- `modeling_memory.md`
- `final_solution.json`
- `model_decision.md`
- `modeling_report.md`
- `solution.py` 或 `solution.m`
- `results/`

运行总控验证并把结果写入 `modeling_memory.md` 和 `modeling_state.json`。
