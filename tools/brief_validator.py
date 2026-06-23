#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全流程核查自动化工具"""

import argparse
import json
import os
import re
import sys


def output(result: dict):
    """统一 JSON 输出到 stdout"""
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    """统一错误输出到 stderr"""
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def extract_brief(brief_path: str) -> dict:
    """提取 problem_brief.md 中的结构化信息"""
    if not os.path.exists(brief_path):
        raise FileNotFoundError(f"文件不存在: {brief_path}")

    with open(brief_path, "r", encoding="utf-8") as f:
        content = f.read()

    solve_targets = []
    known_conditions = []
    constraints = []
    output_requirements = []

    target_match = re.search(
        r"#+\s*\d*[\.\、]?\s*求解目标\s*\n([\s\S]*?)(?=\n#+|\Z)", content
    )
    if target_match:
        targets_text = target_match.group(1)
        for line in targets_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                solve_targets.append(line.lstrip("-* ").strip())
            elif re.match(r"\d+[\.\、]", line):
                solve_targets.append(re.sub(r"^\d+[\.\、]\s*", "", line).strip())

    cond_match = re.search(
        r"#+\s*\d*[\.\、]?\s*已知条件[与和与及]?参数\s*\n([\s\S]*?)(?=\n#+|\Z)", content
    )
    if cond_match:
        cond_text = cond_match.group(1)
        for line in cond_text.strip().split("\n"):
            line = line.strip()
            if "|" in line and "---" not in line and "条件" not in line and "参数" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    known_conditions.append({
                        "name": parts[0],
                        "value": parts[1],
                        "unit": parts[2] if len(parts) > 2 else "",
                        "note": parts[3] if len(parts) > 3 else ""
                    })
            elif line.startswith("-") or line.startswith("*"):
                known_conditions.append({"name": line.lstrip("-* ").strip(), "value": "", "unit": "", "note": ""})

    cons_match = re.search(
        r"#+\s*\d*[\.\、]?\s*约束条件\s*\n([\s\S]*?)(?=\n#+|\Z)", content
    )
    if cons_match:
        cons_text = cons_match.group(1)
        for line in cons_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                constraints.append(line.lstrip("-* ").strip())
            elif re.match(r"\d+[\.\、]", line):
                constraints.append(re.sub(r"^\d+[\.\、]\s*", "", line).strip())

    out_match = re.search(
        r"#+\s*\d*[\.\、]?\s*输出要求\s*\n([\s\S]*?)(?=\n#+|\Z)", content
    )
    if out_match:
        out_text = out_match.group(1)
        for line in out_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                output_requirements.append(line.lstrip("-* ").strip())

    sections = []
    for match in re.finditer(r"#+\s*(.+)", content):
        sections.append(match.group(1).strip())

    return {
        "solve_targets": solve_targets,
        "known_conditions": known_conditions,
        "constraints": constraints,
        "output_requirements": output_requirements,
        "sections": sections,
        "total_lines": len(content.split("\n")),
        "total_chars": len(content)
    }


