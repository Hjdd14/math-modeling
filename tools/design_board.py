#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模决策板工具：渲染、回写、状态与人工确认"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import html
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BOARD_FILE = "design_board.json"
MD_FILE = "design_board.md"
HTML_FILE = "design_board.html"
XLSX_FILE = "design_choices.xlsx"
ROUNDS_DIR = "design_rounds"
SUPPORTED_FORMATS = ("md", "html", "xlsx", "all")
# 本地回传服务器（serve）相关常量
DEFAULT_SERVE_PORT = 8765
MAX_SUBMIT_BYTES = 1_000_000
# 页面里留这个占位符，serve 每次请求用它注入本次会话的一次性 token。
# render 落盘时不替换，所以磁盘上的 HTML 里它是字面量，不会被当成可用凭证。
SUBMIT_TOKEN_MARKER = "__MM_SUBMIT_TOKEN__"
ROUND_NAME_PATTERN = re.compile(r"^round_(\d+)\.json$")
CONFIRM_CODE_ENV = "MM_CONFIRM_CODE"
MIN_NO_CHANGE_ROUNDS = 2

# 内容哈希口径（重要）：
# 1) 按约定先移除 board_sha256；
# 2) 再移除本工具自己回写的派生字段（confirm_code 等）与用户状态字段。
# 原因：confirm_code = board_sha256[:4].upper() 要回写到同一份 JSON。若 confirm_code
# 也参与哈希，就形成「哈希 -> 确认码 -> 回写 -> 哈希变化」的自指循环：render 不再幂等，
# status 的哈希一致性判据永远为假，confirm 也永远无法通过。
# 因此内容哈希只锚定"方案内容"（题意、导图、每题的候选与其理由/风险/试算/来源），
# 用于发现"render 之后偷偷改候选或导图"这类篡改；用户选择与确认状态由回执/时间线锚定。
HASH_EXCLUDED_TOP_LEVEL = frozenset({
    "board_sha256",
    "confirm_code",
    "confirm_attested",
    "confirmed",
    "confirmed_at",
    "confirmed_by",
    "receipt_origin",
    "receipt_nonce",
    "revision",
    "no_change_rounds",
    "history",
    "skip_reason",
})
HASH_EXCLUDED_QUESTION_LEVEL = frozenset({
    "user_choice",
    "user_comment",
    "user_locked",
    "confirmed",
})

TIER_LABELS = {
    "recommended": "🟢 推荐",
    "alternative": "⚪ 备选",
    "backup": "⚪ 备选",
    "rejected": "⛔ 不推荐",
    "excluded": "⛔ 不推荐",
}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def workspace_root(workspace: str) -> Path:
    root = Path(workspace)
    if not root.exists():
        raise ValueError(f"工作区不存在: {root}")
    if not root.is_dir():
        raise ValueError(f"工作区不是目录: {root}")
    return root.resolve()


# ---------------------------------------------------------------------------
# 读入 / 原子写
# ---------------------------------------------------------------------------


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"文件不存在: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败({path}): {exc}") from None
    except OSError as exc:
        raise ValueError(f"读取失败({path}): {exc}") from None


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temp, path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _atomic_write_json(path: Path, payload: dict) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# 板内容校验、哈希与确认码
# ---------------------------------------------------------------------------


def validate_board(payload: object, *, for_render: bool = False) -> list[str]:
    """返回缺失/非法字段清单；空列表表示通过。"""
    if not isinstance(payload, dict):
        return ["顶层必须是 JSON 对象"]
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions 必须是非空数组"]
    problems: list[str] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            problems.append(f"questions[{index}] 必须是对象")
            continue
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            problems.append(f"questions[{index}].id 缺失")
            question_id = f"#{index}"
        options = question.get("options")
        if not isinstance(options, list) or not options:
            problems.append(f"{question_id}.options 必须是非空数组")
            continue
        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                problems.append(f"{question_id}.options[{option_index}] 必须是对象")
                continue
            if not isinstance(option.get("id"), str) or not option.get("id", "").strip():
                problems.append(f"{question_id}.options[{option_index}].id 缺失")
            if not isinstance(option.get("name"), str) or not option.get("name", "").strip():
                problems.append(f"{question_id}.options[{option_index}].name 缺失")
    if for_render:
        mindmap = payload.get("mindmap")
        source = mindmap.get("source") if isinstance(mindmap, dict) else None
        if not isinstance(source, str) or not source.strip():
            problems.append("mindmap.source 缺失（渲染导图必需）")
    return problems


def load_board(root: Path, *, for_render: bool = False) -> dict:
    path = root / BOARD_FILE
    if not path.is_file():
        raise ValueError(f"缺少 {BOARD_FILE}: {path}")
    payload = read_json(path)
    problems = validate_board(payload, for_render=for_render)
    if problems:
        raise ValueError(f"{BOARD_FILE} 缺少关键字段: " + "；".join(problems))
    return payload  # type: ignore[return-value]


def _hash_payload(payload: dict) -> dict:
    cleaned = {key: value for key, value in payload.items() if key not in HASH_EXCLUDED_TOP_LEVEL}
    questions = cleaned.get("questions")
    if isinstance(questions, list):
        cleaned["questions"] = [
            {key: value for key, value in question.items() if key not in HASH_EXCLUDED_QUESTION_LEVEL}
            if isinstance(question, dict)
            else question
            for question in questions
        ]
    return cleaned


def compute_board_sha256(payload: dict) -> str:
    canonical = json.dumps(
        _hash_payload(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_confirm_code(board_sha256: str) -> str:
    return board_sha256[:4].upper()


# ---------------------------------------------------------------------------
# design_rounds 回执
# ---------------------------------------------------------------------------


def rounds_dir(root: Path) -> Path:
    return root / ROUNDS_DIR


def list_round_files(root: Path) -> list[tuple[int, Path]]:
    directory = rounds_dir(root)
    if not directory.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        match = ROUND_NAME_PATTERN.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry))
    found.sort(key=lambda item: item[0])
    return found


