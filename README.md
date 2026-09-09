<div align="center">

# math-modeling

**面向数学建模竞赛的 AI Agent Skill —— 把题目解析、并行建模、代码交付、图表证据、验证闭环和写作交接串成一条可审计流程**

> **正式版 1.0.0** · MIT License · Python ≥ 3.10 · Windows / Linux / macOS

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-%E2%89%A5_3.10-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

[功能](#-核心功能) ·
[安装](#-安装) ·
[快速开始](#-快速开始) ·
[使用方式](#-使用方式) ·
[固验产物](#-固定产物) ·
[架构](#-项目结构) ·
[贡献](#-贡献)

</div>

---

## 📖 项目简介

`math-modeling` 是一个为 **数学建模竞赛**（CUMCM、美赛 MCM/ICM、研究生赛、MathorCup、电工杯、深圳杯、统计建模大赛等）量身打造的 **AI Agent Skill**。它能接入 Claude Code、OpenCode、Codex 等支持 Skill 协议的 Agent 宿主，把原本需要人手工完成的建模工程流程**结构化并自动化**。

### 它做什么 ✅

- **题目解析**：从 PDF / DOCX / Markdown / TXT 题目 + Excel / CSV 附件自动生成 `problem_brief.md`
- **题意审计**：暴露歧义、单位坑、隐藏约束，生成 `ambiguity_register.json` 与 `assumption_ledger.md`
- **并行建模共识**：5 个独立建模 Agent（优化/统计/物理机理/工程实践/创新方法）并行出方案、并行批评、并行修正、最终裁决
- **创新筛选**：每个创新点必须有题目痛点、baseline 增益、验证证据和失败风险
- **代码交付**：生成 `solution.py` 或 `solution.m`，先写契约测试再实现，保证可复现
- **结果验证**：baseline、oracle 小例验证、solver 交叉验证、敏感性分析、独立复现
- **图表证据**：每张图必须包含 file、claim、source_data、x_unit、y_unit、supports_question
- **多评委审查**：国赛建模评委、美赛评委、代码复现评委、图表证据评委、工程/业务解释评委并行评审
- **写作交接**：输出 `writer_prompt.md`，把模型、代码、结果、验证证据交接给后续独立写作 Skill

### 它不做什么 ❌

- **不生成正式论文正文** —— 它只产出现实的"建模 + 代码 + 验证 + 交接提示词"，正式论文由后续独立写作 Skill 基于 `writer_prompt.md` 完成
- **不替代真实并行 Agent** —— Python CLI 只做确定性编排、状态管理和结构化验证；并行 Agent 推理仍必须由 Agent 宿主真实派发

### 适用场景

- 数学建模竞赛（CUMCM、MCM/ICM 等各级别赛事）
- 课程项目中的多阶段数学建模任务
- 工业研究中需要可审计建模 + 代码交付 + 证据链的复杂问题

---

## ✨ 核心功能

| 阶段 | 做什么 | 关键产物 |
|------|--------|----------|
| **Phase 0** 题目与数据 | 解析题目与附件，建立数据契约与题意审计 | `problem_brief.md`、`ambiguity_register.json`、`assumption_ledger.md`、`data_schema.json` |
| **Phase 1** 并行建模共识 | 5 视角建模 + 题型层面动态专家 + 资料库检索，并行批评与修正，最终裁决 | `baseline_solution.json`、`final_solution.json`、`model_decision.md`、`innovation_register.json` |
| **Phase 2/3** 写作交接 + 代码 | 写作交接文档 Agent 与代码 Agent 并行，生成契约测试与可运行代码 + 图表 | `writer_prompt.md`、`solution.py`/`solution.m`、`results/validation_summary.json` |
| **Phase 4** 评审验证 | 语法/逻辑/输出三 Agent 并行，独立复现，多评委并行审查，工具链 gate | `judge_panel_review.json`、`results/figure_quality_report.json` |
| **Phase 5** 最终交付 | 合规审计、复现清单、状态归档 | `compliance_record.json`、`reproducibility_manifest.json` |

伴随 24 个结构化 checker 把"模型 / 数据 / 代码 / 图表 / 复现 / 合规"全链路连成证据簿。

---

## 📦 安装

### 前置条件

- **Git** ≥ 2.20：[安装指南](https://git-scm.com/downloads)
- **Python** ≥ 3.10：[安装指南](https://www.python.org/downloads/)
- **（可选）Node.js**：用于 `node --check workflows/*.js` 静态检查
- **（可选）MATLAB**：用于运行 `solution.m` 的真实集成测试
- **（可选）Claude CLI**：用于 `tools/claude_eval_runner.py` 的真实对比 eval

### 通用安装（任何 Agent 都适用的两条命令）

本 Skill 通过 `SKILL.md` 协议接入。安装本质就两步：① 把仓库放到 Agent 找得到的位置，② 让依赖 Python 的验证工具链可用。

**Linux / macOS / Git Bash：**

```bash
# 1) 把仓库克隆到任意 Agent 的 skills 目录（下表任选其一）
git clone https://github.com/Hjdd14/math-modeling.git ~/.claude/skills/math-modeling

# 2) 进入目录并运行安装脚本（自动 pip 依赖 + 自检 + 尝试符号链接到 skills 目录）
cd ~/.claude/skills/math-modeling
bash install.sh
```

**Windows PowerShell：**

```powershell
# 1) 克隆到 Claude Code 的 skills 目录
git clone https://github.com/Hjdd14/math-modeling.git $env:USERPROFILE\.claude\skills\math-modeling

# 2) 进入目录并运行安装脚本
cd $env:USERPROFILE\.claude\skills\math-modeling
.\install.ps1
```

> **一行命令完成所有（推荐）：**

```bash
git clone https://github.com/Hjdd14/math-modeling.git ~/.claude/skills/math-modeling \
  && bash ~/.claude/skills/math-modeling/install.sh
```

`install.sh` / `install.ps1` 会自动检测常见 Agent 的 skills 目录（Claude Code、OpenCode 等），尝试创建符号链接。若自动检测失败，按表手动指定 `--skills-dir` 即可（见下方示例）。

### 不同 Agent 的 skills / rules 目录

下面是主流 Agent 读取 skills 或 rules 文件的位置。把仓库放到对应目录即可，**仅当你使用了非默认的目录时**才需要显式传 `--skills-dir`。

| Agent | 全局 skills 目录 | 项目级 skills 目录 | 备注 |
|-------|-----------------|------------------|------|
| **Claude Code** (Anthropic) | `~/.claude/skills/` | `.claude/skills/` | 原生支持 `SKILL.md` 的 front-matter 触发 |
| **OpenCode** | `~/.config/opencode/skills/` | `.opencode/skills/` | 原生支持 `SKILL.md` |
| **Cursor** | n/a | `.cursor/rules/*.mdc` | 用 rules 而非 skill，可在 rule 里 `@import` 本仓库的 `SKILL.md` |
| **Continue** | `~/.continue/rules/` | `.continue/rules/` | 同步仅做规则匹配，可参考 SKILL.md 触发段 |
| **Codex CLI** (Microsoft) | n/a | `AGENTS.md` 于项目根 | 把 skill 触发段写入 `AGENTS.md`，工具用绝对路径调用 |
| **Roo Code / Cline** | n/a | `.roo/rules/` 或 `cline_rules/` | 项目级 rules 目录，用 `@import` 引用本仓库文件 |
| **Aider** | n/a | `.aider.conf.yml` | 在配置里引用本仓库 `SKILL.md` 与 tools 路径 |

> **注意**：只原生支持 `SKILL.md` 的是 Claude Code 和 OpenCode，其它 Agent 通常需要你在其 rule 文件中通过 `@import` 引用本仓库的 `SKILL.md` 与 `references/` 目录。

### 按 Agent 配置的安装示例

**安装到 Claude Code 全局目录：**

```bash
git clone https://github.com/Hjdd14/math-modeling.git ~/.claude/skills/math-modeling
bash ~/.claude/skills/math-modeling/install.sh
```

**安装到 OpenCode 全局目录：**

```bash
git clone https://github.com/Hjdd14/math-modeling.git ~/.config/opencode/skills/math-modeling
bash ~/.config/opencode/skills/math-modeling/install.sh
```

**自定义 skills 目录（任意 Agent）：**

```bash
# Linux / macOS / Git Bash
bash install.sh --skills-dir ~/your-agent-skills-dir

# Windows PowerShell
.\install.ps1 -SkillsDir "$env:USERPROFILE\your-agent-skills-dir"
```

**项目级安装（仅当前项目生效）：**

```bash
# 在你的项目根目录下克隆
git clone https://github.com/Hjdd14/math-modeling.git .claude/skills/math-modeling

# 进入并运行安装（注意：项目级 install 通常不需要 --skills-dir）
cd .claude/skills/math-modeling && bash install.sh --no-doctor
```

### 手动安装（完全可控）

```bash
# 1) 克隆仓库
git clone https://github.com/Hjdd14/math-modeling
cd math-modeling

# 2) 安装 Python 依赖
python -m pip install -r requirements.txt

# 3) 运行本地体检
python tools/doctor.py --workspace .
```

### 安装脚本参数

两个脚本支持相同的参数语义：

| 参数（bash） | 参数（PowerShell） | 含义 |
|------|------|------|
| `--skills-dir <path>` | `-SkillsDir <path>` | 指定 skills 目录，会尝试创建符号链接 |
| `--no-pip` | `-NoPip` | 跳过 `pip install` |
| `--no-doctor` | `-NoDoctor` | 跳过 doctor 健康检查 |

也可以通过环境变量 `SKILLS_DIR=...` 设置 skills 目录。

### 安装后验证

无论用哪种方式安装，完成后可运行体检：

```bash
python tools/doctor.py --workspace .
```

输出 JSON 中 `summary.failed = 0` 即可视为安装就绪。

---

## 🚀 快速开始

### 1. 用 Agent 触发 skill

将 `SKILL.md` 触发它。在你的 Agent 中输入：

> 我有一道数学建模题，附件是一个 Excel，帮我做。

或更具体：

> 帮我做这题。题目文件：`path/to/problem.pdf`，数据：`path/to/data.xlsx`

Agent 会扫描到 skill 描述匹配，自动加载 `SKILL.md` 并按 `references/workflow.md` 执行 Phase 0-5。

### 2. 用 CLI 工具手动驱动

如果你想自己跑流程，而不是通过 Agent 派发并行任务：

```bash
# 初始化工作区
python tools/workflow_runner.py scaffold --workspace runs/my_case --language python

# 解析题目 + 数据，生成 problem_brief
python tools/input_parser.py brief \
  --problem path/to/problem.pdf \
  --data path/to/data.xlsx \
  --out runs/my_case/problem_brief.md

# 恢复已有工作区
python tools/workflow_runner.py resume --workspace runs/my_case --language python

# 总控验证
python tools/pipeline_check.py --workspace runs/my_case --language python
```

### 3. 跑一个公开合成样例

仓库自带合成示例，便于快速验证安装是否成功：

```bash
# Quickstart 样例：题目 + 数据 + brief 生成
python tools/workflow_runner.py scaffold --workspace runs/quickstart --language python
python tools/input_parser.py brief \
  --problem examples/quickstart/problem.md \
  --data examples/quickstart/production_data.csv \
  --out runs/quickstart/problem_brief.md
```

完整 solved example 见 [`examples/solved-python/`](examples/solved-python/)，展示了所有固定产物的理想结构。

### 4. 难题与奖项级交付

```bash
# 难题使用严格证据模式
python tools/pipeline_check.py --workspace runs/my_case \
  --language python --evidence-mode strict

# 奖项级完整交付使用严格证据 + 卓越质量模式
python tools/pipeline_check.py --workspace runs/my_case \
  --language python --evidence-mode strict --quality-mode excellence
```

---

## 🎯 使用方式

### Agent 宿主如何接入

支持 Skill 协议的 Agent（如 Claude Code、OpenCode 等）按以下方式接入：

1. 安装本 skill 到 skills 目录（见上文）
2. 重启 Agent，让它重新扫描 skills 目录
3. 在 Agent 中发出与数学建模相关的请求，它会自动触发

### 给其他 Agent 的使用约定

1. **先读 `SKILL.md`**，再按其要求读取并执行 `references/workflow.md`
2. **不要把 `workflow_runner.py` 当成建模推理替代品** —— 它只负责 scaffold、resume、verify 和状态文件维护
3. **并行 Agent 步骤必须真实执行或明确记录为外部已执行步骤** —— 把摘要写入 `modeling_state.json`
4. 使用 `tools/state_manager.py agent-run` 记录 Agent 运行，使用 `tool-run` 记录工具运行
5. Phase 1 只产出建模决策和方案产物，不生成正式写作正文
6. 难题或完整交付必须保留 `validation_summary.json`、baseline、oracle/小例验证、solver 交叉验证、敏感性分析和独立复现摘要
7. 奖项级交付额外运行 `pipeline_check.py --quality-mode excellence`

### 仓库结构

```
math-modeling/
├── SKILL.md                  # 主入口：触发条件、核心约束、Phase Gates
├── install.sh                # Linux/macOS/Git Bash 一键安装
├── install.ps1               # Windows PowerShell 一键安装
├── references/               # 详细文档（降低上下文负担）
│   ├── workflow.md           # 完整 Phase 0-5 流程
│   ├── templates.md          # 固定产物模板
│   ├── tools.md              # 所有 CLI 工具命令与失败判定
│   ├── competition_sources.json  # 权威竞赛来源总索引
│   ├── award_playbook.md     # 题型方法卡谱系
│   ├── evaluator_panel.md   # 多评委并行审查规则
│   └── evals.md              # 本地 eval 与触发评估
├── tools/                    # Python CLI 工具（39 个，含 24 个 checker）
│   ├── workflow_runner.py    # scaffold/resume/verify
│   ├── pipeline_check.py     # 总控验证入口
│   ├── input_parser.py       # PDF/DOCX/MD/TXT + Excel/CSV 解析
│   ├── state_manager.py     # 原子状态维护
│   ├── doctor.py             # 本地依赖与仓库体检
│   └── ...                   # 详见 references/tools.md
├── workflows/                # 宿主 workflow 模板（JS，仅语法检查）
├── evals/                    # 本地 eval 与 mini benchmark
├── examples/                # 公开合成样例
│   ├── quickstart/           # 最小可跑样例
│   └── solved-python/        # 完整理想产物样例
├── tests/                    # pytest 测试套件（200+ 用例）
└── docs/                     # 安装、发布、可移植性指南
```

---

## 📋 固定产物

每个建模工作区会包含以下产物，用于审计与可复现：

<details>
<summary><b>工作区产物清单（点击展开）</b></summary>

| 产物 | 阶段 | 说明 |
|------|------|------|
| `problem_brief.md` | Phase 0 | 题目、目标、约束、附件摘要 |
| `ambiguity_register.json` | Phase 0 | 题意歧义、单位、隐藏约束审计 |
| `assumption_ledger.md` | Phase 0+ | 假设来源、影响和验证状态 |
| `modeling_state.json` | 全程 | 机器可读状态 |
| `modeling_memory.md` | 全程 | 人类可读过程记忆 |
| `baseline_solution.json` | Phase 1 | 简单可解释的基线模型 |
| `case_retrieval.json` | Phase 1 | 相似题型与可借鉴方法 |
| `model_spec.json` | Phase 1+ | 变量、目标、约束、单位、验证计划 |
| `model_selection_audit.json` | Phase 1 | 模型选择评分与证据 |
| `optimization_certificate.json` | Phase 1 | 可行性残差、上下界、gap |
| `uncertainty_budget.json` | Phase 1 | 各类误差预算 |
| `validation_profile.json` | Phase 1 | 按题型的验证证据 |
| `data_schema.json` | Phase 0 | 字段契约 |
| `symbol_table.json` | Phase 1 | 符号-单位-代码变量映射 |
| `final_solution.json` | Phase 1 | 最终建模方案 |
| `model_decision.md` | Phase 1 | 共识与裁决理由 |
| `solver_strategy.json` | Phase 1 | 求解器策略与 fallback |
| `ablation_study.json` | Phase 1 | 消融实验 |
| `innovation_register.json` | Phase 1 | 创新点证据链 |
| `writer_prompt.md` | Phase 2 | 给写作 Skill 的交接提示词 |
| `solution.py` / `solution.m` | Phase 3 | 可运行代码 |
| `solution_tests.py` / `solution_tests.m` | Phase 3 | 契约测试 |
| `figure_style.json` | Phase 3 | 图表风格规范 |
| `figure_storyboard.md` | Phase 3 | 图表叙事板 |
| `results/validation_summary.json` | Phase 3+ | 验证证据汇总 |
| `results/figure_quality_report.json` | Phase 4 | 图表质量审计 |
| `judge_panel_review.json` | Phase 4 | 多评委并行审查 |
| `decision_insights.md` | Phase 4/5 | 决策建议与工程含义 |
| `defense_questions.md` | Phase 4/5 | 评委质询准备 |
| `compliance_record.json` | Phase 5 | 合规与匿名审计 |
| `reproducibility_manifest.json` | Phase 5 | OS、库、hash、耗时 |

</details>

---

## 🔍 验证边界

默认工具链检查覆盖：代码执行、图表、brief 对齐、可信度证据、权威来源索引 (`source_registry_checker.py`)、案例检索 (`case_retrieval_checker.py`)、奖项级产物 (`award_readiness_checker.py`)、模型选择 (`model_selection_checker.py`)、优化证书 (`optimization_certificate_checker.py`)、不确定性预算 (`uncertainty_budget_checker.py`)、题型验证 profile (`validation_profile_checker.py`)、数据泄漏 (`data_leakage_checker.py`)、统计验证 (`statistical_validation_checker.py`)、数据契约 (`schema_checker.py`)、模型规范 (`model_spec_checker.py`)、符号单位 (`unit_checker.py`)、数值鲁棒性 (`robustness_checker.py`)、图表证据 (`figure_auditor.py`)、创新筛选 (`innovation_checker.py`)、评委组审查 (`judge_panel_checker.py`)、合规记录 (`compliance_checker.py`)、写作交接提示词 (`writer_prompt_checker.py`) 与可复现清单 (`manifest_checker.py`)。题目对齐与可信度证据由 `evidence_checker.py` 与 `consistency_checker.py` 把关，权威资料来源分层由 `competition_sources.json` 索引。

**重要边界**：所有 checker 都是**结构化检查，不等价于数学证明**。真实任务仍需要 Phase 4 的并行审查 Agent、独立复现 Agent、评委质询 Agent 和问题级断言共同验证。

资料内容读取需显式运行 `source_material_reader.py`，或在总控中加 `--online-source-materials` 做发布前联网深扫。

---

## 🧪 测试

```bash
# 编译检查
python -m compileall tools

# 单元 + 集成测试
python -m pytest tests -q

# 完整测试编排
python tests/run_all_tests.py
```

完整验证清单见 [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)。

---

## ⚙️ 项目结构

- **`SKILL.md`** —— 短主入口，明确触发条件、核心约束与 Phase Gates
- **`references/`** —— 降低上下文负担的详细文档：`references/workflow.md`（完整流程）、`references/templates.md`（产物模板）、`references/tools.md`（CLI 字段说明）、`references/competition_sources.json`（权威来源）、`references/award_playbook.md`（题型方法卡）、`references/evaluator_panel.md`（评委规则）、`references/evals.md`（eval 流程）
- **`tools/`** —— Python CLI 工具（39 个，其中 24 个 *_checker.py），全部可独立运行
- **`workflows/`** —— 宿主 workflow JS 模板，用于派发并行 Agent
- **`evals/`** —— 本地 eval、触发评估、mini contest benchmark
- **`examples/`** —— 公开合成样例，便于其他 Agent 与开源用户对齐
- **`tests/`** —— pytest 测试套件，200+ 用例

---

## 🛡️ 安全

请勿在公开 issue 中贴出敏感数据、未公开竞赛题、API key 或个人信息。详见 [`SECURITY.md`](SECURITY.md)。

---

## 🤝 贡献

欢迎贡献。开发前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。本地开发流程：

```bash
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
python tools/pipeline_check.py --workspace tests/test_data --language python
python tools/workflow_runner.py resume --workspace tests/test_data --language python
```

---

## 📄 许可证

本项目使用 **MIT License** 开源。详见 [`LICENSE`](LICENSE)。

## 📜 变更历史

详见 [`CHANGELOG.md`](CHANGELOG.md)。

---

<div align="center">

**Made with care for the math modeling community.**

If this skill helps your team, please ⭐ the repo to help others discover it.

</div>