def validate_against_brief(brief_path: str, stage: str, target_path: str) -> dict:
    """验证当前阶段输出与 brief 的一致性"""
    if not os.path.exists(brief_path):
        raise FileNotFoundError(f"Brief 文件不存在: {brief_path}")

    effective_stage = "model" if stage == "document" else stage
    brief_info = extract_brief(brief_path)
    checks = []
    score = 100.0

    try:
        path_exists = os.path.exists(target_path)
    except (PermissionError, OSError):
        path_exists = False

    if not path_exists:
        # Check if it's a permission issue on an existing path
        try:
            if os.path.isdir(target_path):
                path_exists = True
        except (PermissionError, OSError):
            pass

    if not path_exists and not os.path.isdir(target_path):
        return {
            "passed": False,
            "checks": [{"item": "目标文件", "status": "fail", "detail": f"文件不存在: {target_path}"}],
            "score": 0.0
        }

    target_content = ""
    if os.path.isfile(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            target_content = f.read()

    if effective_stage == "model":
        for target in brief_info["solve_targets"]:
            found = any(
                keyword in target_content
                for keyword in target.split()[:3]
                if len(keyword) > 1
            )
            checks.append({
                "item": f"求解目标: {target[:30]}",
                "status": "pass" if found else "warning",
                "detail": "模型中找到相关内容" if found else "模型中未明确找到相关内容"
            })
            if not found:
                score -= 5

        for cond in brief_info["known_conditions"]:
            if cond["name"]:
                found = cond["name"] in target_content
                checks.append({
                    "item": f"已知条件: {cond['name'][:20]}",
                    "status": "pass" if found else "warning",
                    "detail": "文档中引用了该条件" if found else "文档中未找到该条件"
                })
                if not found:
                    score -= 3

        for cons in brief_info["constraints"]:
            keywords = cons.split()[:2]
            found = any(kw in target_content for kw in keywords if len(kw) > 1)
            checks.append({
                "item": f"约束: {cons[:30]}",
                "status": "pass" if found else "warning",
                "detail": "模型中包含相关约束" if found else "模型中未找到相关约束"
            })
            if not found:
                score -= 4

    elif effective_stage == "code":
        code_ext = os.path.splitext(target_path)[1].lower()
        for target in brief_info["solve_targets"]:
            keywords = [w for w in target.split() if len(w) > 1][:3]
            found = any(kw in target_content for kw in keywords)
            checks.append({
                "item": f"求解目标: {target[:30]}",
                "status": "pass" if found else "warning",
                "detail": "代码中找到相关内容" if found else "代码中未明确找到相关内容"
            })
            if not found:
                score -= 5

        if code_ext == ".py":
            has_import = "import" in target_content
            has_main = "if __name__" in target_content or "def main" in target_content
            has_print = "print(" in target_content
            checks.append({
                "item": "代码结构: import",
                "status": "pass" if has_import else "fail",
                "detail": "包含导入语句" if has_import else "缺少导入语句"
            })
            checks.append({
                "item": "代码结构: main",
                "status": "pass" if has_main else "warning",
                "detail": "包含主入口" if has_main else "建议添加 main 入口"
            })
            checks.append({
                "item": "代码结构: 输出",
                "status": "pass" if has_print else "warning",
                "detail": "包含输出语句" if has_print else "建议添加输出语句"
            })
        elif code_ext == ".m":
            has_clc = "clc" in target_content
            checks.append({
                "item": "代码结构: clc/clear",
                "status": "pass" if has_clc else "warning",
                "detail": "包含 clc/clear" if has_clc else "建议添加 clc; clear; close all;"
            })

    elif effective_stage == "output":
        is_dir = False
        try:
            is_dir = os.path.isdir(target_path)
        except (PermissionError, OSError):
            pass
        if is_dir:
            try:
                files = os.listdir(target_path)
            except (PermissionError, OSError):
                files = []
                checks.append({
                    "item": "目录访问",
                    "status": "warning",
                    "detail": f"目录权限不足: {target_path}"
                })
            has_figures = any(f.endswith((".png", ".jpg", ".pdf")) for f in files)
            has_results = any(f.endswith((".csv", ".txt", ".json", ".mat")) for f in files)
            checks.append({
                "item": "输出: 图表文件",
                "status": "pass" if has_figures else "warning",
                "detail": f"找到图表文件" if has_figures else "未找到图表文件"
            })
            checks.append({
                "item": "输出: 结果文件",
                "status": "pass" if has_results else "warning",
                "detail": f"找到结果文件" if has_results else "未找到结果文件"
            })
            for target in brief_info["solve_targets"]:
                keywords = [w for w in target.split() if len(w) > 1][:2]
                found = any(
                    any(kw in f for kw in keywords if len(kw) > 1)
                    for f in files
                )
                checks.append({
                    "item": f"目标覆盖: {target[:30]}",
                    "status": "pass" if found else "warning",
                    "detail": "输出中有相关文件" if found else "输出中未找到相关文件"
                })
        else:
            checks.append({
                "item": "输出路径",
                "status": "fail",
                "detail": f"不是目录: {target_path}"
            })

    if not checks:
        checks.append({
            "item": "检查项",
            "status": "fail",
            "detail": f"未为阶段生成任何检查项: {stage}"
        })
        score = 0.0

    score = max(0, min(100, score))
    passed = all(c["status"] != "fail" for c in checks) and score >= 60

    return {
        "passed": passed,
        "checks": checks,
        "score": round(score, 2)
    }


def generate_report(brief_path: str, files_json: str) -> dict:
    """生成完整核查报告"""
    if not os.path.exists(brief_path):
        raise FileNotFoundError(f"Brief 文件不存在: {brief_path}")

    try:
        files = json.loads(files_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"files 参数 JSON 解析失败: {e}")

    brief_info = extract_brief(brief_path)
    all_checks = {}
    overall_score = 0
    count = 0

    stage_map = {
        "model": "model",
        "document": "model",
        "code": "code",
        "output": "output"
    }

    for key, file_path in files.items():
        stage = stage_map.get(key, "model")
        if os.path.exists(file_path):
            result = validate_against_brief(brief_path, stage, file_path)
            all_checks[key] = result
            overall_score += result["score"]
            count += 1
        else:
            all_checks[key] = {
                "passed": False,
                "checks": [{"item": "文件存在性", "status": "fail", "detail": f"文件不存在: {file_path}"}],
                "score": 0.0
            }
            count += 1

    avg_score = overall_score / count if count > 0 else 0

    report_lines = ["# 核查报告\n"]
    report_lines.append(f"**总体评分**: {avg_score:.1f}/100\n")

    for key, result in all_checks.items():
        report_lines.append(f"\n## {key}")
        report_lines.append(f"- 评分: {result['score']:.1f}/100")
        report_lines.append(f"- 通过: {'是' if result['passed'] else '否'}\n")
        report_lines.append("| 检查项 | 状态 | 详情 |")
        report_lines.append("|--------|------|------|")
        for check in result["checks"]:
            status_icon = "[PASS]" if check["status"] == "pass" else ("[WARN]" if check["status"] == "warning" else "[FAIL]")
            report_lines.append(f"| {check['item']} | {status_icon} {check['status']} | {check['detail']} |")

    return {
        "report": "\n".join(report_lines),
        "overall_score": round(avg_score, 2),
        "checks": all_checks
    }


def main():
    parser = argparse.ArgumentParser(description="全流程核查自动化工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_extract = subparsers.add_parser("extract", help="提取 problem_brief.md 结构化信息")
    p_extract.add_argument("--brief", required=True, help="brief 文件路径")

    p_validate = subparsers.add_parser("validate", help="验证阶段输出与 brief 一致性")
    p_validate.add_argument("--brief", required=True, help="brief 文件路径")
    p_validate.add_argument("--stage", required=True, choices=["model", "document", "code", "output"], help="验证阶段")
    p_validate.add_argument("--target", required=True, help="目标文件/目录路径")

    p_report = subparsers.add_parser("report", help="生成完整核查报告")
    p_report.add_argument("--brief", required=True, help="brief 文件路径")
    p_report.add_argument("--files", required=True, help='JSON 格式的文件映射: \'{"model": "report.md", "code": "solution.py"}\'')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "extract":
            result = extract_brief(args.brief)
            output(result)
        elif args.action == "validate":
            result = validate_against_brief(args.brief, args.stage, args.target)
            output(result)
        elif args.action == "report":
            result = generate_report(args.brief, args.files)
            output(result)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
