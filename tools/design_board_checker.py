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
# A 板 v2（framework gate）引入 paradigm_set 后，mini_trial 变为可选：
# 范式阶段还没有"最终候选"，强求试算等于逼 AI 编数字。
A_OPTION_REQUIRED_FIELDS = ("rationale", "risk", "source_ref")
# B 板（model gate）的候选来自建议 Agent，字段重心从"理由/风险"转到"结论/分数"。
B_OPTION_REQUIRED_FIELDS = ("name", "verdict", "score")
PARADIGM_REQUIRED_FIELDS = ("paradigm_id", "name", "family", "source_ref", "why_explore", "explore_cost")
PARADIGM_COST_LEVELS = ("low", "medium", "high")
ADVICE_FILENAME = "model_advice.json"
TRIALS_FILENAME = "perspective_trials.json"
TRIALS_DIRNAME = "perspective_trials"
BOARD_FILES = {"a": "design_board.json", "b": "design_board_gate_b.json"}
ROUNDS_DIRS = {"a": "design_rounds", "b": "design_rounds_gate_b"}
ADVICE_MIN_CANDIDATES = 5
ADVICE_MAX_CANDIDATES = 8
ADVICE_MIN_SLICES = 2
ADVICE_MIN_PERSPECTIVES = 5
ADVICE_NUMBER_TOLERANCE = 1e-9
JUDGE_WORDING_PATTERNS = ("评委通过", "评委不通过", "评审通过", "评审结论")
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


def _empty_result(root: Path, mode: str, cross_audit: bool, gate: str = "a", board_path: Path | None = None) -> dict:
    return {
        "workspace": str(root),
        "mode": mode,
        "gate": gate,
        "path": str(board_path or (root / BOARD_FILES.get(gate, BOARD_FILES["a"]))),
        "passed": True,
        "warning": False,
        "confirmed": False,
        "cross_audit": "not_applicable" if cross_audit else "skipped",
        "timeline": "skipped",
        "checks": [],
        "issues": [],
    }


def _missing_result(
    root: Path,
    mode: str,
    cross_audit: bool,
    allow_legacy: bool = False,
    gate: str = "a",
    board_path: Path | None = None,
) -> dict:
    """缺决策板的返回。

    `allow_legacy=True` 时把这条 error 降级为 warning，并把 issue code 换成
    `legacy_workspace_without_board`，让旧工作区可以带着一条可读的待办继续跑；
    其它校验项维持原样（没文件本来就都会跳过）。

    **双闸门硬规则**：若板不在了、但交付代码已经存在，仍然是 error——
    "先写代码、后补板"不能因为板被删掉就变成 skipped。
    """
    severity = "error" if _strict(mode) else "warning"
    if allow_legacy:
        severity = "warning"
    board_name = (board_path.name if board_path else BOARD_FILES.get(gate, BOARD_FILES["a"]))
    result = _empty_result(root, mode, cross_audit, gate, board_path)
    delivery = _delivery_code_files(root)
    if delivery:
        # 契约 §2.8：**strict/excellence** 下"缺板 + 有交付代码"才是 error；
        # standard 仍按 warning 留痕，否则所有"还没做板"的旧工作区会一片红。
        # --allow-legacy 是旧工作区逃生口：即使有代码也只降为 warning。
        write_severity = "warning" if (not _strict(mode) or allow_legacy) else "error"
        allow_legacy = False
        result["issues"] = [
            {
                "code": f"code_written_before_gate_{gate}",
                "severity": write_severity,
                "message": f"缺少 {board_name}，但已存在交付代码 {delivery}；"
                "闸门板不在场不能把这条降级为跳过。",
                "files": delivery,
            }
        ]
        result["passed"] = write_severity != "error"
        result["warning"] = write_severity == "warning"
        result["checks"] = [
            {"name": "design_board", "passed": False},
            {"name": "timeline", "passed": write_severity != "error", "skipped": False, "violations": delivery},
            {"name": "board_audit", "passed": True, "skipped": True, "reason": "missing_design_board"},
        ]
        return result
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
            "message": f"缺少 {board_name}；excellence 模式必须先给用户看方案并取得确认回执。",
        }
    ]
    return result


def _invalid_json_result(
    root: Path,
    mode: str,
    cross_audit: bool,
    message: str,
    gate: str = "a",
    board_path: Path | None = None,
) -> dict:
    result = _empty_result(root, mode, cross_audit, gate, board_path)
    result["passed"] = False
    result["warning"] = False
    result["checks"] = [
        {"name": "design_board", "passed": False},
        {"name": "timeline", "passed": True, "skipped": True, "reason": "invalid_json"},
        {"name": "board_audit", "passed": True, "skipped": True, "reason": "invalid_json"},
    ]
    result["issues"] = [{"code": "invalid_json", "severity": "error", "message": message}]
    return result


def _board_schema(payload: dict) -> int:
    """读取板结构版本；缺失或非法一律按 1（legacy）处理。"""
    version = payload.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    return 1


