#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设计闸门宿主 hook（L5 防线）：写 solution 代码前检查决策板是否已确认。

双闸门语义（见 docs/DESIGN_GATE_PLAN.md 与施工契约 §8.6）：

* **A 闸门**（框架与探索边界）：整题一块板 ``design_board.json``，只确认题意框架、
  假设与待探索范式集合，不锁定模型选型。
* **B 闸门**（方案择定）：``design_board_gate_b.json``。主仓库是整题一块板
  （工作区根），分支是每问一块板（``questions/qN/``）。

判定链（除第 1 条外都只对受保护交付代码生效）：

1. 目标在 ``perspective_trials/`` 下 → 放行（试算代码是可跑证据，不是交付代码）；
2. 目标在 ``questions/<qid>/`` 下 → 向上 ≤5 层找 ``design_board_gate_b.json``，
   必须已确认（``questions[]`` 逐条 ``confirmed`` 全为 true）；找不到该板时
   向上找 A 板：A 板 ``schema_version >= 2`` → 拒绝（提示先做 B 闸门），
   否则按 legacy 放行并给出警告；
3. 其余交付代码（工作区根 ``solution.*``）→ A 板必须已确认；A 板
   ``schema_version >= 2`` 时还要求同级 ``design_board_gate_b.json`` 已确认；
4. 其它目标不拦。

用法::

    python hooks/pre_tool_use_guard.py < event.json

支持两种宿主：

* Claude Code ``PreToolUse``：拒绝时向 stdout 输出
  ``{"decision": "deny", "reason": "..."}`` 并 exit 0（Claude Code 用 JSON
  里的 decision 表达拒绝，不用退出码报错）。
* Cursor（设置 ``MM_HOOK_STYLE=cursor``）：拒绝时把原因写到 stderr 并
  exit 2；允许时向 stdout 输出 ``{"permission": "allow", ...}``。

行为约定：

* ``MM_GATE_BYPASS=1``：一律放行，只在 stderr 留一行警告（给“我就想手动
  改一下”的场景，这本身也是一条绕过路径）。
* 事件解析等内部异常：fail-open（放行）并在 stderr 留痕，避免 hook 崩掉
  用户的所有编辑。
* 例外：一旦已经确定目标是受保护文件，后续任何异常都必须 fail-closed
  （拒绝，安全优先）。

