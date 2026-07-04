#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威竞赛资料内容读取检查工具"""

from __future__ import annotations

import argparse
import json
import contextlib
import re
import ssl
import sys
import urllib.request
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import parse_qs, quote, urldefrag, urljoin, urlparse, urlsplit, urlunsplit


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
TLS_VERIFIED = False
TLS_WARNING = "certificate verification disabled for material probing"
MATERIAL_KEYWORDS = [
    "优秀论文",
    "优秀作品",
    "论文展示",
    "作品展示",
    "获奖论文",
    "赛题",
    "获奖",
    "评审",
    "评阅",
    "outstanding",
    "paper",
    "papers",
    "results",
]
DOCUMENT_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".zip": "archive",
    ".rar": "archive",
}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _strict(mode: str) -> bool:
    return mode in STRICT_MODES


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _fetch(url: str, timeout: int = 15, max_bytes: int = 2_000_000) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 math-modeling-source-material-reader/1.0"}
    context = ssl._create_unverified_context()
    request_url = _normalize_url(_unwrap_download_url(url))
    request = urllib.request.Request(request_url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        return {
            "url": url,
            "final_url": response.geturl(),
            "status": getattr(response, "status", 200),
            "content_type": response.headers.get("content-type", ""),
            "bytes": len(data),
            "truncated": truncated,
            "tls_verified": TLS_VERIFIED,
            "tls_warning": TLS_WARNING,
            "data": data,
        }


def _decode_text(data: bytes, content_type: str = "") -> str:
    charset_match = re.search(r"charset=([\w.-]+)", content_type, flags=re.I)
    encodings = []
    if charset_match:
        encodings.append(charset_match.group(1))
    encodings.extend(["utf-8", "gb18030", "gbk"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _unwrap_download_url(url: str) -> str:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    wrapped = query.get("url")
    if wrapped and wrapped[0].startswith(("http://", "https://")):
        return wrapped[0]
    return url


def _normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https", "file"}:
        return url
    path = quote(parsed.path, safe="/%")
    query = quote(parsed.query, safe="=&?/%:+,;@!$'()*[]")
    fragment = quote(parsed.fragment, safe="/%")
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, fragment))


def _material_keywords(text: str) -> list[str]:
    lower = text.lower()
    return [keyword for keyword in MATERIAL_KEYWORDS if keyword.lower() in lower]


def _document_kind(url: str, content_type: str = "") -> str | None:
    url = _unwrap_download_url(url)
    lowered_type = content_type.lower()
    if "pdf" in lowered_type:
        return "pdf"
    if "wordprocessingml" in lowered_type or "officedocument.wordprocessingml" in lowered_type:
        return "docx"
    if "zip" in lowered_type:
        return "archive"
    path = urlparse(url).path.lower()
    full_url = url.lower()
    for extension, kind in DOCUMENT_EXTENSIONS.items():
        if path.endswith(extension) or extension in path or extension in full_url:
            return kind
    return None


def _extract_links(html: str, base_url: str) -> list[str]:
    links = []
    seen = set()
    for match in re.finditer(r"""(?:href|src)\s*=\s*['"]([^'"]+)['"]""", html, flags=re.I):
        raw = match.group(1).strip()
        if not raw or raw.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urldefrag(urljoin(base_url, raw))[0]
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links


def _read_pdf_text(data: bytes, min_chars: int = 20) -> dict:
    try:
        from pypdf import PdfReader

        with contextlib.redirect_stderr(StringIO()):
            reader = PdfReader(BytesIO(data))
            text_parts = []
            for page in reader.pages[:2]:
                text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts).strip()
        return {
            "readable": len(text) >= min_chars,
            "kind": "pdf",
            "pages_checked": min(len(reader.pages), 2),
            "text_chars": len(text),
            "sample": text[:160],
        }
    except Exception as exc:
        return {"readable": False, "kind": "pdf", "error": str(exc)}


