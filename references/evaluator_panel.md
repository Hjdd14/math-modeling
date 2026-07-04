# 多评委并行审查参考

本文件用于 Phase 4 的评委组并行审查。评委组只审查建模、代码、结果、图表、验证证据和写作交接提示词，不审查正式写作正文。

## 必需角色

| 角色 | judge_type | 关注点 |
|------|------------|--------|
| 国赛建模评委 | `national_modeling_judge` | 假设合理性、建模创造性、结果正确性、表达交接清晰度 |
| 美赛评委 | `comap_judge` | thought process、problem analysis、modeling approaches、mathematical methods |
| 代码复现评委 | `code_reproducibility_judge` | 代码可运行、随机种子、hash、依赖、结果可复现 |
| 图表证据评委 | `figure_evidence_judge` | 图表是否支撑关键结论、单位/轴/图例/可读性 |
| 工程/业务解释评委 | `engineering_business_judge` | 方案可执行性、风险、情景解释、决策建议 |
| chair judge | `chair_judge` | 汇总评分、确认 high severity 问题是否已解决 |

## 单个评委输出

```json
{
  "judge_type": "national_modeling_judge",
  "score": 88,
  "passed": true,
  "strengths": ["模型选择与题意匹配", "baseline 与敏感性证据充分"],
  "issues": [
    {
      "severity": "medium",
      "status": "resolved",
      "location": "figure_storyboard.md",
      "description": "图表用途需要更明确",
      "fix": "补充每张图回答的问题"
    }
  ]
}
```

## chair judge 汇总

```json
{
  "overall_score": 87,
  "decision": "pass",
  "required_fixes": [],
  "summary": "模型、代码、图表和验证证据可以交给写作阶段。"
}
```

## 判定规则

1. 五类评委必须全部存在；chair judge 必须给出 `chair_summary`。
2. 任一 high severity 问题状态不是 resolved/fixed/closed 时，不能交付。
3. 评委组只能要求回溯修正建模、代码、图表、验证或交接提示词，不能直接写正式论文正文。
4. 评委输出写入 `judge_panel_review.json`，再由 `tools/judge_panel_checker.py --mode excellence` 检查。
