#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞赛合规与复现提示检查工具"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}
FINAL_SUBMISSION_FIELDS = {
    "anonymity": "匿名性最终复核",
    "ai_disclosure": "AI 使用披露",
    "citation_check": "引用与外部来源复核",
    "page_limit_checked": "页数/格式限制复核",
    "attachment_check": "附件提交复核",
    "code_submission_note": "代码提交提示",
    "official_rules_reviewed": "官方规则复核",
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


def _missing_result(root: Path, mode: str) -> dict:
    severity = "error" if _strict(mode) else "warning"
    return {
        "workspace": str(root),
        "mode": mode,
        "path": str(root / "compliance_record.json"),
        "passed": severity == "warning",
        "warning": severity == "warning",
        "checks_passed": 0,
        "checks": [],
        "issues": [
            {
                "code": "missing_compliance_record",
                "severity": severity,
                "message": "缺少 compliance_record.json；excellence 模式必须记录 AI 使用、匿名性、引用和复现信息。",
            }
        ],
    }


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def check_compliance(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    normalized_mode = mode.lower()
    path = root / "compliance_record.json"
    if not path.exists():
        return _missing_result(root, normalized_mode)

    checks: list[dict] = []
    issues: list[dict] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "workspace": str(root),
            "mode": normalized_mode,
            "path": str(path),
            "passed": False,
            "warning": False,
            "checks_passed": 0,
            "checks": [],
            "issues": [{"code": "invalid_json", "severity": "error", "message": str(exc)}],
        }

    ai_usage = payload.get("ai_usage", {}) if isinstance(payload, dict) else {}
    ai_disclosure_ok = isinstance(ai_usage, dict) and (
        ai_usage.get("disclosure_required") is True
        or ai_usage.get("disclosed") is True
        or ai_usage.get("ai_disclosure") is True
    )
    ai_ok = isinstance(ai_usage, dict) and _present(ai_usage.get("tools")) and ai_usage.get("human_reviewed") is True and ai_disclosure_ok
    checks.append({"name": "ai_usage_detail", "passed": ai_ok})
    if not ai_ok:
        _add_issue(
            issues,
            "missing_ai_usage_detail",
            "AI 使用记录必须包含工具、用途、披露要求和人工复核状态。",
        )
        if not ai_disclosure_ok:
            _add_issue(issues, "missing_ai_disclosure", "缺少 AI 使用披露记录。")

    anonymity = payload.get("anonymity", {}) if isinstance(payload, dict) else {}
    identity_terms = anonymity.get("identity_terms_found", []) if isinstance(anonymity, dict) else []
    anonymity_ok = isinstance(anonymity, dict) and anonymity.get("checked") is True and not identity_terms
    checks.append({"name": "anonymity", "passed": anonymity_ok})
    if identity_terms:
        _add_issue(issues, "identity_leak", "匿名性检查发现身份信息。", terms=identity_terms)
    elif not anonymity_ok:
        _add_issue(issues, "missing_anonymity_check", "缺少匿名性检查记录。")

    sources = payload.get("external_sources", []) if isinstance(payload, dict) else []
    sources_ok = isinstance(sources, list)
    checks.append({"name": "external_sources", "passed": sources_ok})
    if not sources_ok:
        _add_issue(issues, "invalid_external_sources", "external_sources 必须是列表。")

    reproducibility = payload.get("reproducibility", {}) if isinstance(payload, dict) else {}
    commands = reproducibility.get("commands", []) if isinstance(reproducibility, dict) else []
    repro_ok = (
        isinstance(reproducibility, dict)
        and _present(reproducibility.get("manifest"))
        and isinstance(commands, list)
        and len(commands) > 0
        and reproducibility.get("input_hashes_recorded") is True
        and reproducibility.get("output_hashes_recorded") is True
    )
    checks.append({"name": "reproducibility", "passed": repro_ok})
    if not repro_ok:
        _add_issue(
            issues,
            "missing_reproducibility_detail",
            "复现记录必须包含 manifest、运行命令、输入 hash 和输出 hash 状态。",
        )

    final_submission = payload.get("final_submission", {}) if isinstance(payload, dict) else {}
    if final_submission:
        submission_checks = []
        for field, label in FINAL_SUBMISSION_FIELDS.items():
            value = final_submission.get(field) if isinstance(final_submission, dict) else None
            ok = value is True if field != "code_submission_note" else _present(value)
            if field == "anonymity":
                ok = ok or anonymity_ok
            if field == "ai_disclosure":
                ok = ok or ai_disclosure_ok
            submission_checks.append({"field": field, "passed": ok})
            if not ok:
                _add_issue(
                    issues,
                    "missing_submission_constraint",
                    f"最终提交约束清单缺少或未通过: {label}。",
                    field=field,
                )
        checks.append(
            {
                "name": "final_submission_constraints",
                "passed": all(item["passed"] for item in submission_checks),
                "fields": submission_checks,
            }
        )

    passed = not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "path": str(path),
        "passed": passed,
        "warning": warning,
        "checks_passed": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="检查 compliance_record.json 的合规与复现提示")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = check_compliance(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
