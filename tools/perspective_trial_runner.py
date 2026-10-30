#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每视角真实试算执行器（B 闸门证据链：perspective_trials.json）。

把"五视角都算过"变成"这是可复跑的执行留痕"：

    python tools/perspective_trial_runner.py open --workspace . --slices slices.json
    python tools/perspective_trial_runner.py run --workspace . --perspective statistician --option-id O1 --slice full
    python tools/perspective_trial_runner.py status --workspace .
    python tools/perspective_trial_runner.py verify --workspace .

契约：D:/Code_Work/_two_gate/CONTRACT.md §7 / §8.2。三条不可让步的性质：

1. **唯一写入口**：perspective_trials.json 只由本工具写，run 真 spawn 子进程、perf_counter 计时、
   捕获 stdout/stderr、解析 stdout 中最后一个 JSON 对象为 metrics，并写 executed_by="tool"。
2. **追加不覆盖**：同一 (perspective, slice) 的旧记录永不重写，新记录带递增 run_seq，下游取最大 run_seq。
3. **原子落盘**：tmp + replace；中途崩溃不会留下半截 JSON 把历史证据一起毁掉。

仅用标准库，不联网，不调用 LLM。
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TRIALS_FILENAME = "perspective_trials.json"
TRIALS_DIRNAME = "perspective_trials"
SCHEMA_VERSION = 2
RUNNER_VERSION = "1.0"
GENERATED_BY = "tools/perspective_trial_runner.py"
SLICE_AXES = ("data_rows", "parameter", "scenario")
DEFAULT_COMPARABLE_METRICS = (
    {"key": "runtime_s", "unit": "s"},
    {"key": "finished", "unit": "bool"},
)
MIN_RUNTIME_S = 0.00001  # 耗时下限（秒）：极快的试算也不写 0.0，避免下游误判"没测到"
TAIL_CHARS = 500
DEFAULT_TIMEOUT = 300
HELP_EPILOG = "契约见 docs/DESIGN_GATE_PLAN.md §21"


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


def _trials_path(workspace) -> Path:
    """perspective_trials.json 的绝对路径（固定在 --workspace 下）。"""
    return Path(workspace).expanduser().resolve() / TRIALS_FILENAME


def _tail(text, limit: int = TAIL_CHARS) -> str:
    """取文本末尾若干字符；None 视为空串。"""
    return str(text)[-limit:] if text else ""


def _hash_text(text: str) -> str:
    """文本的 sha256（UTF-8）。"""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _hash_file(path: Path):
    """文件的 sha256；文件不存在返回 None（不编造哈希）。"""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _quote(part: str) -> str:
    """命令行片段加引号：Windows 路径常含空格。"""
    text = str(part)
    return f'"{text}"' if " " in text else text


def _parse_json_output(stdout: str):
    """从 stdout 里找最后一个可解析的 JSON 对象（脚本前面可能先打印日志）。

    与 tools/mini_trial.py 同一判定策略：整段不是 JSON 时逐个 '{' 试 raw_decode，
    取"结束位置最靠后"的对象；同一位置上外层对象总比内层结束得更晚，因此自然选中外层。
    """
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return next((item for item in reversed(parsed) if isinstance(item, dict)), None)

    decoder = json.JSONDecoder()
    best, best_end, best_start = None, -1, 0
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(text, index)
        except (ValueError, RecursionError):
            continue
        if isinstance(candidate, dict) and (end > best_end or (end == best_end and index < best_start)):
            best, best_end, best_start = candidate, end, index
    return best