本脚本零第三方依赖，仅使用 Python 标准库；可独立复制到任意项目使用。
"""

import json
import os
import re
import sys


# 受保护的代码文件名（统一小写比较，兼容 Windows 大小写不敏感文件系统）
PROTECTED_BASENAMES = frozenset(
    {
        "solution.py",
        "solution.m",
        "solution_tests.py",
        "solution_tests.m",
    }
)

BOARD_FILENAME = "design_board.json"

# B 闸门（方案择定）的板文件名；与 A 板并存，互不覆盖。
GATE_B_FILENAME = "design_board_gate_b.json"

# 试算代码目录：perspective_trials/** 是可跑证据，不是交付代码，一律放行。
TRIALS_DIRNAME = "perspective_trials"

# 小问目录：分支仓库把 B 板放在 questions/qN/ 下（主仓库放在工作区根）。
QUESTIONS_DIRNAME = "questions"

# 从目标文件目录开始，最多向上找 5 层
MAX_UPWARD_LEVELS = 5

# 宿主事件里可能承载目标路径的键名
PATH_KEYS = (
    "file_path",
    "filePath",
    "path",
    "target_file",
    "targetFile",
    "notebook_path",
    "notebookPath",
)

# 宿主事件里可能承载工具参数的键名
INPUT_KEYS = ("tool_input", "input", "arguments", "params")

# 工作目录相关的键名
CWD_KEYS = ("cwd", "working_directory", "workingDirectory")

# 明显的 shell 重定向：>、>>、1>、2>>、&> 等（&> 由后面的 & 判断单独处理）
_REDIRECT_RE = re.compile(r"[0-9]?>>?")

# tee 及其参数
_TEE_RE = re.compile(r"(?<![A-Za-z0-9_-])tee(?:\.exe)?\b(?P<args>[^\n;|]*)", re.IGNORECASE)

# PowerShell 常见写文件 cmdlet
_PS_WRITE_RE = re.compile(
    r"\b(?:Out-File|Set-Content|Add-Content|Tee-Object|New-Item)\b(?P<args>[^\n;|]*)",
    re.IGNORECASE,
)

# 常见复制/移动命令（目标文件可能是受保护文件）
_COPY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:cp|copy|mv|move)(?:\.exe)?(?=\s|$)(?P<args>[^\n;|]*)",
    re.IGNORECASE,
)

# PowerShell 复制/移动 cmdlet
_PS_COPY_RE = re.compile(
    r"\b(?:Copy-Item|Move-Item)\b(?P<args>[^\n;|]*)",
    re.IGNORECASE,
)

# 命名参数：-Path / -FilePath / -LiteralPath / -Destination
_NAMED_PATH_KEYS = frozenset(
    {"-path", "-filepath", "-literalpath", "-destination"}
)


def _warn(text):
    """向 stderr 写一行警告/错误；写失败也不能让 hook 崩掉。"""
    if not text.endswith("\n"):
        text += "\n"
    try:
        _write_stream(sys.stderr, text)
    except Exception:
        pass


def _write_stream(stream, text):
    """优先按 UTF-8 字节写，避免 Windows 控制台编码把中文输出打崩。"""
    if stream is None:
        return
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
    else:
        stream.write(text)
        stream.flush()


def _write_stdout(text):
    _write_stream(sys.stdout, text)


def _read_stdin_text():
    """读取宿主事件；读失败返回空串（随后按 fail-open 处理）。"""
    try:
        # 手工直接运行脚本且没有管道时不应挂起等 EOF
        if getattr(sys.stdin, "isatty", lambda: False)():
            return ""
        buffer = getattr(sys.stdin, "buffer", None)
        if buffer is not None:
            return buffer.read().decode("utf-8", "replace")
        return sys.stdin.read()
    except Exception as exc:  # pragma: no cover - 防御性分支
        _warn("[design-gate] hook error: 读取 stdin 失败: %s" % (exc,))
        return ""


def _hook_style():
    """返回 claude 或 cursor；默认按 Claude Code 风格输出。"""
    value = os.environ.get("MM_HOOK_STYLE", "").strip().lower()
    return "cursor" if value.startswith("cursor") else "claude"


def _bypass_enabled():
    return os.environ.get("MM_GATE_BYPASS", "").strip() == "1"


def _parse_event(raw):
    """解析宿主事件；空输入视为空事件，非法 JSON 抛异常交由上层 fail-open。"""
    if not raw or not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("hook 事件 JSON 顶层不是对象")
    return data


def _iter_containers(event):
    """把可能承载 tool_input 的容器都列出来。

    兼容：
    * Claude Code：``{"tool_name": "...", "tool_input": {...}}``
    * Cursor：``{"tool": "...", "input": {...}}`` 或
      ``beforeShellExecution`` 的顶层 ``command`` / ``cwd``
    * 某些宿主把参数序列化成 JSON 字符串
    """
    for key in INPUT_KEYS:
        value = event.get(key)
        if isinstance(value, dict):
            yield value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict):
                yield parsed
    # 事件本身也当作容器：Cursor 的 beforeShellExecution / afterFileEdit
    # 会把 command、cwd、file_path 放在顶层。
    yield event


def _split_words(text):
    """极简 shell / PowerShell 词法分析。

    只处理空白分隔、单双引号；不处理转义、变量展开、命令替换。
    这是“尽力提取”，不是完整的 shell 解析器。
    """
    words = []
    current = []
    quote = None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
            else:
                current.append(ch)
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch in (" ", "\t", "\r", "\n", ";", "|", "&", "<", ">"):
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        words.append("".join(current))
    return words


def _is_option(word):
    """判断一个词是不是命令行选项（Windows 的 /Y 也算）。"""
    if word.startswith("--"):
        return True
    if word.startswith("-") and len(word) > 1:
        return True
    return bool(re.fullmatch(r"/[A-Za-z]", word))


def _extract_redirect_targets(command):
    """提取 shell 重定向目标，如 ``> solution.py``、``2>> "solution.py"``。"""
    targets = []
    for match in _REDIRECT_RE.finditer(command):
        rest = command[match.end():]
        # 跳过 >&2 / 2>&1 这类文件描述符复制
        if rest.lstrip().startswith("&"):
            continue
        words = _split_words(rest)
        if not words:
            continue
        token = words[0]
        if token in ("/dev/null", "nul", "NUL", "NUL:"):
            continue
        targets.append(token)
    return targets


def _extract_tee_targets(command):
    targets = []
    for match in _TEE_RE.finditer(command):
        words = _split_words(match.group("args"))
        for word in words:
            if not word or _is_option(word):
                continue
            targets.append(word)
    return targets


def _extract_powershell_targets(command):
    """提取 Out-File / Set-Content / Tee-Object / New-Item 的目标。"""
    targets = []
    for match in _PS_WRITE_RE.finditer(command):
        words = _split_words(match.group("args"))
        named = False
        for index, word in enumerate(words):
            lower = word.lower()
            if lower in _NAMED_PATH_KEYS:
                named = True
                if index + 1 < len(words):
                    targets.append(words[index + 1])
            elif "=" in lower:
                prefix, value = word.split("=", 1)
                if prefix.lower() in _NAMED_PATH_KEYS and value:
                    named = True
                    targets.append(value)
        if not named:
            for word in words:
                if word and not _is_option(word):
                    targets.append(word)
                    break
    return targets


def _extract_copy_targets(command):
    """提取 cp/copy/mv/move 与 Copy-Item/Move-Item 的目标（最后一个路径）。"""
    targets = []
    for match in _COPY_RE.finditer(command):
        operands = [
            word
            for word in _split_words(match.group("args"))
            if word and not _is_option(word)
        ]
        if operands:
            targets.append(operands[-1])

    for match in _PS_COPY_RE.finditer(command):
        words = _split_words(match.group("args"))
        destination = None
        operands = []
        for index, word in enumerate(words):
            lower = word.lower()
            if lower in ("-destination", "-path", "-literalpath"):
                if index + 1 < len(words):
                    destination = words[index + 1]
            elif lower.startswith("-destination=") or lower.startswith("-path="):
                destination = word.split("=", 1)[1]
            elif word and not _is_option(word):
                operands.append(word)
        if destination:
            targets.append(destination)
        elif operands:
            targets.append(operands[-1])
    return targets


def _extract_command_targets(command):
    """从命令字符串里尽力提取“会被写入”的文件路径。"""
    targets = []
    targets.extend(_extract_redirect_targets(command))
    targets.extend(_extract_tee_targets(command))
    targets.extend(_extract_powershell_targets(command))
    targets.extend(_extract_copy_targets(command))
    return targets


def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _extract_targets(event):
    """返回 (候选目标路径列表, 基准工作目录)。"""
    containers = list(_iter_containers(event))

    base_dir = os.getcwd()
    for container in containers:
        found = False
        for key in CWD_KEYS:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                base_dir = value.strip()
                found = True
                break
        if found:
            break

    targets = []
    for container in containers:
        for key in PATH_KEYS:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                targets.append(value.strip())
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        targets.append(item.strip())
        command = container.get("command")
        if isinstance(command, str) and command.strip():
            targets.extend(_extract_command_targets(command))
    return _dedupe(targets), base_dir


def _is_protected(path):
    """按 basename 判断是否受保护（兼容反斜杠路径、大小写）。"""
    normalized = path.replace("\\", "/").rstrip("/")
    name = normalized.rsplit("/", 1)[-1]
    return name.strip().lower() in PROTECTED_BASENAMES


def _resolve_target(target, base_dir):
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(os.path.abspath(base_dir), expanded))


def _normalize_parts(path):
    """把路径拆成非空段（Windows 反斜杠一并归一），便于识别 questions/<qid> 结构。"""
    return [part for part in path.replace("\\", "/").split("/") if part]


def _join_parts(parts):
    """把 _normalize_parts 的段拼回路径；保留 Windows 盘符写法（C:\\...）。"""
    if not parts:
        return ""
    head = parts[0]
    if head.endswith(":") and len(head) == 2:
        return head + os.sep + os.sep.join(parts[1:])
    if len(parts) == 1:
        return head
    return os.sep.join(parts)


def _find_named_file_upward(start_dir, filename):
    """从 start_dir 开始向上最多 5 层查找指定文件名；找不到返回 None。"""
    current = start_dir or os.getcwd()
    for _ in range(MAX_UPWARD_LEVELS + 1):
        candidate = os.path.join(current, filename)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _find_gate_b_for(directory):
    """从指定目录向上最多 5 层找 design_board_gate_b.json（B 闸门）。"""
    return _find_named_file_upward(directory, GATE_B_FILENAME)


def _load_board(board_path):
    """读取板文件；解析失败抛异常，由调用方决定 fail-closed。"""
    with open(board_path, "r", encoding="utf-8-sig") as handle:
        board = json.load(handle)
    if not isinstance(board, dict):
        raise ValueError("板文件顶层不是 JSON 对象: %s" % (board_path,))
    return board


def _board_is_confirmed_payload(board):
    """判断板对象是否已确认。

    兼容两种写法（满足其一即可）：
    * 顶层 ``confirmed`` 为 true；
    * ``questions`` 非空，且每个 question 的 ``confirmed`` 都为 true。
    """
    if not isinstance(board, dict):
        return False
    if board.get("confirmed") is True:
        return True
    questions = board.get("questions")
    if not isinstance(questions, list) or not questions:
        return False
    for question in questions:
        if not isinstance(question, dict):
            return False
        if question.get("confirmed") is not True:
            return False
    return True


def _board_schema_version(board):
    """读取板结构版本；缺失或非法按 1（legacy）处理，与 checker 口径一致。"""
    version = board.get("schema_version") if isinstance(board, dict) else None
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    return 1


def _board_is_new_flow(board):
    """``schema_version >= 2`` 即新流程：必须有 B 板，缺板不放行。"""
    return _board_schema_version(board) >= 2


def _is_trials_target(target_abs):
    """目标是否位于 ``perspective_trials/`` 目录下（试算代码，非交付代码）。"""
    parts = [part.lower() for part in _normalize_parts(target_abs)]
    return TRIALS_DIRNAME in parts[:-1]


def _question_dir(target_abs):
    """若目标在 ``<...>/questions/<qid>/...`` 下，返回该 qid 目录；否则 None。"""
    parts = _normalize_parts(target_abs)
    lowered = [part.lower() for part in parts]
    for index in range(len(parts) - 2):
        if lowered[index] != QUESTIONS_DIRNAME:
            continue
        # 必须真的落在 qid 目录里面（至少还有 qid + 文件名两段）
        if index + 2 > len(parts) - 1:
            continue
        return _join_parts(parts[: index + 2])
    return None


def _deny_reason_gate_a(display_path, workspace):
    """A 闸门未通过的拒绝文案：两板命令都给，避免用户只补一半。"""
    return (
        "设计闸门未通过：%s 是交付代码，但它所在工作区还没有已确认的 design_board.json。\n"
        "A 闸门（框架与探索边界）：\n"
        "  python tools/design_board.py render --workspace %s\n"
        "  python tools/design_board.py confirm --workspace %s --apply"
        "   # 用户本人输入 4 位确认码\n"
        "B 闸门（方案择定，A 板 schema_version >= 2 时必需）：\n"
        "  python tools/design_board.py render --gate b --workspace %s\n"
        "  python tools/design_board.py confirm --gate b --workspace %s --apply"
        % (display_path, workspace, workspace, workspace, workspace)
    )


def _deny_reason_gate_b(display_path, workspace, detail):
    """B 闸门未通过的拒绝文案：先给 B 板四步命令，再附 A 板命令。"""
    return (
        "设计闸门未通过：%s 是交付代码，但 B 闸门（方案择定）还没有通过：%s\n"
        "先完成 B 闸门（design_board_gate_b.json，确认码取该板 board_sha256[:4]）：\n"
        "  python tools/design_board.py render --gate b --workspace %s\n"
        "  python tools/design_board.py serve --gate b --workspace %s\n"
        "  python tools/design_board.py ingest --gate b --workspace %s\n"
        "  python tools/design_board.py confirm --gate b --workspace %s --apply"
        "   # 用户本人输入 4 位确认码\n"
        "A 闸门（框架与探索边界，design_board.json）：\n"
        "  python tools/design_board.py render --workspace %s\n"
        "  python tools/design_board.py confirm --workspace %s --apply"
        % (display_path, detail, workspace, workspace, workspace, workspace, workspace, workspace)
    )


def _legacy_warning(workspace, scope):
    return (
        "%s 使用旧版 A 板（schema_version < 2 或 legacy_gate_a_only），按单闸门流程放行。"
        "建议补做 B 闸门：python tools/design_board.py render --gate b --workspace %s，"
        "再由用户本人执行 confirm --gate b --apply。"
        % (scope, workspace)
    )


def _evaluate_question_target(target_abs, question_dir, warnings):
    """``questions/<qid>/`` 下的交付代码：先看该问的 B 板，再看 A 板。"""
    gate_b_path = _find_gate_b_for(question_dir)
    if gate_b_path is not None:
        workspace = os.path.dirname(gate_b_path)
        board = _load_board(gate_b_path)
        if _board_is_confirmed_payload(board):
            return True, ""
        return False, _deny_reason_gate_b(
            target_abs,
            workspace,
            "该问的 design_board_gate_b.json 存在但未确认（questions[] 的 confirmed 必须全为 true）",
        )

    board_path = _find_named_file_upward(question_dir, BOARD_FILENAME)
    if board_path is None:
        return False, _deny_reason_gate_a(target_abs, question_dir)

    workspace = os.path.dirname(board_path)
    board = _load_board(board_path)
    if _board_is_new_flow(board):
        return False, _deny_reason_gate_b(
            target_abs,
            workspace,
            "A 板已是 schema_version >= 2 的新流程，但该问还没有 design_board_gate_b.json",
        )
    if not _board_is_confirmed_payload(board):
        return False, _deny_reason_gate_a(target_abs, workspace)

    warnings.append(_legacy_warning(workspace, "questions/%s" % os.path.basename(question_dir)))
    return True, ""


def _evaluate_root_target(target_abs, warnings):
    """工作区根（或其它位置）的交付代码：A 板必须确认，新流程还要同级 B 板。"""
    start = target_abs if os.path.isdir(target_abs) else os.path.dirname(target_abs)
    board_path = _find_named_file_upward(start, BOARD_FILENAME)
    if board_path is None:
        return False, _deny_reason_gate_a(target_abs, start)

    workspace = os.path.dirname(board_path)
    board = _load_board(board_path)
    if not _board_is_confirmed_payload(board):
        return False, _deny_reason_gate_a(target_abs, workspace)

    if _board_is_new_flow(board):
        gate_b_path = os.path.join(workspace, GATE_B_FILENAME)
        if not os.path.isfile(gate_b_path):
            return False, _deny_reason_gate_b(
                target_abs,
                workspace,
                "A 板已是 schema_version >= 2 的新流程，但同级还没有 design_board_gate_b.json",
            )
        if not _board_is_confirmed_payload(_load_board(gate_b_path)):
            return False, _deny_reason_gate_b(
                target_abs, workspace, "design_board_gate_b.json 存在但未确认"
            )
        return True, ""

    warnings.append(_legacy_warning(workspace, "工作区根"))
    return True, ""


def _evaluate_target(target_abs, warnings):
    """判定单个受保护目标，返回 (是否放行, 拒绝文案)。"""
    if _is_trials_target(target_abs):
        return True, ""
    question_dir = _question_dir(target_abs)
    if question_dir is not None:
        return _evaluate_question_target(target_abs, question_dir, warnings)
    return _evaluate_root_target(target_abs, warnings)


def _allow(style):
    """放行。Cursor 需要返回符合 schema 的 allow；Claude Code 空输出即可。"""
    if style == "cursor":
        # 只输出 Cursor 权限 hook 明确接受的字段，避免额外字段导致 schema 不匹配
        _write_stdout(json.dumps({"permission": "allow"}, ensure_ascii=False) + "\n")
    return 0


def _deny(display_path, style, reason=None):
    """拒绝。Cursor 用 exit 2 + stderr；Claude Code 用 JSON deny + exit 0。

    ``reason`` 为空时退回 A 闸门文案（fail-closed 兜底路径用得上）。
    """
    if not reason:
        reason = _deny_reason_gate_a(display_path, os.path.dirname(display_path))
    if style == "cursor":
        _warn("[design-gate] " + reason)
        return 2
    payload = json.dumps(
        {"decision": "deny", "reason": reason},
        ensure_ascii=False,
    )
    try:
        _write_stdout(payload + "\n")
    except Exception as exc:  # 连 deny JSON 都写不出去时，退回 exit 2
        _warn("[design-gate] hook error: 无法输出 deny JSON: %s" % (exc,))
        return 2
    return 0


def main():
    style = _hook_style()
    raw = _read_stdin_text()

    if _bypass_enabled():
        _warn(
            "[design-gate] 警告：MM_GATE_BYPASS=1，已跳过设计闸门检查。"
            "仅建议在“用户明确要求手动修改”的场景临时使用。"
        )
        return _allow(style)

    # 第一阶段：解析事件、提取路径。任何异常都 fail-open（还不知道目标）。
    try:
        event = _parse_event(raw)
        targets, base_dir = _extract_targets(event)
    except Exception as exc:
        _warn("[design-gate] hook error: %s" % (exc,))
        return _allow(style)

    try:
        protected = [target for target in targets if _is_protected(target)]
    except Exception as exc:  # pragma: no cover - 防御性分支
        _warn("[design-gate] hook error: %s" % (exc,))
        return _allow(style)

    if not protected:
        return _allow(style)

    # 第二阶段：已经确定目标受保护。从这里开始任何异常都 fail-closed。
    try:
        warnings = []
        for target in protected:
            target_abs = _resolve_target(target, base_dir)
            allowed, reason = _evaluate_target(target_abs, warnings)
            if not allowed:
                return _deny(target_abs, style, reason)
        # 放行也要把"旧工作区单闸门兼容"的提醒说清楚，不能默默吃掉。
        for message in warnings:
            _warn("[design-gate] 警告：" + message)
        return _allow(style)
    except Exception as exc:
        _warn("[design-gate] hook error: %s" % (exc,))
        try:
            fallback = _resolve_target(protected[0], base_dir)
        except Exception:
            fallback = protected[0]
        return _deny(fallback, style)


if __name__ == "__main__":
    sys.exit(main())