# ---------------------------------------------------------------------------
# Markdown 渲染辅助
# ---------------------------------------------------------------------------


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _clip(value: object, limit: int = 40) -> str:
    text = " ".join(_as_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "…"


def _cell(value: object) -> str:
    text = _as_text(value)
    text = text.replace("\r", " ").replace("\n", "<br>").replace("|", "\\|")
    return text.strip() or "—"


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(_cell(header) for header in headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return lines


def _options(question: dict) -> list[dict]:
    options = question.get("options")
    if not isinstance(options, list):
        return []
    return [option for option in options if isinstance(option, dict)]


def _find_option(question: dict, option_id: object) -> dict | None:
    target = str(option_id) if option_id is not None else ""
    for option in _options(question):
        if str(option.get("id")) == target:
            return option
    return None


def _has_choice(question: dict) -> bool:
    choice = question.get("user_choice")
    return isinstance(choice, str) and bool(choice.strip())


def _board_round(board: dict) -> int:
    for key in ("revision", "round"):
        value = board.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    history = board.get("history")
    if isinstance(history, list) and history:
        return len(history) + 1
    return 1


def _change_summary(board: dict) -> str:
    history = board.get("history")
    if isinstance(history, list) and history and isinstance(history[-1], dict):
        last = history[-1]
        changes = last.get("changes")
        count = len(changes) if isinstance(changes, list) else 0
        round_no = last.get("round")
        label = f"第 {round_no} 轮" if isinstance(round_no, int) else "上一轮"
        return f"{label}无改动（0 项）" if count == 0 else f"{label}共 {count} 项改动"
    return "首次渲染，暂无历史轮次"


def _question_label(question: dict) -> str:
    question_id = _as_text(question.get("id")) or "未命名小问"
    goal = _clip(question.get("goal"), 28)
    return f"{question_id} · {goal}" if goal else question_id


def _source_text(option: dict) -> str:
    source_ref = option.get("source_ref")
    if not isinstance(source_ref, dict) or not source_ref:
        return "未登记来源"
    parts = [
        f"{_as_text(source_ref.get('type')) or '未标类型'} {_as_text(source_ref.get('ref')) or '未编号'}",
    ]
    if source_ref.get("tier"):
        parts.append(f"tier={_as_text(source_ref.get('tier'))}")
    verified = source_ref.get("verified")
    if verified is True:
        parts.append("已核验")
    elif verified is False:
        reason = source_ref.get("unverified_reason")
        parts.append(f"未核验（{_clip(reason, 40)}）" if reason else "未核验（未给出原因）")
    if source_ref.get("note"):
        parts.append(_clip(source_ref.get("note"), 80))
    return "；".join(parts)


def _seconds_text(trial: dict) -> str:
    seconds = trial.get("seconds")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
        return f"{seconds:g} s"
    return ""


def _trial_output_text(trial: dict) -> str:
    output = trial.get("output")
    if isinstance(output, dict):
        return ", ".join(f"{key}={_as_text(value)}" for key, value in output.items())
    if output not in (None, ""):
        return _as_text(output)
    return ""


def _trial_table_text(option: dict) -> str:
    trial = option.get("mini_trial")
    if not isinstance(trial, dict):
        return "未试算"
    parts: list[str] = []
    output_text = _trial_output_text(trial)
    if output_text:
        parts.append(output_text)
    seconds_text = _seconds_text(trial)
    if seconds_text:
        parts.append(seconds_text)
    return "；".join(parts) or "未试算"


def _trial_detail_text(option: dict) -> str:
    trial = option.get("mini_trial")
    if not isinstance(trial, dict):
        return "未试算（候选缺 mini_trial，评委会追问为什么没验证）"
    parts: list[str] = []
    if trial.get("sample"):
        parts.append(f"样本：{_clip(trial.get('sample'), 40)}")
    output_text = _trial_output_text(trial)
    if output_text:
        parts.append(output_text)
    seconds_text = _seconds_text(trial)
    if seconds_text:
        parts.append(f"耗时 {seconds_text}")
    if trial.get("reproduce_cmd"):
        parts.append(f"复跑：`{_as_text(trial.get('reproduce_cmd'))}`")
    return "；".join(parts) or "未试算"


def _tier_label(option: dict) -> str:
    tier = _as_text(option.get("tier"))
    return TIER_LABELS.get(tier, "🟡 待评估")


def render_markdown(board: dict) -> str:
    questions = [question for question in board.get("questions", []) if isinstance(question, dict)]
    confirm_code = _as_text(board.get("confirm_code"))
    confirmed = bool(board.get("confirmed"))
    lines: list[str] = [
        f"# 建模方案决策板 · 第 {_board_round(board)} 轮",
        "",
        f"> **确认码：{confirm_code}**",
        ">",
        f"> 运行 `python tools/design_board.py confirm --workspace . --apply` 时需要输入上面这 4 位确认码。",
        ">",
        f"> **状态**：{'✅ 已确认' if confirmed else '⏳ 待确认'}",
    ]
    if confirmed:
        lines.append(
            f"> **确认信息**：{_as_text(board.get('confirmed_at')) or '未知时间'} · by {_as_text(board.get('confirmed_by')) or '未知来源'}"
        )
    lines.extend([
        ">",
        f"> **变更摘要**：{_change_summary(board)}",
    ])
    problem_summary = board.get("problem_summary")
    if isinstance(problem_summary, dict) and problem_summary.get("title"):
        lines.append(">")
        lines.append(f"> **题目**：{_clip(problem_summary.get('title'), 60)}")
    lines.extend(["", "---", ""])

    # 一、结论速览
    lines.extend(["## 一、结论速览", ""])
    overview_rows: list[list[object]] = []
    for question in questions:
        option = _find_option(question, question.get("user_choice"))
        if option is None:
            overview_rows.append([_question_label(question), "（待选择）", "—"])
        else:
            overview_rows.append([
                _question_label(question),
                f"**{_as_text(option.get('id'))} {_as_text(option.get('name'))}**",
                _clip(option.get("rationale"), 40) or "（未给出理由）",
            ])
    lines.extend(_table(["小问", "选定方案", "一句话理由"], overview_rows))
    lines.extend(["", "---", ""])

    # 二、模型结构总览
    mindmap = board.get("mindmap") if isinstance(board.get("mindmap"), dict) else {}
    lines.extend([
        "## 二、模型结构总览",
        "",
        "```mermaid",
        _as_text(mindmap.get("source")).strip(),
        "```",
        "",
        "> 导图只读：节点直接来自 `design_board.json` 的 `mindmap.source`；要改结构请改 JSON 后重新 `render`。",
        "",
        "---",
        "",
    ])

    # 三、待你决定
    undecided = [question for question in questions if not _has_choice(question)]
    pending_raw = board.get("pending_decisions")
    pending_items = [_as_text(item) for item in pending_raw] if isinstance(pending_raw, list) else []
    lines.extend([
        f"## 三、待你决定（{len(undecided) + len(pending_items)} 项）",
        "",
        "> `- [x]` 标记的是 AI 推荐项（`tier: recommended`），不是你的最终选择；最终选择以 `user_choice` 为准。",
        "",
    ])
    if pending_items:
        lines.append("**附加待决项（`pending_decisions`）**：")
        lines.append("")
        for item in pending_items:
            lines.append(f"- {item}")
        lines.append("")
    for question in questions:
        lines.extend([f"### {_question_label(question)}", ""])
        if not _has_choice(question):
            lines.extend(["> 本题尚未选择。", ""])
        for option in _options(question):
            recommended = _as_text(option.get("tier")) == "recommended"
            tags: list[str] = []
            if recommended:
                tags.append("推荐 ⭐")
            if str(option.get("id")) == str(question.get("user_choice")):
                tags.append("你当前的选择")
            if question.get("user_locked"):
                tags.append("已锁定")
            suffix = f"（{'；'.join(tags)}）" if tags else ""
            lines.append(
                f"- [{'x' if recommended else ' '}] "
                f"**{_as_text(option.get('id'))} {_as_text(option.get('name'))}**{suffix}"
            )
            lines.append(f"  - 理由：{_clip(option.get('rationale'), 120) or '（未给出理由）'}")
            lines.append(f"  - 来源：{_source_text(option)}")
            lines.append(f"  - 试算：{_trial_detail_text(option)}")
            lines.append(f"  - 复杂度：{_clip(option.get('complexity'), 80) or '（未给出）'}")
            lines.append(f"  - 风险：{_clip(option.get('risk'), 120) or '（未给出）'}")
            dependencies = option.get("dependencies")
            lines.append(f"  - 依赖：{_as_text(dependencies) if dependencies else '无'}")
        comment = question.get("user_comment")
        if isinstance(comment, str) and comment.strip():
            lines.extend(["", f"**你的批注**：{comment.strip()}"])
        lines.append("")
    lines.extend(["---", ""])

    # 四、候选方案对比
    lines.extend([
        "## 四、候选方案对比",
        "",
        "> 这是做决策的地方：先看推荐度与主要风险，再看试算结果是否为真实数值（应附复跑命令）。",
        "",
    ])
    for question in questions:
        lines.extend([f"### {_question_label(question)}", ""])
        comparison_rows: list[list[object]] = []
        for option in _options(question):
            chosen = str(option.get("id")) == str(question.get("user_choice"))
            name_cell = f"{_as_text(option.get('id'))} {_as_text(option.get('name'))}"
            if chosen:
                name_cell = f"**{name_cell}** ✅"
            comparison_rows.append([
                name_cell,
                _clip(option.get("rationale"), 28) or "—",
                _clip(option.get("complexity"), 28) or "—",
                _clip(option.get("risk"), 28) or "—",
                _clip(_trial_table_text(option), 48) or "—",
                _tier_label(option),
            ])
        lines.extend(_table(["方案", "一句话理由", "复杂度", "主要风险", "试算结果", "推荐度"], comparison_rows))
        lines.append("")
    lines.extend(["---", ""])

    # 五、已锁定
    lines.extend(["## 五、已锁定（AI 不得推翻）", ""])
    locked_questions = [question for question in questions if question.get("user_locked")]
    if locked_questions:
        locked_rows: list[list[object]] = []
        for question in locked_questions:
            option = _find_option(question, question.get("user_choice"))
            locked_rows.append([
                _question_label(question),
                f"{_as_text(question.get('id'))} 模型选择",
                f"**{_as_text(option.get('id'))} {_as_text(option.get('name'))}**" if option else "（未选择）",
                _clip(question.get("user_comment"), 40) or "—",
            ])
        lines.extend(_table(["小问", "锁定项", "选择", "备注"], locked_rows))
    else:
        lines.append("暂无锁定项（所有 `user_locked` 均为 false）。")
    lines.extend(["", "---", ""])

    # 六、来源速查
    lines.extend([
        "## 六、来源速查",
        "",
        "<details>",
        "<summary>展开：各候选的来源、tier 与核验状态（默认折叠，避免淹没正文）</summary>",
        "",
    ])
    source_rows: list[list[object]] = []
    for question in questions:
        for option in _options(question):
            source_ref = option.get("source_ref") if isinstance(option.get("source_ref"), dict) else {}
            verified = source_ref.get("verified")
            verified_text = "✅" if verified is True else ("❌" if verified is False else "—")
            note = _clip(source_ref.get("note"), 60)
            if verified is False and source_ref.get("unverified_reason"):
                prefix = f"未核验原因：{_clip(source_ref.get('unverified_reason'), 40)}"
                note = f"{prefix}；{note}" if note else prefix
            source_rows.append([
                _question_label(question),
                f"{_as_text(option.get('id'))} {_as_text(option.get('name'))}",
                _as_text(source_ref.get("type")) or "—",
                _as_text(source_ref.get("ref")) or "—",
                _as_text(source_ref.get("tier")) or "—",
                verified_text,
                note or "—",
            ])
    if source_rows:
        lines.extend(_table(["小问", "方案", "来源类型", "编号", "tier", "已核验", "备注"], source_rows))
    else:
        lines.append("暂无来源登记。")
    lines.extend(["", "</details>", "", "---", ""])

    lines.append("<sub>本文件由 design_board.json 渲染生成，不是唯一真实来源。</sub>")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def _load_optional_view(name: str):
    """按需加载可选的视图模块。

    `design_board_html` / `design_board_xlsx` 是可选视图（html 只需要标准库，
    xlsx 需要 openpyxl）。做成懒加载的原因：只要用户不请求该格式，就不该因为
    缺 openpyxl 而让整个工具不可用。
    """
    import importlib

    for module_name in (f"tools.design_board_{name}", f"design_board_{name}"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    return None


def render_board(workspace: str, fmt: str = "md") -> dict:
    root = workspace_root(workspace)
    board = load_board(root, for_render=True)
    board_sha256 = compute_board_sha256(board)
    confirm_code = derive_confirm_code(board_sha256)
    board["board_sha256"] = board_sha256
    board["confirm_code"] = confirm_code
    _atomic_write_json(root / BOARD_FILE, board)

    targets = SUPPORTED_FORMATS[:-1] if fmt == "all" else (fmt,)
    written: list[str] = []
    skipped: list[str] = []

    if "md" in targets:
        md_path = root / MD_FILE
        _atomic_write_text(md_path, render_markdown(board))
        written.append(str(md_path))

    if "html" in targets:
        html_module = _load_optional_view("html")
        if html_module is None:
            skipped.append("html: 缺少 tools/design_board_html.py")
        else:
            html_path = root / HTML_FILE
            _atomic_write_text(html_path, html_module.render_html(board))
            written.append(str(html_path))

    if "xlsx" in targets:
        xlsx_module = _load_optional_view("xlsx")
        if xlsx_module is None:
            skipped.append("xlsx: 缺少 tools/design_board_xlsx.py")
        else:
            try:
                written.append(str(xlsx_module.render_xlsx(board, root / XLSX_FILE)))
            except RuntimeError as exc:  # 缺 openpyxl
                skipped.append(f"xlsx: {exc}")

    result = {
        "action": "render",
        "workspace": str(root),
        "format": fmt,
        "path": written[0] if written else None,
        "written": written,
        "board_sha256": board_sha256,
        "confirm_code": confirm_code,
    }
    if skipped:
        result["skipped"] = skipped
    return result


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def _resolve_submission(root: Path, source: str) -> Path:
    candidate = Path(source)
    if candidate.is_absolute():
        if not candidate.is_file():
            raise ValueError(f"用户提交文件不存在: {candidate}")
        return candidate
    for base in (Path.cwd(), root):
        path = base / candidate
        if path.is_file():
            return path.resolve()
    raise ValueError(f"用户提交文件不存在: {source}（已尝试当前目录与工作区）")


def _question_index(board: dict) -> tuple[dict[str, tuple[int, dict]], dict[str, list[str]]]:
    index: dict[str, tuple[int, dict]] = {}
    option_ids: dict[str, list[str]] = {}
    questions = board.get("questions")
    if isinstance(questions, list):
        for position, question in enumerate(questions):
            if not isinstance(question, dict):
                continue
            question_id = _as_text(question.get("id"))
            index[question_id] = (position, question)
            option_ids[question_id] = [str(option.get("id")) for option in _options(question)]
    return index, option_ids


def _apply_question_updates(
    board: dict,
    decisions: dict[str, dict],
    comments: dict[str, str],
    changes: list[dict],
) -> None:
    index, option_ids = _question_index(board)
    for question_id, decision in decisions.items():
        if question_id not in index:
            raise ValueError(f"回执中的 question_id 不存在: {question_id}；可用: {', '.join(index)}")
        option_id = decision.get("option_id")
        position, question = index[question_id]
        old_choice = question.get("user_choice")
        if option_id is None:
            # 用户把某题清空：允许，但会让 ready_to_confirm 判据 3 不通过。
            if old_choice not in (None, ""):
                changes.append({
                    "path": f"questions[{position}].user_choice",
                    "from": old_choice,
                    "to": None,
                })
                question["user_choice"] = None
        elif option_id not in option_ids[question_id]:
            raise ValueError(
                f"option_id {option_id!r} 不存在于 {question_id} 的候选中；可用: {', '.join(option_ids[question_id])}"
            )
        elif str(old_choice) != str(option_id):
            changes.append({
                "path": f"questions[{position}].user_choice",
                "from": old_choice,
                "to": option_id,
            })
            question["user_choice"] = option_id
        if "locked" in decision and decision["locked"] is not None:
            new_locked = bool(decision["locked"])
            old_locked = bool(question.get("user_locked"))
            if new_locked != old_locked:
                changes.append({
                    "path": f"questions[{position}].user_locked",
                    "from": old_locked,
                    "to": new_locked,
                })
                question["user_locked"] = new_locked
        if "comment" in decision and decision["comment"] is not None:
            comments.setdefault(question_id, str(decision["comment"]))

    for question_id, new_comment in comments.items():
        if question_id not in index:
            raise ValueError(f"批注中的 question_id 不存在: {question_id}；可用: {', '.join(index)}")
        position, question = index[question_id]
        old_comment = question.get("user_comment")
        old_text = old_comment if isinstance(old_comment, str) else ""
        if new_comment == old_text:
            continue
        if not old_text.strip():
            changes.append({
                "path": f"questions[{position}].user_comment",
                "op": "added",
                "value": new_comment,
            })
        elif not new_comment.strip():
            changes.append({
                "path": f"questions[{position}].user_comment",
                "op": "removed",
                "from": old_text,
            })
        else:
            changes.append({
                "path": f"questions[{position}].user_comment",
                "op": "updated",
                "from": old_text,
                "to": new_comment,
            })
        question["user_comment"] = new_comment


def _parse_envelope(raw: dict, board: dict, changes: list[dict]) -> tuple[dict[str, dict], dict[str, str], str, str]:
    board_id = raw.get("board_id")
    current_board_id = board.get("board_id")
    if board_id and current_board_id and str(board_id) != str(current_board_id):
        raise ValueError(f"回执 board_id 与决策板不一致: {board_id} != {current_board_id}")

    decisions_raw = raw.get("decisions")
    if not isinstance(decisions_raw, list):
        raise ValueError("回执缺少 decisions 数组")
    decisions: dict[str, dict] = {}
    comments: dict[str, str] = {}
    for index, item in enumerate(decisions_raw):
        if not isinstance(item, dict):
            raise ValueError(f"decisions[{index}] 必须是对象，例如 {{\"question_id\": \"Q1\", \"option_id\": \"O1\"}}")
        question_id = item.get("question_id") or item.get("qid") or item.get("question")
        option_id = item.get("option_id") or item.get("option") or item.get("choice")
        if not question_id or not option_id:
            raise ValueError(f"decisions[{index}] 缺少 question_id 或 option_id")
        comment = item.get("comment", item.get("user_comment"))
        decisions[str(question_id)] = {
            "option_id": str(option_id),
            "comment": comment,
            "locked": item.get("locked", item.get("user_locked")),
        }

    comments_raw = raw.get("comments") or []
    if comments_raw is not None and not isinstance(comments_raw, list):
        raise ValueError("comments 必须是数组")
    for index, item in enumerate(comments_raw):
        if isinstance(item, dict):
            question_id = item.get("question_id") or item.get("qid")
            if not question_id:
                raise ValueError(f"comments[{index}] 缺少 question_id")
            text = item.get("comment") or item.get("text") or item.get("message") or ""
            comments[str(question_id)] = str(text)
        else:
            raise ValueError(
                f"comments[{index}] 必须是对象，例如 {{\"question_id\": \"Q1\", \"comment\": \"...\"}}"
            )

    origin = _as_text(raw.get("receipt_origin")) or "file-drop"
    nonce = _as_text(raw.get("receipt_nonce", raw.get("nonce")))
    return decisions, comments, origin, nonce


def _parse_board_submission(raw: dict, board: dict, changes: list[dict]) -> tuple[dict[str, dict], dict[str, str], str, str]:
    board_id = raw.get("board_id")
    current_board_id = board.get("board_id")
    if board_id and current_board_id and str(board_id) != str(current_board_id):
        raise ValueError(f"提交的 board_id 与当前决策板不一致: {board_id} != {current_board_id}")
    current_index, current_option_ids = _question_index(board)
    decisions: dict[str, dict] = {}
    comments: dict[str, str] = {}
    submitted_questions = raw.get("questions")
    if not isinstance(submitted_questions, list):
        raise ValueError("提交的 design_board.json 缺少 questions 数组")
    for submitted in submitted_questions:
        if not isinstance(submitted, dict):
            continue
        question_id = _as_text(submitted.get("id"))
        if question_id not in current_index:
            raise ValueError(f"提交中的 question_id 不存在: {question_id}；可用: {', '.join(current_index)}")
        if "user_choice" in submitted:
            choice = submitted.get("user_choice")
            if choice is None or (isinstance(choice, str) and not choice.strip()):
                decisions[question_id] = {"option_id": None, "comment": submitted.get("user_comment")}
            else:
                if str(choice) not in current_option_ids[question_id]:
                    raise ValueError(
                        f"option_id {choice!r} 不存在于 {question_id} 的候选中；可用: {', '.join(current_option_ids[question_id])}"
                    )
                decisions[question_id] = {
                    "option_id": str(choice),
                    "comment": submitted.get("user_comment"),
                    "locked": submitted.get("user_locked"),
                }
        elif "user_comment" in submitted:
            comments[question_id] = str(submitted.get("user_comment") or "")
    origin = _as_text(raw.get("receipt_origin")) or "file-drop"
    nonce = _as_text(raw.get("receipt_nonce", raw.get("nonce")))
    return decisions, comments, origin, nonce


def ingest_submission(workspace: str, source: str) -> dict:
    root = workspace_root(workspace)
    board = load_board(root)
    submission_path = _resolve_submission(root, source)

    # xlsx 回读：用户在 Excel 里改了「当前选择」/「批注」，先转成回执信封再走同一套流程。
    if submission_path.suffix.lower() in {".xlsx", ".xlsm"}:
        xlsx_module = _load_optional_view("xlsx")
        if xlsx_module is None:
            raise ValueError("回读 xlsx 需要 tools/design_board_xlsx.py")
        raw = xlsx_module.read_submission_xlsx(submission_path, board)
        if not isinstance(raw, dict):
            raise ValueError(f"xlsx 回读结果必须是对象: {submission_path}")
    else:
        raw = read_json(submission_path)
    if not isinstance(raw, dict):
        raise ValueError(f"用户提交必须是 JSON 对象或 xlsx: {submission_path}")

    return apply_submission(root, raw, board=board)


def apply_submission(root: Path, raw: dict, *, board: dict | None = None) -> dict:
    """把一份**已解析**的回执对象落盘（JSON 回执、xlsx 回读、HTTP POST 共用这条路径）。

    所有入口共用同一套校验与落盘逻辑，避免"网页提交绕过校验"这类分叉：
    `serve` 收到 POST 后也只调这里，不自己写 `design_rounds/` 或 `design_board.json`。
    """
    if board is None:
        board = load_board(root)

    changes: list[dict] = []
    if isinstance(raw.get("decisions"), list):
        decisions, comments, origin, nonce = _parse_envelope(raw, board, changes)
    elif isinstance(raw.get("questions"), list):
        decisions, comments, origin, nonce = _parse_board_submission(raw, board, changes)
    else:
        raise ValueError(
            "无法识别用户提交：既不是完整 design_board.json（缺 questions），也不是回执信封（缺 decisions）"
        )

    _apply_question_updates(board, decisions, comments, changes)

    round_files = list_round_files(root)
    round_number = (round_files[-1][0] if round_files else 0) + 1
    at = now_local_iso()
    user_edited = bool(changes)
    current_sha256 = _as_text(board.get("board_sha256")) or compute_board_sha256(board)
    no_change_rounds = 0 if changes else int(board.get("no_change_rounds") or 0) + 1
    revision = int(board.get("revision") or 0) + 1

    board["no_change_rounds"] = no_change_rounds
    board["revision"] = revision
    history = board.get("history")
    if not isinstance(history, list):
        history = []
    history.append({
        "round": round_number,
        "at": at,
        "board_sha256": current_sha256,
        "user_edited": user_edited,
        "changes": changes,
    })
    board["history"] = history

    round_payload = {
        "round": round_number,
        "at": at,
        "board_id": _as_text(board.get("board_id")),
        "board_sha256": current_sha256,
        "user_edited": user_edited,
        "changes": changes,
        "receipt_origin": origin,
        "receipt_nonce": nonce,
    }
    round_path = rounds_dir(root) / f"round_{round_number:03d}.json"
    _atomic_write_json(round_path, round_payload)
    _atomic_write_json(root / BOARD_FILE, board)

    return {
        "action": "ingest",
        "workspace": str(root),
        "board_id": _as_text(board.get("board_id")),
        "revision": revision,
        "round": round_number,
        "path": str(round_path),
        "user_edited": user_edited,
        "changes": changes,
        "no_change_rounds": no_change_rounds,
        "receipt_origin": origin,
        "receipt_nonce": nonce,
    }


# ---------------------------------------------------------------------------
# 收敛判据 / status
# ---------------------------------------------------------------------------


def _round_detail(round_files: list[tuple[int, Path]], index: int) -> str:
    number, path = round_files[index]
    return f"round_{number:03d}.json"


def evaluate_readiness(root: Path, board: dict) -> dict:
    round_files = list_round_files(root)
    checks: list[dict] = []
    blocking: list[str] = []

    no_change_raw = board.get("no_change_rounds")
    no_change_rounds = no_change_raw if isinstance(no_change_raw, int) and not isinstance(no_change_raw, bool) else 0
    no_change_ok = no_change_rounds >= MIN_NO_CHANGE_ROUNDS
    checks.append({
        "name": "no_change_rounds",
        "passed": no_change_ok,
        "detail": f"no_change_rounds={no_change_rounds}（需 ≥ {MIN_NO_CHANGE_ROUNDS}）",
    })
    if not no_change_ok:
        blocking.append(f"连续无修改轮次不足（{no_change_rounds}/{MIN_NO_CHANGE_ROUNDS}）")

    last_payload: object = None
    last_error = ""
    if round_files:
        try:
            last_payload = read_json(round_files[-1][1])
        except ValueError as exc:
            last_error = str(exc)
    if isinstance(last_payload, dict) and last_payload.get("user_edited") is False:
        last_round_ok = True
        last_detail = f"最后一轮 {_round_detail(round_files, -1)} 的 user_edited=false"
    elif not round_files:
        last_round_ok = False
        last_detail = "缺少 design_rounds/round_NNN.json 回执"
    elif last_error:
        last_round_ok = False
        last_detail = f"最后一轮回执读取失败：{last_error}"
    else:
        last_round_ok = False
        last_detail = f"最后一轮 {_round_detail(round_files, -1)} 的 user_edited 不是 false"
    checks.append({"name": "last_round_not_edited", "passed": last_round_ok, "detail": last_detail})
    if not last_round_ok:
        blocking.append(last_detail)

    questions = [question for question in board.get("questions", []) if isinstance(question, dict)]
    undecided = [_as_text(question.get("id")) for question in questions if not _has_choice(question)]
    invalid = [
        _as_text(question.get("id"))
        for question in questions
        if _has_choice(question) and _find_option(question, question.get("user_choice")) is None
    ]
    decided_ok = bool(questions) and not undecided and not invalid
    detail_parts: list[str] = []
    if undecided:
        detail_parts.append(f"未选择的小问: {', '.join(undecided)}")
    if invalid:
        detail_parts.append(f"user_choice 不是有效候选的小问: {', '.join(invalid)}")
    checks.append({
        "name": "all_questions_decided",
        "passed": decided_ok,
        "detail": "；".join(detail_parts) or "所有小问均已选择有效候选",
    })
    if not decided_ok:
        blocking.append("；".join(detail_parts) or "决策板没有questions")

    pending_raw = board.get("pending_decisions", [])
    pending_ok = isinstance(pending_raw, list) and len(pending_raw) == 0
    checks.append({
        "name": "no_pending_decisions",
        "passed": pending_ok,
        "detail": "pending_decisions 为空" if pending_ok else f"仍有 {len(pending_raw) if isinstance(pending_raw, list) else '未知数量'} 项待决",
    })
    if not pending_ok:
        blocking.append("pending_decisions 不为空")

    stored_sha256 = board.get("board_sha256")
    current_sha256 = compute_board_sha256(board)
    if not isinstance(stored_sha256, str) or not stored_sha256:
        hash_ok = False
        hash_detail = "缺少 board_sha256（请先运行 render）"
    elif stored_sha256 == current_sha256:
        hash_ok = True
        hash_detail = "board_sha256 与当前内容哈希一致"
    else:
        hash_ok = False
        hash_detail = (
            f"board_sha256 与当前内容哈希不一致：存储 {stored_sha256[:12]}…，当前 {current_sha256[:12]}…"
        )
    checks.append({"name": "board_hash_matches", "passed": hash_ok, "detail": hash_detail})
    if not hash_ok:
        blocking.append(hash_detail)

    ready = all(check["passed"] for check in checks)
    return {
        "ready": ready,
        "checks": checks,
        "blocking": blocking,
        "current_sha256": current_sha256,
        "round_files": round_files,
    }


def board_status(workspace: str) -> dict:
    root = workspace_root(workspace)
    board = load_board(root)
    readiness = evaluate_readiness(root, board)
    questions: list[dict] = []
    for question in board.get("questions", []):
        if not isinstance(question, dict):
            continue
        option = _find_option(question, question.get("user_choice"))
        questions.append({
            "id": _as_text(question.get("id")),
            "user_choice": question.get("user_choice"),
            "option_name": _as_text(option.get("name")) if option else None,
            "confirmed": bool(question.get("confirmed")),
        })
    pending = board.get("pending_decisions")
    return {
        "action": "status",
        "workspace": str(root),
        "board_id": _as_text(board.get("board_id")),
        "revision": board.get("revision", 0),
        "confirmed": bool(board.get("confirmed")),
        "no_change_rounds": board.get("no_change_rounds", 0),
        "pending_decisions": pending if isinstance(pending, list) else [],
        "questions": questions,
        "confirm_code": _as_text(board.get("confirm_code")),
        "rounds": len(readiness["round_files"]),
        "ready_to_confirm": readiness["ready"],
    }


# ---------------------------------------------------------------------------
# confirm
# ---------------------------------------------------------------------------


def _is_real_terminal() -> bool:
    """判断当前是否真的连着交互式控制台。

    只在 Windows 上有个坑：`subprocess.DEVNULL` 把 stdin 接到 NUL，
    而 CRT 的 `isatty(NUL)` 返回 True。此时 getpass 会走 msvcrt 读控制台
    的分支，在无控制台的进程里永久阻塞。因此额外要求 stdout 也是终端
    （真实交互时两者同时为 tty；`echo code | tool`、`> log.txt` 都会被剔除）。
    """
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def _prompt_confirm_code() -> str:
    """读取确认码。

    交互式终端下用 getpass 隐藏回显；管道 / 重定向 / CI 下直接读一行 stdin。
    """
    prompt = "请输入你在决策板上看到的 4 位确认码: "
    if not _is_real_terminal():
        try:
            value = sys.stdin.readline()
        except (EOFError, OSError, ValueError) as exc:
            raise ValueError(
                "无法读取确认码（交互式输入不可用）：可改用 MM_CONFIRM_CODE 环境变量或 --skip-interactive"
            ) from None
        if not value or not value.strip():
            raise ValueError(
                "无法读取确认码（标准输入已关闭或为空）：可改用 MM_CONFIRM_CODE 环境变量或 --skip-interactive"
            )
        return value.strip()
    try:
        return getpass.getpass(prompt)
    except (EOFError, OSError, getpass.GetPassWarning) as exc:
        raise ValueError(
            "无法读取确认码（交互式输入不可用）：可改用 MM_CONFIRM_CODE 环境变量或 --skip-interactive"
        ) from exc
    except KeyboardInterrupt:
        raise ValueError("用户取消输入确认码，未写入任何确认字段") from None


def confirm_board(workspace: str, apply: bool = False, skip_interactive: bool = False, reason: str = "") -> dict:
    root = workspace_root(workspace)
    board = load_board(root)
    readiness = evaluate_readiness(root, board)
    confirm_code = _as_text(board.get("confirm_code"))

    result: dict = {
        "action": "confirm",
        "apply": bool(apply),
        "workspace": str(root),
        "board_id": _as_text(board.get("board_id")),
        "confirm_code": confirm_code,
        "ready_to_confirm": readiness["ready"],
        "checks": readiness["checks"],
        "blocking": readiness["blocking"],
    }

    if not apply:
        result["message"] = (
            "满足全部收敛判据，可执行 confirm --apply。" if readiness["ready"]
            else "尚未满足收敛判据，confirm --apply 会被拒绝。"
        )
        result["hint"] = (
            f"确认码：{confirm_code}（在 design_board.md 顶部也能看到同一串；"
            "也可用 confirm --apply --skip-interactive 跳过交互，但会留下 confirm_not_attested 痕迹）"
        )
        return result

    if not readiness["ready"]:
        raise ValueError("未满足收敛判据，拒绝写入确认字段：" + ("；".join(readiness["blocking"]) or "原因未知"))
    if not confirm_code:
        raise ValueError("决策板缺少 confirm_code，请先运行 render")

    # 优先级：--skip-interactive（显式 flag）> MM_CONFIRM_CODE（CI 环境）> 交互式输入。
    if skip_interactive:
        confirmed_by = "user_non_interactive"
        confirmed_attested = False
        receipt_origin = "skipped_interactive"
    else:
        env_code = os.environ.get(CONFIRM_CODE_ENV)
        if env_code and env_code.strip():
            provided = env_code.strip()
            confirmed_by = "ci"
            receipt_origin = "ci"
        else:
            # 交互式确认**必须**连着真实终端。
            # 否则 `echo <码> | confirm --apply` 就能拿到 confirmed_by="user" +
            # confirm_attested=true，与真人操作完全无法区分——而 AI 只要读一眼
            # design_board.md 就知道那个码。把"非 TTY"这条路堵死之后，AI 只剩
            # 两条路：显式 --skip-interactive（留 confirm_not_attested 痕迹，
            # excellence 判 error）或手改 JSON 伪造字段（属更明确的造假行为）。
            if not _is_real_terminal():
                raise ValueError(
                    "确认必须在真实终端里进行：当前标准输入/输出不是交互式终端，"
                    "无法证明是人工确认。请在终端里亲自运行本命令；"
                    "若确需在无终端环境放行，请显式使用 --skip-interactive（会留下 "
                    "confirm_not_attested 痕迹，excellence 模式视为不通过）。"
                )
            provided = _prompt_confirm_code()
            confirmed_by = "user"
            receipt_origin = "interactive"
        if provided.strip().upper() != confirm_code.strip().upper():
            raise ValueError("确认码不正确，未写入任何确认字段")
        # 走在场确认码校验通过之后才置真：错码路径已在上面 raise，不会写 attested。
        confirmed_attested = True

    confirmed_at = now_utc_iso()
    board["confirmed"] = True
    questions = board.get("questions")
    if isinstance(questions, list):
        for question in questions:
            if isinstance(question, dict):
                question["confirmed"] = True
    board["confirmed_at"] = confirmed_at
    board["confirmed_by"] = confirmed_by
    board["receipt_origin"] = receipt_origin
    board["confirm_attested"] = confirmed_attested
    if skip_interactive and reason:
        board["skip_reason"] = reason
    _atomic_write_json(root / BOARD_FILE, board)

    result.update({
        "confirmed": True,
        "confirmed_at": confirmed_at,
        "confirmed_by": confirmed_by,
        "confirm_attested": confirmed_attested,
        "receipt_origin": receipt_origin,
    })
    if skip_interactive:
        result["warning"] = "confirm_not_attested"
        if reason:
            result["reason"] = reason
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# serve：本地回传服务器（P2 任务 14）
# ---------------------------------------------------------------------------


def serve_board(
    workspace: str,
    *,
    port: int = DEFAULT_SERVE_PORT,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    once: bool = False,
) -> dict:
    """起一个只监听本机的 HTTP 服务，把决策板页面和回执通道一起提供。

    设计要点（都是踩过的坑，不要简化掉）：

    1. **只绑 127.0.0.1**：板上写的是用户的建模决策，不该暴露到局域网。
    2. **POST 必须带 `X-MM-Token` 头**：页面里注入一次性随机 token，服务端校验。
       这挡住"恶意网页用表单 POST 到 localhost 伪造回执"——跨源表单发不出自定义头。
    3. **页面每次请求现渲染**：改过 `design_board.json` 后刷新就能看到最新态，不会读到陈旧 HTML。
    4. **回执走 `apply_submission()`**：与命令行 `ingest` 同一条校验路径，网页提交不能绕过任何规则。
    5. **`--once` 模式**：收到第一份回执就返回，方便脚本化与测试；默认是常驻服务。
    """
    root = workspace_root(workspace)
    if not (root / BOARD_FILE).is_file():
        raise ValueError(f"{root} 下没有 {BOARD_FILE}，请先运行 render")
    if not 0 <= port <= 65535:
        raise ValueError(f"端口不合法: {port}")

    token = secrets.token_urlsafe(24)
    state: dict = {"stopped": False, "submissions": 0, "last_result": None}

def build_serve_server(
    root: Path,
    token: str,
    state: dict,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_SERVE_PORT,
    once: bool = False,
):
    """构造 (http_server, handler, url)；抽出来是为了让测试能在进程内起服务。"""
    if not (root / BOARD_FILE).is_file():
        raise ValueError(f"{root} 下没有 {BOARD_FILE}，请先运行 render")
    handler = build_serve_handler(root, token, state, once=once)
    http_server = ThreadingHTTPServer((host, port), handler)
    actual_port = http_server.server_address[1]
    return http_server, handler, f"http://{host}:{actual_port}/"


def build_serve_handler(
    root: Path,
    token: str,
    state: dict,
    *,
    once: bool = False,
):
    """构造回传服务的请求处理器类（把 root/token/state 闭包进去）。

    单独拆出来是为了让测试能在**进程内**起服务（`port=0` 拿随机端口），
    不必启动子进程、也不必靠 sleep 猜测何时就绪。
    """

    class Handler(BaseHTTPRequestHandler):
        server_version = "design-board"
        sys_version = ""

        # ---- 工具方法 ----
        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status: int, html_text: str) -> None:
            body = html_text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _render_page(self) -> str:
            """现渲染 HTML 并注入本次会话的 token。缺 html 模块时退回 md 的纯文本包装。"""
            html_module = _load_optional_view("html")
            board = load_board(root)
            if html_module is not None:
                html_text = html_module.render_html(board)
            else:
                escaped = html.escape(render_markdown(board))
                html_text = (
                    "<!DOCTYPE html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
                    "<title>建模方案决策板</title><body><pre>"
                    + escaped
                    + "</pre></body></html>"
                )
            return html_text.replace(SUBMIT_TOKEN_MARKER, token)

        def log_message(self, fmt, *args):  # noqa: A003 - 覆盖基类签名
            # 默认会往 stderr 打访问日志，对用户是噪音；只保留显式错误。
            return

        # ---- 路由 ----
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 约定
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html", f"/{HTML_FILE}"):
                    self._send_html(200, self._render_page())
                elif path == "/api/ping":
                    board = load_board(root)
                    self._send_json(200, {
                        "ok": True,
                        "board_id": _as_text(board.get("board_id")),
                        "confirm_code": _as_text(board.get("confirm_code")),
                        "confirmed": _board_confirmed(board),
                    })
                elif path == "/api/board":
                    self._send_json(200, load_board(root))
                else:
                    self._send_json(404, {"ok": False, "error": f"未知路径: {path}"})
            except Exception as exc:  # 服务端不能因为一次坏请求就退栈
                self._send_json(500, {"ok": False, "error": str(exc)})

        def do_POST(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/submit":
                self._send_json(404, {"ok": False, "error": f"未知路径: {path}"})
                return
            if self.headers.get("X-MM-Token", "") != token:
                self._send_json(403, {
                    "ok": False,
                    "error": "缺少或错误的 X-MM-Token；请通过服务器打印的地址打开页面后再提交。",
                })
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0:
                self._send_json(400, {"ok": False, "error": "请求体为空"})
                return
            if length > MAX_SUBMIT_BYTES:
                self._send_json(413, {"ok": False, "error": f"请求体过大（>{MAX_SUBMIT_BYTES} 字节）"})
                return
            raw_bytes = self.rfile.read(length)
            try:
                raw = json.loads(raw_bytes.decode("utf-8"))
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": f"请求体不是合法 JSON: {exc}"})
                return
            if not isinstance(raw, dict):
                self._send_json(400, {"ok": False, "error": "回执必须是 JSON 对象"})
                return
            raw.setdefault("receipt_origin", "browser-submit")
            try:
                result = apply_submission(root, raw)
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            state["submissions"] = int(state["submissions"]) + 1
            state["last_result"] = result
            self._send_json(200, {"ok": True, "result": result})
            if once:
                state["stopped"] = True
                # 让 serve_forever 在本次响应写出后退出
                threading.Thread(target=self.server.shutdown, daemon=True).start()

    return Handler


def serve_board(
    workspace: str,
    *,
    port: int = DEFAULT_SERVE_PORT,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    once: bool = False,
) -> dict:
    """起一个只监听本机的 HTTP 服务，把决策板页面和回执通道一起提供。

    设计要点（都是踩过的坑，不要简化掉）：

    1. **只绑 127.0.0.1**：板上写的是用户的建模决策，不该暴露到局域网。
    2. **POST 必须带 `X-MM-Token` 头**：页面里注入一次性随机 token，服务端校验。
       这挡住"恶意网页用表单 POST 到 localhost 伪造回执"——跨源表单发不出自定义头。
    3. **页面每次请求现渲染**：改过 `design_board.json` 后刷新就能看到最新态。
    4. **回执走 `apply_submission()`**：与命令行 `ingest` 同一条校验路径，网页提交绕不过规则。
    5. **`--once` 模式**：收到第一份回执就返回，方便脚本化与测试；默认常驻。
    """
    root = workspace_root(workspace)
    if not (root / BOARD_FILE).is_file():
        raise ValueError(f"{root} 下没有 {BOARD_FILE}，请先运行 render")
    if not 0 <= port <= 65535:
        raise ValueError(f"端口不合法: {port}")

    token = secrets.token_urlsafe(24)
    state: dict = {"stopped": False, "submissions": 0, "last_result": None}
    http_server, _handler, url = build_serve_server(
        root, token, state, host=host, port=port, once=once
    )
    actual_port = http_server.server_address[1]

    info = {
        "action": "serve",
        "workspace": str(root),
        "url": url,
        "port": actual_port,
        "host": host,
        "once": once,
        "note": "按 Ctrl+C 停止；回执写入 design_rounds/，不会自动 confirm",
    }
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)

    if open_browser and not once:
        try:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        except Exception:
            pass

    try:
        http_server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()

    return {
        "action": "serve",
        "workspace": str(root),
        "url": url,
        "port": actual_port,
        "submissions": int(state["submissions"]),
        "last_result": state["last_result"],
        "stopped": True,
    }



def _board_confirmed(board: dict) -> bool:
    """顶层有布尔 confirmed 就采信；否则回退为"每题都 confirmed 为 true"。"""
    top = board.get("confirmed")
    if isinstance(top, bool):
        return top
    questions = board.get("questions")
    if isinstance(questions, list) and questions:
        return all(isinstance(q, dict) and q.get("confirmed") is True for q in questions)
    return False


def main():
    parser = argparse.ArgumentParser(description="数学建模决策板工具")
    subparsers = parser.add_subparsers(dest="action")

    p_render = subparsers.add_parser("render", help="渲染决策板为 Markdown 并回写哈希与确认码")
    p_render.add_argument("--workspace", required=True)
    p_render.add_argument("--format", default="md", choices=list(SUPPORTED_FORMATS))

    p_ingest = subparsers.add_parser("ingest", help="读入用户回执，写 design_rounds/round_NNN.json")
    p_ingest.add_argument("--workspace", required=True)
    p_ingest.add_argument("--from", dest="source", required=True, help="用户提交的 JSON 路径")

    p_status = subparsers.add_parser("status", help="输出轮次、收敛进度、待决项与确认码")
    p_status.add_argument("--workspace", required=True)

    p_confirm = subparsers.add_parser("confirm", help="检查收敛判据；--apply 时写入确认字段")
    p_confirm.add_argument("--workspace", required=True)
    p_confirm.add_argument("--apply", action="store_true", help="实际写入确认字段（默认 dry-run）")
    p_confirm.add_argument("--skip-interactive", action="store_true", help="跳过确认码交互（会记 confirm_not_attested）")
    p_confirm.add_argument("--reason", default="", help="配合 --skip-interactive 记录跳过原因")

    p_serve = subparsers.add_parser("serve", help="起本地回传服务器（页面提交回执 + 下载 JSON 兜底）")
    p_serve.add_argument("--workspace", required=True)
    p_serve.add_argument("--port", type=int, default=DEFAULT_SERVE_PORT, help="端口，0 表示随机空闲端口")
    p_serve.add_argument("--host", default="127.0.0.1", help="监听地址（默认只绑本机）")
    p_serve.add_argument("--no-browser", action="store_true", help="不要自动打开浏览器")
    p_serve.add_argument("--once", action="store_true", help="收到第一份回执后退出（便于脚本化/测试）")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    if args.action == "confirm" and args.skip_interactive and not args.apply:
        error("--skip-interactive 必须与 --apply 一起使用")

    try:
        exit_code = 0
        if args.action == "render":
            result = render_board(args.workspace, args.format)
        elif args.action == "ingest":
            result = ingest_submission(args.workspace, args.source)
        elif args.action == "status":
            result = board_status(args.workspace)
        elif args.action == "serve":
            result = serve_board(
                args.workspace,
                port=args.port,
                host=args.host,
                open_browser=not args.no_browser,
                once=args.once,
            )
        else:
            result = confirm_board(args.workspace, args.apply, args.skip_interactive, args.reason)
            if not args.apply:
                exit_code = 0 if result["ready_to_confirm"] else 1
        output(result)
        sys.exit(exit_code)
    except SystemExit:
        raise
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
