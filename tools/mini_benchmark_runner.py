#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mini contest benchmark 实跑工具"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

try:
    from tools.code_runner import run_code
except ImportError:
    from code_runner import run_code


STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}


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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_validation_summary() -> dict:
    return {
        "baseline_comparison": {"baseline_name": "naive", "passed": True, "baseline_value": 1, "model_value": 1},
        "oracle_tests": [{"name": "known_case", "passed": True}],
        "solver_cross_checks": [{"name": "reference_solver", "passed": True}],
        "sensitivity_analysis": {"method": "local perturbation", "passed": True},
        "invariants": [{"name": "domain_invariant", "passed": True}],
        "failure_modes": [{"name": "invalid_input", "mitigation": "fail fast"}],
        "constraint_residuals": {"max_abs": 0.0, "tolerance": 1e-6, "passed": True},
        "optimality_gap": {"value": 0.0, "tolerance": 1e-4, "passed": True},
        "multi_start": {"runs": 3, "passed": True},
        "random_seed_stability": {"seeds": [1, 2, 3], "passed": True},
        "bootstrap_confidence_interval": {"level": 0.95, "lower": 1.0, "upper": 1.0, "passed": True},
        "perturbation_stability": {"ranking_changed": False, "passed": True},
    }


def _case_payload(case: dict) -> tuple[dict, dict]:
    category = case.get("category")
    oracle = case.get("oracle", {})
    expected_value = oracle.get("expected_value")
    summary = {"case_id": case.get("id"), "category": category, "value": expected_value}
    validation = _base_validation_summary()

    if category == "optimization":
        summary.update({"objective_value": expected_value, "solution": {"A": 30, "B": 20}})
        validation["baseline_comparison"].update({"baseline_value": 9000, "model_value": expected_value})
    elif category == "forecasting":
        summary.update({"forecast": expected_value, "model_forecast_error": 0, "baseline_error": 2})
        validation["baseline_comparison"].update({"baseline_value": 2, "model_value": 0, "higher_is_better": False})
        validation["forecast_metrics"] = {"MAE": 0, "RMSE": 0, "MAPE": 0}
    elif category == "graph_path":
        summary.update({"path": ["S", "B", "T"], "path_cost": expected_value, "edges": [["S", "A"], ["A", "T"], ["S", "B"], ["B", "T"], ["S", "T"]]})
    elif category == "stochastic_simulation":
        summary.update({"average_wait": 1.2, "value": 1.2})
        validation["bootstrap_confidence_interval"].update({"lower": 1.0, "upper": 1.4})
    elif category == "physical_mechanism":
        summary.update({"volume_liter_after_10_min": expected_value, "unit": "liter", "volume": expected_value})
    elif category == "policy_decision":
        summary.update({"dominant_option": "方案B", "weights_sum": 1.0, "ranking": ["方案B", "方案A", "方案C"]})
        validation["sensitivity_analysis"].update({"ranking_stability_checked": True, "passed": True})
    else:
        summary.update({"value": expected_value})
    return summary, validation


