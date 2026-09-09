#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模交付物总控验证工具"""

import argparse
import json
import sys
from pathlib import Path

try:
    from tools.award_readiness_checker import check_award_readiness
    from tools.brief_completeness_checker import check_brief_completeness
    from tools.brief_validator import validate_against_brief
    from tools.code_runner import run_code
    from tools.consistency_checker import check_formula_consistency
    from tools.data_leakage_checker import check_data_leakage
    from tools.evidence_checker import check_evidence
    from tools.figure_auditor import audit_figures
    from tools.figure_checker import batch_check
    from tools.innovation_checker import check_innovations
    from tools.judge_panel_checker import check_judge_panel
    from tools.latex_validator import validate_latex_file
    from tools.manifest_checker import check_manifest
    from tools.model_selection_checker import check_model_selection
    from tools.model_spec_checker import check_model_spec
    from tools.optimization_certificate_checker import check_optimization_certificate
    from tools.robustness_checker import check_robustness
    from tools.schema_checker import check_schema
    from tools.source_freshness_checker import check_source_freshness
    from tools.source_material_reader import check_source_materials
    from tools.source_registry_checker import check_source_registry
    from tools.statistical_validation_checker import check_statistical_validation
    from tools.uncertainty_budget_checker import check_uncertainty_budget
    from tools.unit_checker import check_units
    from tools.validation_profile_checker import check_validation_profile
    from tools.case_retrieval_checker import check_case_retrieval
    from tools.compliance_checker import check_compliance
    from tools.writer_prompt_checker import check_writer_prompt
except ImportError:
    from award_readiness_checker import check_award_readiness
    from brief_completeness_checker import check_brief_completeness
    from brief_validator import validate_against_brief
    from code_runner import run_code
    from consistency_checker import check_formula_consistency
    from data_leakage_checker import check_data_leakage
    from evidence_checker import check_evidence
    from figure_auditor import audit_figures
    from figure_checker import batch_check
    from innovation_checker import check_innovations
    from judge_panel_checker import check_judge_panel
    from latex_validator import validate_latex_file
    from manifest_checker import check_manifest
    from model_selection_checker import check_model_selection
    from model_spec_checker import check_model_spec
    from optimization_certificate_checker import check_optimization_certificate
    from robustness_checker import check_robustness
    from schema_checker import check_schema
    from source_freshness_checker import check_source_freshness
    from source_material_reader import check_source_materials
    from source_registry_checker import check_source_registry
    from statistical_validation_checker import check_statistical_validation
    from uncertainty_budget_checker import check_uncertainty_budget
    from unit_checker import check_units
    from validation_profile_checker import check_validation_profile
    from case_retrieval_checker import check_case_retrieval
    from compliance_checker import check_compliance
    from writer_prompt_checker import check_writer_prompt


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


# Phase 5 固定产物清单，取自 references/workflow.md 的归档要求。
# 仅用于生成 artifact_completeness 提示，不参与 passed 判定：
# standard 模式必须保持对旧工作区的兼容（warning-only）。
RECOMMENDED_ARTIFACTS = (
    "ambiguity_register.json",
    "assumption_ledger.md",
    "scoring_strategy.md",
    "data_schema.json",
    "symbol_table.json",
    "modeling_state.json",
    "modeling_memory.md",
    "baseline_solution.json",
    "case_retrieval.json",
    "model_selection_audit.json",
    "model_spec.json",
    "optimization_certificate.json",
    "uncertainty_budget.json",
    "validation_profile.json",
    "data_validation.json",
    "statistical_validation.json",
    "solver_strategy.json",
    "ablation_study.json",
    "innovation_register.json",
    "final_solution.json",
    "model_decision.md",
    "writer_prompt.md",
    "figure_style.json",
    "figure_storyboard.md",
    "results/validation_summary.json",
    "results/figure_quality_report.json",
    "judge_panel_review.json",
    "decision_insights.md",
    "defense_questions.md",
    "compliance_record.json",
    "reproducibility_manifest.json",
)


