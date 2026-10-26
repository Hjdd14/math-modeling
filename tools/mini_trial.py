#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选算法真实试算工具（设计板 P1 任务 11）。

把"我验证过"变成"这是可复跑的数值证据"：

    python tools/mini_trial.py run --workspace . --trial "python solution.py --method enum"
    python tools/mini_trial.py run --workspace . --trial "python solution.py --method enum" --label "O1 枚举"
    python tools/mini_trial.py status --workspace .

每次 run 在 workspace 下执行一条命令，用 perf_counter 测真实耗时，解析 stdout 里的 JSON
数值，并**追加**一条记录到 mini_trials.json（schema 见 docs/DESIGN_GATE_PLAN.md §4.4）。
同一命令重复跑不会被去重，靠 at 时间戳区分，所以"改一版再跑一次"天然留痕。仅用标准库。
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TRIALS_FILENAME = "mini_trials.json"
SCHEMA_VERSION = 1
TAIL_CHARS = 500
MIN_SECONDS = 0.00001  # 耗时下限（秒）：极快的试算也不写 0.0，避免下游误判"没测到"


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


def _trials_path(workspace) -> Path:
    """mini_trials.json 的绝对路径。"""
    return Path(workspace).expanduser().resolve() / TRIALS_FILENAME


def _tail(text, limit: int = TAIL_CHARS) -> str:
    """取文本末尾若干字符；None 视为空串。"""
    return str(text)[-limit:] if text else ""


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


def _is_number(value) -> bool:
    """是否真实数值。bool 是 int 子类，必须排除，否则 true 会被当成试算数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return (value == value and value not in (float("inf"), float("-inf"))) if isinstance(value, float) else True


def _has_number(obj, depth: int = 0) -> bool:
    """递归判断输出里是否有数值字段（嵌套结构也认）。"""
    if depth > 4 or not isinstance(obj, (dict, list)):
        return False
    values = list(obj.values()) if isinstance(obj, dict) else obj
    return any(_is_number(v) or _has_number(v, depth + 1) for v in values)


def _parse_json_output(stdout: str):
    """从 stdout 里找最后一个可解析的 JSON 对象（脚本前面可能先打印日志）。"""
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

    # 整段不是 JSON：逐个 '{' 试 raw_decode，取"结束位置最靠后"的对象。同一位置上外层
    # 对象总比内层结束得更晚，因此会自然选中外层，而不是嵌套的子对象。
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


def _load_doc(path: Path, workspace_path: Path) -> dict:
    """读取已有 mini_trials.json；不存在则返回符合 schema 的空文档。"""
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "workspace": str(workspace_path),
                "updated_at": _now_iso(), "trials": []}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError(f"{path} 不是合法 JSON（{exc}），拒绝覆盖以免丢失历史试算") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("trials"), list):
        raise ValueError(f"{path} 结构异常（顶层应为对象且含 trials 数组），拒绝覆盖")
    return doc


def _write_doc(path: Path, doc: dict):
    """先写临时文件再替换，避免中断时留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_trial(workspace: str, command: str, *, label: str = "", timeout: int = 300) -> dict:
    """执行一次试算命令，测量耗时，解析 stdout 的 JSON，追加写入 mini_trials.json。"""
    command = (command or "").strip()
    if not command:
        raise ValueError("试算命令不能为空")
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.is_dir():
        raise FileNotFoundError(f"工作目录不存在: {workspace_path}")
    timeout = int(timeout)
    if timeout <= 0:
        raise ValueError(f"timeout 必须为正整数秒，收到: {timeout}")

    # 显式锁定 UTF-8 两端：题库与求解日志几乎必然含中文。若子进程按系统默认编码
    # （简体 Windows 常为 GBK）输出、父进程又用它解码，会抛 UnicodeDecodeError，
    # 把一次成功的试算误判成失败。errors="replace" 保证残留非法字节也不中断读取。
    child_env = dict(os.environ)
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
            # 超时必须真的回收进程树：只杀 cmd.exe 时孙进程仍在跑，communicate 会继续等。
            _kill_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = "", ""
            stdout, stderr = stdout or "", stderr or ""
            reason = f"试算超时：超过 {timeout} 秒，已终止"
    elapsed = time.perf_counter() - started

    parsed = _parse_json_output(stdout)
    has_numbers = bool(parsed) and _has_number(parsed)
    # 只有真的拿到数值字段才写 output：空对象或纯文本 JSON 不算"有真实数值"。
    output_obj = parsed if has_numbers else {}
    success = exit_code == 0 and has_numbers
    if not success and not reason:
        reason = (f"退出码 {exit_code} 非 0" if exit_code != 0
                  else "stdout 中没有解析到 JSON 对象" if not parsed
                  else "JSON 输出中没有数值字段")

    record = {
        "label": label or command, "command": command, "at": _now_iso(),
        "seconds": round(max(elapsed, MIN_SECONDS), 5), "exit_code": exit_code,
        "success": success, "output": output_obj, "raw_stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr), "reproduce_cmd": command,
    }
    if not success:
        record["reason"] = reason

    path = _trials_path(workspace_path)
    doc = _load_doc(path, workspace_path)
    doc["trials"].append(record)
    doc["schema_version"] = doc.get("schema_version") or SCHEMA_VERSION
    doc["workspace"] = str(workspace_path)
    doc["updated_at"] = _now_iso()
    _write_doc(path, doc)

    return dict(record, trials_file=str(path), total_trials=len(doc["trials"]))