def _read_docx_text(data: bytes, min_chars: int = 20) -> dict:
    try:
        from docx import Document

        document = Document(BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        return {
            "readable": len(text) >= min_chars,
            "kind": "docx",
            "text_chars": len(text),
            "sample": text[:160],
        }
    except Exception as exc:
        return {"readable": False, "kind": "docx", "error": str(exc)}


def _document_read_result(fetched: dict, kind: str) -> dict:
    data = fetched["data"]
    if kind == "pdf":
        return _read_pdf_text(data)
    if kind == "docx":
        return _read_docx_text(data)
    if kind == "archive":
        return {
            "readable": fetched.get("bytes", 0) > 1024,
            "kind": "archive",
            "text_chars": 0,
            "sample": "",
        }
    return {
        "readable": False,
        "kind": kind,
        "error": "旧版 doc 或未知文档格式不能稳定抽取文本。",
    }


def _tls_result_fields(fetched: dict | None = None) -> dict:
    fetched = fetched or {}
    return {
        "tls_verified": bool(fetched.get("tls_verified", TLS_VERIFIED)),
        "tls_warning": fetched.get("tls_warning", TLS_WARNING),
    }


def _source_urls(source: dict) -> list[str]:
    urls = []
    for key in ["official_url", "secondary_urls", "material_probe_urls"]:
        value = source.get(key)
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            urls.extend(str(item) for item in value if item)
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _flatten_sources(registry: dict) -> list[dict]:
    sources = []
    for tier, items in registry.get("tiers", {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                source = dict(item)
                source.setdefault("tier", tier)
                sources.append(source)
    return sources


def _probe_source(source: dict, timeout: int, max_bytes: int, sample_documents: int) -> dict:
    pages = []
    document_links = []
    readable_documents = []
    html_material_pages = 0
    issues = []

    for url in _source_urls(source):
        page_result = {
            "url": url,
            "ok": False,
            "content_type": "",
            "bytes": 0,
            **_tls_result_fields(),
            "material_keywords": [],
            "document_links": [],
            "error": None,
        }
        try:
            fetched = _fetch(url, timeout=timeout, max_bytes=max_bytes)
            page_result["ok"] = 200 <= int(fetched.get("status", 200)) < 400
            page_result["content_type"] = fetched.get("content_type", "")
            page_result["bytes"] = fetched.get("bytes", 0)
            page_result.update(_tls_result_fields(fetched))
            kind = _document_kind(fetched.get("final_url", url), fetched.get("content_type", ""))
            if kind:
                read_result = _document_read_result(fetched, kind)
                read_result.update({"url": url, "content_type": fetched.get("content_type", ""), **_tls_result_fields(fetched)})
                if read_result.get("readable"):
                    readable_documents.append(read_result)
            else:
                text = _decode_text(fetched["data"], fetched.get("content_type", ""))
                keywords = _material_keywords(text)
                page_result["material_keywords"] = keywords
                if keywords:
                    html_material_pages += 1
                for link in _extract_links(text, fetched.get("final_url", url)):
                    resolved_link = _unwrap_download_url(link)
                    link_kind = _document_kind(resolved_link)
                    if link_kind:
                        item = {"url": resolved_link, "kind": link_kind}
                        page_result["document_links"].append(item)
                        document_links.append(item)
        except Exception as exc:
            page_result["error"] = str(exc)
        pages.append(page_result)

    for link in document_links[:sample_documents]:
        try:
            fetched = _fetch(link["url"], timeout=timeout, max_bytes=max_bytes)
            kind = _document_kind(fetched.get("final_url", link["url"]), fetched.get("content_type", "")) or link["kind"]
            read_result = _document_read_result(fetched, kind)
            read_result.update({"url": link["url"], "content_type": fetched.get("content_type", ""), **_tls_result_fields(fetched)})
            if read_result.get("readable"):
                readable_documents.append(read_result)
        except Exception as exc:
            _add_issue(issues, "document_sample_fetch_failed", "资料文档抽样下载失败。", "warning", url=link["url"], error=str(exc))

    material_ok = bool(readable_documents) or html_material_pages > 0 or bool(document_links)
    return {
        "name": source.get("name"),
        "tier": source.get("tier"),
        "passed": material_ok,
        "urls_checked": len(_source_urls(source)),
        "html_material_pages": html_material_pages,
        "document_links_found": len(document_links),
        "readable_documents": readable_documents,
        "pages": pages,
        **_tls_result_fields(),
        "issues": issues,
    }


def check_source_materials(
    skill_root: str,
    mode: str = "standard",
    timeout: int = 15,
    max_bytes: int = 2_000_000,
    sample_documents: int = 2,
) -> dict:
    root = Path(skill_root)
    normalized_mode = mode.lower()
    registry_path = root / "references" / "competition_sources.json"
    issues: list[dict] = []
    if not registry_path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        _add_issue(issues, "missing_source_registry", "缺少 references/competition_sources.json。", severity)
        return {
            "skill_root": str(root),
            "mode": normalized_mode,
            "passed": severity != "error",
            "warning": severity == "warning",
            **_tls_result_fields(),
            "sources_checked": 0,
            "sources_with_material": 0,
            "sources_with_readable_documents": 0,
            "source_results": [],
            "issues": issues,
        }

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    source_results = [
        _probe_source(source, timeout=timeout, max_bytes=max_bytes, sample_documents=sample_documents)
        for source in _flatten_sources(registry)
    ]

    severity = "error" if _strict(normalized_mode) else "warning"
    for result in source_results:
        if not result["passed"]:
            _add_issue(
                issues,
                "missing_readable_source_material",
                "未在该竞赛来源中读到可核验材料入口、文档链接或材料关键词。",
                severity,
                source=result["name"],
                tier=result["tier"],
            )
        for issue in result.get("issues", []):
            issues.append(issue)

    passed = not any(issue.get("severity") == "error" for issue in issues)
    return {
        "skill_root": str(root),
        "mode": normalized_mode,
        "registry_path": str(registry_path),
        "passed": passed,
        "warning": any(issue.get("severity") == "warning" for issue in issues),
        **_tls_result_fields(),
        "sources_checked": len(source_results),
        "sources_with_material": sum(1 for result in source_results if result["passed"]),
        "sources_with_readable_documents": sum(1 for result in source_results if result["readable_documents"]),
        "source_results": source_results,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="联网抽检竞赛来源是否能读到优秀论文、赛题、获奖或评审等材料内容")
    parser.add_argument("--skill-root", default=".")
    parser.add_argument("--workspace", default=None, help="兼容旧命令；等同于 --skill-root")
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    parser.add_argument("--sample-documents", type=int, default=2)
    args = parser.parse_args()
    try:
        root = args.workspace or args.skill_root
        result = check_source_materials(root, args.mode, args.timeout, args.max_bytes, args.sample_documents)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
