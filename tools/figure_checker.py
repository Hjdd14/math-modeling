#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图表质量验证工具"""

import argparse
import glob
import json
import os
import sys

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def check_figure(file_path: str) -> dict:
    """检查单个图表质量"""
    result = {
        "exists": False,
        "file_size": 0,
        "width": 0,
        "height": 0,
        "dpi": [0, 0],
        "is_blank": True,
        "quality_score": 0.0,
        "issues": []
    }

    if not os.path.exists(file_path):
        result["issues"].append("文件不存在")
        return result

    result["exists"] = True
    result["file_size"] = os.path.getsize(file_path)

    if result["file_size"] == 0:
        result["issues"].append("文件大小为0")
        return result

    if result["file_size"] < 1024:
        result["issues"].append("文件过小（<1KB），可能是空白图")

    if Image is None:
        result["issues"].append("Pillow 未安装，无法进行图像分析")
        result["quality_score"] = 50.0
        return result

    try:
        img = Image.open(file_path)
        result["width"] = img.size[0]
        result["height"] = img.size[1]

        dpi_info = img.info.get("dpi", (72, 72))
        if isinstance(dpi_info, tuple) and len(dpi_info) >= 2:
            result["dpi"] = [int(round(dpi_info[0])), int(round(dpi_info[1]))]
        else:
            result["dpi"] = [72, 72]

        if result["width"] < 100 or result["height"] < 100:
            result["issues"].append(f"尺寸过小: {result['width']}x{result['height']}")

        if np is not None:
            img_array = np.array(img.convert("RGB"))
            pixel_mean = float(img_array.mean())
            pixel_std = float(img_array.std())

            if pixel_std < 5:
                result["is_blank"] = True
                result["issues"].append("空白图表（像素标准差过低）")
            else:
                result["is_blank"] = False

            if pixel_mean > 250:
                result["issues"].append("图表几乎全白")
        else:
            result["is_blank"] = False
            result["issues"].append("numpy 未安装，跳过像素分析")

        if result["dpi"][0] < 300:
            result["issues"].append(f"DPI过低: {result['dpi'][0]}（建议>=300）")

        score = 100.0
        if result["is_blank"]:
            score -= 50
        for issue in result["issues"]:
            if "DPI" in issue or "dpi" in issue.lower():
                score -= 15
            elif "空白" in issue:
                score -= 30
            elif "过小" in issue:
                score -= 20
            elif "全白" in issue:
                score -= 40
        result["quality_score"] = max(0, min(100, round(score, 2)))

    except Exception as e:
        result["issues"].append(f"图像读取失败: {str(e)}")
        result["quality_score"] = 0.0

    return result


def batch_check(dir_path: str, pattern: str = "*.png") -> dict:
    """批量检查图表"""
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f"目录不存在: {dir_path}")

    search_pattern = os.path.join(dir_path, pattern)
    files = glob.glob(search_pattern)

    details = []
    passed = 0
    failed = 0
    issues = []

    if not files:
        issues.append(f"未找到匹配图表: {pattern}")
        failed = 1

    for f in sorted(files):
        result = check_figure(f)
        file_info = {
            "file": os.path.basename(f),
            "quality_score": result["quality_score"],
            "issues": result["issues"]
        }
        details.append(file_info)
        if result["quality_score"] >= 60 and not result["is_blank"]:
            passed += 1
        else:
            failed += 1

    return {
        "total": len(files),
        "passed": passed,
        "failed": failed,
        "details": details,
        "passed_all": len(files) > 0 and failed == 0,
        "issues": issues
    }


def main():
    parser = argparse.ArgumentParser(description="图表质量验证工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_check = subparsers.add_parser("check", help="检查单个图表")
    p_check.add_argument("--file", required=True, help="图表文件路径")

    p_batch = subparsers.add_parser("batch", help="批量检查图表")
    p_batch.add_argument("--dir", required=True, help="目录路径")
    p_batch.add_argument("--pattern", default="*.png", help="文件匹配模式（默认 *.png）")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "check":
            result = check_figure(args.file)
            output(result)
        elif args.action == "batch":
            result = batch_check(args.dir, args.pattern)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
