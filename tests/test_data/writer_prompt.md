# 写作交接提示词

本 skill 已完成建模、代码、图表和验证证据，不生成正式写作正文。后续写作 skill 应基于以下材料组织正文，并保持匿名性与合规披露。

## 题目与模型

- 题目来源：problem_brief.md
- 最终方案：final_solution.json
- 模型规范：model_spec.json
- 决策说明：model_decision.md
- 多评委审查：judge_panel_review.json
- 决策变量：x 为 A 产品产量，y 为 B 产品产量。

## 代码与结果

- 代码文件：solution.py
- 结果文件：results/output.csv、results/summary.json、results/validation_summary.json
- 复现清单：reproducibility_manifest.json

## 图表交接

- 图表叙事板：figure_storyboard.md
- 图表风格：figure_style.json
- 图表质量报告：results/figure_quality_report.json
- figure: figure.png 支撑结论：最优方案生成了非空且可引用的结果图，回答 Q1-Q2，应放在模型求解与验证讨论附近。

## 验证证据

- baseline comparison: results/validation_summary.json
- oracle tests: results/validation_summary.json
- solver cross checks: results/validation_summary.json
- sensitivity analysis: results/validation_summary.json

## 合规提示

- AI 使用、匿名性和外部资料引用见 compliance_record.json。
- 不复制优秀论文原文，只使用方法、验证和图表结构启发。
- 风险提示：若后续正文扩展模型假设或新增结论，必须回到验证证据中复核。

## 后续写作/提交复核清单

- 匿名：正文、代码、附件和图片元数据不得出现可识别作者或团队的个人信息。
- 引用：外部资料必须在参考文献或注释中标注来源。
- AI：按官方规则披露 AI 工具使用与人工复核。
- 页数：复核竞赛页数、摘要、目录和附录限制。
- 附件：复核数据、图表、结果表和补充材料命名。
- 代码：提交前复跑 solution.py，并确认 reproducibility_manifest.json 与 hash 记录一致。
