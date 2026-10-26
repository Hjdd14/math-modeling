#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建模方案决策板检查工具。

校验 `design_board.json` 自身（候选方案、用户选择、确认回执、内容哈希、收敛轮次），
并按需追加两类外部对齐校验：

1. **时间线校验**：`solution.py` / `solution.m` / `solution_tests.*` 与 `results/` 下的
   代码 / 结果文件，其 mtime 必须不早于 `confirmed_at`（容差 5 秒），用来拦住
   "先写代码、后补确认板"这条最省力的绕过路径；
2. **交叉校验（方案 C）**：板里每题候选与 `model_selection_audit.json` 的 `candidates`
   必须至少有一对能对上，`user_choice` 对应的候选名必须能对上 `final_selection.name`，
   保证"用户决策"与"AI 评估"两套产物可以互相印证。

夹具目录的 mtime 由 git 检出时间决定，与板内 `confirmed_at` 没有因果关系，
因此命中 `FIXTURE_MARKERS` 时跳过时间线校验，否则 CI 会随机变红。

`--allow-legacy` 是"设计闸门"上线前的旧工作区逃生口：**只**把"缺 `design_board.json`"
这一条从 error 降级为 warning（issue code 改为 `legacy_workspace_without_board`，
并补一条 `legacy_mode` check 留痕），其它失败码（未确认、哈希不符、候选不足等）
严格度一律不变。它不伪造任何确认状态，只是让 Phase 0 之前就存在的项目在补齐决策板
之前不被突然判红；补齐骨架请用 `tools/migrate_workspace.py`。

本工具只读工作区产物，不写任何文件，也不替代建模推理。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
# 哈希排除清单：必须与 tools/design_board.py 的 HASH_EXCLUDED_* 保持逐字一致。
# 这些字段会在 render 之后被 ingest / confirm 改写，若参与哈希就会让"确认动作本身"破坏校验。
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
# 夹具目录豁免：这些目录的 mtime 来自 git 检出，与板内 confirmed_at 无因果关系。
FIXTURE_MARKERS = ("tests/test_data", "examples/solved-python", "examples/design-board-sample")
# 确认后立刻跑代码属于正常流程，留 5 秒容差，避免文件系统时间精度误伤。
TIMELINE_TOLERANCE_SECONDS = 5.0
# 每个候选方案必须说明：为什么选它、风险、来源、试算证据。
OPTION_REQUIRED_FIELDS = ("rationale", "risk", "source_ref", "mini_trial")
# 确认回执必须能回答：谁、什么时候、通过什么通道、用什么确认码。
RECEIPT_REQUIRED_FIELDS = ("confirmed_at", "confirmed_by", "receipt_origin", "confirm_code")
TIMELINE_CODE_FILES = ("solution.py", "solution.m", "solution_tests.py", "solution_tests.m")
TIMELINE_RESULT_SUFFIXES = (".py", ".csv", ".json")
ROUND_FILE_PATTERN = "round_*.json"
# board_sha256 的占位值（模板默认产出），代表"尚未由 render 写入真实哈希"。
PLACEHOLDER_MARKERS = ("placeholder",)


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _strict(mode: str) -> bool:
    return mode in STRICT_MODES


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _marked(value) -> bool:
    """判断标记字段是否被真正置位（False / None / 空值都不算）。"""
    if value is True:
        return True
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return False


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _normalize(name) -> str:
    """把候选名归一化后再比对。"""
    s = str(name or "").strip().lower()
    s = re.sub(r"[（(].*?[)）]", "", s)  # 去括号内容
    s = s.replace(" ", "").replace("-", "").replace("_", "")
    return s


def _match(option_name: str, candidate_names: list[str]) -> str | None:
    target = _normalize(option_name)
    if not target:
        return None
    for cand in candidate_names:
        norm = _normalize(cand)
        if not norm:
            continue
        if norm in target or target in norm:
            return cand
    return None


