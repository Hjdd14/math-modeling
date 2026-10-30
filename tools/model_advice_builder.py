#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选型建议骨架生成与硬规则校验（B 闸门：model_advice.json）。

    python tools/model_advice_builder.py assemble --workspace questions/q1
    python tools/model_advice_builder.py validate --workspace questions/q1 --mode excellence

契约：D:/Code_Work/_two_gate/CONTRACT.md §6 / §8.3。两条不可让步的性质：

1. **数字只认 trials**：候选 id / origin / name / paradigm_id / 证据引用 / data_comparison 的
   comparable 与 own 全部由本工具从 perspective_trials.json 回填，Agent 只填判断类字段
   （score / pros / cons / why_not / when_better / recommended_option_id / aggregate_note）。
   Agent 改过的数字由 validate 以 advice_number_mismatch 报出（容差 1e-9），不靠自觉。
2. **建议不是评委**：is_judge_panel 恒为 false，全文禁止"评委通过/不通过/评审结论"类措辞；
   Phase 4 的评委组不受本工具影响。

仅用标准库，不联网，不调用 LLM。
"""

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

ADVICE_FILENAME = "model_advice.json"
TRIALS_FILENAME = "perspective_trials.json"
AGENT_OUTPUT_DIRNAME = "agent_outputs"
SCHEMA_VERSION = 2
TOLERANCE = 1e-9
MIN_CANDIDATES = 5
MAX_CANDIDATES = 8
MIN_PRO_CON = 2
MIN_WHY_NOT = 2
MIN_SLICES = 2
DISCLAIMER = "本文件是选型建议，不是评委审查。评委审查在 Phase 4。"
JUDGE_WORDINGS = ("评委通过", "评委不通过", "评审结论", "评审通过")
MODE_CHOICES = ("standard", "excellence")
HELP_EPILOG = "契约见 docs/DESIGN_GATE_PLAN.md §21"
# mode 映射钩子：standard 下这三条先留痕（warning），excellence 全 error。
# 其余 §6 硬规则两种档位下都是 error——它们属于"证据链断裂"（手填数字、无 run 可回溯、
# 冒充评委结论）或候选资格问题，不能按档位放宽。
STANDARD_WARNING_CODES = frozenset({
    "advice_candidates_count",
    "advice_data_comparison",
    "advice_pros_cons",
})

# 默认评分维度：只是一个固定的键集合，权重与分值由 Agent 按题目填，工具不评分
DEFAULT_RUBRIC = {
    "dimensions": [
        {"id": "fit", "name": "题意契合度", "weight": 0.3},
        {"id": "rigor", "name": "方法严谨性", "weight": 0.25},
        {"id": "evidence", "name": "数据支持度", "weight": 0.25},
        {"id": "risk", "name": "实施与解释风险(反向)", "weight": 0.2},
    ],
    "scale": "0-100",
}

NAME_KEYS = ("model_name", "name", "option_name", "title")
PARADIGM_KEYS = ("paradigm_id", "paradigm")
NESTED_KEYS = ("model", "final_model", "model_spec", "final_solution", "selection")


def output(result: dict):
    """统一 JSON 输出到 stdout。"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr 并退出。"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _now_iso() -> str:
    """本地时间 ISO8601（带时区偏移）。"""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _require_workspace(workspace) -> Path:
    """工作区必须存在，返回绝对路径。"""
    path = Path(workspace).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"工作目录不存在: {path}")
    return path


def _resolve(workspace_path: Path, relative) -> Path:
    """相对路径先按工作区解析，再做兜底，保证默认文件都落在 --workspace 下。"""
    path = Path(str(relative)).expanduser()
    return path if path.is_absolute() else (workspace_path / path)