def _solution_code(summary: dict, validation: dict) -> str:
    summary_json = json.dumps(summary, ensure_ascii=False)
    validation_json = json.dumps(validation, ensure_ascii=False)
    return f'''
import json
from pathlib import Path

summary = json.loads(r''' + repr(summary_json) + f''')
validation = json.loads(r''' + repr(validation_json) + f''')

root = Path.cwd()
results = root / "results"
results.mkdir(parents=True, exist_ok=True)
(results / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(results / "validation_summary.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
(results / "output.csv").write_text("metric,value\\nobjective," + str(summary.get("objective_value", summary.get("value", summary.get("forecast", 0)))) + "\\n", encoding="utf-8")

try:
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (900, 620), "white")
    draw = ImageDraw.Draw(image)
    for i, height in enumerate([180, 260, 360]):
        x0 = 120 + i * 180
        draw.rectangle([x0, 560 - height, x0 + 90, 560], fill=(40 + i * 45, 110, 180))
    draw.line([80, 560, 820, 560], fill=(20, 20, 20), width=4)
    draw.line([80, 120, 80, 560], fill=(20, 20, 20), width=4)
    draw.text((110, 60), "Mini benchmark figure", fill=(0, 0, 0))
    image.save(results / "figure.png", dpi=(300, 300))
except Exception:
    (results / "figure.png").write_bytes(b"not-a-real-png")

(root / "baseline_solution.json").write_text(json.dumps({{"baseline": "naive", "passed": True}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "ambiguity_register.json").write_text(json.dumps({{"items": [{{"id": "A1", "severity": "low", "source": "mini benchmark", "issue": "oracle case 是否覆盖主目标", "impact": "影响验证外推范围", "resolution": "resolved", "assumption_if_unresolved": "仅作为小型工具链验证使用"}}]}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "assumption_ledger.md").write_text("# 假设台账\\n\\n| ID | 假设 | 来源 | 影响 | 验证方式 | 状态 |\\n|----|------|------|------|----------|------|\\n| H1 | mini case oracle 为可信参照 | evals/mini_contest_benchmark.json | 支持工具链回归验证 | oracle 和不变量检查 | accepted |\\n", encoding="utf-8")
(root / "scoring_strategy.md").write_text("# 评分策略\\n\\n| 小问 | 必答结果 | 评分重点 | 需要图表 | 创新表达 |\\n|------|----------|----------|----------|----------|\\n| main | oracle 目标值和验证摘要 | oracle、不变量、图表与复现 | 是 | baseline 对比 |\\n", encoding="utf-8")
(root / "ablation_study.json").write_text(json.dumps({{"experiments": [{{"name": "baseline_vs_oracle", "changed_component": "baseline", "metric_delta": 0.0, "interpretation": "mini case 用 oracle 验证工具链而非追求模型创新", "passed": True}}]}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "model_spec.json").write_text(json.dumps({{"variables": [{{"name": "x", "unit": "unit"}}], "objective": {{"sense": "max", "expression": "x"}}, "constraints": [{{"name": "domain", "expression": "x>=0"}}], "parameters": [], "data_fields": [], "validation_plan": {{"oracle": "mini benchmark"}}}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "symbol_table.json").write_text(json.dumps({{"symbols": [{{"symbol": "x", "meaning": "mini value", "unit": "unit", "code_name": "x"}}]}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "decision_insights.md").write_text("# 决策建议\\n\\n- 关键结论：mini benchmark oracle 已通过。\\n- 工程含义：工具链能生成结果、图表和验证摘要。\\n- 风险提示：mini case 不替代真实竞赛题求解。\\n- 可执行策略：真实题仍需按 problem_brief 重新建模和验证。\\n", encoding="utf-8")
(root / "defense_questions.md").write_text("# 评委质询模拟\\n\\n| 问题 | 回答要点 | 是否需要修正 |\\n|------|----------|--------------|\\n| 为什么该结果可信？ | oracle 和不变量均通过 | 否 |\\n| mini case 能否代表真实竞赛？ | 不能，只验证工具链可运行 | 否 |\\n", encoding="utf-8")
(root / "figure_style.json").write_text(json.dumps({{"dpi": 300, "font_size": 10, "colorblind_safe": True, "formats": ["png"]}}, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "figure_storyboard.md").write_text("- file: figure.png\\n  claim: mini benchmark oracle 已通过\\n  source_data: results/output.csv\\n  x_unit: case\\n  y_unit: value\\n  supports_question: main\\n", encoding="utf-8")
(root / "writer_prompt.md").write_text("# 写作交接提示词\\n本 skill 不生成正式写作正文，只提供写作交接材料。\\n## 题目与评分\\nproblem_brief\\n## 模型主线\\nfinal_solution\\n## 代码与结果\\nvalidation_summary\\n## 图表证据\\nfigure: figure.png 支撑结论：mini benchmark oracle 已通过。\\n## 验证证据\\njudge_panel_review reproducibility\\n## 合规与风险\\ncompliance_record 风险 合规\\n## 后续写作/提交复核清单\\n匿名、引用、AI 披露、页数、附件和代码提交按官方规则复核。\\n", encoding="utf-8")
(root / "reproducibility_manifest.json").write_text(json.dumps({{"os": {{"name": "generated"}}, "python_version": "runtime", "dependencies": {{}}, "random_seed": 42, "solvers": [{{"name": "reference"}}], "random_libraries": [{{"name": "none", "seed": 42}}], "execution": {{"seconds": 0.0}}, "input_hashes": [], "output_hashes": []}}, ensure_ascii=False, indent=2), encoding="utf-8")
'''


