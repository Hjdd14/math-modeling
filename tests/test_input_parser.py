#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""input_parser 工具测试"""

import os
import zipfile

import pytest

from tools import input_parser


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA = os.path.join(SKILL_DIR, "tests", "test_data")


def create_minimal_docx(path, text):
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>"
        f"{text}"
        "</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        zf.writestr("word/document.xml", xml)


def test_extract_markdown_and_docx_text(tmp_path):
    md_file = tmp_path / "problem.md"
    md_file.write_text("# 题目\n请建立模型最大化利润。", encoding="utf-8")
    md_result = input_parser.extract_text(str(md_file))
    assert md_result["file_type"] == "md"
    assert "最大化利润" in md_result["text"]

    docx_file = tmp_path / "problem.docx"
    create_minimal_docx(docx_file, "DOCX数学建模题目：优化生产计划")
    docx_result = input_parser.extract_text(str(docx_file))
    assert docx_result["file_type"] == "docx"
    assert "优化生产计划" in docx_result["text"]


def test_extract_pdf_text(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf_file = tmp_path / "problem.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF modeling problem: maximize profit")
    doc.save(pdf_file)
    doc.close()

    result = input_parser.extract_text(str(pdf_file))
    assert result["file_type"] == "pdf"
    assert "maximize profit" in result["text"]


def test_build_brief_combines_problem_text_and_data_summary(tmp_path):
    problem_file = tmp_path / "problem.txt"
    problem_file.write_text("生产优化问题：求最大利润。", encoding="utf-8")
    out_file = tmp_path / "problem_brief.md"

    result = input_parser.build_brief(
        str(problem_file),
        [os.path.join(TEST_DATA, "data.csv")],
        str(out_file),
    )

    content = out_file.read_text(encoding="utf-8")
    assert result["brief_path"] == str(out_file)
    assert "生产优化问题" in content
    assert "附件数据" in content
    assert "data.csv" in content
    assert result["data_summaries"][0]["structure"]["file_name"] == "data.csv"


def test_quickstart_example_can_generate_brief(tmp_path):
    out_file = tmp_path / "problem_brief.md"
    result = input_parser.build_brief(
        os.path.join(SKILL_DIR, "examples", "quickstart", "problem.md"),
        [os.path.join(SKILL_DIR, "examples", "quickstart", "production_data.csv")],
        str(out_file),
    )

    content = out_file.read_text(encoding="utf-8")
    assert result["written"] is True
    assert "绿色生产计划优化" in content
    assert "production_data.csv" in content
