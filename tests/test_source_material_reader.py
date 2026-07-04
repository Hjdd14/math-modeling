#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞赛来源材料读取工具测试"""

import json

from tools import source_material_reader


def write_registry(root, source):
    references = root / "references"
    references.mkdir()
    (references / "competition_sources.json").write_text(
        json.dumps({"tiers": {"tier_a": [source], "tier_b": [], "tier_c": []}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_source_material_reader_accepts_html_material_and_archive(monkeypatch, tmp_path):
    write_registry(
        tmp_path,
        {
            "name": "示例竞赛",
            "tier": "tier_a",
            "official_url": "https://example.test/index.html",
            "secondary_urls": [],
        },
    )

    def fake_fetch(url, timeout=15, max_bytes=2_000_000):
        if url.endswith("index.html"):
            return {
                "url": url,
                "final_url": url,
                "status": 200,
                "content_type": "text/html; charset=utf-8",
                "bytes": 120,
                "truncated": False,
                "tls_verified": False,
                "tls_warning": "certificate verification disabled for material probing",
                "data": '<html><a href="/excellent.zip">优秀论文汇总.zip</a><p>优秀论文 赛题 获奖</p></html>'.encode("utf-8"),
            }
        return {
            "url": url,
            "final_url": url,
            "status": 200,
            "content_type": "application/zip",
            "bytes": 4096,
            "truncated": False,
            "tls_verified": False,
            "tls_warning": "certificate verification disabled for material probing",
            "data": b"x" * 4096,
        }

    monkeypatch.setattr(source_material_reader, "_fetch", fake_fetch)

    result = source_material_reader.check_source_materials(str(tmp_path), mode="excellence", sample_documents=1)

    assert result["passed"] is True
    assert result["sources_checked"] == 1
    assert result["sources_with_material"] == 1
    assert result["sources_with_readable_documents"] == 1


def test_source_material_reader_reports_unverified_tls(monkeypatch, tmp_path):
    write_registry(
        tmp_path,
        {
            "name": "证书异常但可读竞赛",
            "tier": "tier_a",
            "official_url": "https://expired.example/index.html",
            "secondary_urls": [],
        },
    )

    def fake_fetch(url, timeout=15, max_bytes=2_000_000):
        return {
            "url": url,
            "final_url": url,
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "bytes": 100,
            "truncated": False,
            "tls_verified": False,
            "tls_warning": "certificate verification disabled for material probing",
            "data": b"<html><p>outstanding paper results</p></html>",
        }

    monkeypatch.setattr(source_material_reader, "_fetch", fake_fetch)

    result = source_material_reader.check_source_materials(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["tls_verified"] is False
    assert result["tls_warning"] == "certificate verification disabled for material probing"
    page = result["source_results"][0]["pages"][0]
    assert page["tls_verified"] is False
    assert page["tls_warning"] == "certificate verification disabled for material probing"


def test_source_material_reader_fails_without_material_signal(monkeypatch, tmp_path):
    write_registry(
        tmp_path,
        {
            "name": "空白竞赛",
            "tier": "tier_a",
            "official_url": "https://example.test/home.html",
            "secondary_urls": [],
        },
    )

    def fake_fetch(url, timeout=15, max_bytes=2_000_000):
        return {
            "url": url,
            "final_url": url,
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "bytes": 100,
            "truncated": False,
            "data": b"<html><p>ordinary homepage</p></html>",
        }

    monkeypatch.setattr(source_material_reader, "_fetch", fake_fetch)

    result = source_material_reader.check_source_materials(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "missing_readable_source_material" for issue in result["issues"])


def test_source_material_reader_detects_document_kind_from_query_url():
    assert source_material_reader._document_kind("https://example.test/download?file=paper.pdf") == "pdf"
    assert source_material_reader._document_kind("https://example.test/download?name=excellent.zip") == "archive"