def _load_doc(path: Path) -> dict:
    """读取 perspective_trials.json；结构异常直接报错，绝不覆盖。"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path} 不是合法 JSON（{exc}），拒绝覆盖以免丢失试算留痕") from exc
    except OSError as exc:
        raise ValueError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{path} 顶层应为 JSON 对象")
    if not isinstance(doc.get("perspectives"), list):
        raise ValueError(f"{path} 缺少 perspectives 数组，不是本工具产出的文档")
    return doc


def _write_doc(path: Path, doc: dict):
    """先写临时文件再替换（原子写），避免中断时留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _normalize_slices(raw) -> list:
    """校验并规整 slices 列表：slice_id 必填且唯一，其余字段给默认值。"""
    if not isinstance(raw, list) or not raw:
        raise ValueError("slices 必须是非空数组")
    normalized, seen = [], set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"slices[{index}] 不是对象")
        slice_id = str(item.get("slice_id") or "").strip()
        if not slice_id:
            raise ValueError(f"slices[{index}] 缺少 slice_id")
        if slice_id in seen:
            raise ValueError(f"slice_id 重复: {slice_id}")
        seen.add(slice_id)
        selector = item.get("selector")
        normalized.append({
            "slice_id": slice_id,
            "description": str(item.get("description") or ""),
            "data_ref": item.get("data_ref"),
            "selector": selector if isinstance(selector, dict) else {},
        })
    return normalized


def _normalize_metric_definitions(raw) -> dict:
    """校验 metric_definitions；缺失时给 runner 自有的可比层默认定义。"""
    default = {"comparable": [dict(item) for item in DEFAULT_COMPARABLE_METRICS], "own": {}}
    if raw is None:
        return default
    if not isinstance(raw, dict):
        raise ValueError("metric_definitions 必须是对象")
    comparable = raw.get("comparable")
    if comparable is None:
        comparable = default["comparable"]
    if not isinstance(comparable, list):
        raise ValueError("metric_definitions.comparable 必须是数组")
    own = raw.get("own") or {}
    if not isinstance(own, dict):
        raise ValueError("metric_definitions.own 必须是对象")
    return {"comparable": comparable, "own": own}