def trial_status(workspace: str) -> dict:
    """汇总 mini_trials.json：总数、每条是否成功、是否都有真实数值。"""
    path = _trials_path(workspace)
    result = {
        "workspace": str(path.parent), "exists": False, "total": 0, "succeeded": 0,
        "failed": 0, "with_numeric_output": 0, "ready": False, "trials": [],
    }
    if not path.is_file():
        return result
    result["exists"] = True
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        result["error"] = f"{path} 不是合法 JSON: {exc}"
        return result
    trials = doc.get("trials") if isinstance(doc, dict) else None
    if not isinstance(trials, list):
        result["error"] = f"{path} 的 trials 不是数组"
        return result

    rows, succeeded, numeric = [], 0, 0
    for trial in trials:
        if not isinstance(trial, dict):
            continue
        out = trial.get("output")
        has_output = isinstance(out, dict) and bool(out)
        has_number = bool(has_output and _has_number(out))
        succeeded += 1 if trial.get("success") else 0
        numeric += 1 if has_number else 0
        rows.append({
            "label": trial.get("label", ""), "command": trial.get("command", ""), "seconds": trial.get("seconds"),
            "success": bool(trial.get("success")), "has_output": has_output,
        })

    result.update({
        "total": len(rows), "succeeded": succeeded, "failed": len(rows) - succeeded, "with_numeric_output": numeric,
        "ready": bool(rows) and succeeded == len(rows) and all(r["has_output"] for r in rows), "trials": rows,
    })
    return result


def main():
    # 锁定 CLI 输出的 UTF-8：Windows 管道默认按本地编码（常为 GBK）输出，中文标签会乱码。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="候选算法真实试算工具（mini_trials.json）")
    sub = parser.add_subparsers(dest="action", help="可用操作")

    p_run = sub.add_parser("run", help="执行试算并追加写入 mini_trials.json")
    p_run.add_argument("--workspace", required=True, help="工作区目录")
    p_run.add_argument("--trial", required=True, action="append", dest="trials",
                       help="试算命令，可重复传入，按顺序依次执行")
    p_run.add_argument("--label", default="", help="本次试算标签，如 'O1 枚举'")
    p_run.add_argument("--timeout", type=int, default=300, help="单条命令超时秒数（默认300）")

    p_status = sub.add_parser("status", help="汇总 mini_trials.json 的试算证据")
    p_status.add_argument("--workspace", required=True, help="工作区目录")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "run":
            results = [run_trial(args.workspace, cmd, label=args.label, timeout=args.timeout)
                       for cmd in args.trials]
            output({
                "workspace": str(Path(args.workspace).expanduser().resolve()),
                "trials_file": results[-1]["trials_file"],
                "total_trials": results[-1]["total_trials"],
                "failed": [r["command"] for r in results if not r["success"]],
                "results": results,
            })
            return
        output(trial_status(args.workspace))
    except Exception as exc:  # CLI 边界：任何异常统一转成 {"error": ...} 并 exit 1
        error(str(exc))


if __name__ == "__main__":
    main()
