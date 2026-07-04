#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""来源新鲜度与可访问性检查工具"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _strict(mode: str) -> bool:
    return mode in STRICT_MODES


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _add_issue(issues: list[dict], code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _candidate_path(root: Path) -> Path:
    direct = root / "source_registry.json"
    if direct.exists():
        return direct
    return root / "references" / "competition_sources.json"


def _flatten_sources(payload: dict) -> list[dict]:
    if isinstance(payload.get("sources"), list):
        return payload["sources"]
    tiers = payload.get("tiers", {})
    if not isinstance(tiers, dict):
        return []
    sources = []
    for tier_name, items in tiers.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                merged = dict(item)
                merged.setdefault("tier", tier_name)
                sources.append(merged)
    return sources


def _years_cover_current(source: dict, current_year: int) -> bool:
    if isinstance(source.get("years"), list) and source["years"]:
        years = []
        for item in source["years"]:
            try:
                years.append(int(item))
            except (TypeError, ValueError):
                pass
        return bool(years) and max(years) >= current_year - 1
    years_covered = source.get("years_covered", {})
    if isinstance(years_covered, dict):
        try:
            return int(years_covered.get("to")) >= current_year - 1
        except (TypeError, ValueError):
            return False
    return False


def _reference_year(sources: list[dict]) -> int:
    """Use checked_at when present so offline fixtures stay deterministic."""
    checked_years = []
    for source in sources:
        checked_at = str(source.get("checked_at", ""))
        if len(checked_at) >= 4 and checked_at[:4].isdigit():
            checked_years.append(int(checked_at[:4]))
    return max(checked_years) if checked_years else date.today().year


def _primary_url(source: dict) -> str | None:
    return source.get("url") or source.get("official_url")


def _secondary_urls(source: dict) -> list[str]:
    value = source.get("secondary_urls", [])
    if isinstance(value, str):
        urls = [value]
    elif isinstance(value, list):
        urls = [str(item) for item in value if item]
    else:
        urls = []
    primary = _primary_url(source)
    seen = {primary} if primary else set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _is_tls_issue(detail: str) -> bool:
    lowered = detail.lower()
    return "certificate" in lowered or "ssl" in lowered or "tls" in lowered


def _url_reachable(url: str, timeout: int = 8) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "math-modeling-source-checker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= int(response.status) < 400, str(response.status)
    except Exception as first_exc:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "math-modeling-source-checker/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return 200 <= int(response.status) < 400, str(response.status)
        except Exception as second_exc:
            return False, f"{first_exc}; {second_exc}"


def _check_online_reachability(source: dict, index: int, issues: list[dict], severity: str) -> tuple[dict, int]:
    primary = _primary_url(source)
    secondary_urls = _secondary_urls(source)
    attempts = []
    reachable_checked = 0

    primary_reachable = False
    primary_issue = None
    reachable_url = None
    fallback_used = False

    if primary:
        reachable_checked += 1
        primary_reachable, detail = _url_reachable(primary)
        attempts.append({"url": primary, "passed": primary_reachable, "detail": detail, "role": "primary"})
        if primary_reachable:
            reachable_url = primary
        else:
            primary_issue = detail

    if not reachable_url and primary_issue is not None:
        for fallback_url in secondary_urls:
            reachable_checked += 1
            reachable, detail = _url_reachable(fallback_url)
            attempts.append({"url": fallback_url, "passed": reachable, "detail": detail, "role": "secondary"})
            if reachable:
                reachable_url = fallback_url
                fallback_used = True
                break

    passed = reachable_url is not None
    check = {
        "name": f"source_{index}_reachable",
        "passed": passed,
        "url": primary,
        "primary_reachable": primary_reachable,
        "reachable_url": reachable_url,
        "fallback_used": fallback_used,
        "primary_issue": primary_issue,
        "attempts": attempts,
        "detail": "200" if primary_reachable else primary_issue,
    }

    if fallback_used and primary_issue:
        code = "primary_url_tls_issue" if _is_tls_issue(primary_issue) else "primary_url_unreachable_with_fallback"
        _add_issue(
            issues,
            code,
            "主来源 URL 当前异常，但备用来源可访问。",
            severity="warning",
            index=index,
            url=primary,
            reachable_url=reachable_url,
            detail=primary_issue,
        )
    elif not passed and primary:
        _add_issue(
            issues,
            "source_url_unreachable",
            "来源 URL 当前不可访问，且备用 URL 均不可访问。",
            severity=severity,
            index=index,
            url=primary,
            detail="; ".join(f"{item['url']}: {item['detail']}" for item in attempts),
        )

    return check, reachable_checked


def check_source_freshness(workspace: str, mode: str = "standard", online: bool = False) -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = _candidate_path(root)
    if not path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "online": online,
            "passed": severity == "warning",
            "warning": severity == "warning",
            "sources_checked": 0,
            "checks": [],
            "issues": [
                {
                    "code": "missing_source_registry",
                    "severity": severity,
                    "message": "缺少 source_registry.json 或 references/competition_sources.json。",
                }
            ],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "online": online,
            "passed": False,
            "warning": False,
            "sources_checked": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    strict = _strict(normalized_mode)
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    checks: list[dict] = []
    sources = _flatten_sources(payload) if isinstance(payload, dict) else []
    current_year = _reference_year(sources)

    if not sources:
        _add_issue(issues, "missing_sources", "来源登记表必须包含非空来源列表。", severity=severity)

    reachable_checked = 0
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            _add_issue(issues, "invalid_source", "来源项必须是对象。", severity=severity, index=index)
            continue
        url = _primary_url(source)
        required_ok = _present(source.get("name")) and _present(url) and _present(source.get("tier"))
        years_ok = _years_cover_current(source, current_year)
        checks.append({"name": f"source_{index}_structure", "passed": required_ok, "source": source.get("name")})
        checks.append({"name": f"source_{index}_years", "passed": years_ok, "source": source.get("name")})
        if not required_ok:
            _add_issue(issues, "missing_source_field", "来源项缺少 name/url/tier。", severity=severity, index=index, source=source.get("name"))
        if not years_ok:
            _add_issue(issues, "stale_source_years", "来源年份覆盖不足或未记录到近两年。", severity=severity, index=index, source=source.get("name"))
        if online and url:
            reachability_check, checked_count = _check_online_reachability(source, index, issues, severity)
            reachable_checked += checked_count
            checks.append(reachability_check)

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "online": online,
        "passed": passed,
        "warning": warning,
        "sources_checked": len(sources),
        "reachable_checked": reachable_checked,
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查来源登记的新鲜度与 URL 可访问性")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    parser.add_argument("--online", action="store_true", help="联网检查 URL 可访问性；默认只做离线结构检查")
    args = parser.parse_args()
    try:
        result = check_source_freshness(args.workspace, args.mode, online=args.online)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
