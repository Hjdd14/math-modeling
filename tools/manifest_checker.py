#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可复现实验清单检查工具"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_FIELDS = [
    "dependencies",
    "random_seed",
    "input_hashes",
    "output_hashes",
    "os",
    "solvers",
    "random_libraries",
    "execution",
]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _missing_result(root: Path, mode: str) -> dict:
    strict = mode in STRICT_MODES
    return {
        "workspace": str(root),
        "mode": mode,
        "manifest_path": str(root / "reproducibility_manifest.json"),
        "passed": not strict,
        "warning": not strict,
        "hashes_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_reproducibility_manifest",
                "severity": "error" if strict else "warning",
                "message": "缺少 reproducibility_manifest.json；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def check_manifest(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    manifest_path = root / "reproducibility_manifest.json"
    if not manifest_path.exists():
        return _missing_result(root, mode)

    checks = []
    issues = []
    hashes_checked = 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": mode,
            "manifest_path": str(manifest_path),
            "passed": False,
            "warning": False,
            "hashes_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    has_runtime = bool(manifest.get("python_version") or manifest.get("matlab_version"))
    checks.append({"name": "runtime_version", "passed": has_runtime})
    if not has_runtime:
        _add_issue(issues, "missing_runtime_version", "复现清单缺少 python_version 或 matlab_version。")

    for field in REQUIRED_FIELDS:
        present = field in manifest
        checks.append({"name": f"field_{field}", "passed": present})
        if not present:
            _add_issue(issues, "missing_manifest_field", f"复现清单缺少 {field}。", field=field)

    execution = manifest.get("execution", {})
    if isinstance(execution, dict) and "seconds" in execution:
        try:
            execution_ok = float(execution["seconds"]) >= 0
        except (TypeError, ValueError):
            execution_ok = False
    else:
        execution_ok = False
    checks.append({"name": "execution_time_recorded", "passed": execution_ok})
    if "execution" in manifest and not execution_ok:
        _add_issue(issues, "invalid_execution_time", "execution.seconds 必须记录非负运行耗时。")

    for group in ["input_hashes", "output_hashes"]:
        entries = manifest.get(group, [])
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            _add_issue(issues, "invalid_hash_group", f"{group} 必须是列表。", group=group)
            continue
        for entry in entries:
            rel_path = entry.get("path") if isinstance(entry, dict) else None
            expected = entry.get("sha256") if isinstance(entry, dict) else None
            if not rel_path or not expected:
                _add_issue(issues, "invalid_hash_entry", f"{group} 中存在缺少 path/sha256 的项。", group=group)
                continue
            target = root / rel_path
            if not target.exists():
                _add_issue(issues, "hash_file_missing", f"hash 目标文件不存在: {rel_path}。", group=group, path=rel_path)
                continue
            hashes_checked += 1
            actual = _sha256(target)
            if actual.lower() != str(expected).lower():
                _add_issue(issues, "hash_mismatch", f"{rel_path} sha256 不匹配。", group=group, path=rel_path)

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": mode,
        "manifest_path": str(manifest_path),
        "passed": passed,
        "warning": False,
        "hashes_checked": hashes_checked,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 reproducibility_manifest.json")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_manifest(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
