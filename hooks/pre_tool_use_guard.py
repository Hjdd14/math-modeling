#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设计闸门宿主 hook（L5 防线）：写 solution 代码前检查决策板是否已确认。

在 AI 通过宿主工具写入 ``solution.py`` / ``solution.m`` /
``solution_tests.py`` / ``solution_tests.m`` 之前，向上查找目标文件所在
工作区里的 ``design_board.json``；只有板已确认时才放行。

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


def _find_board_for(target_abs):
    """从目标文件所在目录向上最多 5 层找 design_board.json。"""
    start = target_abs if os.path.isdir(target_abs) else os.path.dirname(target_abs)
    current = start
    for _ in range(MAX_UPWARD_LEVELS + 1):
        candidate = os.path.join(current, BOARD_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _board_is_confirmed(board_path):
    """读取并判断 board 是否已确认。

    兼容两种写法（满足其一即可）：
    * 顶层 ``confirmed`` 为 true；
    * ``questions`` 非空，且每个 question 的 ``confirmed`` 都为 true。
    """
    with open(board_path, "r", encoding="utf-8-sig") as handle:
        board = json.load(handle)
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


def _deny_reason(display_path):
    return (
        "设计闸门未通过：%s 所在工作区还没有已确认的 design_board.json。"
        "请先运行 python tools/design_board.py render 并让用户本人执行 confirm --apply。"
        % (display_path,)
    )


def _allow(style):
    """放行。Cursor 需要返回符合 schema 的 allow；Claude Code 空输出即可。"""
    if style == "cursor":
        # 只输出 Cursor 权限 hook 明确接受的字段，避免额外字段导致 schema 不匹配
        _write_stdout(json.dumps({"permission": "allow"}, ensure_ascii=False) + "\n")
    return 0


def _deny(display_path, style):
    """拒绝。Cursor 用 exit 2 + stderr；Claude Code 用 JSON deny + exit 0。"""
    reason = _deny_reason(display_path)
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
        for target in protected:
            target_abs = _resolve_target(target, base_dir)
            board_path = _find_board_for(target_abs)
            if board_path is None or not _board_is_confirmed(board_path):
                return _deny(target_abs, style)
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