def _artifact_completeness(root: Path, language: str, required_missing: list) -> dict:
    """汇总固定产物齐备情况，让"standard 模式通过"不等于"产物齐全"。"""
    code_name = "solution.m" if language == "matlab" else "solution.py"
    tests_name = "solution_tests.m" if language == "matlab" else "solution_tests.py"
    required = ["problem_brief.md", code_name, "results"]
    recommended = list(RECOMMENDED_ARTIFACTS) + [tests_name]

    present, missing = [], []
    for rel in recommended:
        if (root / rel).exists():
            present.append(rel)
        else:
            missing.append(rel)
    return {
        "required": required,
        "required_missing": [str(item) for item in required_missing],
        "recommended_total": len(recommended),
        "recommended_present": present,
        "recommended_missing": missing,
        "recommended_present_count": len(present),
        "note": (
            "recommended_missing 不影响 passed。standard 模式只做兼容性自检；"
            "完整交付请使用 --evidence-mode strict --quality-mode excellence。"
        ),
    }


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def _safe(name: str, checks: dict, func):
    try:
        checks[name] = func()
    except Exception as exc:
        checks[name] = {"passed": False, "error": str(exc)}
    return checks[name]


def _latex_advisory(model_decision: Path) -> dict:
    """对 model_decision.md 中的 LaTeX 公式做提示性检查。

    该检查只产出 warning：LaTeX 校验是启发式的，不足以作为总控失败依据，
    但此前 validate_latex_file 被导入却从未调用，模型文档里的公式完全没被看过。
    需要判失败时请单独运行 tools/latex_validator.py。
    """
    result = {"passed": True, "warning": False, "advisory_only": True, "issues": []}
    try:
        report = validate_latex_file(str(model_decision))
    except Exception as exc:
        result["warning"] = True
        result["issues"].append({"code": "latex_check_skipped", "severity": "warning", "detail": str(exc)})
        return result

    result.update({
        "total_formulas": report.get("total_formulas", 0),
        "valid": report.get("valid", 0),
        "invalid": report.get("invalid", 0),
        "score": report.get("score"),
    })
    invalid_details = [item for item in report.get("details", []) if not item.get("valid")]
    if invalid_details:
        result["warning"] = True
        for item in invalid_details[:10]:
            result["issues"].append({
                "code": "latex_formula_issue",
                "severity": "warning",
                "line": item.get("line"),
                "detail": "; ".join(str(x) for x in item.get("issues", [])) or "公式可能存在语法问题",
            })
    return result


