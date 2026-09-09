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


def _max_covered_year(source: dict) -> int | None:
    """返回该来源记录的最新覆盖年份；无法解析时返回 None。"""
    if isinstance(source.get("years"), list) and source["years"]:
        years = []
        for item in source["years"]:
            try:
                years.append(int(item))
            except (TypeError, ValueError):
                pass
        return max(years) if years else None
    years_covered = source.get("years_covered", {})
    if isinstance(years_covered, dict):
        try:
            return int(years_covered.get("to"))
        except (TypeError, ValueError):
            return None
    return None


def _reference_year(payload: dict, sources: list[dict]) -> tuple[int, str]:
    """确定用于比较年份覆盖的基准年及其来源。

    优先使用注册表自身的维护版本，其次是逐条来源的 checked_at，最后才回落到系统时钟。
    历史赛事资料本来就不会每年更新，用墙上时钟当基准会让所有来源在跨年时集体误报过期。
    """
    version = str(payload.get("version", "")) if isinstance(payload, dict) else ""
    if len(version) >= 4 and version[:4].isdigit():
        return int(version[:4]), "registry_version"
    checked_years = []
    for source in sources:
        checked_at = str(source.get("checked_at", ""))
        if len(checked_at) >= 4 and checked_at[:4].isdigit():
            checked_years.append(int(checked_at[:4]))
    if checked_years:
        return max(checked_years), "source_checked_at"
    return date.today().year, "system_clock"


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
    reference_year, reference_basis = _reference_year(payload if isinstance(payload, dict) else {}, sources)

    if not sources:
        _add_issue(issues, "missing_sources", "来源登记表必须包含非空来源列表。", severity=severity)

    if reference_basis == "system_clock" and sources:
        # 注册表既没有 version 也没有 checked_at 时无法判断维护时点，只提示不判失败。
        _add_issue(
            issues,
            "missing_registry_maintenance_date",
            "来源登记表缺少 version 或 checked_at，无法判断维护时点；已回落到系统时钟。",
            severity="warning",
        )

    reachable_checked = 0
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            _add_issue(issues, "invalid_source", "来源项必须是对象。", severity=severity, index=index)
            continue
        url = _primary_url(source)
        required_ok = _present(source.get("name")) and _present(url) and _present(source.get("tier"))
        max_year = _max_covered_year(source)
        coverage_recorded = max_year is not None
        # 覆盖年份落后于注册表维护时点只说明尚未收录新一届赛事，不等于来源失效，
        # 因此固定为 warning；真正的结构缺陷是年份覆盖压根没记录。
        coverage_behind = coverage_recorded and max_year < reference_year - 1
        checks.append({"name": f"source_{index}_structure", "passed": required_ok, "source": source.get("name")})
        checks.append({
            "name": f"source_{index}_years",
            "passed": coverage_recorded,
            "source": source.get("name"),
            "max_covered_year": max_year,
            "reference_year": reference_year,
            "reference_basis": reference_basis,
            "coverage_behind_reference": coverage_behind,
        })
        if not required_ok:
            _add_issue(issues, "missing_source_field", "来源项缺少 name/url/tier。", severity=severity, index=index, source=source.get("name"))
        if not coverage_recorded:
            _add_issue(
                issues,
                "missing_year_coverage",
                "来源项未记录可解析的 years 或 years_covered.to。",
                severity=severity,
                index=index,
                source=source.get("name"),
            )
        elif coverage_behind:
            _add_issue(
                issues,
                "source_years_behind_registry_version",
                f"来源覆盖到 {max_year}，落后于基准年 {reference_year}（依据: {reference_basis}）；"
                "历史赛事资料可能只是尚未收录新一届，需人工确认是否需要更新登记表。",
                severity="warning",
                index=index,
                source=source.get("name"),
            )
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
        "reference_year": reference_year,
        "reference_basis": reference_basis,
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