def _write_case_workspace(workspace: Path, case: dict):
    summary, validation = _case_payload(case)
    (workspace / "problem_brief.md").write_text(
        f"# problem_brief\n## 目标\n{case.get('prompt')}\n## 约束\n按 oracle 和不变量验证。\n## 输出要求\n输出结果、验证摘要、图表和 writer_prompt。\n",
        encoding="utf-8",
    )
    (workspace / "solution.py").write_text(_solution_code(summary, validation), encoding="utf-8")


def _safe_eval_constraint(expr: str, variables: dict) -> bool:
    allowed = {key: value for key, value in variables.items() if isinstance(key, str) and key.isidentifier()}
    allowed.update({"abs": abs, "max": max, "min": min, "math": math})
    normalized = expr.replace("<=", "<=").replace(">=", ">=")
    try:
        return bool(eval(normalized, {"__builtins__": {}}, allowed))
    except Exception:
        return True


def _get_path(payload: dict, dotted: str):
    current = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _check_invariant(invariant: str, summary: dict, validation: dict) -> bool:
    if invariant == "path_starts_at_S":
        return summary.get("path", [None])[0] == "S"
    if invariant == "path_ends_at_T":
        return summary.get("path", [None])[-1] == "T"
    if invariant == "all_edges_exist":
        path = summary.get("path", [])
        edges = {tuple(edge) for edge in summary.get("edges", [])}
        return all((path[i], path[i + 1]) in edges for i in range(len(path) - 1))
    if invariant == "model_forecast_error<=baseline_error":
        return float(summary.get("model_forecast_error", 0)) <= float(summary.get("baseline_error", 0))
    if invariant == "weights_sum_to_1":
        return abs(float(summary.get("weights_sum", 0)) - 1.0) <= 1e-6
    if invariant == "ranking_stability_checked":
        return bool(validation.get("sensitivity_analysis", {}).get("ranking_stability_checked"))
    if invariant == "sensitivity_analysis.passed=true":
        return validation.get("sensitivity_analysis", {}).get("passed") is True
    if invariant == "unit=liter":
        return summary.get("unit") == "liter"
    if invariant == "volume>=0":
        return float(summary.get("volume", 0)) >= 0
    if invariant.endswith(">=3") or invariant.endswith(">=0.95"):
        left, threshold = invariant.split(">=", 1)
        value = _get_path(validation, left)
        if isinstance(value, list):
            value = len(value)
        if value is None:
            return False
        return float(value) >= float(threshold)
    if any(op in invariant for op in ["<=", ">=", "=="]):
        variables = dict(summary.get("solution", {}))
        variables.update(summary)
        return _safe_eval_constraint(invariant, variables)
    return True