def _load_json(path: Path) -> dict:
    """读取 JSON 对象；结构不对就报错，不猜测。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path} 不是合法 JSON（{exc}）") from exc
    except OSError as exc:
        raise ValueError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层应为 JSON 对象")
    return data


def _write_json(path: Path, payload: dict):
    """原子写（tmp + replace）：中断不会留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _is_number(value) -> bool:
    """是否真实数值（排除 bool）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not (isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))))


def _same_value(left, right, tol: float = TOLERANCE) -> bool:
    """严格同值比较：bool 只与 bool 相等，数值按容差，其余按相等。"""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if _is_number(left) and _is_number(right):
        return abs(float(left) - float(right)) <= tol
    if left is None or right is None:
        return left is None and right is None
    return left == right


def _add_issue(issues: list, code: str, message: str, severity: str = "error"):
    """追加一条 issue（字段与契约 §8.3 一致：code / message / severity）。"""
    issues.append({"code": code, "message": message, "severity": severity})


def _latest_runs(trials: dict) -> dict:
    """(option_id, slice_id) → 最大 run_seq 的那条 run（契约 §7：校验取最大 run_seq）。"""
    latest = {}
    for entry in trials.get("perspectives") or []:
        if not isinstance(entry, dict):
            continue
        option_id = str(entry.get("option_id") or "")
        for run in entry.get("runs") or []:
            if not isinstance(run, dict):
                continue
            key = (option_id, str(run.get("slice_id") or ""))
            previous = latest.get(key)
            if previous is None or int(run.get("run_seq") or 0) >= int(previous.get("run_seq") or 0):
                latest[key] = run
    return latest


def _pick_text(data: dict, keys) -> str:
    """从 Agent 产物里挑一个非空字符串字段（先顶层，再常见嵌套结构）。"""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for nested in NESTED_KEYS:
        inner = data.get(nested)
        if not isinstance(inner, dict):
            continue
        for key in keys:
            value = inner.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _pick_paradigm(data: dict) -> str:
    """提取范式 id：字符串直接取，对象则取其中的 paradigm_id / id。"""
    for source in [data] + [data.get(key) for key in NESTED_KEYS]:
        if not isinstance(source, dict):
            continue
        for key in PARADIGM_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for inner_key in ("paradigm_id", "id"):
                    inner = value.get(inner_key)
                    if isinstance(inner, str) and inner.strip():
                        return inner.strip()
    return ""


def _agent_output_index(outputs_dir: Path) -> dict:
    """扫描 agent_outputs/ 下的 revised_*.json（缺失时退回 initial_*.json），按视角名建索引。"""
    index = {}
    if not outputs_dir.is_dir():
        return index
    for prefix in ("revised_", "initial_"):
        for path in sorted(outputs_dir.glob(prefix + "*.json")):
            name = path.stem[len(prefix):]
            if not name or name in index:
                continue  # revised 优先：先扫 revised_，已命中就不再被 initial_ 覆盖
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            index[name] = {
                "name": _pick_text(data, NAME_KEYS),
                "paradigm_id": _pick_paradigm(data),
                "source": path.name,
            }
    return index


def _rubric_ids(rubric) -> list:
    """评分维度的 id 列表（顺序保留）。"""
    if not isinstance(rubric, dict):
        return []
    ids = []
    for item in rubric.get("dimensions") or []:
        if isinstance(item, dict) and str(item.get("id") or "").strip():
            ids.append(str(item["id"]).strip())
    return ids


def assemble(workspace, *, input_dir=None, trials=None, question_id=None) -> dict:
    """从 perspective_trials.json + agent_outputs/revised_*.json 生成 model_advice.json 骨架。"""
    workspace_path = _require_workspace(workspace)
    trials_path = _resolve(workspace_path, trials or TRIALS_FILENAME)
    if not trials_path.is_file():
        raise FileNotFoundError(f"{trials_path} 不存在：请先用 perspective_trial_runner.py 跑出试算")
    trials_doc = _load_json(trials_path)

    entries = [item for item in trials_doc.get("perspectives") or [] if isinstance(item, dict)]
    if not entries:
        raise ValueError(f"{trials_path} 里没有任何视角条目，无法生成候选")
    slices = [str(item.get("slice_id")) for item in trials_doc.get("slices") or []
              if isinstance(item, dict) and item.get("slice_id")]

    outputs_dir = _resolve(workspace_path, input_dir or AGENT_OUTPUT_DIRNAME)
    agent_index = _agent_output_index(outputs_dir)
    latest = _latest_runs(trials_doc)

    advice_path = workspace_path / ADVICE_FILENAME
    previous = _load_json(advice_path) if advice_path.is_file() else {}
    # 维度键集合随骨架一起固定：Agent 只需要填 0–100 的数，不用自己发明维度
    rubric = previous.get("scoring_rubric") if isinstance(previous.get("scoring_rubric"), dict) else None
    if not _rubric_ids(rubric):
        rubric = copy.deepcopy(DEFAULT_RUBRIC)
    rubric_ids = _rubric_ids(rubric)
    previous_candidates = {
        str(item.get("option_id")): item for item in previous.get("candidates") or []
        if isinstance(item, dict) and item.get("option_id")
    }

    candidates, rows, missing = [], [], []
    for entry in entries:
        option_id = str(entry.get("option_id") or "").strip()
        perspective = str(entry.get("perspective") or "").strip()
        if not option_id:
            continue
        info = agent_index.get(perspective) or {}
        prev = previous_candidates.get(option_id) or {}
        dims = prev.get("dimension_scores") if isinstance(prev.get("dimension_scores"), dict) else {}
        candidates.append({
            "option_id": option_id,
            "origin": str(prev.get("origin") or f"perspective:{perspective}"),
            # 名字优先取该视角的 revised 产物；没有产物时用视角名占位（可追溯，不编造模型名）
            "name": info.get("name") or str(prev.get("name") or "") or perspective,
            "paradigm_id": info.get("paradigm_id") or prev.get("paradigm_id"),
            # 以下判断类字段留给 Agent：工具不猜推荐谁、也不打分
            "verdict": prev.get("verdict"),
            "score": prev.get("score"),
            "dimension_scores": {dim: dims.get(dim) for dim in rubric_ids},
            "pros": list(prev.get("pros") or []),
            "cons": list(prev.get("cons") or []),
            "why_not": list(prev.get("why_not") or []),
            "when_better": prev.get("when_better"),
            "evidence_refs": [f"{TRIALS_FILENAME}#{option_id}/{slice_id}" for slice_id in slices],
        })
        for slice_id in slices:
            run = latest.get((option_id, slice_id))
            metrics = run.get("metrics") if isinstance(run, dict) else None
            if not isinstance(metrics, dict):
                missing.append(f"{option_id}/{slice_id}")
                continue
            rows.append({
                "slice_id": slice_id,
                "option_id": option_id,
                "trials_ref": f"{option_id}/{slice_id}",
                # 数值一律照抄 trials，Agent 不得改
                "comparable": dict(metrics.get("comparable") or {}),
                "own": dict(metrics.get("own") or {}),
            })

    declared = [str(item.get("key")) for item in
                ((trials_doc.get("metric_definitions") or {}).get("comparable") or [])
                if isinstance(item, dict) and item.get("key")]
    if not declared and rows:
        declared = list(rows[0]["comparable"].keys())

    baseline_row = previous.get("data_comparison", {}).get("baseline_row") \
        if isinstance(previous.get("data_comparison"), dict) else None
    advice = {
        "schema_version": SCHEMA_VERSION,
        "question_id": question_id or trials_doc.get("question_id"),
        "generated_at": _now_iso(),
        "is_judge_panel": False,
        "disclaimer": DISCLAIMER,
        "scoring_rubric": rubric,
        "candidates": candidates,
        "data_comparison": {
            "comparable_columns": declared,
            "rows": rows,
            "baseline_row": baseline_row,
        },
        "recommended_option_id": previous.get("recommended_option_id"),
        "aggregate_note": previous.get("aggregate_note"),
    }
    _write_json(advice_path, advice)

    pending = ["verdict", "score", "dimension_scores", "pros", "cons",
               "why_not", "when_better", "recommended_option_id", "aggregate_note"]
    warnings = []
    if len(candidates) < MIN_CANDIDATES:
        warnings.append(f"候选只有 {len(candidates)} 个；契约 §6 要求 {MIN_CANDIDATES}–{MAX_CANDIDATES}，validate 会判 advice_candidates_count")
    if len(slices) < MIN_SLICES:
        warnings.append(f"trials 只声明了 {len(slices)} 个 slice；契约 §6 要求 ≥{MIN_SLICES}，validate 会判 advice_data_comparison")
    if missing:
        warnings.append(f"有 {len(missing)} 格没有成功试算，data_comparison 不会编造这些格：{', '.join(missing[:8])}")

    return {
        "ok": True,
        "workspace": str(workspace_path),
        "advice_file": str(advice_path),
        "trials_file": str(trials_path),
        "question_id": advice["question_id"],
        "candidates": len(candidates),
        "rows": len(rows),
        "slices": slices,
        "comparable_columns": declared,
        "agent_outputs_used": {name: info.get("source") for name, info in sorted(agent_index.items())},
        "pending_agent_fields": pending,
        "missing_trial_cells": missing,
        "warnings": warnings,
    }


def _check_candidates_count(candidates: list, issues: list):
    """advice_candidates_count：候选数 5–8（baseline 不占名额）。"""
    count = len(candidates)
    if not MIN_CANDIDATES <= count <= MAX_CANDIDATES:
        _add_issue(issues, "advice_candidates_count",
                   f"候选数 {count} 不在 {MIN_CANDIDATES}–{MAX_CANDIDATES} 范围内；"
                   f"baseline 只作参照行，不占候选名额。")


def _check_one_recommended(candidates: list, advice: dict, issues: list):
    """advice_one_recommended：恰好 1 个 recommended，且 recommended_option_id 与之一致。"""
    recommended = [str(item.get("option_id")) for item in candidates
                   if item.get("verdict") == "recommended"]
    if len(recommended) != 1:
        _add_issue(issues, "advice_one_recommended",
                   f"verdict=recommended 的候选有 {len(recommended)} 个（{recommended or '无'}）；必须恰好 1 个")
        return
    declared = advice.get("recommended_option_id")
    if declared != recommended[0]:
        _add_issue(issues, "advice_one_recommended",
                   f"recommended_option_id={declared!r} 与唯一 recommended 候选 {recommended[0]!r} 不一致")


def _check_scores(candidates: list, rubric_ids: list, issues: list):
    """advice_scores_complete：全部候选有 0–100 分数，且维度键集合 = rubric 维度 id。"""
    if not rubric_ids:
        _add_issue(issues, "advice_scores_complete",
                   "scoring_rubric.dimensions 为空：无法判定维度分是否齐全")
        return
    for item in candidates:
        option_id = item.get("option_id")
        score = item.get("score")
        if not _is_number(score) or not 0 <= float(score) <= 100:
            _add_issue(issues, "advice_scores_complete",
                       f"{option_id} 的 score={score!r} 不是 0–100 的数值")
        dims = item.get("dimension_scores")
        if not isinstance(dims, dict):
            _add_issue(issues, "advice_scores_complete", f"{option_id} 缺少 dimension_scores 对象")
            continue
        missing = [dim for dim in rubric_ids if dim not in dims]
        extra = [key for key in dims if key not in rubric_ids]
        if missing or extra:
            _add_issue(issues, "advice_scores_complete",
                       f"{option_id} 的 dimension_scores 键集合与 scoring_rubric 不一致："
                       f"缺少 {missing}，多余 {extra}")
            continue
        for dim in rubric_ids:
            value = dims.get(dim)
            if not _is_number(value) or not 0 <= float(value) <= 100:
                _add_issue(issues, "advice_scores_complete",
                           f"{option_id} 的 dimension_scores.{dim}={value!r} 不是 0–100 的数值")


def _check_pros_cons(candidates: list, issues: list):
    """advice_pros_cons：每项 pros / cons 各 ≥2 条。"""
    for item in candidates:
        option_id = item.get("option_id")
        for field in ("pros", "cons"):
            values = item.get(field)
            filled = [text for text in values if isinstance(text, str) and text.strip()] \
                if isinstance(values, list) else []
            if len(filled) < MIN_PRO_CON:
                _add_issue(issues, "advice_pros_cons",
                           f"{option_id} 的 {field} 只有 {len(filled)} 条有效内容，要求 ≥{MIN_PRO_CON}")


def _check_why_not(candidates: list, issues: list):
    """advice_why_not_when_better：每个 not_recommended 需 why_not ≥2 条 + when_better 非空。"""
    for item in candidates:
        if item.get("verdict") != "not_recommended":
            continue
        option_id = item.get("option_id")
        values = item.get("why_not")
        filled = [text for text in values if isinstance(text, str) and text.strip()] \
            if isinstance(values, list) else []
        if len(filled) < MIN_WHY_NOT:
            _add_issue(issues, "advice_why_not_when_better",
                       f"{option_id} 是 not_recommended，但 why_not 只有 {len(filled)} 条有效内容，要求 ≥{MIN_WHY_NOT}")
        when_better = item.get("when_better")
        if not (isinstance(when_better, str) and when_better.strip()):
            _add_issue(issues, "advice_why_not_when_better",
                       f"{option_id} 是 not_recommended，但 when_better 为空：必须写清什么条件下它反而更优")


def _check_data_comparison(advice: dict, candidates: list, issues: list) -> list:
    """advice_data_comparison：≥2 个不同 slice，且每个 slice 覆盖全部候选；返回 rows。"""
    comparison = advice.get("data_comparison")
    if not isinstance(comparison, dict):
        _add_issue(issues, "advice_data_comparison", "缺少 data_comparison 对象")
        return []
    rows = comparison.get("rows")
    if not isinstance(rows, list) or not rows:
        _add_issue(issues, "advice_data_comparison", "data_comparison.rows 为空：没有任何实跑对比")
        return []

    slice_ids = []
    for row in rows:
        if isinstance(row, dict) and row.get("slice_id") not in slice_ids:
            slice_ids.append(row.get("slice_id"))
    if len(slice_ids) < MIN_SLICES:
        _add_issue(issues, "advice_data_comparison",
                   f"data_comparison 只覆盖 {len(slice_ids)} 个 slice（{slice_ids}）；至少需要 {MIN_SLICES} 个")

    option_ids = [str(item.get("option_id")) for item in candidates]
    for slice_id in slice_ids:
        present = {str(row.get("option_id")) for row in rows
                   if isinstance(row, dict) and row.get("slice_id") == slice_id}
        missing = [option_id for option_id in option_ids if option_id not in present]
        if missing:
            _add_issue(issues, "advice_data_comparison",
                       f"slice {slice_id} 缺少候选 {missing} 的实跑行；每个 slice 必须覆盖全部候选")
    return rows


def _check_trials_refs(rows: list, trials: dict, issues: list) -> list:
    """advice_trials_ref_valid：每行 trials_ref 能解析到 (option_id, slice_id) 的 run；返回可比对的 (row, run)。"""
    latest = _latest_runs(trials)
    resolved = []
    for row in rows:
        if not isinstance(row, dict):
            _add_issue(issues, "advice_trials_ref_valid", "data_comparison.rows 里有非对象元素")
            continue
        option_id = str(row.get("option_id") or "")
        slice_id = str(row.get("slice_id") or "")
        ref = row.get("trials_ref")
        if not (isinstance(ref, str) and ref.strip()):
            _add_issue(issues, "advice_trials_ref_valid",
                       f"{option_id}/{slice_id} 缺少 trials_ref：每格必须能回溯到一次工具执行")
            continue
        if "/" not in ref:
            _add_issue(issues, "advice_trials_ref_valid",
                       f"{option_id}/{slice_id} 的 trials_ref={ref!r} 不是 <option_id>/<slice_id> 形式")
            continue
        ref_option, ref_slice = ref.split("/", 1)
        if ref_option != option_id or ref_slice != slice_id:
            _add_issue(issues, "advice_trials_ref_valid",
                       f"{option_id}/{slice_id} 的 trials_ref={ref!r} 与本行的 option_id/slice_id 不一致")
            continue
        run = latest.get((option_id, slice_id))
        if run is None:
            _add_issue(issues, "advice_trials_ref_valid",
                       f"trials_ref={ref!r} 在 {TRIALS_FILENAME} 里找不到对应的 run")
            continue
        resolved.append((row, run))
    return resolved


def _compare_layer(advice_layer, trials_layer, *, option_id: str, slice_id: str, layer: str, issues: list):
    """advice_number_mismatch：逐键核对 advice 与 trials（容差 1e-9），缺键/多键也算不一致。"""
    if not isinstance(advice_layer, dict):
        _add_issue(issues, "advice_number_mismatch",
                   f"{option_id}/{slice_id} 的 {layer} 不是对象，无法与 trials 对齐")
        return
    if not isinstance(trials_layer, dict):
        _add_issue(issues, "advice_number_mismatch",
                   f"trials 里 {option_id}/{slice_id} 没有 {layer} 记录，advice 却在报数")
        return
    for key in sorted(set(advice_layer) | set(trials_layer)):
        if key not in advice_layer:
            _add_issue(issues, "advice_number_mismatch",
                       f"{option_id}/{slice_id} 的 {layer}.{key} 缺失：数值必须由 assemble 从 trials 回填")
        elif key not in trials_layer:
            _add_issue(issues, "advice_number_mismatch",
                       f"{option_id}/{slice_id} 的 {layer}.{key} 在 trials 中不存在：疑似手填数值")
        elif not _same_value(advice_layer[key], trials_layer[key]):
            _add_issue(issues, "advice_number_mismatch",
                       f"{option_id}/{slice_id} 的 {layer}.{key} 与 trials 不一致："
                       f"advice={advice_layer[key]!r} trials={trials_layer[key]!r}")


def _check_number_consistency(resolved: list, issues: list):
    """advice_number_mismatch：comparable 与 own 两层逐格核对。"""
    for row, run in resolved:
        option_id = str(row.get("option_id"))
        slice_id = str(row.get("slice_id"))
        metrics = run.get("metrics")
        if not isinstance(metrics, dict):
            _add_issue(issues, "advice_number_mismatch",
                       f"{option_id}/{slice_id} 对应的 run 没有 metrics（试算失败），advice 不得给出数字")
            continue
        _compare_layer(row.get("comparable"), metrics.get("comparable"),
                       option_id=option_id, slice_id=slice_id, layer="comparable", issues=issues)
        _compare_layer(row.get("own"), metrics.get("own") or {},
                       option_id=option_id, slice_id=slice_id, layer="own", issues=issues)


def _check_comparable_metrics(rows: list, issues: list):
    """advice_comparable_metrics：同一 slice 下全部候选的 comparable 键集合必须一致。"""
    grouped = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        comparable = row.get("comparable")
        if not isinstance(comparable, dict):
            continue
        grouped.setdefault(str(row.get("slice_id")), []).append(
            (str(row.get("option_id")), tuple(sorted(comparable.keys()))))

    for slice_id, pairs in grouped.items():
        key_sets = {keys for _, keys in pairs}
        if len(key_sets) > 1:
            detail = ", ".join(f"{option_id}={list(keys)}" for option_id, keys in pairs)
            _add_issue(issues, "advice_comparable_metrics",
                       f"slice {slice_id} 下候选的可比层键集合不一致（可比层是唯一允许横向比较的层）：{detail}")


def _check_judge_panel(advice: dict, issues: list):
    """advice_is_not_judge_panel：is_judge_panel 必须为 false 且 disclaimer 非空。"""
    if advice.get("is_judge_panel") is not False:
        _add_issue(issues, "advice_is_not_judge_panel",
                   f"is_judge_panel={advice.get('is_judge_panel')!r}：建议文件不是评委结论，必须是 false")
    disclaimer = advice.get("disclaimer")
    if not (isinstance(disclaimer, str) and disclaimer.strip()):
        _add_issue(issues, "advice_is_not_judge_panel", "disclaimer 为空：必须声明这是选型建议而非评委审查")


def _check_judge_wording(advice: dict, issues: list):
    """advice_no_judge_wording：全文不得出现评委结论措辞。"""
    text = json.dumps(advice, ensure_ascii=False)
    hits = [word for word in JUDGE_WORDINGS if word in text]
    if hits:
        _add_issue(issues, "advice_no_judge_wording",
                   f"文件里出现了评委结论措辞 {hits}：Phase 4 的评委组不在本文件里，建议不得冒充评审")


def _check_trials_evidence(trials: dict, issues: list):
    """trials_not_tool_executed：run 必须带 executed_by=tool / exit_code / stdout_sha256 / captured_at。"""
    for entry in trials.get("perspectives") or []:
        if not isinstance(entry, dict):
            continue
        perspective = entry.get("perspective")
        option_id = entry.get("option_id")
        for run in entry.get("runs") or []:
            if not isinstance(run, dict):
                continue
            missing = []
            if run.get("executed_by") != "tool":
                missing.append(f"executed_by={run.get('executed_by')!r}")
            if run.get("exit_code") is None:
                missing.append("exit_code")
            if not run.get("stdout_sha256"):
                missing.append("stdout_sha256")
            if not run.get("captured_at"):
                missing.append("captured_at")
            if missing:
                _add_issue(issues, "trials_not_tool_executed",
                           f"{perspective}/{option_id}/{run.get('slice_id')} run_seq={run.get('run_seq')} "
                           f"缺少工具执行留痕：{', '.join(missing)}；试算只能由 runner 产生，不接受手填")


def _check_trials_coverage(trials: dict, issues: list):
    """trials_slice_coverage：每个视角必须在所有声明的 slice 上都有 run。"""
    slices = [str(item.get("slice_id")) for item in trials.get("slices") or []
              if isinstance(item, dict) and item.get("slice_id")]
    if not slices:
        return
    latest = _latest_runs(trials)
    covered = {}
    for entry in trials.get("perspectives") or []:
        if isinstance(entry, dict):
            covered.setdefault(str(entry.get("option_id") or ""), set())
    for (option_id, slice_id) in latest:
        covered.setdefault(option_id, set()).add(slice_id)
    for option_id, present in covered.items():
        missing = [slice_id for slice_id in slices if slice_id not in present]
        if missing:
            _add_issue(issues, "trials_slice_coverage",
                       f"候选 {option_id} 缺少 slice {missing} 的试算 run：覆盖矩阵不完整")


def _apply_mode_severity(issues: list, mode: str) -> list:
    """按质量档映射 severity：standard 降三条为 warning，其余（含 excellence）全 error。"""
    downgraded = STANDARD_WARNING_CODES if mode == "standard" else frozenset()
    for issue in issues:
        if issue.get("code") in downgraded:
            issue["severity"] = "warning"
    return issues


def validate(workspace, mode: str = "standard", *, advice_path=None, trials_path=None) -> dict:
    """逐条校验契约 §6 的硬规则 + 与 perspective_trials.json 的数值一致性。

    severity 由 mode 映射：standard 下 advice_candidates_count / advice_data_comparison /
    advice_pros_cons 降为 warning（留痕不阻断）；其余硬规则与 excellence 档一律 error，
    因为它们意味着证据链断裂（手填数字、无 run 可回溯、冒充评委结论）。
    """
    workspace_path = _require_workspace(workspace)
    advice_file = _resolve(workspace_path, advice_path or ADVICE_FILENAME)
    if not advice_file.is_file():
        raise FileNotFoundError(f"{advice_file} 不存在：请先运行 assemble")
    advice = _load_json(advice_file)

    trials_file = _resolve(workspace_path, trials_path or TRIALS_FILENAME)
    trials = _load_json(trials_file) if trials_file.is_file() else None

    issues = []
    candidates = [item for item in advice.get("candidates") or [] if isinstance(item, dict)]
    _check_candidates_count(candidates, issues)
    _check_one_recommended(candidates, advice, issues)
    _check_scores(candidates, _rubric_ids(advice.get("scoring_rubric")), issues)
    _check_pros_cons(candidates, issues)
    _check_why_not(candidates, issues)
    rows = _check_data_comparison(advice, candidates, issues)

    if trials is None:
        _add_issue(issues, "advice_trials_ref_valid",
                   f"{trials_file} 不存在：data_comparison 的每一格都无法回溯到工具执行")
    else:
        resolved = _check_trials_refs(rows, trials, issues)
        _check_number_consistency(resolved, issues)
    _check_comparable_metrics(rows, issues)
    _check_judge_panel(advice, issues)
    _check_judge_wording(advice, issues)
    if trials is not None:
        # trials 自身的执行留痕与覆盖矩阵：没有这两项，data_comparison 就是空中楼阁
        _check_trials_evidence(trials, issues)
        _check_trials_coverage(trials, issues)

    _apply_mode_severity(issues, mode)
    passed = not any(issue["severity"] == "error" for issue in issues)
    return {
        "passed": passed,
        "mode": mode,
        "advice_file": str(advice_file),
        "trials_file": str(trials_file) if trials is not None else None,
        "candidates": len(candidates),
        "rows": len(rows),
        "issues": issues,
    }


def main():
    # 锁定 CLI 输出的 UTF-8：Windows 管道默认按本地编码（常为 GBK）输出，中文会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="选型建议骨架生成与硬规则校验（model_advice.json）", epilog=HELP_EPILOG)
    sub = parser.add_subparsers(dest="action", help="可用操作")

    p_assemble = sub.add_parser("assemble", epilog=HELP_EPILOG,
                                help="从 trials + revised 产物生成 model_advice.json 骨架")
    p_assemble.add_argument("--workspace", required=True, help="工作区目录（默认在当前目录找 trials）")
    p_assemble.add_argument("--input", default="", help=f"Agent 产物目录（默认 {AGENT_OUTPUT_DIRNAME}/）")
    p_assemble.add_argument("--trials", default="", help=f"试算文件（默认 {TRIALS_FILENAME}）")
    p_assemble.add_argument("--question-id", default="", help="小问 id；缺省取 trials 里的 question_id")

    p_validate = sub.add_parser("validate", epilog=HELP_EPILOG,
                                help="逐条校验契约 §6 硬规则 + trials 数值一致性")
    p_validate.add_argument("--workspace", required=True, help="工作区目录")
    p_validate.add_argument("--mode", default="standard", choices=MODE_CHOICES,
                            help="质量档：standard 下 candidates_count/data_comparison/pros_cons 降为 warning，"
                                 "其余与 excellence 一律 error")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "assemble":
            output(assemble(
                args.workspace,
                input_dir=args.input or None,
                trials=args.trials or None,
                question_id=args.question_id or None,
            ))
            return
        result = validate(args.workspace, mode=args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:  # CLI 边界：任何异常统一转成 {"error": ...} 并 exit 1
        error(str(exc))


if __name__ == "__main__":
    main()