def _content_hash(payload: dict) -> str:
    """计算板的内容哈希，与 `tools/design_board.py` 的口径逐字一致。

    哈希只覆盖"方案内容"（题目、候选、导图、待决项等），**不覆盖**以下两类可变状态，
    否则确认动作本身会把哈希改掉，导致 render 之后永远对不上：

    - 顶层确认/回写状态：`board_sha256`、`confirm_code`、`confirm_attested`、
      `confirmed*`、`receipt_*`、`revision`、`no_change_rounds`、`history`、`skip_reason`
    - question 级用户选择：`user_choice` / `user_comment` / `user_locked` / `confirmed`
      （用户改选择不需要重新确认；只有 AI 改了方案内容才要求重新确认）

    排除清单必须与 `design_board.HASH_EXCLUDED_TOP_LEVEL` 与
    `HASH_EXCLUDED_QUESTION_LEVEL` 保持同步，两处任一漂移都会让 gate 永远失败。
    """
    cleaned = {key: value for key, value in payload.items() if key not in HASH_EXCLUDED_TOP_LEVEL}
    questions = cleaned.get("questions")
    if isinstance(questions, list):
        cleaned["questions"] = [
            {key: value for key, value in question.items() if key not in HASH_EXCLUDED_QUESTION_LEVEL}
            if isinstance(question, dict)
            else question
            for question in questions
        ]
    encoded = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_placeholder_hash(value) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def _parse_timestamp(value) -> float | None:
    """把 ISO8601 时间戳转成 epoch 秒；无法解析返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # 无时区按 UTC 处理，保证不同机器上的判定一致，不随本地时区漂移。
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _format_timestamp(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _is_fixture_directory(root: Path) -> bool:
    """夹具目录判定：用规范化绝对路径做子串匹配，避免相对路径/反斜杠漏判。"""
    try:
        normalized = str(root.resolve()).replace("\\", "/").lower()
    except OSError:
        normalized = str(root).replace("\\", "/").lower()
    return any(marker in normalized for marker in FIXTURE_MARKERS)


def _board_confirmed(payload: dict) -> bool:
    """判定整块板是否已确认。

    顶层 `confirmed` 若存在且是布尔值，则以它为准（显式覆盖）；否则回退到
    "每题都 confirmed 为 true" —— 现有 schema 把 confirmed 写在每个 question 里，
    顶层只放 confirmed_at / confirmed_by / receipt_origin / confirm_code。
    """
    top = payload.get("confirmed")
    if isinstance(top, bool):
        return top
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return False
    flags = [item.get("confirmed") for item in questions if isinstance(item, dict)]
    return bool(flags) and all(flag is True for flag in flags)


def _read_rounds(rounds_dir: Path) -> list[tuple[str, dict | None]]:
    """读取 design_rounds/round_*.json；无法解析的记录保留文件名、内容记 None。"""
    if not rounds_dir.is_dir():
        return []
    records: list[tuple[str, dict | None]] = []
    for path in sorted(rounds_dir.glob(ROUND_FILE_PATTERN)):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        records.append((path.name, payload if isinstance(payload, dict) else None))
    return records


def _post_confirm_edits(confirmed_ts: float | None, rounds: list[tuple[str, dict | None]]) -> list[str]:
    """找出 design_rounds/ 里的"确认后改动"证据。

    判定只有两种，避免把"确认前的正常改选"误报成可疑行为：

    1. 显式标记：记录或单条 change 带 `post_confirm_edit` 真值 → 一定报；
    2. 时间证据：该轮 `at` **晚于** `confirmed_at` 且记录了 `changes[].path` → 报。

    确认之前（或时间无法比较且无显式标记）的改动属于正常决策流程，不报——
    否则任何走过一轮改选的板都会永久带这条警告，警告本身会失去信号价值。

    只做 warning 留痕，不阻断。
    """
    details: list[str] = []
    for name, record in rounds:
        if not isinstance(record, dict):
            continue
        changes = record.get("changes")
        changes = changes if isinstance(changes, list) else []
        paths = [
            str(item.get("path"))
            for item in changes
            if isinstance(item, dict) and _present(item.get("path"))
        ]
        marked_paths = [
            str(item.get("path") or "<change>")
            for item in changes
            if isinstance(item, dict) and _marked(item.get("post_confirm_edit"))
        ]
        record_marked = _marked(record.get("post_confirm_edit"))
        round_ts = _parse_timestamp(record.get("at"))
        after_confirm = (
            confirmed_ts is not None and round_ts is not None and round_ts > confirmed_ts
        )
        timing = "确认之后" if after_confirm else "确认之前"

        if record_marked:
            details.append(f"{name}: 记录带 post_confirm_edit 标记（{timing}）")
        elif marked_paths:
            details.append(f"{name}: changes 带 post_confirm_edit 标记 {marked_paths}（{timing}）")
        elif paths and after_confirm:
            details.append(f"{name}: 确认之后仍有改动记录 changes[].path {paths}（{timing}）")
    return details


def _collect_timeline_files(root: Path) -> list[tuple[str, float]]:
    """收集需要参与时间线校验的代码 / 结果文件（存在才收）。"""
    entries: list[tuple[str, float]] = []
    for name in TIMELINE_CODE_FILES:
        candidate = root / name
        if candidate.is_file():
            entries.append((name, datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc).timestamp()))
    results_dir = root / "results"
    if results_dir.is_dir():
        for child in sorted(results_dir.rglob("*")):
            if not child.is_file() or child.suffix.lower() not in TIMELINE_RESULT_SUFFIXES:
                continue
            try:
                relative = child.relative_to(root).as_posix()
            except ValueError:
                relative = child.as_posix()
            entries.append((relative, datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc).timestamp()))
    return entries


def _empty_result(root: Path, mode: str, cross_audit: bool) -> dict:
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "design_board.json"),
        "passed": True,
        "warning": False,
        "confirmed": False,
        "cross_audit": "not_applicable" if cross_audit else "skipped",
        "timeline": "skipped",
        "checks": [],
        "issues": [],
    }


def _missing_result(root: Path, mode: str, cross_audit: bool, allow_legacy: bool = False) -> dict:
    """缺 design_board.json 的返回。

    `allow_legacy=True` 时把这条 error 降级为 warning，并把 issue code 换成
    `legacy_workspace_without_board`，让旧工作区可以带着一条可读的待办继续跑；
    其它校验项维持原样（没文件本来就都会跳过）。
    """
    severity = "error" if _strict(mode) else "warning"
    if allow_legacy:
        severity = "warning"
    result = _empty_result(root, mode, cross_audit)
    result["passed"] = severity == "warning"
    result["warning"] = severity == "warning"
    result["checks"] = [
        {"name": "design_board", "passed": False},
        {"name": "timeline", "passed": True, "skipped": True, "reason": "missing_design_board"},
        {"name": "board_audit", "passed": True, "skipped": True, "reason": "missing_design_board"},
    ]
    if allow_legacy:
        result["checks"].insert(
            1,
            {
                "name": "legacy_mode",
                "passed": True,
                "note": "allow_legacy=True：缺 design_board.json 按旧工作区豁免，仅留痕不阻断；"
                "建议运行 tools/migrate_workspace.py 补齐骨架后走 render → 确认流程。",
            },
        )
        result["issues"] = [
            {
                "code": "legacy_workspace_without_board",
                "severity": "warning",
                "message": "缺少 design_board.json；已启用 --allow-legacy，按旧工作区豁免（仅留痕不阻断）。"
                "建议运行 python tools/migrate_workspace.py --workspace . --apply 补齐决策板骨架。",
            }
        ]
        return result
    result["issues"] = [
        {
            "code": "missing_design_board",
            "severity": severity,
            "message": "缺少 design_board.json；excellence 模式必须先给用户看候选建模方案并取得确认回执。",
        }
    ]
    return result


def _invalid_json_result(root: Path, mode: str, cross_audit: bool, message: str) -> dict:
    result = _empty_result(root, mode, cross_audit)
    result["passed"] = False
    result["warning"] = False
    result["checks"] = [
        {"name": "design_board", "passed": False},
        {"name": "timeline", "passed": True, "skipped": True, "reason": "invalid_json"},
        {"name": "board_audit", "passed": True, "skipped": True, "reason": "invalid_json"},
    ]
    result["issues"] = [{"code": "invalid_json", "severity": "error", "message": message}]
    return result


def check_design_board(
    workspace: str,
    mode: str = "standard",
    cross_audit: bool = True,
    skip_timeline: bool = False,
    allow_legacy: bool = False,
) -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "design_board.json"
    fixture = _is_fixture_directory(root)

    if not path.exists():
        return _missing_result(root, normalized_mode, cross_audit, allow_legacy)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _invalid_json_result(root, normalized_mode, cross_audit, f"design_board.json 不是合法 JSON: {exc}")
    if not isinstance(payload, dict):
        return _invalid_json_result(root, normalized_mode, cross_audit, "design_board.json 顶层必须是 JSON 对象。")

    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []

    confirmed = _board_confirmed(payload)
    confirmed_at_raw = payload.get("confirmed_at")
    confirmed_ts = _parse_timestamp(confirmed_at_raw)
    if _present(confirmed_at_raw) and confirmed_ts is None:
        _add_issue(
            issues,
            "invalid_confirmed_at",
            f"confirmed_at={confirmed_at_raw!r} 不是可解析的 ISO8601 时间戳，时间线校验被跳过。",
            severity="warning",
            confirmed_at=confirmed_at_raw,
        )

    # ---------- A. 板自身校验 ----------
    questions = payload.get("questions")
    questions = questions if isinstance(questions, list) else []
    checks.append({"name": "questions", "passed": bool(questions), "count": len(questions)})
    if not questions:
        _add_issue(
            issues,
            "insufficient_options",
            "design_board.json 的 questions 为空或缺失，无法满足每个小问至少 2 个候选方案。",
            severity=severity,
        )

    option_names: list[str] = []
    chosen_names: list[tuple[str, str]] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            _add_issue(
                issues,
                "insufficient_options",
                f"第 {index + 1} 个小问不是对象，无法校验候选方案。",
                severity=severity,
                question_index=index,
            )
            continue
        question_id = str(question.get("id") or f"Q{index + 1}")
        options = question.get("options")
        options = options if isinstance(options, list) else []
        options_ok = len(options) >= 2
        checks.append(
            {"name": "options", "question_id": question_id, "passed": options_ok, "count": len(options)}
        )
        if not options_ok:
            _add_issue(
                issues,
                "insufficient_options",
                f"{question_id} 只有 {len(options)} 个候选方案，至少需要 2 个（推荐 + 备选）才能让用户比较。",
                severity=severity,
                question_id=question_id,
                option_count=len(options),
            )

        option_ids: list[str] = []
        for position, option in enumerate(options):
            if not isinstance(option, dict):
                _add_issue(
                    issues,
                    "missing_option_field",
                    "候选方案必须是对象。",
                    severity=severity,
                    question_id=question_id,
                    option_id=f"O{position + 1}",
                    field="<option_object>",
                )
                continue
            option_id = option.get("id")
            if _present(option_id):
                option_ids.append(option_id)
            # 候选可能没写 id：issue 里仍要给一个可定位的编号，方便人回去改。
            option_label = option_id if _present(option_id) else f"O{position + 1}"
            name = option.get("name")
            if _present(name):
                option_names.append(str(name))
            for field in OPTION_REQUIRED_FIELDS:
                if not _present(option.get(field)):
                    _add_issue(
                        issues,
                        "missing_option_field",
                        f"{question_id} 的候选 {option_label} 缺少 {field}；"
                        "每个候选都要说明理由、风险、来源与试算证据。",
                        severity=severity,
                        question_id=question_id,
                        option_id=option_label,
                        field=field,
                    )
            source_ref = option.get("source_ref")
            if isinstance(source_ref, dict) and source_ref.get("verified") is False:
                if not _present(source_ref.get("unverified_reason")):
                    _add_issue(
                        issues,
                        "unverified_source_without_reason",
                        f"{question_id} 的候选 {option_label} 标记来源未核实，"
                        "但没有写 unverified_reason。",
                        severity=severity,
                        question_id=question_id,
                        option_id=option_label,
                        source_ref=source_ref.get("ref"),
                    )

        user_choice = question.get("user_choice")
        if _present(user_choice):
            if user_choice not in option_ids:
                _add_issue(
                    issues,
                    "invalid_user_choice",
                    f"{question_id} 的 user_choice={user_choice!r} 不是该题候选 id 之一 {option_ids}。",
                    severity="error",
                    question_id=question_id,
                    user_choice=user_choice,
                    option_ids=option_ids,
                )
            else:
                for option in options:
                    if isinstance(option, dict) and option.get("id") == user_choice and _present(option.get("name")):
                        chosen_names.append((question_id, str(option["name"])))
                        break

    checks.append({"name": "confirmed", "passed": confirmed})
    if not confirmed:
        _add_issue(
            issues,
            "unconfirmed_board",
            "决策板尚未确认（confirmed 不为 true）；确认之前不允许写 solution.py 等代码产物。",
            severity=severity,
        )

    expected_sha = payload.get("board_sha256")
    actual_sha = _content_hash(payload)
    sha_ok = isinstance(expected_sha, str) and expected_sha.strip().lower() == actual_sha
    checks.append({"name": "board_hash", "passed": sha_ok, "expected": expected_sha, "actual": actual_sha})
    if _is_placeholder_hash(expected_sha):
        _add_issue(
            issues,
            "board_hash_mismatch",
            "board_sha256 仍为空或占位值，尚未由 render 写入真实内容哈希，用户确认的内容无锚点。",
            severity=severity,
            expected_placeholder=True,
            expected=expected_sha,
            actual=actual_sha,
        )
    elif not sha_ok:
        _add_issue(
            issues,
            "board_hash_mismatch",
            "board_sha256 与当前 design_board.json 的内容哈希不一致：确认后板被改动过，必须重新确认。",
            severity="error",
            expected=str(expected_sha),
            actual=actual_sha,
        )

    missing_receipt = [field for field in RECEIPT_REQUIRED_FIELDS if not _present(payload.get(field))]
    checks.append({"name": "receipt_provenance", "passed": not missing_receipt, "missing": missing_receipt})
    if confirmed and missing_receipt:
        _add_issue(
            issues,
            "missing_receipt_provenance",
            f"confirmed 为 true，但回执缺少 {', '.join(missing_receipt)}；无法说明谁在何时通过什么通道确认。",
            severity=severity,
            missing=missing_receipt,
        )

    rounds = _read_rounds(root / "design_rounds")
    checks.append(
        {
            "name": "design_rounds",
            "passed": bool(rounds),
            "count": len(rounds),
            "path": str(root / "design_rounds"),
        }
    )
    if confirmed and not rounds:
        _add_issue(
            issues,
            "missing_rounds",
            "confirmed 为 true，但 design_rounds/ 不存在或没有任何 round_*.json 回执，无法证明用户改过什么。",
            severity=severity,
        )

    no_change_rounds = payload.get("no_change_rounds")
    converged = (
        isinstance(no_change_rounds, (int, float))
        and not isinstance(no_change_rounds, bool)
        and no_change_rounds >= 2
    )
    skip_reason = payload.get("skip_reason")
    explicit_skip = _marked(skip_reason)
    checks.append(
        {
            "name": "convergence",
            "passed": bool(converged or explicit_skip),
            "no_change_rounds": no_change_rounds,
            "explicit_skip": explicit_skip,
        }
    )
    if not converged and not explicit_skip:
        _add_issue(
            issues,
            "insufficient_rounds",
            f"no_change_rounds={no_change_rounds!r} < 2 且没有 skip_reason：至少连续两轮用户未修改才允许确认。",
            severity=severity,
            no_change_rounds=no_change_rounds,
        )
    if explicit_skip:
        _add_issue(
            issues,
            "skipped_by_explicit_request",
            f"板内声明 skip_reason={skip_reason!r}：整轮决策流程被显式跳过，仅留痕不阻断。",
            severity="warning",
            skip_reason=skip_reason,
        )

    confirmed_by = str(payload.get("confirmed_by") or "").strip()
    confirm_attested = payload.get("confirm_attested")
    attested_ok = confirmed_by != "user_non_interactive" and confirm_attested is not False
    checks.append(
        {
            "name": "confirm_attestation",
            "passed": attested_ok,
            "confirmed_by": confirmed_by,
            "confirm_attested": confirm_attested,
        }
    )
    if not attested_ok:
        # 「只是留痕」不足以叫闸门：AI 完全可以跑 --skip-interactive 自证。
        # standard 保持 warning（兼容旧工作区），strict/excellence 判 error——
        # 否则这条路径就是"零成本绕过人工确认"。
        _add_issue(
            issues,
            "confirm_not_attested",
            "确认未经交互式确认码（confirmed_by=user_non_interactive 或 confirm_attested=false），"
            "无法证明是人工确认。standard 仅留痕，excellence 视为不通过。",
            severity=severity,
            confirmed_by=confirmed_by,
            confirm_attested=confirm_attested,
        )
    if confirmed_by == "ci":
        # CI 自动化确认不是"人确认"。excellence 声称的是人工决策，故判 error。
        _add_issue(
            issues,
            "confirm_ci",
            "确认由 CI 自动化完成（confirmed_by=ci），不是人工决策证据。"
            "standard 仅留痕，excellence 视为不通过。",
            severity=severity,
            confirmed_by=confirmed_by,
        )

    # 确认码必须真的由 board_sha256 派生。只查"存在且非空"是可被手写绕过的：
    # 随便填 ABCD 也能过，而确认码的全部意义就是"你看到的这版方案的内容指纹"。
    board_sha = str(payload.get("board_sha256") or "").strip().lower()
    confirm_code = str(payload.get("confirm_code") or "").strip().upper()
    looks_like_sha = bool(re.fullmatch(r"[0-9a-f]{64}", board_sha))
    if confirm_code and looks_like_sha:
        derived = board_sha[:4].upper()
        code_ok = confirm_code == derived
        checks.append(
            {
                "name": "confirm_code_matches_hash",
                "passed": code_ok,
                "confirm_code": confirm_code,
                "derived_from_hash": derived,
            }
        )
        if not code_ok:
            _add_issue(
                issues,
                "confirm_code_mismatch",
                f"confirm_code={confirm_code!r} 与 board_sha256 派生的 {derived!r} 不一致："
                "确认码必须是当前方案内容的哈希前 4 位，不能手写。",
                severity=severity,
                confirm_code=confirm_code,
                derived_from_hash=derived,
            )

    post_confirm = _post_confirm_edits(confirmed_ts, rounds)
    checks.append({"name": "post_confirm_edit", "passed": not post_confirm, "details": post_confirm})
    if post_confirm:
        _add_issue(
            issues,
            "post_confirm_edit",
            "design_rounds/ 里存在确认后的改动记录，需说明是否属于方案变更。",
            severity="warning",
            details=post_confirm,
        )

    # ---------- B. 时间线校验（防"先写代码、后补板"） ----------
    timeline_reason: str | None = None
    if skip_timeline:
        timeline_reason = "skip_timeline"
    elif fixture:
        timeline_reason = "fixture_directory"
    elif confirmed_ts is None:
        timeline_reason = "invalid_confirmed_at" if _present(confirmed_at_raw) else "missing_confirmed_at"

    if timeline_reason is not None:
        timeline_state = "skipped"
        checks.append({"name": "timeline", "passed": True, "skipped": True, "reason": timeline_reason})
    else:
        timeline_state = "checked"
        timeline_files = _collect_timeline_files(root)
        violations = [
            {"file": name, "mtime": _format_timestamp(mtime), "seconds_before": round(confirmed_ts - mtime, 3)}
            for name, mtime in timeline_files
            if mtime + TIMELINE_TOLERANCE_SECONDS < confirmed_ts
        ]
        checks.append(
            {
                "name": "timeline",
                "passed": not violations,
                "skipped": False,
                "checked_files": len(timeline_files),
                "violations": violations,
            }
        )
        for violation in violations:
            _add_issue(
                issues,
                "code_written_before_confirm",
                f"{violation['file']} 的 mtime 早于 confirmed_at 约 {violation['seconds_before']} 秒，"
                "疑似先写代码、后补确认板。",
                severity=severity,
                file=violation["file"],
                mtime=violation["mtime"],
                confirmed_at=_format_timestamp(confirmed_ts),
                seconds_before=violation["seconds_before"],
            )

    # ---------- C. 交叉校验（方案 C：板与审计必须能对账） ----------
    if not cross_audit:
        cross_audit_state = "skipped"
        checks.append({"name": "board_audit", "passed": True, "skipped": True, "reason": "cross_audit_disabled"})
    elif not confirmed:
        cross_audit_state = "not_applicable"
        checks.append({"name": "board_audit", "passed": True, "skipped": True, "reason": "board_not_confirmed"})
    else:
        cross_audit_state = "checked"
        audit_path = root / "model_selection_audit.json"
        audit_payload: dict | None = None
        if not audit_path.exists():
            _add_issue(
                issues,
                "board_audit_missing",
                "决策板已确认，但缺少 model_selection_audit.json，无法核对 AI 的候选评估与最终选择。",
                severity=severity,
            )
        else:
            try:
                loaded = json.loads(audit_path.read_text(encoding="utf-8"))
            except Exception as exc:
                _add_issue(
                    issues,
                    "board_audit_missing",
                    f"model_selection_audit.json 不是合法 JSON: {exc}",
                    severity=severity,
                )
            else:
                if isinstance(loaded, dict):
                    audit_payload = loaded
                else:
                    _add_issue(
                        issues,
                        "board_audit_missing",
                        "model_selection_audit.json 顶层必须是 JSON 对象。",
                        severity=severity,
                    )

        if audit_payload is not None:
            raw_candidates = audit_payload.get("candidates")
            raw_candidates = raw_candidates if isinstance(raw_candidates, list) else []
            candidate_names = [
                str(item.get("name"))
                for item in raw_candidates
                if isinstance(item, dict) and _present(item.get("name"))
            ]
            final_selection = audit_payload.get("final_selection")
            final_name = None
            if isinstance(final_selection, dict) and _present(final_selection.get("name")):
                final_name = str(final_selection["name"])

            if not candidate_names:
                _add_issue(
                    issues,
                    "board_audit_missing",
                    "model_selection_audit.json 缺少 candidates[].name，无法与板的候选对账。",
                    severity=severity,
                )
            elif option_names:
                matched = [name for name in option_names if _match(name, candidate_names)]
                candidates_ok = bool(matched)
                checks.append(
                    {
                        "name": "board_audit_candidates",
                        "passed": candidates_ok,
                        "matched": matched,
                        "board_names": option_names,
                        "audit_names": candidate_names,
                    }
                )
                if not candidates_ok:
                    _add_issue(
                        issues,
                        "board_audit_candidate_mismatch",
                        "板的候选名与审计的 candidates[].name 没有任何一对能归一化匹配，两套产物对不上账。",
                        severity=severity,
                        board_names=option_names,
                        audit_names=candidate_names,
                    )

            if not _present(final_name):
                _add_issue(
                    issues,
                    "board_audit_missing",
                    "model_selection_audit.json 缺少 final_selection.name，无法核对最终选择。",
                    severity=severity,
                )
            elif chosen_names:
                chosen = [name for _, name in chosen_names]
                selection_ok = any(_match(name, [final_name]) for name in chosen)
                checks.append(
                    {
                        "name": "board_audit_selection",
                        "passed": selection_ok,
                        "board_choice": chosen,
                        "audit_selection": final_name,
                    }
                )
                if not selection_ok:
                    _add_issue(
                        issues,
                        "board_audit_selection_mismatch",
                        "板里 user_choice 对应的候选名与审计 final_selection.name 既不相等也不能互相包含。",
                        severity=severity,
                        board_choice=chosen,
                        audit_selection=final_name,
                        questions=[question_id for question_id, _ in chosen_names],
                    )
            else:
                checks.append(
                    {
                        "name": "board_audit_selection",
                        "passed": True,
                        "skipped": True,
                        "reason": "no_user_choice",
                    }
                )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "confirmed": confirmed,
        "cross_audit": cross_audit_state,
        "timeline": timeline_state,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 design_board.json 决策板与审计的一致性")
    parser.add_argument("--workspace", required=True, help="建模工作区")
    parser.add_argument(
        "--mode",
        default="standard",
        choices=["standard", "strict", "hard", "complete", "full", "excellence"],
        help="standard 向后兼容；strict/hard/complete/full/excellence 缺板或结构不全即失败",
    )
    parser.add_argument(
        "--no-cross-audit",
        action="store_true",
        help="跳过与 model_selection_audit.json 的交叉校验（方案 C 回滚开关）",
    )
    parser.add_argument(
        "--skip-timeline",
        action="store_true",
        help="跳过代码/结果文件 mtime 与 confirmed_at 的时间线校验（回滚开关）",
    )
    parser.add_argument(
        "--allow-legacy",
        action="store_true",
        help="旧工作区逃生口：缺 design_board.json 只给 warning"
        "（code=legacy_workspace_without_board），其它失败码严格度不变",
    )
    args = parser.parse_args()
    try:
        result = check_design_board(
            args.workspace,
            args.mode,
            cross_audit=not args.no_cross_audit,
            skip_timeline=args.skip_timeline,
            allow_legacy=args.allow_legacy,
        )
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
