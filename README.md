<div align="center">

# math-modeling

### 数学建模竞赛的 AI Agent Skill

**读题 → 审题 → 建模 → 选型 → 代码 → 图表 → 评审 → 交接**
**全程留下可复现的证据链，关键决定由你亲手放行**

![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Tests](https://img.shields.io/badge/tests-354%20passed-brightgreen)
![Checkers](https://img.shields.io/badge/checkers-26-orange)
![Python](https://img.shields.io/badge/python-%E2%89%A5_3.10-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

[功能](#-你会得到什么) · [两道闸门](#-两道人工闸门) · [工作流](#-工作流) · [快速开始](#-快速开始) · [产物](#-产物一览) · [质量体系](#-质量与证据)

</div>

---

## 🎯 这是什么

一个给 **数学建模竞赛** 用的 AI Agent Skill：CUMCM、美赛 MCM/ICM、研究生赛、MathorCup、电工杯、深圳杯、统计建模大赛都适用。

它把"一个人闷头做完、交上去不知道靠不靠谱"的黑箱流程，换成一条 **有证据、有评审、有你来拍板** 的流水线：每个数字都能追溯到脚本，每张图都能追溯到数据，每次模型选择都经过你的确认。

> 一句话：**AI 负责把活干完并自证，你负责在关键岔路口说"行"或"换"。**

---

## ✨ 你会得到什么

| 能力 | 你拿到的东西 |
|---|---|
| **读题与审题** | 题目/附件自动解析成 `problem_brief.md`；歧义、单位坑、隐藏约束单独列成 `ambiguity_register.json` 与假设台账 |
| **五视角并行建模** | 优化 / 统计 / 物理机理 / 工程实践 / 创新方法 五个 Agent 同时出方案，互评互批后再收敛，避免单一路径自嗨 |
| **真实选型对比** | 每个候选模型在 ≥2 组数据切片上**真跑一遍**，给出可复跑的成本、误差、稳定性与优缺点 |
| **能跑的代码** | `solution.py` 或 `solution.m`，先写契约测试再实现，结果落到 `results/` |
| **可证伪的验证** | baseline 对比、oracle 小例、求解器交叉验证、敏感性/鲁棒性、独立复现记录 |
| **出版级图表** | 每张图绑定"论点 + 数据来源 + 轴单位 + 支撑哪一问"，风格、DPI、色盲友好度统一（`figure_storyboard.md`） |
| **多评委评审** | 国赛评委、美赛评委、代码复现评委、图表证据评委、工程解释评委并行打分，chair judge 汇总 |
| **写作交接包** | `writer_prompt.md`：模型、代码、结果、证据、图表清单一次性交给后续写作 Skill |

**它不做什么**：不生成正式论文正文（交给独立写作 Skill）；不替代真实的并行 Agent 推理（CLI 只做确定性编排与验证）。

---

## 🚪 两道人工闸门

这是本版最重要的设计：把"一次性大确认"拆成**两次轻量确认**，各问各的问题。

| | **闸门 A：框架与探索边界** | **闸门 B：方案择定** |
|---|---|---|
| 什么时候 | 读完题、建完简报之后 | 五视角跑完、试算落盘之后 |
| 问你什么 | 题目读对了吗？高危假设接受吗？**要探索哪几个方法族**？ | 这一问**最终用哪个模型**？ |
| 你看到 | 题意摘要 + 歧义清单 + 假设逐条 + 每问 3–5 个待探索范式（含异质族与探索成本） | 5–8 个候选的**分数、优缺点、真实数据对比表**，1 个建议 + 其余不建议及理由 |
| 次数 | 整题 **1 次** | 整题 **1 次**（主仓库）/ 每问 1 次（[按小问分支](https://github.com/Hjdd14/math-modeling-per-question)） |
| 放行方式 | 你本人在终端输入 4 位确认码 | 同上（独立确认码） |

**为什么值得**：
- **A 闸门**把"题目理解错了"这种最贵的错误拦在 10 分钟级，而不是 60 分钟后。
- **B 闸门**把选型从"AI 自己挑"变成"你看数据挑"——而且**确认之前写不出 `solution.py`**：工具校验会报错，宿主 hook 会直接拒绝写盘。
- 两道闸门都不锁定模型：A 只划定探索范围，五视角在范围内自由发挥；B 才由你定胜负。

---

## 🧭 工作流

```text
Phase 0    读题 · 附件解析 · 歧义审计 · 假设台账
   │
   ▼
Phase 0.5  【闸门 A】确认题意框架 + 待探索范式集合          ← 你确认
   │
   ▼
Phase 1    五视角并行建模 → 批评 → 修正 → 每视角真实试算
   │
   ▼
Phase 1.5  【闸门 B】1 建议 + 其余不建议 + 打分 + 数据对比    ← 你选定模型
   │
   ▼
Phase 2/3  写作交接文档 与 代码/测试/结果 并行产出
   │
   ▼
Phase 4    技术审查 + 独立复现 + 五评委并行评分
   │
   ▼
Phase 5    合规记录 · 复现清单 · 归档交付
```

---

## 🚀 快速开始

### 1. 安装

需要 **Python ≥ 3.10** 与 **Git**。MATLAB、Node.js、Claude CLI 都是可选增强。

```bash
# Linux / macOS / Git Bash
git clone https://github.com/Hjdd14/math-modeling.git ~/.claude/skills/math-modeling
bash ~/.claude/skills/math-modeling/install.sh
```

```powershell
# Windows PowerShell
git clone https://github.com/Hjdd14/math-modeling.git $env:USERPROFILE\.claude\skills\math-modeling
cd $env:USERPROFILE\.claude\skills\math-modeling
.\install.ps1
```

安装脚本会自动装依赖、跑自检，并尝试把仓库链接到常见 Agent 的 skills 目录；非默认目录用 `--skills-dir <path>` 指定。

### 2. 开始一次建模

在 Agent 里直接把题目和附件丢给它，例如：

> 用 math-modeling skill 做这道题：`A题.pdf`，附件 `data.xlsx`。Python，国赛标准。

它会先产出简报与决策板，然后**停下来等你输入确认码**——这是设计如此，不是卡住。

### 3. 手动命令（可选）

```bash
python tools/workflow_runner.py scaffold --workspace . --language python   # 初始化工作区
python tools/design_board.py render --workspace . --format all             # 生成 A 板（框架闸门）
python tools/design_board.py serve  --workspace .                          # 浏览器里改、提交
python tools/design_board.py confirm --workspace . --apply                 # 你本人输入确认码
python tools/pipeline_check.py --workspace . --quality-mode excellence     # 全链路验证
```

---

## 🗂 产物一览

| 阶段 | 关键文件 | 作用 |
|---|---|---|
| Phase 0 | `problem_brief.md`、`ambiguity_register.json`、`assumption_ledger.md`、`data_schema.json` | 题目与数据的唯一真实来源 |
| 闸门 A | `design_board.json`、`design_board.md/.html/.xlsx`、`design_rounds/` | 框架与范式集合的确认记录 |
| Phase 1 | `model_spec.json`、`solver_strategy.json`、`innovation_register.json`、`perspective_trials.json` | 模型规范、求解策略、创新登记、试算证据 |
| 闸门 B | `design_board_gate_b.json`、`model_advice.json`、`design_rounds_gate_b/` | 选型建议与你的最终选择 |
| Phase 2/3 | `writer_prompt.md`、`solution.py/.m`、`solution_tests.*`、`results/` | 写作交接包 + 可运行代码与结果 |
| Phase 4 | `judge_panel_review.json`、`defense_questions.md`、`decision_insights.md` | 评审意见、质疑清单、结果解读 |
| Phase 5 | `compliance_record.json`、`reproducibility_manifest.json` | 合规与一键复现清单 |

---

## ✅ 质量与证据

不是"AI 说它对了"，是**工具链逐项验过**：

| 层 | 机制 | 用户感受 |
|---|---|---|
| 结构 | 26 个 checker 覆盖模型、数据、代码、图表、复现、合规 | 产物缺项/对不上账，立刻报错 |
| 数值 | 试算只能由工具执行并留痕，手填数字会被判假 | 对比表里的每个数都可复跑 |
| 时序 | 代码/结果的时间必须晚于对应闸门确认 | "先写代码后补板"过不了 |
| 事中 | 宿主 hook 在写 `solution.*` 时直接拒绝 | 确认前根本写不进去 |
| 评审 | 五评委 + 独立复现 Agent + 证据审计 | 结论被质疑时拿得出依据 |
| 自检 | 354 项自动化测试 + 全流程/对抗探针 | 改 skill 不会悄悄改坏行为 |

---

## 🤖 适配的 Agent 宿主

| Agent | 接入方式 |
|---|---|
| **Claude Code** / **OpenCode** | 原生支持 `SKILL.md`，放进 skills 目录即用 |
| **Cursor** / **Roo Code** / **Cline** / **Continue** | 在项目 rules 里 `@import` 本仓库的 `SKILL.md` 与 `references/` |
| **Codex CLI** | 触发段写入 `AGENTS.md`，工具用绝对路径调用 |
| **Aider** 等自定义宿主 | 在配置里引用 `SKILL.md` 与 `tools/` |

> 装好后让 Agent 自己读 `SKILL.md` 即可；`references/` 是按需展开的细节文档，不占上下文。

---

## 📁 目录结构

```text
math-modeling/
├── SKILL.md                # 入口：流程、硬规则、两道闸门
├── references/             # 按需展开：workflow / templates / tools / 方法卡 / 评委规则
├── tools/                  # 48 个确定性工具：决策板、试算、校验、绘图审计、总控
├── hooks/                  # 宿主 hook：未确认就拒绝写 solution.*
├── tests/                  # 354 项自动化测试 + 探针
├── examples/               # 最小可跑样例与完整理想产物
├── docs/                   # 双闸门规格、安装与可移植性说明
└── workflows/              # 宿主 workflow 模板
```

---

## ⚠️ 边界与取舍

- **不写论文正文**：只交付建模、代码、结果、证据与 `writer_prompt.md`。
- **不替你做决定**：两道闸门的确认码必须由你本人在终端输入；AI 代跑会留痕并判不通过。
- **确定性工具不做推理**：Python 侧只负责编排、校验与取证；真正的并行推理由 Agent 宿主派发。
- **图表统一后置**：写作与代码阶段只产数据，图表在最后统一绘制，保证风格与叙事一致。

---

## 🆕 1.1.0 更新要点

- 新增 **双闸门**：A 框架/范式闸门 + B 方案择定闸门，确认前写不出 `solution.*`。
- 新增 **真实试算链路**：每视角脚本由工具执行、计时、留痕，对比表数字不可手填。
- 新增 **建议 Agent 产出**：1 建议 + 其余不建议 + 打分 + 优缺点 + 数据对比。
- 校验与 hook 同步升级：双时间线、按板确认、CI/非交互确认一律判不通过。
- 测试从 265 项扩到 **354 项**，新增全流程与对抗探针。

---

## 📄 License

MIT © math-modeling contributors

> 姊妹项目：**[math-modeling-per-question](https://github.com/Hjdd14/math-modeling-per-question)** —— 按小问分别交付，做完一问论文手立刻能写这一问。
