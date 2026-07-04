#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模流程状态管理工具"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


STATE_FILE = "modeling_state.json"
LOCK_TIMEOUT_SECONDS = 10
LOCK_STALE_SECONDS = 60
ARTIFACT_FILES = {
    "problem_brief": "problem_brief.md",
    "modeling_memory": "modeling_memory.md",
    "final_solution": "final_solution.json",
    "model_decision": "model_decision.md",
    "writer_prompt": "writer_prompt.md",
    "results_dir": "results",
}
PHASE_ORDER = ["phase0", "phase1", "phase2", "phase3", "phase4", "phase5"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def workspace_root(workspace: str) -> Path:
    return Path(workspace).resolve()


def state_path(workspace: str) -> Path:
    return workspace_root(workspace) / STATE_FILE


def lock_path(workspace: str) -> Path:
    return Path(str(state_path(workspace)) + ".lock")


def resolve_workspace_path(workspace: str, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return workspace_root(workspace) / candidate


class StateLock:
    """跨进程文件锁，避免并行工具同时覆盖 modeling_state.json。"""

    def __init__(self, workspace: str, timeout: int = LOCK_TIMEOUT_SECONDS):
        self.workspace = workspace
        self.timeout = timeout
        self.path = lock_path(workspace)
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        payload = f"pid={os.getpid()} time={now_iso()}\n".encode("utf-8")
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.fd, payload)
                return self
            except (FileExistsError, PermissionError):
                self._remove_stale_lock()
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"等待状态文件锁超时: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except (FileNotFoundError, PermissionError):
            pass

    def _remove_stale_lock(self):
        try:
            age = time.time() - self.path.stat().st_mtime
            if age > LOCK_STALE_SECONDS:
                self.path.unlink()
        except (FileNotFoundError, PermissionError):
            pass


def _atomic_write_json(path: Path, state: dict):
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def artifact_info(path: Path) -> dict:
    exists = path.exists()
    info = {
        "path": str(path),
        "exists": exists,
        "kind": "directory" if exists and path.is_dir() else "file",
    }
    if exists and path.is_file():
        stat = path.stat()
        info.update({"size": stat.st_size, "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
    return info


def artifact_info_for_workspace(workspace: str, path: str) -> dict:
    actual = resolve_workspace_path(workspace, path)
    info = artifact_info(actual)
    info["path"] = str(Path(path)) if not Path(path).is_absolute() else str(actual)
    return info


def default_state(workspace: str, language: str) -> dict:
    return {
        "schema_version": 1,
        "workspace": str(workspace_root(workspace)),
        "language": language,
        "current_phase": "phase0",
        "phases": {},
        "artifacts": {},
        "tool_runs": [],
        "agent_runs": [],
        "issues": [],
        "updated_at": now_iso(),
    }


def save_state(workspace: str, state: dict) -> dict:
    state["updated_at"] = now_iso()
    path = state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, state)
    return state


def load_state(workspace: str) -> dict:
    path = state_path(workspace)
    if not path.exists():
        raise FileNotFoundError(f"状态文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _clone_state(state: dict) -> dict:
    return json.loads(json.dumps(state, ensure_ascii=False))


def _max_phase(left: str, right: str) -> str:
    left_rank = PHASE_ORDER.index(left) if left in PHASE_ORDER else -1
    right_rank = PHASE_ORDER.index(right) if right in PHASE_ORDER else -1
    return right if right_rank >= left_rank else left


def inspect_workspace(workspace: str, language: str = "python", base_state: dict | None = None) -> dict:
    state = _clone_state(base_state) if base_state else default_state(workspace, language)
    state["workspace"] = str(workspace_root(workspace))
    state["language"] = language
    state.setdefault("phases", {})
    state.setdefault("artifacts", {})
    state.setdefault("tool_runs", [])
    state.setdefault("agent_runs", [])
    state.setdefault("issues", [])
    artifacts = dict(ARTIFACT_FILES)
    artifacts["solution"] = "solution.m" if language == "matlab" else "solution.py"
    for name, rel in artifacts.items():
        state["artifacts"][name] = artifact_info_for_workspace(workspace, rel)

    inferred_phase = "phase0"
    if state["artifacts"].get("writer_prompt", {}).get("exists"):
        inferred_phase = "phase2"
    if state["artifacts"].get("solution", {}).get("exists"):
        inferred_phase = "phase3"
    if state["artifacts"].get("results_dir", {}).get("exists"):
        inferred_phase = "phase4"
    state["current_phase"] = _max_phase(state.get("current_phase", "phase0"), inferred_phase)
    state["updated_at"] = now_iso()
    return state


def init_state(workspace: str, language: str) -> dict:
    root = workspace_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(exist_ok=True)
    with StateLock(workspace):
        state = inspect_workspace(workspace, language, default_state(workspace, language))
        return save_state(workspace, state)


def mutate_state(workspace: str, mutator, language: str = "python") -> dict:
    with StateLock(workspace):
        try:
            state = load_state(workspace)
        except FileNotFoundError:
            state = default_state(workspace, language)
        mutator(state)
        return save_state(workspace, state)


def resume_state(workspace: str, language: str = "python") -> dict:
    with StateLock(workspace):
        try:
            existing = load_state(workspace)
        except FileNotFoundError:
            existing = default_state(workspace, language)
        state = inspect_workspace(workspace, language, existing)
        return save_state(workspace, state)


def update_phase(workspace: str, phase: str, status: str) -> dict:
    def mutator(state):
        state["current_phase"] = phase
        state["phases"][phase] = {"status": status, "updated_at": now_iso()}

    return mutate_state(workspace, mutator)


def record_artifact(workspace: str, name: str, path: str) -> dict:
    def mutator(state):
        state["artifacts"][name] = artifact_info_for_workspace(workspace, path)

    return mutate_state(workspace, mutator)


def record_tool_run(workspace: str, name: str, status: str, score=None, summary: str = "") -> dict:
    def mutator(state):
        state["tool_runs"].append({
            "name": name,
            "status": status,
            "score": score,
            "summary": summary,
            "updated_at": now_iso(),
        })

    return mutate_state(workspace, mutator)


def record_agent_run(workspace: str, phase: str, agent: str, role: str, status: str, summary: str, output_path: str = "") -> dict:
    def mutator(state):
        state["agent_runs"].append({
            "phase": phase,
            "agent": agent,
            "role": role,
            "status": status,
            "summary": summary,
            "output_path": output_path,
            "updated_at": now_iso(),
        })

    return mutate_state(workspace, mutator)


def main():
    parser = argparse.ArgumentParser(description="数学建模流程状态管理工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_init = subparsers.add_parser("init", help="初始化状态")
    p_init.add_argument("--workspace", required=True)
    p_init.add_argument("--language", required=True, choices=["python", "matlab"])

    p_inspect = subparsers.add_parser("inspect", help="检查工作区")
    p_inspect.add_argument("--workspace", required=True)
    p_inspect.add_argument("--language", default="python", choices=["python", "matlab"])

    p_phase = subparsers.add_parser("phase", help="更新阶段状态")
    p_phase.add_argument("--workspace", required=True)
    p_phase.add_argument("--phase", required=True)
    p_phase.add_argument("--status", required=True)

    p_artifact = subparsers.add_parser("artifact", help="记录产物")
    p_artifact.add_argument("--workspace", required=True)
    p_artifact.add_argument("--name", required=True)
    p_artifact.add_argument("--path", required=True)

    p_tool = subparsers.add_parser("tool-run", help="记录工具运行")
    p_tool.add_argument("--workspace", required=True)
    p_tool.add_argument("--name", required=True)
    p_tool.add_argument("--status", required=True)
    p_tool.add_argument("--score", type=float, default=None)
    p_tool.add_argument("--summary", default="")

    p_agent = subparsers.add_parser("agent-run", help="记录 Agent 运行")
    p_agent.add_argument("--workspace", required=True)
    p_agent.add_argument("--phase", required=True)
    p_agent.add_argument("--agent", required=True)
    p_agent.add_argument("--role", required=True)
    p_agent.add_argument("--status", required=True)
    p_agent.add_argument("--summary", default="")
    p_agent.add_argument("--output-path", default="")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "init":
            output(init_state(args.workspace, args.language))
        elif args.action == "inspect":
            output(inspect_workspace(args.workspace, args.language))
        elif args.action == "phase":
            output(update_phase(args.workspace, args.phase, args.status))
        elif args.action == "artifact":
            output(record_artifact(args.workspace, args.name, args.path))
        elif args.action == "tool-run":
            output(record_tool_run(args.workspace, args.name, args.status, args.score, args.summary))
        elif args.action == "agent-run":
            output(record_agent_run(
                args.workspace,
                args.phase,
                args.agent,
                args.role,
                args.status,
                args.summary,
                args.output_path,
            ))
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
