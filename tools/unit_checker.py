#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""符号与单位一致性检查工具"""

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
REQUIRED_SYMBOL_FIELDS = ["symbol", "meaning", "unit", "code_name"]


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _missing_result(root: Path, mode: str) -> dict:
    strict = mode in STRICT_MODES
    return {
        "workspace": str(root),
        "mode": mode,
        "symbol_table_path": str(root / "symbol_table.json"),
        "passed": not strict,
        "warning": not strict,
        "symbols_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_symbol_table",
                "severity": "error" if strict else "warning",
                "message": "缺少 symbol_table.json；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def check_units(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    symbol_path = root / "symbol_table.json"
    if not symbol_path.exists():
        return _missing_result(root, mode)

    checks = []
    issues = []
    try:
        payload = json.loads(symbol_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": mode,
            "symbol_table_path": str(symbol_path),
            "passed": False,
            "warning": False,
            "symbols_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        _add_issue(issues, "missing_symbols", "symbol_table.json 必须包含非空 symbols 列表。")
        return {
            "workspace": str(root),
            "mode": mode,
            "symbol_table_path": str(symbol_path),
            "passed": False,
            "warning": False,
            "symbols_checked": 0,
            "checks": checks,
            "issues": issues,
        }

    seen = set()
    duplicates = []
    for item in symbols:
        symbol = item.get("symbol") if isinstance(item, dict) else None
        if symbol in seen:
            duplicates.append(symbol)
        seen.add(symbol)
        for field in REQUIRED_SYMBOL_FIELDS:
            if not isinstance(item, dict) or not item.get(field):
                _add_issue(issues, "missing_symbol_field", f"符号 {symbol or '<unknown>'} 缺少 {field}。", symbol=symbol, field=field)

    if duplicates:
        _add_issue(issues, "duplicate_symbol", f"符号重复: {', '.join(map(str, duplicates))}。", duplicates=duplicates)

    checks.append({"name": "required_symbol_fields", "passed": not issues, "required": REQUIRED_SYMBOL_FIELDS})

    model_spec_path = root / "model_spec.json"
    if model_spec_path.exists():
        try:
            spec = json.loads(model_spec_path.read_text(encoding="utf-8"))
            spec_names = {
                item.get("name")
                for item in spec.get("variables", []) + spec.get("parameters", [])
                if isinstance(item, dict) and item.get("name")
            }
            code_names = {item.get("code_name") for item in symbols if isinstance(item, dict) and item.get("code_name")}
            missing = sorted(name for name in spec_names if name not in code_names and name not in seen)
            checks.append({"name": "model_spec_symbol_coverage", "passed": not missing, "missing": missing})
            for name in missing:
                _add_issue(issues, "symbol_not_in_table", f"model_spec 中的 {name} 未进入 symbol_table。", "warning", symbol=name)
        except Exception as exc:
            _add_issue(issues, "model_spec_read_failed", f"读取 model_spec.json 失败: {exc}", "warning")

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": mode,
        "symbol_table_path": str(symbol_path),
        "passed": passed,
        "warning": False,
        "symbols_checked": len(symbols),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 symbol_table.json 的符号与单位契约")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_units(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
