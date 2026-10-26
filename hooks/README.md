# 设计闸门宿主 hook（L5 防线）

这个目录是 math-modeling skill 的**可选宿主钩子**：在 AI 调用写文件工具时，检查目标
工作区里的 `design_board.json` 是否已经确认；没有确认就拒绝写 `solution.py` /
`solution.m` / `solution_tests.py` / `solution_tests.m`。

前 4 层防线（prose 约定 / 产物结构 / 哈希绑定 / 确认码 + 时间线）都在 skill 内部；
这一层需要宿主（Claude Code 或 Cursor）配合，所以是**可选增强**，不是 skill 的默认能力。
没装 hook 时，skill 仍然可以工作，但只剩 L1–L4。

## 文件清单

| 文件 | 用途 |
| --- | --- |
| `pre_tool_use_guard.py` | 守卫脚本本身，零第三方依赖，读 stdin 的宿主事件 JSON |
| `claude_code_settings.json` | 可直接合并进 Claude Code `settings.json` 的 `PreToolUse` 片段 |
| `cursor_hooks.json` | Cursor `.cursor/hooks.json` 的等价片段（带 `MM_HOOK_STYLE=cursor`） |
| `selftest.py` | 6 个场景的自测脚本，`python hooks/selftest.py` 运行 |
| `README.md` | 本文件 |

## 判定逻辑

1. 从宿主事件里尽力提取目标路径：
   - `tool_input` / `input` 里的 `file_path`、`path`、`target_file`、`notebook_path`
     （也兼容 Cursor `beforeShellExecution` 顶层的 `command` / `cwd`）；
   - 命令字符串里明显的重定向目标（`>`、`>>`）、`tee` 目标、
     PowerShell 的 `Out-File` / `Set-Content` / `Add-Content` / `Tee-Object` /
     `New-Item`，以及 `cp` / `copy` / `mv` / `move` / `Copy-Item` / `Move-Item`
     的最后一个目标。
2. 若目标 basename 是 `solution.py` / `solution.m` / `solution_tests.py` /
   `solution_tests.m`：
   - 从目标文件所在目录开始，**向上最多 5 层**找最近的 `design_board.json`；
   - 板里**顶层 `confirmed` 为 `true`**，或者**所有 question 的 `confirmed` 都为
     `true`**，才算已确认；
   - 找不到板、解析失败、未确认，一律拒绝。
3. 非受保护文件（例如 `README.md`）不检查，直接放行。

拒绝时的输出：

- **Claude Code 风格**（默认）：stdout 输出
  `{"decision": "deny", "reason": "设计闸门未通过：..."}`，exit 0。
- **Cursor 风格**（`MM_HOOK_STYLE=cursor`）：stderr 输出原因，exit 2（Cursor 用
  exit 2 表达阻断）；放行时 stdout 输出 `{"permission": "allow"}`。

## 安装：Claude Code

1. 把 `hooks/` 目录放到项目根目录（推荐；下面的 command 用
   `$CLAUDE_PROJECT_DIR/hooks/...`）。若想复用本 skill 仓库里的这一份，不要复制，
   而是把 command 里的路径改成该脚本的绝对路径（Windows 路径建议写成
   `C:/Users/.../hooks/pre_tool_use_guard.py` 这种正斜杠形式）。
2. 把 `hooks/claude_code_settings.json` 的内容合并进项目
   `.claude/settings.json`（或用户级 `~/.claude/settings.json`）。若已经有
   `hooks.PreToolUse` 数组，**追加**一个 matcher 条目，不要覆盖已有配置。
3. 确保 `python` 在 PATH 里。Windows 上如果只有 `py`，把 command 里的 `python`
   换成 `py -3` 或解释器的绝对路径。
4. 在 Claude Code 里用 `/hooks` 检查配置是否被识别；修改 settings 后重开会话。
5. 手工验证（PowerShell）：

   ```powershell
   '{"tool_name":"Write","tool_input":{"file_path":"C:\\tmp\\gate-demo\\solution.py"}}' |
     python hooks/pre_tool_use_guard.py
   ```

   在没有已确认板的工作区里，预期输出
   `{"decision": "deny", ...}`，且 `$LASTEXITCODE` 为 0。

> 默认片段只匹配 `Write|Edit|MultiEdit|NotebookEdit`。想额外覆盖 shell 重定向，
> 可以再加一个 matcher 为 `Bash` 的条目；脚本已经兼容 Bash 的
> `{"tool_name": "Bash", "tool_input": {"command": "..."}}` 事件。

## 安装：Cursor

