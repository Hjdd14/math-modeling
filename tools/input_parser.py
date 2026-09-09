#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题目文件解析与 problem_brief.md 生成工具"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

try:
    from tools.data_analyzer import check_quality, generate_stats, read_data_structure
except ImportError:
    from data_analyzer import check_quality, generate_stats, read_data_structure


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "big5")


def _read_text_file(path: Path) -> tuple[str, str, bool]:
    """按常见中文赛题编码依次尝试读取。

    返回 (文本, 实际使用的编码, 是否降级)。裸 utf-8 读取会让 GBK/GB18030
    编码的中文题目直接失败，而这类编码在国内赛题里很常见。
    """
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding), encoding, False
        except UnicodeDecodeError:
            continue
    # 全部失败时保底解码，并显式标记降级，避免静默产出乱码而调用方不知情。
    return raw.decode("utf-8", errors="replace"), "utf-8(errors=replace)", True


def _read_pdf(path: Path) -> tuple[str, list[dict]]:
    """提取 PDF 文本，并逐页记录抽取状态。

    返回 (文本, 每页状态)。保留页级状态是为了让扫描件或公式排版复杂的页面
    可被识别，而不是被静默丢弃。
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 pypdf，请先安装 requirements.txt") from exc

    reader = PdfReader(str(path))
    parts = []
    page_report = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            page_text = ""
            page_report.append({"page": index, "chars": 0, "extracted": False, "error": str(exc)})
        else:
            page_report.append({"page": index, "chars": len(page_text.strip()), "extracted": bool(page_text.strip())})
        parts.append(page_text)
    return "\n".join(part for part in parts if part).strip(), page_report


def _read_docx_with_zip(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    text_parts = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            text_parts.append(node.text)
    return "\n".join(text_parts).strip()


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError:
        return _read_docx_with_zip(path)

    try:
        document = Document(str(path))
        parts = [p.text for p in document.paragraphs if p.text]
        for table in document.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    parts.append(" | ".join(row_text))
        return "\n".join(parts).strip()
    except Exception:
        return _read_docx_with_zip(path)


def extract_text(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = path.suffix.lower()
    encoding = None
    encoding_fallback = False
    page_report: list[dict] = []
    if ext in {".txt", ".md"}:
        text, encoding, encoding_fallback = _read_text_file(path)
    elif ext == ".pdf":
        text, page_report = _read_pdf(path)
    elif ext == ".docx":
        text = _read_docx(path)
    else:
        raise ValueError(f"不支持的题目文件格式: {ext}")

    if not text.strip():
        if ext == ".pdf":
            raise ValueError(
                f"PDF 文本抽取为空（共 {len(page_report)} 页）："
                "该文件可能是扫描件或纯图片版。请提供带文本层的 PDF，或先做 OCR，"
                "不要基于空题目文本继续建模。"
            )
        raise ValueError(f"题目文本抽取为空: {file_path}；请确认文件内容与编码。")

    result = {
        "file_name": path.name,
        "file_type": ext.lstrip("."),
        "text": text,
        "char_count": len(text),
        "line_count": len(text.splitlines()),
    }
    if encoding is not None:
        result["encoding"] = encoding
        result["encoding_fallback"] = encoding_fallback
    if page_report:
        empty_pages = [item["page"] for item in page_report if not item["extracted"]]
        result["pages"] = page_report
        result["empty_pages"] = empty_pages
        result["extraction_ratio"] = round(1 - len(empty_pages) / len(page_report), 4)
    return result


def summarize_data_file(file_path: str) -> dict:
    """汇总单个附件的结构、统计与质量。

    Excel 多工作表必须逐表统计：pandas 在 sheet_name=None 时只读第一个工作表，
    旧实现把首个工作表的质量评分复用到全部工作表，并且其余工作表从未被统计。
    """
    structure = read_data_structure(file_path)
    is_excel = structure.get("file_type") in {"xlsx", "xls"}
    sheets = structure.get("sheets", [])

    by_sheet = {}
    for sheet in sheets:
        sheet_name = sheet.get("sheet_name")
        sheet_arg = sheet_name if is_excel else None
        by_sheet[sheet_name] = {
            "stats": generate_stats(file_path, sheet_arg),
            "quality": check_quality(file_path, sheet_arg),
        }

    first_sheet = sheets[0].get("sheet_name") if sheets else None
    # stats/quality 保留为首个工作表的结果，维持既有调用方的返回形状。
    if first_sheet is not None and first_sheet in by_sheet:
        first_stats = by_sheet[first_sheet]["stats"]
        first_quality = by_sheet[first_sheet]["quality"]
    else:
        first_stats = generate_stats(file_path)
        first_quality = check_quality(file_path)

    return {
        "structure": structure,
        "stats": first_stats,
        "quality": first_quality,
        "by_sheet": by_sheet,
    }


def _first_lines(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[题目文本已截断，完整文本见原文件]"


def render_brief(problem_info: dict, data_summaries: list) -> str:
    lines = [
        "# 数学建模题目简报",
        "",
        "## 1. 题目原文",
        "",
        _first_lines(problem_info["text"]),
        "",
        "## 2. 求解目标",
        "",
        "- 待 Agent 根据题目原文提取并确认",
        "",
        "## 3. 已知条件与参数",
        "",
        "- 待 Agent 根据题目原文和附件数据提取",
        "",
        "## 4. 约束条件",
        "",
        "- 待 Agent 根据题目原文提取",
        "",
        "## 5. 附件数据",
        "",
        "### 5.1 附件清单",
        "",
        "| 文件名 | 工作表名 | 行数 | 列数 | 质量评分 | 备注 |",
        "|--------|----------|------|------|----------|------|",
    ]

    for summary in data_summaries:
        structure = summary["structure"]
        by_sheet = summary.get("by_sheet", {})
        for sheet in structure["sheets"]:
            sheet_name = sheet["sheet_name"]
            sheet_quality = by_sheet.get(sheet_name, {}).get("quality") or summary.get("quality", {})
            score = sheet_quality.get("quality_score", "-")
            flags = []
            if sheet_quality.get("empty_data"):
                flags.append("空数据")
            if sheet_quality.get("outlier_detection_applied") is False and not sheet_quality.get("empty_data"):
                flags.append("样本过少")
            note = "；".join(flags) if flags else "-"
            lines.append(
                f"| {structure['file_name']} | {sheet_name} | "
                f"{sheet['rows']} | {sheet['columns']} | {score} | {note} |"
            )

    lines.extend([
        "",
        "### 5.2 数据结构与示例",
        "",
    ])

    for summary in data_summaries:
        structure = summary["structure"]
        for sheet in structure["sheets"]:
            cols = ", ".join(str(c) for c in sheet["column_names"])
            lines.extend([
                f"#### {structure['file_name']} / {sheet['sheet_name']}",
                "",
                f"- 行数：{sheet['rows']}",
                f"- 列数：{sheet['columns']}",
                f"- 字段：{cols}",
                "",
            ])

    lines.extend([
        "## 6. 输出要求",
        "",
        "- 待 Agent 根据题目原文提取",
        "",
        "## 7. 评分标准（如有）",
        "",
        "- 待 Agent 根据题目原文提取",
        "",
    ])
    return "\n".join(lines)


def build_brief(problem_file: str, data_files: list[str], out_path: str) -> dict:
    problem_info = extract_text(problem_file)
    data_summaries = [summarize_data_file(path) for path in data_files]
    content = render_brief(problem_info, data_summaries)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")

    return {
        "brief_path": str(out),
        "problem": problem_info,
        "data_summaries": data_summaries,
        "written": True,
    }


def main():
    parser = argparse.ArgumentParser(description="题目文件解析与 problem_brief.md 生成工具")
    subparsers = parser.add_subparsers(dest="action", help="可用操作")

    p_extract = subparsers.add_parser("extract", help="提取题目文本")
    p_extract.add_argument("--file", required=True, help="PDF/DOCX/MD/TXT 文件路径")

    p_brief = subparsers.add_parser("brief", help="生成 problem_brief.md")
    p_brief.add_argument("--problem", required=True, help="题目文件路径")
    p_brief.add_argument("--data", nargs="*", default=[], help="附件数据文件路径")
    p_brief.add_argument("--out", required=True, help="输出 problem_brief.md 路径")

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        if args.action == "extract":
            output(extract_text(args.file))
        elif args.action == "brief":
            output(build_brief(args.problem, args.data, args.out))
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
