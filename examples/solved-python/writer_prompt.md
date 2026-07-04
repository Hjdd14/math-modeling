# 写作交接提示词

本 skill 已完成建模、代码、图表和验证证据，不生成正式写作正文。后续写作 skill 应基于以下材料组织论文，并保持匿名性、引用和 AI 使用披露。

## 题目与小问

- 题目来源：problem_brief.md
- 评分策略：scoring_strategy.md
- 最终方案：final_solution.json

## 模型主线

- 模型规范：model_spec.json
- 选择理由：model_decision.md
- 创新登记：innovation_register.json
- 多评委审查：judge_panel_review.json
- 决策变量：x_a 为 A 产品整数产量，x_b 为 B 产品整数产量。

## 代码与结果

- 代码文件：solution.py
- 契约测试：solution_tests.py
- 结果文件：results/output.csv、results/summary.json、results/validation_summary.json
- 复现清单：reproducibility_manifest.json

## 图表交接

- 图表叙事板：figure_storyboard.md
- 图表风格：figure_style.json
- 图表质量：results/figure_quality_report.json
- figure: result_resource_usage.png 支撑结论：碳排和工时是最优方案的关键资源瓶颈，回答 Q1-Q3，并支撑 baseline comparison、resource utilization 与 sensitivity analysis。

## 验证证据

- baseline comparison: results/validation_summary.json
- oracle tests: results/validation_summary.json
- solver cross checks: results/validation_summary.json
- sensitivity analysis: results/validation_summary.json

## 合规提示

- AI 使用、匿名性、外部资料引用和复现命令见 compliance_record.json。
- 不复制优秀论文原文，只使用题型、方法、验证和图表结构启发。
- 风险提示：若后续写作新增政策建议或放宽整数约束，必须回到 validation_summary.json 与模型裁决中复核。

## 后续写作/提交复核清单

- 匿名：正文、代码、附件和图表元数据不得出现可识别作者或团队的个人信息。
- 引用：外部资料和规则入口必须按竞赛要求标注。
- AI：按官方规则披露 AI 工具使用与人工复核。
- 页数：检查摘要、正文、附录、参考文献和附件是否符合页数/格式限制。
- 附件：确认数据、结果、图表和补充材料命名清晰。
- 代码：提交前复跑 solution.py，并确认 reproducibility_manifest.json 与 hash 记录一致。