def run_checks(
    workspace: str,
    language: str = "python",
    timeout: int = 300,
    evidence_mode: str = "standard",
    quality_mode: str = "standard",
    online_source_materials: bool = False,
) -> dict:
    root = Path(workspace)
    brief = root / "problem_brief.md"
    model_decision = root / "model_decision.md"
    code = root / ("solution.m" if language == "matlab" else "solution.py")
    results_dir = root / "results"

    required_paths = [brief, code, results_dir]
    missing = [str(path) for path in required_paths if not path.exists()]
    checks = {
        "required_files": {
            "passed": not missing,
            "missing": missing,
        }
    }

    if code.exists():
        _safe("code_runner", checks, lambda: run_code(str(code), language, timeout, str(root)))

    if results_dir.exists():
        _safe("figure_checker", checks, lambda: batch_check(str(results_dir), "*.png"))

    if model_decision.exists() and code.exists():
        def consistency_step():
            result = check_formula_consistency(str(model_decision), str(code), language)
            result.setdefault("passed", "error" not in result)
            return result
        _safe("consistency_checker", checks, consistency_step)

    if model_decision.exists():
        checks["latex_advisory"] = _latex_advisory(model_decision)

    if brief.exists() and model_decision.exists():
        _safe("brief_model", checks, lambda: validate_against_brief(str(brief), "model", str(model_decision)))
    if brief.exists() and code.exists():
        _safe("brief_code", checks, lambda: validate_against_brief(str(brief), "code", str(code)))
    if brief.exists() and results_dir.exists():
        _safe("brief_output", checks, lambda: validate_against_brief(str(brief), "output", str(results_dir)))

    _safe("evidence_checker", checks, lambda: check_evidence(str(root), evidence_mode))
    _safe("brief_completeness_checker", checks, lambda: check_brief_completeness(str(root), quality_mode))
    _safe("schema_checker", checks, lambda: check_schema(str(root), quality_mode))
    _safe("model_spec_checker", checks, lambda: check_model_spec(str(root), quality_mode))
    _safe("unit_checker", checks, lambda: check_units(str(root), quality_mode))
    _safe("model_selection_checker", checks, lambda: check_model_selection(str(root), quality_mode))
    _safe("optimization_certificate_checker", checks, lambda: check_optimization_certificate(str(root), quality_mode))
    _safe("uncertainty_budget_checker", checks, lambda: check_uncertainty_budget(str(root), quality_mode))
    _safe("validation_profile_checker", checks, lambda: check_validation_profile(str(root), quality_mode))
    _safe("data_leakage_checker", checks, lambda: check_data_leakage(str(root), quality_mode))
    _safe("statistical_validation_checker", checks, lambda: check_statistical_validation(str(root), quality_mode))
    _safe("robustness_checker", checks, lambda: check_robustness(str(root), quality_mode))
    _safe("figure_auditor", checks, lambda: audit_figures(str(root), quality_mode))
    _safe("manifest_checker", checks, lambda: check_manifest(str(root), quality_mode))
    _safe("source_registry_checker", checks, lambda: check_source_registry(str(Path(__file__).resolve().parents[1]), quality_mode))
    _safe("source_freshness_checker", checks, lambda: check_source_freshness(str(Path(__file__).resolve().parents[1]), quality_mode, online=False))
    if online_source_materials:
        _safe("source_material_reader", checks, lambda: check_source_materials(str(Path(__file__).resolve().parents[1]), quality_mode))
    _safe("award_readiness_checker", checks, lambda: check_award_readiness(str(root), quality_mode))
    _safe("case_retrieval_checker", checks, lambda: check_case_retrieval(str(root), quality_mode))
    _safe("innovation_checker", checks, lambda: check_innovations(str(root), quality_mode))
    _safe("judge_panel_checker", checks, lambda: check_judge_panel(str(root), quality_mode))
    _safe("compliance_checker", checks, lambda: check_compliance(str(root), quality_mode))
    _safe("writer_prompt_checker", checks, lambda: check_writer_prompt(str(root), quality_mode))

    passed = checks["required_files"]["passed"]
    for name, result in checks.items():
        if name == "required_files":
            continue
        if result.get("success") is False or result.get("passed") is False:
            passed = False
        if name == "figure_checker" and (result.get("total", 0) == 0 or result.get("passed_all") is False):
            passed = False

    completeness = _artifact_completeness(root, language, missing)
    warned = sorted(
        name for name, result in checks.items()
        if isinstance(result, dict) and (result.get("warning") or result.get("issues"))
    )
    if not passed:
        status = "fail"
    elif warned or completeness["recommended_missing"]:
        status = "pass_with_warnings"
    else:
        status = "pass"

    return {
        "workspace": str(root),
        "language": language,
        "evidence_mode": evidence_mode,
        "quality_mode": quality_mode,
        "online_source_materials": online_source_materials,
        "passed": passed,
        "status": status,
        "warned_checks": warned,
        "artifact_completeness": completeness,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="数学建模交付物总控验证工具")
    parser.add_argument("--workspace", required=True, help="建模工作区")
    parser.add_argument("--language", default="python", choices=["python", "matlab"])
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--evidence-mode",
        default="standard",
        choices=["standard", "strict", "hard", "complete", "full"],
        help="standard 兼容旧工作区；strict/hard/complete/full 缺证据即失败",
    )
    parser.add_argument(
        "--quality-mode",
        default="standard",
        choices=["standard", "strict", "hard", "complete", "full", "excellence"],
        help="standard 兼容旧工作区；strict/excellence 要求质量闭环产物完整",
    )
    parser.add_argument(
        "--online-source-materials",
        action="store_true",
        help="显式联网抽检竞赛资料内容；默认关闭，避免普通 CI 受外部网站波动影响。",
    )
    args = parser.parse_args()

    try:
        result = run_checks(
            args.workspace,
            args.language,
            args.timeout,
            args.evidence_mode,
            args.quality_mode,
            args.online_source_materials,
        )
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
