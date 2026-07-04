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
STORYBOARD_REQUIRED_FIELDS = ["file", "claim", "source_data", "x_unit", "y_unit", "supports_question"]


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


def _parse_storyboard(text: str) -> list[dict]:
    """解析 figure_storyboard.md 中的 YAML-like 列表或 Markdown 表格。"""
    entries: list[dict] = []
    current: dict | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            if len(cells) >= 5 and cells[0] not in {"图表", "------", "---"} and not set(cells[0]) <= {"-"}:
                entries.append(
                    {
                        "file": cells[0],
                        "supports_question": cells[1],
                        "source_data": cells[2],
                        "claim": cells[3],
                        "report_position": cells[4],
                    }
                )
            continue
        if line.startswith("- file:"):
            if current:
                entries.append(current)
            current = {"file": line.split(":", 1)[1].strip().strip("`")}
            continue
        if current and ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip().strip("`")

    if current:
        entries.append(current)
    return entries


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
        storyboard_entries = _parse_storyboard(storyboard_text)
        checks.append({"name": "figure_storyboard_schema", "passed": bool(storyboard_entries), "entries": len(storyboard_entries)})
        if strict and not storyboard_entries:
            _add_issue(
                issues,
                "invalid_figure_storyboard_schema",
                "figure_storyboard.md 必须按每图 file/claim/source_data/x_unit/y_unit/supports_question 记录语义证据。",
            )
    else:
        storyboard_entries = []
        _add_issue(
            issues,
            "missing_figure_storyboard",
            "缺少 figure_storyboard.md；图表缺少先验叙事设计。",
            "error" if strict else "warning",
        )

    png_files = sorted(results_dir.glob("*.png"))
    png_names = {path.name for path in png_files}
    if not png_files:
        _add_issue(issues, "missing_figures", "results/ 中未找到 PNG 图表。", "error" if strict else "warning")

    storyboard_by_file = {}
    for entry in storyboard_entries:
        file_name = entry.get("file")
        if file_name:
            storyboard_by_file[file_name] = entry
        missing_fields = [field for field in STORYBOARD_REQUIRED_FIELDS if not entry.get(field)]
        if strict and missing_fields:
            _add_issue(
                issues,
                "missing_storyboard_field",
                "figure_storyboard.md 中每张图必须包含 file、claim、source_data、x_unit、y_unit 和 supports_question。",
                file=file_name,
                missing=missing_fields,
            )
        if strict and file_name and file_name not in png_names:
            _add_issue(
                issues,
                "storyboard_file_missing",
                f"figure_storyboard.md 引用的图表文件不存在: {file_name}。",
                file=file_name,
            )

    for path in png_files:
        base = check_figure(str(path))
        aspect_ratio = (base["width"] / base["height"]) if base.get("height") else 0
        figure_issues = list(base.get("issues", []))
        dpi = base.get("dpi", [0, 0])
        if aspect_ratio and (aspect_ratio < 0.35 or aspect_ratio > 3.5):
            figure_issues.append("图表比例失衡，可能不适合论文排版")
        low_dpi = bool(dpi and min(dpi) < 300)
        if strict and low_dpi:
            _add_issue(
                issues,
                "figure_low_dpi",
                f"{path.name} 的 DPI 低于 300，不能支撑奖项级图表交付。",
                file=path.name,
                dpi=dpi,
                threshold=300,
            )
        has_story = not storyboard_text or path.name in storyboard_text or path.stem in storyboard_text
        storyboard_entry = storyboard_by_file.get(path.name)
        if storyboard_text and not has_story:
            figure_issues.append("图表未在 figure_storyboard.md 中说明叙事用途")
        if strict and storyboard_text and not storyboard_entry:
            figure_issues.append("图表未按结构化 schema 在 figure_storyboard.md 中登记")

        passed = base.get("quality_score", 0) >= 60 and not base.get("is_blank", True)
        if strict and storyboard_text and not has_story:
            passed = False
        if strict and storyboard_text and not storyboard_entry:
            passed = False
        if strict and low_dpi:
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
                "storyboard_claim": storyboard_entry.get("claim") if storyboard_entry else None,
                "source_data": storyboard_entry.get("source_data") if storyboard_entry else None,
                "x_unit": storyboard_entry.get("x_unit") if storyboard_entry else None,
                "y_unit": storyboard_entry.get("y_unit") if storyboard_entry else None,
                "supports_question": storyboard_entry.get("supports_question") if storyboard_entry else None,
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
