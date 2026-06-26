#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出版级图表审计工具"""

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.figure_checker import check_figure
except ImportError:
    from figure_checker import check_figure


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _add_issue(issues: list, code: str, message: str, severity: str = "error", **extra):
    issue = {"code": code, "severity": severity, "message": message}
    issue.update(extra)
    issues.append(issue)


def _load_style(root: Path):
    path = root / "figure_style.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def audit_figures(workspace: str, mode: str = "standard") -> dict:
    root = Path(workspace)
    results_dir = root / "results"
    report_path = results_dir / "figure_quality_report.json"
    strict = mode in STRICT_MODES

    issues = []
    checks = []
    figures = []
    style = None

    if not results_dir.exists():
        _add_issue(issues, "missing_results_dir", "缺少 results/ 目录。", "error" if strict else "warning")
        result = {
            "workspace": str(root),
            "mode": mode,
            "passed": not strict,
            "warning": not strict,
            "figures_audited": 0,
            "checks": checks,
            "issues": issues,
            "figures": figures,
        }
        return result

    try:
        style = _load_style(root)
    except Exception as exc:
        _add_issue(issues, "invalid_figure_style", f"figure_style.json 无法解析: {exc}")

    if style is None:
        _add_issue(
            issues,
            "missing_figure_style",
            "缺少 figure_style.json，无法确认统一字体、DPI、色板和输出格式。",
            "error" if strict else "warning",
        )
    else:
        checks.append({"name": "figure_style_present", "passed": True, "style": style})

    storyboard_path = root / "figure_storyboard.md"
    storyboard_text = ""
    if storyboard_path.exists():
        storyboard_text = storyboard_path.read_text(encoding="utf-8", errors="ignore")
        checks.append({"name": "figure_storyboard_present", "passed": True})
    else:
        _add_issue(
            issues,
            "missing_figure_storyboard",
            "缺少 figure_storyboard.md；图表缺少先验叙事设计。",
            "error" if strict else "warning",
        )

    png_files = sorted(results_dir.glob("*.png"))
    if not png_files:
        _add_issue(issues, "missing_figures", "results/ 中未找到 PNG 图表。", "error" if strict else "warning")

    for path in png_files:
        base = check_figure(str(path))
        aspect_ratio = (base["width"] / base["height"]) if base.get("height") else 0
        figure_issues = list(base.get("issues", []))
        if aspect_ratio and (aspect_ratio < 0.35 or aspect_ratio > 3.5):
            figure_issues.append("图表比例失衡，可能不适合论文排版")
        has_story = not storyboard_text or path.name in storyboard_text or path.stem in storyboard_text
        if storyboard_text and not has_story:
            figure_issues.append("图表未在 figure_storyboard.md 中说明叙事用途")

        passed = base.get("quality_score", 0) >= 60 and not base.get("is_blank", True)
        if strict and storyboard_text and not has_story:
            passed = False
        if not passed:
            _add_issue(issues, "figure_quality_failed", f"{path.name} 未达到最低图表质量要求。", file=path.name)

        figures.append(
            {
                "file": path.name,
                "passed": passed,
                "quality_score": base.get("quality_score", 0),
                "width": base.get("width", 0),
                "height": base.get("height", 0),
                "dpi": base.get("dpi", [0, 0]),
                "issues": figure_issues,
                "storyboard_referenced": has_story,
            }
        )

    checks.append({"name": "figures_present", "passed": bool(png_files), "count": len(png_files)})
    checks.append({"name": "all_figures_nonblank", "passed": all(item["passed"] for item in figures) if figures else False})

    passed = not any(issue.get("severity") == "error" for issue in issues)
    warning = any(issue.get("severity") == "warning" for issue in issues)
    result = {
        "workspace": str(root),
        "mode": mode,
        "passed": passed,
        "warning": warning,
        "figures_audited": len(figures),
        "checks": checks,
        "issues": issues,
        "figures": figures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description="审计 results/ 中图表的出版级质量")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    args = parser.parse_args()
    try:
        result = audit_figures(args.workspace, args.mode)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