1. 把 `hooks/cursor_hooks.json` 复制为项目根目录的 `.cursor/hooks.json`。
2. 保持 `hooks/pre_tool_use_guard.py` 在项目根目录的 `hooks/` 下（Cursor 的项目级
   hook 以**项目根**为工作目录，所以路径写 `hooks/...`，不要写 `./hooks/...`）。
   若复用 skill 仓库里的脚本，把命令里的 `'hooks/pre_tool_use_guard.py'` 换成
   该脚本的绝对路径。
3. 片段用 `python -c "...runpy..."` 在子进程里设置 `MM_HOOK_STYLE=cursor` 再执行
   守卫，这样跨平台且不用改全局环境变量。如果你的 Cursor 版本支持在 hook 条目里
   写 `env`，也可以改成 `"env": {"MM_HOOK_STYLE": "cursor"}`。
4. 保存后 Cursor 会自动重载 hooks；在 Customize → Hooks（或 Hooks 输出通道）确认
   配置和实际执行记录。
5. `preToolUse` 覆盖通用工具调用，`beforeShellExecution` 额外覆盖 shell 重定向
   （只能是尽力识别，见下文）。放行时守卫输出 `{"permission": "allow", ...}`，
   拒绝时 exit 2。

手工验证（Cursor 的事件形状）：

```powershell
'{"tool":"edit","input":{"path":"C:\\tmp\\gate-demo\\solution.py"}}' |
  python hooks/pre_tool_use_guard.py
```

## 旁路与失败策略

- `MM_GATE_BYPASS=1`：一律放行，只在 stderr 打一行警告。这是给“我就想手动改一下”
  的逃生口，**它本身也是一条绕过路径**，不要在日常流程里常开。
- 事件缺字段 / 非法 JSON / 读 stdin 失败：**fail-open**（放行），并在 stderr 打印
  `[design-gate] hook error: ...`。不能让一个坏事件把用户的所有编辑卡死。
- 一旦已经确定目标是受保护文件，之后读板、解析板等任何异常都 **fail-closed**
  （拒绝）：此时“安全优先”，宁可误拦也不放行。

## 它不是万能的（重要）

### 它能拦

- AI 通过宿主文件工具（Claude Code 的 `Write`/`Edit`/`MultiEdit`/`NotebookEdit`，
  Cursor 的 `preToolUse`）直接写受保护的 `solution*` 文件，而目标 5 层内没有
  已确认的 `design_board.json`。
- 明显的 shell 重定向 / `tee` / PowerShell 写文件命令 / 复制移动目标（尽力识别）。
- 目标已确定受保护时，守卫自身出错也 fail-closed，不会“一报错就放行”。

### 它拦不住

- **用 shell 任意写文件**。`python -c "open('solution.py','w').write(...)"`、heredoc、
  变量拼接、base64、`python - <<'PY'` 等都可以绕过。守卫只对**明显的**重定向和
  写文件命令做字符串级识别，它**不是沙箱**，也不是 shell 解释器。
- **用户自己手写**。hook 只挂在 AI 的工具调用上；人在编辑器里敲字通常不经过它
  （即使经过，也未必是我们的 matcher）。
- **宿主不支持 / 没装 hook**。Claude Code 和 Cursor 的版本、企业策略、用户设置都
  可能让 hook 不生效；没装就是没有 L5。
- **AI 直接改宿主配置或删掉 hook**。本脚本不会保护 `.claude/settings.json`、
  `.cursor/hooks.json` 或 `hooks/` 自身；有文件写权限的 AI 可以移除这层防线。
- **手改 `design_board.json` 写 `"confirmed": true`**。守卫只读这个字段，它无法
  证明“用户本人输入过 4 位确认码”。确认码、`confirm_attested`、哈希和时间线由
  skill 内的 `design_board_checker.py` 负责；守卫只是一个便宜的入口拦截。
- **未匹配的工具 / MCP / 自定义工具**。不在 matcher 里的写文件通道不会被检查。

### 结论

这一层的作用是 **提高伪造成本 + 留痕**：AI 想绕过必须主动改用 shell、改宿主配置
或伪造板字段，而且拒绝原因会出现在宿主的 hook 日志 / stderr 里。它**不是**
“证明用户确认过”的密码学证明。

真正的“人确认”仍然是：**你本人**运行
`python tools/design_board.py confirm --apply` 并输入视图上的 4 位确认码。
hook 只是在这之前多加一道物理拦截；不要把它的存在当成确认已经发生。

## 自测

```bash
python hooks/selftest.py
```

全部通过会打印 `6/6 passed` 并 exit 0。自测覆盖：未确认拒绝、已确认放行、
非保护文件放行、`solution_tests.py` 拒绝、`MM_GATE_BYPASS=1` 旁路、畸形事件
fail-open；此外还验证了 Cursor 的 exit 2 风格、逐题 `confirmed` 兼容写法和
`design_board.json` 解析失败时的 fail-closed。