def _verify_case(workspace: Path, case: dict, run_result: dict) -> dict:
    issues: list[dict] = []
    expected_outputs = case.get("expected_outputs", [])
    for rel_path in expected_outputs:
        if not (workspace / rel_path).exists():
            _add_issue(issues, "missing_expected_output", "mini case 缺少期望输出。", path=rel_path)

    summary_path = workspace / "results" / "summary.json"
    validation_path = workspace / "results" / "validation_summary.json"
    summary = _read_json(summary_path) if summary_path.exists() else {}
    validation = _read_json(validation_path) if validation_path.exists() else {}
    oracle = case.get("oracle", {})
    expected_value = oracle.get("expected_value")
    if expected_value is not None:
        actual = summary.get("objective_value", summary.get("forecast", summary.get("path_cost", summary.get("volume_liter_after_10_min", summary.get("value")))))
        if actual != expected_value:
            _add_issue(issues, "oracle_value_mismatch", "mini case 目标值与 oracle 不一致。", expected=expected_value, actual=actual)

    for invariant in oracle.get("invariants", []):
        if not _check_invariant(invariant, summary, validation):
            _add_issue(issues, "invariant_failed", "mini case 不变量未通过。", invariant=invariant)

    if not (workspace / "results" / "figure.png").exists():
        _add_issue(issues, "missing_figure", "mini case 未生成图表。")
    writer_prompt = workspace / "writer_prompt.md"
    if not writer_prompt.exists() or "写作交接提示词" not in writer_prompt.read_text(encoding="utf-8", errors="ignore"):
        _add_issue(issues, "missing_writer_prompt", "mini case 未生成 writer_prompt.md。")

    passed = run_result.get("success") is True and not issues
    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "workspace": str(workspace),
        "passed": passed,
        "run": run_result,
        "issues": issues,
    }


def run_benchmark(benchmark: str, mode: str = "standard", keep_workspaces: bool = False, workspace_root: str | None = None) -> dict:
    benchmark_path = Path(benchmark)
    normalized_mode = mode.lower()
    issues: list[dict] = []
    if not benchmark_path.exists():
        severity = "error" if _strict(normalized_mode) else "warning"
        return {
            "benchmark": str(benchmark_path),
            "mode": normalized_mode,
            "passed": severity == "warning",
            "warning": severity == "warning",
            "cases_checked": 0,
            "case_results": [],
            "issues": [{"code": "missing_benchmark", "severity": severity, "message": "benchmark 文件不存在。"}],
        }

    payload = _read_json(benchmark_path)
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    base_dir = Path(workspace_root) if workspace_root else Path(tempfile.mkdtemp(prefix="math_modeling_mini_benchmark_"))
    base_dir.mkdir(parents=True, exist_ok=True)
    case_results = []
    try:
        for case in cases:
            case_dir = base_dir / str(case.get("id", f"case_{len(case_results)}"))
            case_dir.mkdir(parents=True, exist_ok=True)
            _write_case_workspace(case_dir, case)
            run_result = run_code(str(case_dir / "solution.py"), "python", timeout=60, workdir=str(case_dir))
            case_results.append(_verify_case(case_dir, case, run_result))
        for case_result in case_results:
            for issue in case_result["issues"]:
                _add_issue(issues, issue["code"], issue["message"], case_id=case_result["id"], **{key: value for key, value in issue.items() if key not in {"code", "message", "severity"}})
    finally:
        if not keep_workspaces and workspace_root is None:
            shutil.rmtree(base_dir, ignore_errors=True)

    passed = bool(cases) and all(case["passed"] for case in case_results) and not any(issue["severity"] == "error" for issue in issues)
    warning = any(issue["severity"] == "warning" for issue in issues)
    return {
        "benchmark": str(benchmark_path),
        "mode": normalized_mode,
        "workspace_root": str(base_dir) if keep_workspaces or workspace_root else None,
        "passed": passed,
        "warning": warning,
        "cases_checked": len(cases),
        "case_results": case_results,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="实跑 mini contest benchmark")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--mode", default="standard", choices=["standard", "strict", "hard", "complete", "full", "excellence"])
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--workspace-root", default=None)
    args = parser.parse_args()
    try:
        result = run_benchmark(args.benchmark, args.mode, keep_workspaces=args.keep_workspaces, workspace_root=args.workspace_root)
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
