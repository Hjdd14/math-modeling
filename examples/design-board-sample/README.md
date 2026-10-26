# 决策板样例说明（Design Board Sample）

> 本目录是 `docs/DESIGN_GATE_PLAN.md` §19 的实物参照，**不是**工具产物，也不参与任何测试。
> 用途：让用户 / 决策者直观看到"设计闸门"最终会产出哪些文件、各是什么格式、长什么样。

---

## 一、文件清单

| 文件 | 格式 | 作用 | 谁看 |
|---|---|---|---|
| `design_board.json` | JSON | **唯一真实来源**：候选方案、用户选择、确认状态、轮次历史 | AI / checker |
| `mini_trials.json` | JSON | 每个候选算法的真实试算结果 + 复跑命令 | AI / 用户 |
| `design_rounds/round_001.json` | JSON | 第 1 轮回执（用户改了选择） | 审计 |
| `design_rounds/round_002.json` | JSON | 第 2 轮回执（无修改 → 触发收敛） | 审计 |
| `design_board.md` | Markdown + Mermaid | 保底视图：VS Code 里 `Ctrl+Shift+V` 直接预览 | 用户 |
| `design_board.html` | 单文件 HTML | 体验视图：点选、批注、提交、降级下载 | 用户 |
| `design_choices.xlsx` | Excel | 参数面板：下拉选择、权重调整、打分矩阵 | 用户 |

## 二、怎么打开

**Markdown（推荐先看这个）**

```powershell
code design_board.md
# 然后在 VS Code 里按 Ctrl+Shift+V 打开预览
# 或右键文件 → "Open Preview"
```

本机 VS Code 1.142 已内置 Mermaid 渲染与数学公式渲染，**无需安装任何插件**。

**先看这两张预览图**（`tools/design_board.py render --format html` 的真实产出，不是手工拼图）：

| 文件 | 说明 |
|---|---|
| `preview_light.png` | 浅色模式全页 |
| `preview_dark.png` | 深色模式全页（跟随系统 `prefers-color-scheme`） |

**HTML**

```powershell
start design_board.html
```

单文件、零外链、离线可用。可点选候选、写批注；点"提交"时若无本地服务，会自动降级为下载 JSON。

**Excel**

```powershell
start design_choices.xlsx
```

黄底单元格可改（下拉 / 权重 / 打分 / 批注），灰底为只读说明。改完 `Ctrl+S`。

**JSON**

直接文本编辑器打开。建议先看 `design_board.json`，再看 `design_rounds/` 理解"每轮回执"长什么样。

## 三、这个样例想说明什么

1. **一份 JSON 驱动四种视图**：md / html / xlsx 都由 `design_board.json` 渲染，改动只在一处。
2. **决策必须可追溯**：`design_rounds/round_001.json` 精确记录了"用户把 O2 改成了 O1"，`round_002.json` 记录"无修改"，两条合起来满足"连续 2 轮无修改"的收敛条件。
3. **试算必须是真数字**：`mini_trials.json` 里三个候选的目标值、耗时、gap 都是真实计算的，带 `reproduce_cmd` 可复跑。
4. **防伪造的第一道线**：`board_sha256` 与 `history[].board_sha256` 让"确认后偷偷改方案"可被发现；`receipt_origin` / `receipt_nonce` 让伪造回执留痕。
5. **可与审计对账（方案 C）**：本样例的候选名与 `../solved-python/model_selection_audit.json` 已对齐（见下节），可直接作为"板 + 审计交叉校验"的正例。

## 四、题目与数值

本题与 `../solved-python` 同题（绿色生产计划）：

- 2 个产品（A/B），3 个约束（工时 120h、材料 160kg、碳排 70kg），非负整数产量，最大化总利润。
- 可行整点共 1071 个。

| 候选算法 | 目标值 | 解 | 实测耗时 | 与最优的差距 |
|---|---|---|---|---|
| O1 完整枚举 | **2175** | x_a=20, x_b=25 | 4.27 ms | **0**（LP 松弛下界 = 2175） |
| O2 贪心 + 爬山 | 2120 | x_a=53, x_b=0 | 0.037 ms | 2.53% |
| O3 随机采样 100（seed=42） | 2170 | x_a=24, x_b=22 | 4.24 ms | 0.23% |

结论：O1 被推荐的理由不是"更高级"，而是它能给出 **gap = 0** 的证明——这正是评委最常追问的点。

### 与 `../solved-python` 审计的对齐关系

| 来源 | 候选名 |
|---|---|
| 本样例板 `design_board.json` | 整数线性规划（枚举/ILP）· 贪心 + 爬山局部搜索 · 随机采样 100 个可行解 |
| `../solved-python/model_selection_audit.json` | 整数线性规划（枚举）· 贪心 + 爬山局部搜索 · 随机采样 100 个可行解 · 连续松弛后取整 |

**审计是板的超集**：板展示给用户的是 3 个可选项，审计额外记录了 AI 考虑过的 `连续松弛后取整`（已被否决）。
按 `docs/DESIGN_GATE_PLAN.md` §7.2 的归一化匹配规则，三条候选全部能对上，`final_selection`（整数线性规划（枚举））也能匹配板的 `user_choice`（O1）。

> 对齐时顺带修正了审计与证书里两个原本矛盾的数字（`oracle_value` 与 `bounds` 从 2050 改为真实最优值 2175），详见计划文档 §14.3。

## 五、注意

- 本目录的 `design_board.md` / `design_board.html` / `design_choices.xlsx` 是**手工制作的设计参照**（表达"信息密度与观感应该长什么样"），并非 `tools/design_board.py render` 的输出；正式工具渲染的版本结构相同、细节会有差异。
- `design_board.json` 则是**可被校验的权威样例**：`board_sha256` 与 `confirm_code`（`508F`）由 `design_board.compute_board_sha256` 真实计算并回填，`model_selection_audit.json` 与本板候选名可交叉对上。
  ```
  python tools/design_board_checker.py --workspace examples/design-board-sample --mode excellence
  # → passed: true, warning: false, confirmed: true, cross_audit: checked
  ```
- 时间线校验在本目录**自动跳过**（命中 `FIXTURE_MARKERS`），因为 git 检出时间与板内 `confirmed_at` 没有因果关系。
- 本目录**不参与** `pytest` 与 `pipeline_check`，可随时删除而不影响任何测试。
- 若要让正式工具覆盖本样例，请先阅读 `docs/DESIGN_GATE_PLAN.md` §19.6 与 §20.5（样例与正式实现的差异）。
