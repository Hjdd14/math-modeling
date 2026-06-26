#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据契约检查工具"""

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover - doctor 会提示缺依赖
    pd = None


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}


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
        "schema_path": str(root / "data_schema.json"),
        "passed": not strict,
        "warning": not strict,
        "datasets_checked": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_data_schema",
                "severity": "error" if strict else "warning",
                "message": "缺少 data_schema.json；standard 模式仅警告，严格/卓越模式失败。",
            }
        ],
    }


def _read_table(path: Path):
    if pd is None:
        raise RuntimeError("pandas 未安装，无法读取数据附件")
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"不支持的数据文件类型: {path.suffix}")


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _check_type(series, expected_type: str) -> bool:
    expected = (expected_type or "").lower()
    non_null = series.dropna()
    if non_null.empty:
        return True
    if expected in {"number", "float", "numeric"}:
        return pd.to_numeric(non_null, errors="coerce").notna().all()
    if expected in {"integer", "int"}:
        numeric = pd.to_numeric(non_null, errors="coerce")
        return numeric.notna().all() and ((numeric % 1) == 0).all()
    if expected in {"string", "str", "text"}:
        return True
    if expected in {"date", "datetime", "time"}:
        return pd.to_datetime(non_null, errors="coerce").notna().all()
    if expected in {"boolean", "bool"}:
        values = {str(value).lower() for value in non_null.unique()}
        return values <= {"true", "false", "0", "1", "yes", "no", "是", "否"}
    return True


def check_schema(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    schema_path = root / "data_schema.json"
    if not schema_path.exists():
        return _missing_result(root, mode)

    checks = []
    issues = []
    datasets_checked = 0

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": mode,
            "schema_path": str(schema_path),
            "passed": False,
            "warning": False,
            "datasets_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    datasets = schema.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        _add_issue(issues, "missing_datasets", "data_schema.json 必须包含非空 datasets 列表。")
        return {
            "workspace": str(root),
            "mode": mode,
            "schema_path": str(schema_path),
            "passed": False,
            "warning": False,
            "datasets_checked": 0,
            "checks": checks,
            "issues": issues,
        }

    for dataset in datasets:
        rel_path = dataset.get("path") or dataset.get("file")
        fields = dataset.get("fields", [])
        if not rel_path:
            _add_issue(issues, "missing_dataset_path", "dataset 缺少 path。")
            continue
        if not isinstance(fields, list) or not fields:
            _add_issue(issues, "missing_fields", f"{rel_path} 缺少 fields 列表。")
            continue

        data_path = root / rel_path
        if not data_path.exists():
            _add_issue(issues, "missing_dataset_file", f"数据文件不存在: {rel_path}", path=rel_path)
            continue

        try:
            frame = _read_table(data_path)
        except Exception as exc:
            _add_issue(issues, "dataset_read_failed", f"读取 {rel_path} 失败: {exc}", path=rel_path)
            continue

        datasets_checked += 1
        columns = set(str(col) for col in frame.columns)
        expected_columns = [field.get("name") for field in fields if field.get("name")]
        missing_columns = [name for name in expected_columns if name not in columns]
        checks.append(
            {
                "name": "columns_present",
                "dataset": rel_path,
                "passed": not missing_columns,
                "missing": missing_columns,
            }
        )
        for name in missing_columns:
            _add_issue(issues, "missing_column", f"{rel_path} 缺少字段 {name}。", path=rel_path, column=name)

        primary_key = dataset.get("primary_key") or dataset.get("primary_keys") or []
        if isinstance(primary_key, str):
            primary_key = [primary_key]
        if primary_key and all(key in columns for key in primary_key):
            duplicated = int(frame.duplicated(subset=primary_key).sum())
            checks.append(
                {
                    "name": "primary_key_unique",
                    "dataset": rel_path,
                    "passed": duplicated == 0,
                    "duplicates": duplicated,
                }
            )
            if duplicated:
                _add_issue(issues, "duplicate_primary_key", f"{rel_path} 主键重复 {duplicated} 行。", path=rel_path)

        for field in fields:
            name = field.get("name")
            if not name or name not in columns:
                continue
            series = frame[name]
            if field.get("required") and series.isna().any():
                _add_issue(issues, "missing_required_value", f"{rel_path}.{name} 存在缺失值。", path=rel_path, column=name)

            max_missing_rate = field.get("max_missing_rate")
            if max_missing_rate is not None:
                missing_rate = float(series.isna().mean())
                if missing_rate > float(max_missing_rate):
                    _add_issue(
                        issues,
                        "missing_rate_exceeded",
                        f"{rel_path}.{name} 缺失率 {missing_rate:.3f} 超过阈值 {max_missing_rate}。",
                        path=rel_path,
                        column=name,
                    )

            expected_type = field.get("type")
            if expected_type and not _check_type(series, expected_type):
                _add_issue(
                    issues,
                    "type_mismatch",
                    f"{rel_path}.{name} 类型不符合 {expected_type}。",
                    path=rel_path,
                    column=name,
                )

            if field.get("min") is not None or field.get("max") is not None:
                numeric = pd.to_numeric(series, errors="coerce")
                if field.get("min") is not None and (numeric.dropna() < float(field["min"])).any():
                    _add_issue(issues, "range_violation", f"{rel_path}.{name} 存在低于最小值的记录。", path=rel_path, column=name)
                if field.get("max") is not None and (numeric.dropna() > float(field["max"])).any():
                    _add_issue(issues, "range_violation", f"{rel_path}.{name} 存在高于最大值的记录。", path=rel_path, column=name)

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "workspace": str(root),
        "mode": mode,
        "schema_path": str(schema_path),
        "passed": passed,
        "warning": False,
        "datasets_checked": datasets_checked,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 data_schema.json 与附件数据是否一致")
    parser.add_argument("--workspace", required=True, help="建模工作区")
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_schema(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