def _load_json_file(path: Path) -> tuple[dict | None, str | None]:
    """读 JSON 对象；返回 (payload, error_message)。"""
    if not path.is_file():
        return None, f"缺少 {path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - 统一转成结构化 issue
        return None, f"{path.name} 不是合法 JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path.name} 顶层必须是 JSON 对象"
    return payload, None


def _sha256_file(path: Path) -> str:
    """文件字节级 sha256（十六进制小写）；文件不存在返回空串。"""
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_number(value) -> bool:
    """排除 bool 的数值判定（True 会被 isinstance(True, int) 骗到）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _delivery_code_files(root: Path) -> list[str]:
    """只收集"交付代码"（solution.* / solution_tests.*），不含试算代码与结果。

    两仓库形态都覆盖：根目录（主仓库整题）与 `questions/qN/`（分支分小问）。
    `perspective_trials/**` 永不进入本清单——它是 B 闸门之前允许存在的试算代码。
    """
    entries: list[str] = []
    for name in TIMELINE_CODE_FILES:
        candidate = root / name
        if candidate.is_file():
            entries.append(name)
    questions_dir = root / "questions"
    if questions_dir.is_dir():
        for question_dir in sorted(child for child in questions_dir.iterdir() if child.is_dir()):
            for name in TIMELINE_CODE_FILES:
                candidate = question_dir / name
                if candidate.is_file():
                    try:
                        entries.append(candidate.relative_to(root).as_posix())
                    except ValueError:
                        entries.append(candidate.as_posix())
    return entries


def _check_paradigm_set(
    question: dict,
    question_id: str,
    schema: int,
    severity: str,
    issues: list[dict],
    checks: list[dict],
) -> bool:
    """校验 A 板的 paradigm_set / paradigm_selection。

    返回 True 表示该问走"范式模式"（不再要求 >=2 个模型候选）。
    """
    paradigm_set = question.get("paradigm_set")
    has_set = isinstance(paradigm_set, list) and bool(paradigm_set)
    if not has_set:
        if schema >= 2:
            _add_issue(
                issues,
                "paradigm_set_missing",
                f"{question_id} 是 schema v2 的 A 板，但缺少 paradigm_set；"
                "框架闸门必须给出 3-5 个待探索范式，而不是直接给模型候选。",
                severity=severity,
                question_id=question_id,
            )
        else:
            # 旧板（schema<2）就是当前存量常态：不额外报警，避免把"还没迁移"变成噪声。
            # 迁移请走 tools/migrate_workspace.py，它会把板升到 schema v2 并写 paradigm 占位。
            checks.append({"name": "paradigm_set", "question_id": question_id, "passed": True, "skipped": True,
                           "reason": "legacy_board"})
        return False

    checks.append({"name": "paradigm_set", "question_id": question_id, "passed": True,
                   "count": len(paradigm_set)})
    if not (3 <= len(paradigm_set) <= 5):
        _add_issue(
            issues,
            "paradigm_set_size",
            f"{question_id} 的 paradigm_set 有 {len(paradigm_set)} 项，要求 3-5 项。",
            severity=severity,
            question_id=question_id,
            count=len(paradigm_set),
        )

    paradigm_ids: list[str] = []
    family_by_id: dict[str, str] = {}
    for index, paradigm in enumerate(paradigm_set):
        label = f"P{index + 1}"
        if not isinstance(paradigm, dict):
            _add_issue(issues, "paradigm_set_field_missing",
                       f"{question_id} 的第 {index + 1} 个范式不是对象。",
                       severity=severity, question_id=question_id, paradigm_id=label)
            continue
        paradigm_id = paradigm.get("paradigm_id")
        if _present(paradigm_id):
            paradigm_ids.append(str(paradigm_id))
            label = str(paradigm_id)
        for field in PARADIGM_REQUIRED_FIELDS:
            if not _present(paradigm.get(field)):
                _add_issue(
                    issues,
                    "paradigm_set_field_missing",
                    f"{question_id} 的范式 {label} 缺少 {field}。",
                    severity=severity,
                    question_id=question_id,
                    paradigm_id=label,
                    field=field,
                )
        explore_cost = paradigm.get("explore_cost")
        if isinstance(explore_cost, dict):
            level = explore_cost.get("level")
            if _present(level) and str(level).lower() not in PARADIGM_COST_LEVELS:
                _add_issue(
                    issues,
                    "paradigm_cost_invalid",
                    f"{question_id} 的范式 {label} 的 explore_cost.level={level!r} "
                    f"不在 {list(PARADIGM_COST_LEVELS)} 内。",
                    severity=severity,
                    question_id=question_id,
                    paradigm_id=label,
                    level=level,
                )
        source_ref = paradigm.get("source_ref")
        if isinstance(source_ref, dict) and source_ref.get("verified") is False:
            if not _present(source_ref.get("unverified_reason")):
                _add_issue(
                    issues,
                    "unverified_source_without_reason",
                    f"{question_id} 的范式 {label} 标记来源未核实，但没有写 unverified_reason。",
                    severity=severity,
                    question_id=question_id,
                    paradigm_id=label,
                )
        family = paradigm.get("family")
        if _present(family):
            family_by_id[label] = str(family)

    distinct_families = {value for value in family_by_id.values()}
    if family_by_id and len(distinct_families) < 2:
        _add_issue(
            issues,
            "paradigm_no_heterogeneous",
            f"{question_id} 的范式集合全部属于同一方法族 {sorted(distinct_families)}；"
            "至少要有 1 个异质族，否则五视角仍然是同族互抄。",
            severity=severity,
            question_id=question_id,
            families=sorted(distinct_families),
        )

    selection = question.get("paradigm_selection")
    selection = selection if isinstance(selection, list) else []
    if len(selection) < 2:
        _add_issue(
            issues,
            "paradigm_selection_invalid",
            f"{question_id} 的 paradigm_selection 少于 2 项；用户至少确认两个要探索的范式。",
            severity=severity,
            question_id=question_id,
            selection=selection,
        )
    else:
        unknown = [item for item in selection if str(item) not in [str(pid) for pid in paradigm_ids]]
        if unknown:
            _add_issue(
                issues,
                "paradigm_selection_invalid",
                f"{question_id} 的 paradigm_selection 含 paradigm_set 里不存在的 id: {unknown}。",
                severity=severity,
                question_id=question_id,
                unknown=unknown,
            )
        selected_families = {
            family_by_id.get(str(item), "") for item in selection if str(item) in family_by_id
        }
        selected_families.discard("")
        if len(selected_families) < 2:
            _add_issue(
                issues,
                "paradigm_selection_not_heterogeneous",
                f"{question_id} 的 paradigm_selection 只覆盖 {sorted(selected_families)} 一个方法族；"
                "选中的范式里至少要有 1 个异质族。",
                severity=severity,
                question_id=question_id,
                families=sorted(selected_families),
            )
    checks.append({"name": "paradigm_selection", "question_id": question_id, "passed": bool(selection)})
    return True


def _trials_index(trials: dict) -> dict[tuple[str, str], dict]:
    """把 perspective_trials.json 摊平成 {(option_id, slice_id): run}，同键取 run_seq 最大的。"""
    index: dict[tuple[str, str], dict] = {}
    for perspective in trials.get("perspectives") or []:
        if not isinstance(perspective, dict):
            continue
        option_id = str(perspective.get("option_id") or "")
        for run in perspective.get("runs") or []:
            if not isinstance(run, dict):
                continue
            key = (option_id, str(run.get("slice_id") or ""))
            existing = index.get(key)
            if existing is None or (run.get("run_seq") or 0) >= (existing.get("run_seq") or 0):
                index[key] = run
    return index


def _check_trials(
    root: Path,
    severity: str,
    issues: list[dict],
    checks: list[dict],
) -> tuple[dict | None, dict[tuple[str, str], dict]]:
    """校验 perspective_trials.json：覆盖、工具执行、可比指标键一致。"""
    trials_path = root / TRIALS_FILENAME
    trials, load_error = _load_json_file(trials_path)
    if trials is None:
        _add_issue(
            issues,
            "trials_missing",
            f"缺少 {TRIALS_FILENAME}（{load_error}）；B 闸门的数据对比必须来自工具执行的试算。",
            severity=severity,
        )
        checks.append({"name": "trials", "passed": False})
        return None, {}

    slices = trials.get("slices")
    slices = slices if isinstance(slices, list) else []
    slice_ids = [str(item.get("slice_id")) for item in slices if isinstance(item, dict) and _present(item.get("slice_id"))]
    checks.append({"name": "trials_slices", "passed": len(slice_ids) >= ADVICE_MIN_SLICES, "count": len(slice_ids)})
    if len(slice_ids) < ADVICE_MIN_SLICES:
        _add_issue(
            issues,
            "trials_slices_insufficient",
            f"{TRIALS_FILENAME} 只有 {len(slice_ids)} 个 slice，至少需要 {ADVICE_MIN_SLICES} 组数据对比"
            "（无数据集的小问改用 slice_axis=parameter/scenario）。",
            severity=severity,
            slice_ids=slice_ids,
        )

    perspectives = trials.get("perspectives")
    perspectives = perspectives if isinstance(perspectives, list) else []
    checks.append(
        {"name": "trials_perspectives", "passed": len(perspectives) >= ADVICE_MIN_PERSPECTIVES,
         "count": len(perspectives)}
    )
    if len(perspectives) < ADVICE_MIN_PERSPECTIVES:
        _add_issue(
            issues,
            "trials_perspectives_insufficient",
            f"{TRIALS_FILENAME} 只覆盖 {len(perspectives)} 个视角，要求 >= {ADVICE_MIN_PERSPECTIVES}。",
            severity=severity,
            count=len(perspectives),
        )

    comparable_keys_by_slice: dict[str, set[str]] = {}
    for perspective in perspectives:
        if not isinstance(perspective, dict):
            continue
        name = str(perspective.get("perspective") or "<unknown>")
        option_id = str(perspective.get("option_id") or "")
        runs = [run for run in (perspective.get("runs") or []) if isinstance(run, dict)]
        run_slices = {str(run.get("slice_id")) for run in runs}
        missing = [slice_id for slice_id in slice_ids if slice_id not in run_slices]
        if missing:
            _add_issue(
                issues,
                "trials_slice_coverage",
                f"视角 {name}（{option_id or '无 option_id'}）缺少 slice: {missing}。",
                severity=severity,
                perspective=name,
                option_id=option_id,
                missing=missing,
            )
        if not option_id:
            _add_issue(
                issues,
                "trials_option_id_missing",
                f"视角 {name} 没有 option_id，无法与建议候选对账。",
                severity=severity,
                perspective=name,
            )
        for run in runs:
            if run.get("executed_by") != "tool":
                _add_issue(
                    issues,
                    "trials_not_tool_executed",
                    f"视角 {name} 的 slice={run.get('slice_id')!r} 记录 executed_by={run.get('executed_by')!r}；"
                    "试算只能由 tools/perspective_trial_runner.py 执行并留痕，手填数字不算证据。",
                    severity=severity,
                    perspective=name,
                    slice_id=run.get("slice_id"),
                )
            if not isinstance(run.get("exit_code"), int) or isinstance(run.get("exit_code"), bool):
                _add_issue(
                    issues,
                    "trials_not_tool_executed",
                    f"视角 {name} 的 slice={run.get('slice_id')!r} 缺少整数 exit_code。",
                    severity=severity,
                    perspective=name,
                    slice_id=run.get("slice_id"),
                )
            for field in ("stdout_sha256", "captured_at"):
                if not _present(run.get(field)):
                    _add_issue(
                        issues,
                        "trials_field_missing",
                        f"视角 {name} 的 slice={run.get('slice_id')!r} 缺少 {field}；run 不是 runner 写的。",
                        severity=severity,
                        perspective=name,
                        slice_id=run.get("slice_id"),
                        field=field,
                    )
            metrics = run.get("metrics")
            comparable = metrics.get("comparable") if isinstance(metrics, dict) else None
            if isinstance(comparable, dict):
                comparable_keys_by_slice.setdefault(str(run.get("slice_id")), set()).update(comparable.keys())

    # 同一 slice 下"全部视角都必须有的可比键"：取交集应等于并集（否则有视角少给键）。
    run_keys_by_slice: dict[str, list[set[str]]] = {}
    for perspective in perspectives:
        if not isinstance(perspective, dict):
            continue
        for run in perspective.get("runs") or []:
            if not isinstance(run, dict):
                continue
            metrics = run.get("metrics")
            comparable = metrics.get("comparable") if isinstance(metrics, dict) else None
            if isinstance(comparable, dict):
                run_keys_by_slice.setdefault(str(run.get("slice_id")), []).append(set(comparable.keys()))
    for slice_id, key_sets in run_keys_by_slice.items():
        if not key_sets:
            continue
        union = set().union(*key_sets)
        if any(keys != union for keys in key_sets):
            _add_issue(
                issues,
                "trials_metric_keys_mismatch",
                f"slice={slice_id} 下各视角的 comparable 指标键不一致："
                f"应为 {sorted(union)}，存在缺键的 run。",
                severity=severity,
                slice_id=slice_id,
                expected=sorted(union),
            )

    comparable_definitions = (trials.get("metric_definitions") or {}).get("comparable")         if isinstance(trials.get("metric_definitions"), dict) else None
    checks.append(
        {"name": "trials_metric_definitions", "passed": bool(comparable_definitions)}
    )
    if not comparable_definitions:
        _add_issue(
            issues,
            "trials_metric_definitions_missing",
            f"{TRIALS_FILENAME} 缺少 metric_definitions.comparable，无法判定横向可比口径。",
            severity=severity,
        )

    return trials, _trials_index(trials)


def _check_advice(
    question_id: str,
    advice: dict,
    board_options: list[dict],
    trials_index: dict[tuple[str, str], dict],
    severity: str,
    issues: list[dict],
    checks: list[dict],
) -> None:
    """校验 model_advice.json 的 8 条硬规则 + 与 trials 的数值一致性。"""
    if advice.get("is_judge_panel") is not False:
        _add_issue(
            issues,
            "advice_is_not_judge_panel",
            f"{question_id} 的 model_advice.json 必须显式写 is_judge_panel=false；"
            "选型建议不是评委审查（评委审查在 Phase 4）。",
            severity=severity,
            question_id=question_id,
            value=advice.get("is_judge_panel"),
        )
    if not _present(advice.get("disclaimer")):
        _add_issue(issues, "advice_is_not_judge_panel",
                   f"{question_id} 的 model_advice.json 缺少 disclaimer 声明。",
                   severity=severity, question_id=question_id)

    dumped = json.dumps(advice, ensure_ascii=False)
    hits = [pattern for pattern in JUDGE_WORDING_PATTERNS if pattern in dumped]
    if hits:
        _add_issue(
            issues,
            "advice_no_judge_wording",
            f"{question_id} 的建议里出现评委结论措辞 {hits}；建议 Agent 不得冒充评委。",
            severity=severity,
            question_id=question_id,
            hits=hits,
        )

    candidates = advice.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    checks.append({"name": "advice_candidates", "question_id": question_id, "passed": True,
                   "count": len(candidates)})
    if not (ADVICE_MIN_CANDIDATES <= len(candidates) <= ADVICE_MAX_CANDIDATES):
        _add_issue(
            issues,
            "advice_candidates_count",
            f"{question_id} 有 {len(candidates)} 个候选，要求 {ADVICE_MIN_CANDIDATES}-{ADVICE_MAX_CANDIDATES} 个"
            "（五视角至少 5 个；追加动态专家最多 8 个；baseline 不占名额）。",
            severity=severity,
            question_id=question_id,
            count=len(candidates),
        )

    recommended = [item for item in candidates
                   if isinstance(item, dict) and item.get("verdict") == "recommended"]
    if len(recommended) != 1:
        _add_issue(
            issues,
            "advice_one_recommended",
            f"{question_id} 有 {len(recommended)} 个 verdict=recommended，必须恰好 1 个。",
            severity=severity,
            question_id=question_id,
            count=len(recommended),
        )
    recommended_id = advice.get("recommended_option_id")
    if len(recommended) == 1 and _present(recommended_id):
        if str(recommended[0].get("option_id")) != str(recommended_id):
            _add_issue(
                issues,
                "advice_one_recommended",
                f"{question_id} 的 recommended_option_id={recommended_id!r} 与 verdict=recommended 的候选不一致。",
                severity=severity,
                question_id=question_id,
            )

    rubric = advice.get("scoring_rubric")
    dimension_ids: list[str] = []
    if isinstance(rubric, dict):
        for dimension in rubric.get("dimensions") or []:
            if isinstance(dimension, dict) and _present(dimension.get("id")):
                dimension_ids.append(str(dimension["id"]))
    if not dimension_ids:
        _add_issue(issues, "advice_scores_complete",
                   f"{question_id} 缺少 scoring_rubric.dimensions，分数没有统一量纲。",
                   severity=severity, question_id=question_id)

    option_ids = [str(item.get("id")) for item in board_options if isinstance(item, dict) and _present(item.get("id"))]
    candidate_ids = [str(item.get("option_id")) for item in candidates
                     if isinstance(item, dict) and _present(item.get("option_id"))]
    if option_ids and candidate_ids and sorted(option_ids) != sorted(candidate_ids):
        _add_issue(
            issues,
            "advice_option_mismatch",
            f"{question_id} 的板候选 {sorted(option_ids)} 与建议候选 {sorted(candidate_ids)} 不是一一对应。",
            severity=severity,
            question_id=question_id,
            board_options=sorted(option_ids),
            advice_candidates=sorted(candidate_ids),
        )

    candidate_by_id = {str(item.get("option_id")): item for item in candidates if isinstance(item, dict)}
    for item in candidates:
        if not isinstance(item, dict):
            _add_issue(issues, "advice_candidates_count",
                       f"{question_id} 的候选列表里混入了非对象元素。", severity=severity,
                       question_id=question_id)
            continue
        option_id = str(item.get("option_id") or "<missing>")
        score = item.get("score")
        if not _is_number(score) or not (0 <= float(score) <= 100):
            _add_issue(
                issues,
                "advice_scores_complete",
                f"{question_id} 的候选 {option_id} 的 score={score!r} 不是 0-100 的数值。",
                severity=severity,
                question_id=question_id,
                option_id=option_id,
            )
        dimension_scores = item.get("dimension_scores")
        if isinstance(dimension_scores, dict) and dimension_ids:
            missing_dims = [dim for dim in dimension_ids if not _is_number(dimension_scores.get(dim))]
            if missing_dims:
                _add_issue(
                    issues,
                    "advice_scores_complete",
                    f"{question_id} 的候选 {option_id} 缺少维度分 {missing_dims}。",
                    severity=severity,
                    question_id=question_id,
                    option_id=option_id,
                    missing=missing_dims,
                )
        pros = item.get("pros") if isinstance(item.get("pros"), list) else []
        cons = item.get("cons") if isinstance(item.get("cons"), list) else []
        if len(pros) < 2 or len(cons) < 2:
            _add_issue(
                issues,
                "advice_pros_cons",
                f"{question_id} 的候选 {option_id} 的 pros/cons 各需 >=2 条（当前 {len(pros)}/{len(cons)}）。",
                severity=severity,
                question_id=question_id,
                option_id=option_id,
                pros=len(pros),
                cons=len(cons),
            )
        if item.get("verdict") != "recommended":
            why_not = item.get("why_not") if isinstance(item.get("why_not"), list) else []
            if len(why_not) < 2 or not _present(item.get("when_better")):
                _add_issue(
                    issues,
                    "advice_why_not_when_better",
                    f"{question_id} 的不推荐候选 {option_id} 必须写 why_not >=2 条 + when_better。",
                    severity=severity,
                    question_id=question_id,
                    option_id=option_id,
                    why_not=len(why_not),
                )

    data_comparison = advice.get("data_comparison")
    rows = data_comparison.get("rows") if isinstance(data_comparison, dict) else None
    rows = rows if isinstance(rows, list) else []
    slice_ids: list[str] = []
    for row in rows:
        if isinstance(row, dict) and _present(row.get("slice_id")):
            slice_id = str(row["slice_id"])
            if slice_id not in slice_ids:
                slice_ids.append(slice_id)
    checks.append({"name": "advice_data_comparison", "question_id": question_id,
                   "passed": len(slice_ids) >= ADVICE_MIN_SLICES,
                   "slice_count": len(slice_ids)})
    if len(slice_ids) < ADVICE_MIN_SLICES:
        _add_issue(
            issues,
            "advice_data_comparison",
            f"{question_id} 的 data_comparison 只有 {len(slice_ids)} 个 slice，要求 >= {ADVICE_MIN_SLICES}。",
            severity=severity,
            question_id=question_id,
            slice_count=len(slice_ids),
        )

    for slice_id in slice_ids:
        covered = {str(row.get("option_id")) for row in rows
                   if isinstance(row, dict) and str(row.get("slice_id")) == slice_id}
        missing = [cid for cid in candidate_ids if cid not in covered]
        if missing:
            _add_issue(
                issues,
                "advice_data_comparison",
                f"{question_id} 的 slice={slice_id} 没有覆盖候选 {missing}；对比表必须覆盖全部候选。",
                severity=severity,
                question_id=question_id,
                slice_id=slice_id,
                missing=missing,
            )
        key_sets = []
        for row in rows:
            if not isinstance(row, dict) or str(row.get("slice_id")) != slice_id:
                continue
            comparable = row.get("comparable")
            if isinstance(comparable, dict):
                key_sets.append(set(comparable.keys()))
        if key_sets:
            union = set().union(*key_sets)
            if any(keys != union for keys in key_sets):
                _add_issue(
                    issues,
                    "advice_comparable_metrics",
                    f"{question_id} 的 slice={slice_id} 上各候选 comparable 键不一致：应为 {sorted(union)}。",
                    severity=severity,
                    question_id=question_id,
                    slice_id=slice_id,
                    expected=sorted(union),
                )

    for row in rows:
        if not isinstance(row, dict):
            continue
        option_id = str(row.get("option_id") or "")
        slice_id = str(row.get("slice_id") or "")
        key = (option_id, slice_id)
        if option_id == "baseline":
            continue
        if not _present(row.get("trials_ref")):
            _add_issue(
                issues,
                "advice_trials_ref_valid",
                f"{question_id} 的对比行 ({option_id}, {slice_id}) 没有 trials_ref，数值无法回溯。",
                severity=severity,
                question_id=question_id,
                option_id=option_id,
                slice_id=slice_id,
            )
        run = trials_index.get(key)
        if run is None:
            if trials_index:
                _add_issue(
                    issues,
                    "advice_trials_ref_valid",
                    f"{question_id} 的对比行 ({option_id}, {slice_id}) 在 perspective_trials.json 里找不到对应 run。",
                    severity=severity,
                    question_id=question_id,
                    option_id=option_id,
                    slice_id=slice_id,
                )
            continue
        run_metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
        for layer in ("comparable", "own"):
            claimed = row.get(layer)
            if not isinstance(claimed, dict):
                continue
            actual = run_metrics.get(layer) if isinstance(run_metrics.get(layer), dict) else {}
            for metric_key, claimed_value in claimed.items():
                actual_value = actual.get(metric_key)
                if _is_number(claimed_value) and _is_number(actual_value):
                    if abs(float(claimed_value) - float(actual_value)) > ADVICE_NUMBER_TOLERANCE:
                        _add_issue(
                            issues,
                            "advice_number_mismatch",
                            f"{question_id} 的 ({option_id}, {slice_id}) 指标 {metric_key}="
                            f"{claimed_value!r} 与试算记录的 {actual_value!r} 不一致；数字不得手改。",
                            severity=severity,
                            question_id=question_id,
                            option_id=option_id,
                            slice_id=slice_id,
                            metric=metric_key,
                            claimed=claimed_value,
                            actual=actual_value,
                        )
                elif claimed_value != actual_value:
                    _add_issue(
                        issues,
                        "advice_number_mismatch",
                        f"{question_id} 的 ({option_id}, {slice_id}) 指标 {metric_key} 与试算记录不一致。",
                        severity=severity,
                        question_id=question_id,
                        option_id=option_id,
                        slice_id=slice_id,
                        metric=metric_key,
                    )
        candidate = candidate_by_id.get(option_id)
        if candidate is not None and _is_number(candidate.get("score")):
            continue


def check_design_board(
    workspace: str,
    mode: str = "standard",
    cross_audit: bool = True,
    skip_timeline: bool = False,
    allow_legacy: bool = False,
    gate: str = "a",
    board_path: str | None = None,
) -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    gate = (gate or "a").lower()
    if gate not in BOARD_FILES:
        gate = "a"
    resolved_board = Path(board_path) if board_path else (root / BOARD_FILES[gate])
    path = resolved_board
    fixture = _is_fixture_directory(root)

    if not path.exists():
        return _missing_result(root, normalized_mode, cross_audit, allow_legacy, gate, resolved_board)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _invalid_json_result(
            root, normalized_mode, cross_audit, f"{path.name} 不是合法 JSON: {exc}", gate, resolved_board
        )
    if not isinstance(payload, dict):
        return _invalid_json_result(
            root, normalized_mode, cross_audit, f"{path.name} 顶层必须是 JSON 对象。", gate, resolved_board
        )

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

    schema = _board_schema(payload)
    lane = "b" if gate == "b" else "a"
    trials_payload: dict | None = None
    trials_index: dict[tuple[str, str], dict] = {}
    advice_file: dict | None = None
    if lane == "b":
        trials_payload, trials_index = _check_trials(root, severity, issues, checks)
        advice_file, advice_error = _load_json_file(root / ADVICE_FILENAME)
        if advice_file is None:
            _add_issue(
                issues,
                "advice_missing",
                f"缺少 {ADVICE_FILENAME}（{advice_error}）；B 闸门的候选与打分必须来自建议 Agent 的结构化文件。",
                severity=severity,
            )
            checks.append({"name": "advice", "passed": False})
        else:
            checks.append({"name": "advice", "passed": True})
            claimed_sha = str(payload.get("advice_sha256") or "").strip().lower()
            if claimed_sha:
                actual_sha = _sha256_file(root / ADVICE_FILENAME)
                if claimed_sha != actual_sha:
                    _add_issue(
                        issues,
                        "advice_board_mismatch",
                        "B 板的 advice_sha256 与 model_advice.json 实际内容不一致：板里展示的建议不是当前建议文件。",
                        severity="error",
                        claimed=claimed_sha,
                        actual=actual_sha,
                    )
            reference = str(payload.get("advice_ref") or ADVICE_FILENAME)
            if Path(reference).name != ADVICE_FILENAME:
                _add_issue(
                    issues,
                    "advice_board_mismatch",
                    f"advice_ref={reference!r} 不是 {ADVICE_FILENAME}；B 板的建议来源必须唯一。",
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
        paradigm_mode = False
        if lane == "a":
            paradigm_mode = _check_paradigm_set(question, question_id, schema, severity, issues, checks)
            # 只有 schema v2 的新 A 板才禁止 user_locked：旧板（schema<2）本来就是"候选板"，
            # user_locked 在那里是有意义的历史字段，不能因为升级检查器就判旧工作区红。
            if schema >= 2 and question.get("user_locked") is True:
                _add_issue(
                    issues,
                    "gate_a_user_locked_forbidden",
                    f"{question_id} 的 A 板仍写着 user_locked=true；框架闸门只确认范式边界，不锁定模型选型。",
                    severity=severity,
                    question_id=question_id,
                )
            if paradigm_mode and _present(question.get("user_choice")):
                _add_issue(
                    issues,
                    "gate_a_user_choice_should_be_empty",
                    f"{question_id} 的 A 板仍有 user_choice={question.get('user_choice')!r}；"
                    "模型选择只能由 B 闸门的 user_choice 决定。",
                    severity=severity,
                    question_id=question_id,
                )

        options = question.get("options")
        options = options if isinstance(options, list) else []
        if lane == "b":
            minimum: int = ADVICE_MIN_CANDIDATES
            maximum: int | None = ADVICE_MAX_CANDIDATES
            required_fields = B_OPTION_REQUIRED_FIELDS
        elif paradigm_mode:
            minimum = 0
            maximum = None
            required_fields = A_OPTION_REQUIRED_FIELDS
        else:
            minimum = 2
            maximum = None
            required_fields = OPTION_REQUIRED_FIELDS

        options_ok = len(options) >= minimum and (maximum is None or len(options) <= maximum)
        checks.append(
            {"name": "options", "question_id": question_id, "passed": options_ok, "count": len(options)}
        )
        if not options_ok:
            if lane == "b":
                message = (
                    f"{question_id} 有 {len(options)} 个候选，B 闸门要求 {minimum}-{maximum} 个"
                    "（五视角至少 5 个，追加动态专家最多 8 个）。"
                )
            else:
                message = (
                    f"{question_id} 只有 {len(options)} 个候选方案，至少需要 2 个（推荐 + 备选）才能让用户比较。"
                )
            _add_issue(
                issues,
                "insufficient_options",
                message,
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
            for field in required_fields:
                if not _present(option.get(field)):
                    _add_issue(
                        issues,
                        "missing_option_field",
                        f"{question_id} 的候选 {option_label} 缺少 {field}。",
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

        if lane == "b":
            if not _present(user_choice):
                _add_issue(
                    issues,
                    "user_choice_present",
                    f"{question_id} 的 B 板还没有 user_choice；模型必须由用户在板上亲自选定。",
                    severity=severity,
                    question_id=question_id,
                )
            if question.get("preauthorized") is True and strict:
                _add_issue(
                    issues,
                    "preauthorized_not_attested",
                    f"{question_id} 使用了 preauthorized=true（按建议自动执行）；excellence 语义要求每问由人选定模型，"
                    "预授权只能留痕，不能当人工确认。",
                    severity="error",
                    question_id=question_id,
                )
            # 优先用文件内容做校验：文件是"建议 Agent 的产物"，板里的 advice 只是渲染副本。
            # 两者不一致由 advice_board_mismatch 单独报，不因为副本旧就跳过实质检查。
            resolved_advice: dict | None = None
            embedded = question.get("advice")
            if advice_file is not None:
                normalized_qid = str(question_id).strip().lower()
                nested = advice_file.get("questions")
                if isinstance(nested, dict):
                    for key, value in nested.items():
                        if str(key).strip().lower() == normalized_qid and isinstance(value, dict):
                            resolved_advice = value
                            break
                elif str(advice_file.get("question_id") or "").strip().lower() == normalized_qid:
                    resolved_advice = advice_file
                elif len(questions) == 1 and _present(advice_file.get("candidates")):
                    resolved_advice = advice_file
            if resolved_advice is None and isinstance(embedded, dict):
                resolved_advice = embedded
            if resolved_advice is None:
                if advice_file is not None:
                    _add_issue(
                        issues,
                        "advice_missing",
                        f"{question_id} 在 {ADVICE_FILENAME} 里找不到对应建议（question_id 对不上），"
                        "板里也没有嵌入 advice。",
                        severity=severity,
                        question_id=question_id,
                    )
            else:
                _check_advice(question_id, resolved_advice, options, trials_index, severity, issues, checks)

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

    rounds_dir = root / ROUNDS_DIRS.get(gate, ROUNDS_DIRS["a"])
    rounds = _read_rounds(rounds_dir)
    checks.append(
        {
            "name": "design_rounds",
            "passed": bool(rounds),
            "count": len(rounds),
            "path": str(rounds_dir),
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
        if lane == "b":
            timeline_code = "code_written_before_gate_b"
        elif schema >= 2:
            timeline_code = "code_written_before_gate_a"
        else:
            # 旧板（schema<2）保留原 failure code，历史报告与测试的锚点不变。
            timeline_code = "code_written_before_confirm"
        for violation in violations:
            _add_issue(
                issues,
                timeline_code,
                f"{violation['file']} 的 mtime 早于 {gate} 闸门 confirmed_at 约 "
                f"{violation['seconds_before']} 秒，疑似先写代码、后补确认板。",
                severity=severity,
                gate=gate,
                file=violation["file"],
                mtime=violation["mtime"],
                confirmed_at=_format_timestamp(confirmed_ts),
                seconds_before=violation["seconds_before"],
            )

    # ---------- C. 交叉校验（方案 C：板与审计必须能对账） ----------
    if not cross_audit:
        cross_audit_state = "skipped"
        checks.append({"name": "board_audit", "passed": True, "skipped": True, "reason": "cross_audit_disabled"})
    elif lane == "a" and schema >= 2:
        # A 板 v2 只确认"题意框架 + 待探索范式"，此时 model_selection_audit.json 还没产出，
        # 拿它来对账必然是假阴性。真正的候选↔选择对账在 B 闸门。
        # 旧板（schema<2）仍然是"候选板"，保留原交叉校验行为，不做降级。
        cross_audit_state = "framework_only"
        checks.append(
            {"name": "board_audit", "passed": True, "skipped": True, "reason": "gate_a_framework_only"}
        )
        _add_issue(
            issues,
            "paradigm_audit_pending",
            "A 闸门只对账范式边界；模型候选与最终选择的对账由 B 闸门（design_board_gate_b.json）负责。",
            severity="warning",
            governance="gate_a",
        )
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
        "gate": gate,
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
    parser.add_argument(
        "--gate",
        default="a",
        choices=["a", "b"],
        help="a=框架与探索边界闸门（design_board.json）；b=方案择定闸门（design_board_gate_b.json）",
    )
    parser.add_argument(
        "--board",
        default=None,
        help="显式指定板文件路径（默认按 --gate 解析到 --workspace 下的固定文件名）",
    )
    args = parser.parse_args()
    try:
        result = check_design_board(
            args.workspace,
            args.mode,
            cross_audit=not args.no_cross_audit,
            skip_timeline=args.skip_timeline,
            allow_legacy=args.allow_legacy,
            gate=args.gate,
            board_path=args.board,
        )
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
