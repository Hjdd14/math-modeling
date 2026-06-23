#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据读取、统计摘要、质量检查工具"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def read_data_structure(file_path: str) -> dict:
    """读取数据文件结构"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    result = {
        "file_name": os.path.basename(file_path),
        "file_type": ext.lstrip("."),
        "sheets": []
    }

    if ext in (".xlsx", ".xls"):
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            sheet_info = {
                "sheet_name": sheet_name,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "first_20_rows": json.loads(
                    df.head(20).to_json(orient="records", force_ascii=False)
                )
            }
            result["sheets"].append(sheet_info)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
        sheet_info = {
            "sheet_name": "Sheet1",
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "first_20_rows": json.loads(
                df.head(20).to_json(orient="records", force_ascii=False)
            )
        }
        result["sheets"].append(sheet_info)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    return result


def generate_stats(file_path: str, sheet_name: str = None) -> dict:
    """生成统计摘要"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    columns = []
    for col in df.columns:
        col_data = df[col]
        col_info = {
            "name": col,
            "dtype": str(col_data.dtype),
            "count": int(col_data.count()),
            "missing": int(col_data.isna().sum()),
            "missing_pct": round(float(col_data.isna().mean() * 100), 2),
        }

        if pd.api.types.is_numeric_dtype(col_data):
            numeric_data = col_data.dropna()
            if len(numeric_data) > 0:
                q25 = float(numeric_data.quantile(0.25))
                q75 = float(numeric_data.quantile(0.75))
                iqr = q75 - q25
                lower_bound = q25 - 1.5 * iqr
                upper_bound = q75 + 1.5 * iqr
                outliers = numeric_data[
                    (numeric_data < lower_bound) | (numeric_data > upper_bound)
                ]
                col_info.update({
                    "mean": round(float(numeric_data.mean()), 4),
                    "std": round(float(numeric_data.std()), 4),
                    "min": round(float(numeric_data.min()), 4),
                    "q25": round(q25, 4),
                    "median": round(float(numeric_data.median()), 4),
                    "q75": round(q75, 4),
                    "max": round(float(numeric_data.max()), 4),
                    "unique_count": int(numeric_data.nunique()),
                    "outliers": [
                        {"row": int(idx) + 2, "value": round(float(val), 4)}
                        for idx, val in outliers.items()
                    ]
                })
            else:
                col_info.update({
                    "mean": None, "std": None, "min": None,
                    "q25": None, "median": None, "q75": None, "max": None,
                    "unique_count": 0, "outliers": []
                })
        else:
            col_info.update({
                "mean": None, "std": None, "min": None,
                "q25": None, "median": None, "q75": None, "max": None,
                "unique_count": int(col_data.nunique()),
                "outliers": []
            })

        columns.append(col_info)

    return {"columns": columns}


def check_quality(file_path: str, sheet_name: str = None) -> dict:
    """数据质量检查"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(file_path)
    elif ext == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    missing_values = []
    outliers = []
    type_issues = []

    for col in df.columns:
        col_data = df[col]
        missing_count = int(col_data.isna().sum())
        if missing_count > 0:
            missing_rows = [int(i) + 2 for i in col_data[col_data.isna()].index]
            missing_values.append({
                "sheet": sheet_name or "Sheet1",
                "column": col,
                "count": missing_count,
                "rows": missing_rows[:20]
            })

        if pd.api.types.is_numeric_dtype(col_data):
            numeric_data = col_data.dropna()
            if len(numeric_data) > 2:
                mean_val = numeric_data.mean()
                std_val = numeric_data.std()
                if std_val > 0:
                    z_scores = ((numeric_data - mean_val) / std_val).abs()
                    outlier_mask = z_scores > 3
                    for idx in outlier_mask[outlier_mask].index:
                        outliers.append({
                            "sheet": sheet_name or "Sheet1",
                            "column": col,
                            "row": int(idx) + 2,
                            "value": round(float(numeric_data[idx]), 4),
                            "z_score": round(float(z_scores[idx]), 4)
                        })

        non_null = col_data.dropna()
        if len(non_null) > 0:
            types = non_null.apply(type).unique()
            if len(types) > 1:
                type_issues.append({
                    "sheet": sheet_name or "Sheet1",
                    "column": col,
                    "types_found": [t.__name__ for t in types]
                })

    duplicate_rows = int(df.duplicated().sum())

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isna().sum().sum())
    outlier_count = len(outliers)
    type_issue_count = len(type_issues)

    if total_cells == 0:
        quality_score = 100.0
    else:
        missing_penalty = (missing_cells / total_cells) * 30
        outlier_penalty = min((outlier_count / max(total_cells, 1)) * 100, 30)
        type_penalty = min(type_issue_count * 5, 20)
        dup_penalty = min((duplicate_rows / max(df.shape[0], 1)) * 20, 20)
        quality_score = max(0, round(100 - missing_penalty - outlier_penalty - type_penalty - dup_penalty, 2))

    return {
        "missing_values": missing_values,
        "outliers": outliers[:50],
        "type_issues": type_issues,
        "duplicate_rows": duplicate_rows,
        "unit_issues": [],
        "quality_score": quality_score
    }


def main():
    parser = argparse.ArgumentParser(description="数据读取、统计摘要、质量检查工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_read = subparsers.add_parser("read", help="读取数据结构")
    p_read.add_argument("--file", required=True, help="文件路径")

    p_stats = subparsers.add_parser("stats", help="生成统计摘要")
    p_stats.add_argument("--file", required=True, help="文件路径")
    p_stats.add_argument("--sheet", default=None, help="工作表名称")

    p_quality = subparsers.add_parser("quality", help="数据质量检查")
    p_quality.add_argument("--file", required=True, help="文件路径")
    p_quality.add_argument("--sheet", default=None, help="工作表名称")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "read":
            result = read_data_structure(args.file)
            output(result)
        elif args.action == "stats":
            result = generate_stats(args.file, args.sheet)
            output(result)
        elif args.action == "quality":
            result = check_quality(args.file, args.sheet)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