def _read_slices_spec(spec_path, workspace_path: Path) -> dict:
    """读取 --slices 规格文件：允许是切片数组，也允许是带 slices 字段的对象。"""
    candidate = Path(spec_path).expanduser()
    if not candidate.is_absolute():
        # 先按工作区相对路径找，再按当前目录相对路径找（两种调用习惯都认）
        candidate = workspace_path / candidate if (workspace_path / candidate).is_file() else candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"slices 规格文件不存在: {candidate}")
    try:
        spec = json.loads(candidate.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{candidate} 不是合法 JSON（{exc}）") from exc
    if isinstance(spec, list):
        return {"slices": spec}
    if not isinstance(spec, dict):
        raise ValueError(f"{candidate} 顶层应为对象或数组")
    return spec


def _new_run_id() -> str:
    """run_id：ISO8601 时间戳 + 6 位随机十六进制，便于多轮试算区分。"""
    return f"{_now_iso()}-{os.urandom(3).hex()}"


def open_document(workspace, slices_path, *, question_id=None, axis=None, note=None,
                  force: bool = False) -> dict:
    """初始化 perspective_trials.json（slices / metric_definitions / run_id）。"""
    workspace_path = _require_workspace(workspace)
    path = _trials_path(workspace_path)
    if path.is_file() and not force:
        raise ValueError(f"{path} 已存在：open 会重置试算留痕，确认要重开请加 --force")

    spec = _read_slices_spec(slices_path, workspace_path)
    slices = _normalize_slices(spec.get("slices"))
    axis_value = str(axis or spec.get("slice_axis") or "data_rows").strip()
    if axis_value not in SLICE_AXES:
        raise ValueError(f"slice_axis 只能是 {'/'.join(SLICE_AXES)}，收到: {axis_value}")
    note_value = str(note if note is not None else (spec.get("slice_axis_note") or "")).strip()
    # 契约 §7：无数据集问题用 parameter/scenario 轴时，说明必填，否则下游无法判断切片含义
    if axis_value != "data_rows" and not note_value:
        raise ValueError(f"slice_axis={axis_value} 时必须给 --note（slice_axis_note 必填）")
    doc_question_id = str(question_id or spec.get("question_id") or "").strip() or None

    doc = {
        "schema_version": SCHEMA_VERSION,
        "question_id": doc_question_id,
        "generated_by": GENERATED_BY,
        "run_id": _new_run_id(),
        "slice_axis": axis_value,
        "slice_axis_note": note_value,
        "slices": slices,
        "metric_definitions": _normalize_metric_definitions(spec.get("metric_definitions")),
        "perspectives": [],
    }
    _write_doc(path, doc)

    warnings = []
    if len(slices) < 2:
        warnings.append(f"slices 只有 {len(slices)} 个；契约 §7 要求 ≥2，checker 会判 error")
    return {
        "ok": True,
        "workspace": str(workspace_path),
        "trials_file": str(path),
        "run_id": doc["run_id"],
        "question_id": doc["question_id"],
        "slice_axis": doc["slice_axis"],
        "slices": [item["slice_id"] for item in slices],
        "metric_definitions": doc["metric_definitions"],
        "warnings": warnings,
    }


def _kill_tree(proc):
    """超时后回收整棵进程树：只杀 cmd.exe 会留下孙进程占着管道，communicate 会一直等下去。"""
    if os.name != "nt":
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass
        return
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


def _execute(command: str, workspace_path: Path, timeout: int):
    """真跑一次子命令：返回 (exit_code, stdout, stderr, runtime_s, reason)。"""
    child_env = dict(os.environ)
    # 显式锁定 UTF-8 两端：试算脚本常打印中文，若子进程按 GBK 输出、父进程按 UTF-8 解码会误判失败
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    exit_code, stdout, stderr, reason = -1, "", "", ""
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(
            command, cwd=str(workspace_path), shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", env=child_env, start_new_session=True,
        )
    except OSError as exc:
        proc = None
        exit_code = -2
        stderr = reason = f"命令无法启动: {exc}"
    if proc is not None:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            stdout, stderr = stdout or "", stderr or ""
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = "", ""
            stdout, stderr = stdout or "", stderr or ""
            exit_code = -1
            reason = f"试算超时：超过 {timeout} 秒，已终止"
    elapsed = time.perf_counter() - started
    return exit_code, stdout, stderr, max(elapsed, MIN_RUNTIME_S), reason


def _build_metrics(parsed, exit_code: int, runtime_s: float):
    """把脚本输出转成 metrics 两层结构。

    可比层 runtime_s / finished 由 runner 判定（runtime 用 perf_counter，不采信脚本自报）；
    脚本若自带 comparable 里的附加键（primary_error / stability 等）原样并入，但不得覆盖 runner 两项。
    专属层 own：脚本给 own 对象就用它，否则把顶层其余数值键当作 own。
    """
    if not isinstance(parsed, dict) or exit_code != 0:
        return None
    comparable = {"runtime_s": runtime_s, "finished": True}
    extra = parsed.get("comparable")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if key not in ("runtime_s", "finished") and isinstance(key, str):
                comparable[key] = value
    own = parsed.get("own")
    if not isinstance(own, dict):
        own = {key: value for key, value in parsed.items() if key not in ("comparable", "own")}
    return {"comparable": comparable, "own": own}


def run_trial(workspace, perspective, option_id, slice_id, *, cmd=None,
              timeout: int = DEFAULT_TIMEOUT) -> dict:
    """真跑一个视角在一个切片上的试算，并把结果**追加**写入 perspective_trials.json。"""
    workspace_path = _require_workspace(workspace)
    perspective = str(perspective or "").strip()
    option_id = str(option_id or "").strip()
    slice_id = str(slice_id or "").strip()
    if not perspective:
        raise ValueError("--perspective 不能为空")
    if not option_id:
        raise ValueError("--option-id 不能为空")
    if not slice_id:
        raise ValueError("--slice 不能为空")
    if any(char in perspective for char in ("/", "\\", "..")):
        raise ValueError(f"--perspective 只能是视角名，不能含路径分隔符: {perspective}")
    timeout = int(timeout)
    if timeout <= 0:
        raise ValueError(f"--timeout 必须为正整数秒，收到: {timeout}")

    path = _trials_path(workspace_path)
    if not path.is_file():
        raise FileNotFoundError(f"{path} 不存在：请先运行 open 初始化 slices 与 run_id")
    doc = _load_doc(path)
    known_slices = [str(item.get("slice_id")) for item in doc.get("slices") or [] if isinstance(item, dict)]
    if slice_id not in known_slices:
        raise ValueError(f"slice {slice_id} 不在 slices {known_slices} 里；未知切片会让覆盖矩阵失真")

    script_rel = f"{TRIALS_DIRNAME}/{perspective}.py"
    script_path = workspace_path / script_rel
    script_sha = _hash_file(script_path)
    command = str(cmd or "").strip() or f"{_quote(sys.executable)} {_quote(script_rel)} --slice {slice_id}"

    exit_code, stdout, stderr, runtime_s, reason = _execute(command, workspace_path, timeout)
    parsed = _parse_json_output(stdout)
    metrics = _build_metrics(parsed, exit_code, round(runtime_s, 6))
    parse_error = ""
    if exit_code == 0 and metrics is None and parsed is None:
        parse_error = "stdout 中没有解析到 JSON 对象，metrics 留 null"

    perspectives = doc.setdefault("perspectives", [])
    entry = next((item for item in perspectives
                  if isinstance(item, dict)
                  and item.get("perspective") == perspective
                  and item.get("option_id") == option_id), None)
    if entry is None:
        entry = {"perspective": perspective, "option_id": option_id,
                 "script": script_rel, "script_sha256": script_sha, "runs": []}
        perspectives.append(entry)
    runs = entry.setdefault("runs", [])
    run_seq = max((int(item.get("run_seq") or 0) for item in runs if isinstance(item, dict)), default=0) + 1

    reproduce_cmd = (f"python {GENERATED_BY} run --workspace . --perspective {perspective} "
                     f"--option-id {option_id} --slice {slice_id}")
    record = {
        "slice_id": slice_id,
        "run_seq": run_seq,
        "executed_by": "tool",
        "runner_version": RUNNER_VERSION,
        "exit_code": exit_code,
        "runtime_s": round(runtime_s, 6),
        "stdout_sha256": _hash_text(stdout),
        "script_sha256": script_sha,
        "captured_at": _now_iso(),
        "metrics": metrics,
        "reproduce_cmd": reproduce_cmd,
        "command": command,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    if parse_error:
        record["parse_error"] = parse_error
    if reason:
        record["reason"] = reason
    runs.append(record)
    # 脚本可能改名/改内容：entry 上的抽样哈希同步到本次执行，verify 以每次 run 的 script_sha256 为准
    entry["script"] = script_rel
    entry["script_sha256"] = script_sha
    doc["schema_version"] = doc.get("schema_version") or SCHEMA_VERSION
    _write_doc(path, doc)

    ok = exit_code == 0 and metrics is not None
    return {
        "ok": ok,
        "workspace": str(workspace_path),
        "trials_file": str(path),
        "record": record,
        "run_seq": run_seq,
        "reason": "" if ok else (reason or parse_error or f"退出码 {exit_code} 非 0"),
    }


def _latest_runs(doc: dict) -> dict:
    """(perspective, option_id, slice_id) → 最大 run_seq 的那条记录。"""
    latest = {}
    for entry in doc.get("perspectives") or []:
        if not isinstance(entry, dict):
            continue
        perspective = str(entry.get("perspective") or "")
        option_id = str(entry.get("option_id") or "")
        for run in entry.get("runs") or []:
            if not isinstance(run, dict):
                continue
            key = (perspective, option_id, str(run.get("slice_id") or ""))
            previous = latest.get(key)
            if previous is None or int(run.get("run_seq") or 0) >= int(previous.get("run_seq") or 0):
                latest[key] = run
    return latest


def trial_status(workspace) -> dict:
    """输出覆盖矩阵（perspective × slice）与缺格/失败清单。"""
    workspace_path = _require_workspace(workspace)
    path = _trials_path(workspace_path)
    result = {
        "workspace": str(workspace_path), "trials_file": str(path), "exists": False,
        "question_id": None, "slice_axis": None,
        "slices": [], "perspectives": [], "matrix": {},
        "missing": [], "failed": [], "total_runs": 0, "ready": False,
    }
    if not path.is_file():
        return result
    result["exists"] = True
    try:
        doc = _load_doc(path)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    slices = [str(item.get("slice_id")) for item in doc.get("slices") or [] if isinstance(item, dict)]
    entries = [item for item in doc.get("perspectives") or [] if isinstance(item, dict)]
    perspectives = []
    for entry in entries:
        name = str(entry.get("perspective") or "")
        if name and name not in perspectives:
            perspectives.append(name)
    latest = _latest_runs(doc)
    matrix, missing, failed = {}, [], []
    for entry in entries:
        name = str(entry.get("perspective") or "")
        option_id = str(entry.get("option_id") or "")
        row = matrix.setdefault(name, {})
        for slice_id in slices:
            run = latest.get((name, option_id, slice_id))
            if run is None:
                row[slice_id] = None
                missing.append({"perspective": name, "option_id": option_id, "slice": slice_id})
                continue
            cell = {
                "option_id": option_id, "run_seq": run.get("run_seq"),
                "exit_code": run.get("exit_code"), "runtime_s": run.get("runtime_s"),
                "ok": run.get("exit_code") == 0 and isinstance(run.get("metrics"), dict),
                "has_metrics": isinstance(run.get("metrics"), dict),
            }
            row[slice_id] = cell
            if not cell["ok"]:
                failed.append({"perspective": name, "option_id": option_id, "slice": slice_id,
                               "run_seq": run.get("run_seq"), "exit_code": run.get("exit_code")})

    total_runs = sum(len(entry.get("runs") or []) for entry in entries)
    result.update({
        "question_id": doc.get("question_id"),
        "slice_axis": doc.get("slice_axis"),
        "slices": slices,
        "perspectives": perspectives,
        "matrix": matrix,
        "missing": missing,
        "failed": failed,
        "total_runs": total_runs,
        "ready": bool(entries) and not missing and not failed,
    })
    return result


def verify_trials(workspace) -> dict:
    """重算 script_sha256：脚本改过但没有重跑的 run 标 stale。"""
    workspace_path = _require_workspace(workspace)
    path = _trials_path(workspace_path)
    result = {
        "workspace": str(workspace_path), "trials_file": str(path), "exists": False,
        "runs": [], "stale": [], "evidence_issues": [], "passed": False,
    }
    if not path.is_file():
        return result
    result["exists"] = True
    try:
        doc = _load_doc(path)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    current_hashes = {}
    rows, stale, evidence_issues = [], [], []
    for entry in doc.get("perspectives") or []:
        if not isinstance(entry, dict):
            continue
        script = str(entry.get("script") or "")
        if script not in current_hashes:
            current_hashes[script] = _hash_file(workspace_path / script) if script else None
        current_sha = current_hashes[script]
        for run in entry.get("runs") or []:
            if not isinstance(run, dict):
                continue
            stored_sha = run.get("script_sha256")
            row = {
                "perspective": entry.get("perspective"), "option_id": entry.get("option_id"),
                "slice_id": run.get("slice_id"), "run_seq": run.get("run_seq"),
                "script": script, "stored_script_sha256": stored_sha,
                "current_script_sha256": current_sha, "stale": False, "reason": "",
            }
            if current_sha is None:
                row["stale"] = True
                row["reason"] = "脚本文件缺失，无法复核"
            elif stored_sha != current_sha:
                row["stale"] = True
                row["reason"] = "script_sha256 与当前脚本不一致：脚本改过但未重跑，必须 run 一次"
            if row["stale"]:
                stale.append(row)
            # 手填记录不会带齐执行留痕：executed_by / exit_code / stdout_sha256 / captured_at
            if (run.get("executed_by") != "tool" or run.get("exit_code") is None
                    or not run.get("stdout_sha256") or not run.get("captured_at")):
                evidence_issues.append({
                    "perspective": entry.get("perspective"), "option_id": entry.get("option_id"),
                    "slice_id": run.get("slice_id"), "run_seq": run.get("run_seq"),
                    "reason": "缺少工具执行留痕（executed_by=tool / exit_code / stdout_sha256 / captured_at）",
                })
            rows.append(row)

    result.update({
        "runs": rows, "stale": stale, "evidence_issues": evidence_issues,
        "passed": bool(rows) and not stale and not evidence_issues,
    })
    return result


def main():
    # 锁定 CLI 输出的 UTF-8：Windows 管道默认按本地编码（常为 GBK）输出，中文标签会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="每视角真实试算执行器（perspective_trials.json）", epilog=HELP_EPILOG)
    sub = parser.add_subparsers(dest="action", help="可用操作")

    p_open = sub.add_parser("open", epilog=HELP_EPILOG,
                            help="初始化 perspective_trials.json（slices / metric_definitions）")
    p_open.add_argument("--workspace", required=True, help="工作区目录（perspective_trials.json 落在这里）")
    p_open.add_argument("--slices", required=True, help="切片规格 JSON：切片数组，或含 slices 字段的对象")
    p_open.add_argument("--question-id", default="", help="小问 id，如 Q1")
    p_open.add_argument("--axis", default="", choices=["", *SLICE_AXES],
                        help="切片轴：data_rows / parameter / scenario（默认 data_rows）")
    p_open.add_argument("--note", default=None, help="切片轴说明；parameter/scenario 轴必填")
    p_open.add_argument("--force", action="store_true", help="已存在时强制重开（会清空既有试算留痕）")

    p_run = sub.add_parser("run", epilog=HELP_EPILOG, help="真跑一个视角 × 一个切片，并追加写入记录")
    p_run.add_argument("--workspace", required=True, help="工作区目录")
    p_run.add_argument("--perspective", required=True, help="视角名，如 statistician")
    p_run.add_argument("--option-id", required=True, help="该视角对应的候选 id，如 O1")
    p_run.add_argument("--slice", required=True, dest="slice_id", help="切片 id，须已在 open 时声明")
    p_run.add_argument("--cmd", default="", help="自定义命令；默认 python perspective_trials/<NAME>.py --slice <ID>")
    p_run.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单次试算超时秒数（默认300）")

    p_status = sub.add_parser("status", epilog=HELP_EPILOG,
                              help="输出覆盖矩阵（perspective × slice）与缺格/失败清单")
    p_status.add_argument("--workspace", required=True, help="工作区目录")

    p_verify = sub.add_parser("verify", epilog=HELP_EPILOG,
                              help="重算 script_sha256，脚本改过未重跑的 run 标 stale")
    p_verify.add_argument("--workspace", required=True, help="工作区目录")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "open":
            output(open_document(
                args.workspace, args.slices,
                question_id=args.question_id, axis=args.axis or None,
                note=args.note, force=args.force,
            ))
            return
        if args.action == "run":
            result = run_trial(
                args.workspace, args.perspective, args.option_id, args.slice_id,
                cmd=args.cmd, timeout=args.timeout,
            )
            output(result)
            sys.exit(0 if result["ok"] else 1)
        if args.action == "status":
            result = trial_status(args.workspace)
            output(result)
            sys.exit(0 if result.get("ready") else 1)
        result = verify_trials(args.workspace)
        output(result)
        sys.exit(0 if result.get("passed") else 1)
    except Exception as exc:  # CLI 边界：任何异常统一转成 {"error": ...} 并 exit 1
        error(str(exc))


if __name__ == "__main__":
    main()
