#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模交付物总控验证工具"""

import argparse
import inspect
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
    from tools.design_board_checker import check_design_board
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
    from design_board_checker import check_design_board
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


# 决策产物硬门清单：最终的模型选择结论与模型决策文档。
# 这两项不再属于“推荐但可缺”的软清单，缺失时由 _check_decision_artifacts 判定。
DECISION_ARTIFACTS = ("final_solution.json", "model_decision.md")

# 与其它 checker（case_retrieval_checker / writer_prompt_checker 等）保持一致：
# standard 之外的严格模式缺证据一律判 error。
STRICT_MODES = {"strict", "hard", "complete", "full", "excellence"}

# 双闸门（A 框架闸门 / B 方案择定闸门）的板文件名，口径与 design_board_checker 一致。
GATE_A_FILENAME = "design_board.json"
GATE_B_FILENAME = "design_board_gate_b.json"

# --stage 取值：主仓库只有 final（整题一次交付）。
# 分支（每问一次交付）才需要 question + --board-root；主仓库保持同构的代码容错，
# 但不把 question 暴露成 CLI 取值（它不是主仓库的特性）。
STAGE_CHOICES = ("final",)
DEFAULT_STAGE = "final"
KNOWN_STAGES = ("final", "question")

# Phase 5 固定产物清单，取自 references/workflow.md 的归档要求。
# 仅用于生成 artifact_completeness 提示，不参与 passed 判定：
# standard 模式必须保持对旧工作区的兼容（warning-only）。
# 注意：final_solution.json 与 model_decision.md 已升为硬门，见 DECISION_ARTIFACTS。
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
    "design_board.json",
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


def _check_decision_artifacts(root: Path, quality_mode: str) -> dict:
    """决策产物硬门：final_solution.json 与 model_decision.md 必须存在。

    standard 模式只 warning（保持旧工作区兼容），excellence/strict 家族判 error。
    """
    mode = (quality_mode or "standard").lower()
    strict = mode in STRICT_MODES
    severity = "error" if strict else "warning"
    issues: list[dict] = []
    missing: list[str] = []

    for name in DECISION_ARTIFACTS:
        if (root / name).exists():
            continue
        missing.append(name)
        if strict:
            message = f"缺少 {name}；excellence/strict 家族要求决策产物齐备，否则模型选择结论无法复核。"
        else:
            message = f"缺少 {name}；standard 模式仅作提示，旧工作区仍可通过。"
        issues.append(
            {
                "code": "missing_decision_artifact",
                "severity": severity,
                "message": message,
                "file": name,
            }
        )

    return {
        "workspace": str(root),
        "mode": mode,
        "passed": not any(issue["severity"] == "error" for issue in issues),
        "warning": any(issue["severity"] == "warning" for issue in issues),
        "checks": [
            {
                "name": "decision_artifacts",
                "passed": not missing,
                "missing": missing,
            }
        ],
        "issues": issues,
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


# ---------------------------------------------------------------------------
# 双闸门（A 框架闸门 / B 方案择定闸门）
# ---------------------------------------------------------------------------


def _read_board_payload(path: Path) -> tuple[dict | None, str | None]:
    """读板文件；缺失或非法都返回 (None, 原因)，不抛异常。"""
    if not path.is_file():
        return None, f"缺少 {path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - 统一转成结构化 issue
        return None, f"{path.name} 不是合法 JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path.name} 顶层必须是 JSON 对象"
    return payload, None


def _board_schema_version(payload: dict) -> int:
    """读板结构版本；缺失或非法按 1（legacy）处理，与 design_board_checker 同口径。"""
    version = payload.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    return 1


def _board_confirmed(payload: dict) -> bool:
    """顶层 confirmed 为 true，或 questions[] 逐条 confirmed 全为 true，都算已确认。"""
    if payload.get("confirmed") is True:
        return True
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return False
    return all(
        isinstance(item, dict) and item.get("confirmed") is True for item in questions
    )


def _choices_complete(payload: dict) -> tuple[bool, list[str]]:
    """B 板每一问都必须有非空 user_choice，否则该问还没真的选定方案。"""
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return False, []
    missing: list[str] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            missing.append(f"questions[{index}]")
            continue
        choice = question.get("user_choice")
        if not isinstance(choice, str) or not choice.strip():
            missing.append(str(question.get("id") or f"questions[{index}]"))
    return not missing, missing


def _two_gate_stage(root: Path, quality_mode: str, stage: str = DEFAULT_STAGE) -> dict:
    """双闸门总控：**只判跨板的硬门槛**，板内规则交给 design_board_checker。

    分工（这条边界必须守住，两处各写一套同一规则必然会漂移）：

    * A 板自身（范式集合、候选、时间线、回执来源……）→ ``check_design_board(gate="a")``；
    * B 板自身（候选 5–8、恰好 1 个推荐、打分、advice 与 trials 的数值回溯……）
      → ``check_design_board(gate="b")``；
    * 本函数只回答一个问题：**A 板声明的新流程，B 板到位了没有。**

    硬规则（契约 §2.3 / §8.5）：

    * A 板 ``schema_version >= 2`` → B 板必须存在、已确认、每题都有 ``user_choice``，
      缺一样都是 **error**（与 quality_mode 无关：A 板自己声明了新流程）；
    * legacy A 板（``schema_version < 2``）缺 B 板 → **warning**，旧工作区照常通过；
    * A 板缺失不在这里报：``design_board_checker`` 的 gate a 已经给了可读的失败码。

    主仓库是整题一次交付，``stage`` 只有 final 有实际语义；question 仅为与分支 CLI
    同构而在函数签名里容错，不改变这里的判定范围。
    """
    normalized_mode = (quality_mode or "standard").lower()
    stage = (stage or DEFAULT_STAGE).lower()
    if stage not in KNOWN_STAGES:
        stage = DEFAULT_STAGE
    strict = normalized_mode in STRICT_MODES

    a_path = root / GATE_A_FILENAME
    b_path = root / GATE_B_FILENAME
    a_payload, a_error = _read_board_payload(a_path)
    b_payload, b_error = _read_board_payload(b_path)

    schema = _board_schema_version(a_payload) if a_payload is not None else None
    new_flow = schema is not None and schema >= 2
    a_confirmed = bool(a_payload) and _board_confirmed(a_payload)
    b_confirmed = bool(b_payload) and _board_confirmed(b_payload)
    choices_ok, missing_choices = _choices_complete(b_payload) if b_payload else (False, [])

    issues: list[dict] = []
    checks: list[dict] = []

    if a_payload is None:
        checks.append(
            {
                "name": "gate_a_board",
                "passed": False,
                "skipped": True,
                "reason": a_error,
                "note": "A 板缺失由 design_board_checker(--gate a) 报失败；这里不重复报码。",
            }
        )
    else:
        checks.append(
            {
                "name": "gate_a_board",
                "passed": a_confirmed,
                "schema_version": schema,
                "new_flow": new_flow,
                "confirmed": a_confirmed,
            }
        )

    if b_path.is_file() and b_payload is None:
        issues.append(
            {
                "code": "invalid_gate_b_board",
                "severity": "error" if new_flow else "warning",
                "message": f"B 板无法解析（{b_error}）；B 闸门必须先能读出板才谈得上确认。",
                "file": GATE_B_FILENAME,
            }
        )
    elif b_payload is None:
        if new_flow:
            issues.append(
                {
                    "code": "missing_gate_b_board",
                    "severity": "error",
                    "message": (
                        f"A 板 schema_version={schema} 已是双闸门流程，但缺少 {GATE_B_FILENAME}；"
                        "B 闸门（方案择定）确认前不得进入 Phase 2/3，尤其不得写交付代码。"
                        "走完 B 板：python tools/design_board.py render --gate b → "
                        "serve --gate b → ingest --gate b → confirm --gate b --apply。"
                    ),
                    "file": GATE_B_FILENAME,
                }
            )
        else:
            issues.append(
                {
                    "code": "gate_b_missing_legacy_workspace",
                    "severity": "warning",
                    "message": (
                        "A 板是 legacy 板（schema_version < 2）且没有 B 板：按旧工作区放行（只警告）。"
                        "建议补做 B 闸门，标记 legacy_gate_a_only 并走 confirm --gate b 后再继续写码。"
                    ),
                    "file": GATE_B_FILENAME,
                }
            )
    else:
        severity = "error" if new_flow else "warning"
        if not b_confirmed:
            issues.append(
                {
                    "code": "gate_b_not_confirmed",
                    "severity": severity,
                    "message": (
                        f"{GATE_B_FILENAME} 尚未确认（顶层 confirmed 或 questions[] 逐条 confirmed "
                        "必须为 true）；确认必须由用户本人在真实终端输入 B 板确认码。"
                    ),
                    "file": GATE_B_FILENAME,
                }
            )
        if not choices_ok:
            issues.append(
                {
                    "code": "gate_b_choice_missing",
                    "severity": severity,
                    "message": (
                        "B 板还没有为全部小问选定方案（user_choice 为空）："
                        "B 闸门的语义就是「每一问都有人拍板」，空选择等于没走闸门。"
                    ),
                    "file": GATE_B_FILENAME,
                    "questions": missing_choices,
                }
            )

    if b_payload is not None:
        checks.append(
            {
                "name": "gate_b_board",
                "passed": b_confirmed and choices_ok,
                "confirmed": b_confirmed,
                "choices_complete": choices_ok,
                "missing_choices": missing_choices,
                "questions": len(b_payload.get("questions") or []),
            }
        )
    else:
        checks.append(
            {
                "name": "gate_b_board",
                "passed": False,
                "present": b_path.is_file(),
                "note": "B 板缺失的判定已在上面的 issues 里给出。",
            }
        )

    return {
        "workspace": str(root),
        "mode": normalized_mode,
        "stage": stage,
        "passed": not any(issue["severity"] == "error" for issue in issues),
        "warning": any(issue["severity"] == "warning" for issue in issues),
        "strict": strict,
        "gate_a": {
            "path": str(a_path),
            "present": a_payload is not None,
            "schema_version": schema,
            "new_flow": new_flow,
            "confirmed": a_confirmed,
        },
        "gate_b": {
            "path": str(b_path),
            "present": b_payload is not None,
            "confirmed": b_confirmed,
            "choices_complete": choices_ok,
            "questions": len(b_payload.get("questions") or []) if b_payload else 0,
            "missing_choices": missing_choices,
        },
        "checks": checks,
        "issues": issues,
    }


def _checker_parameters() -> set[str]:
    """取 design_board_checker.check_design_board 的参数名，用于探测 --gate 支持。"""
    try:
        return set(inspect.signature(check_design_board).parameters)
    except (TypeError, ValueError):  # pragma: no cover - 防御性分支
        return set()


def _design_board_gate_a(root: Path, quality_mode: str) -> dict:
    """A 闸门（框架与探索边界）校验：直接委托 checker 的 gate="a"。"""
    return check_design_board(str(root), quality_mode)


def _design_board_gate_b(root: Path, quality_mode: str, stage: str = DEFAULT_STAGE) -> dict:
    """B 闸门（方案择定）校验：委托 checker 的 gate="b"。

    * B 板不在场时不在这里报错：缺板 + "已存在交付代码"的硬规则由
      ``_two_gate_stage`` 统一给出，避免同一件事出现两条互相覆盖的 error；
    * B 板在场时全量跑 B 组检查——候选 5–8、恰好 1 个推荐、打分完整性、
      pros/cons、why_not+when_better、data_comparison 回溯、advice 与 trials 的
      数值一致性（1e-9）、executed_by=tool 等，全部在 checker 内部完成。
    """
    stage = (stage or DEFAULT_STAGE).lower()
    if stage not in KNOWN_STAGES:
        stage = DEFAULT_STAGE
    board = root / GATE_B_FILENAME
    if not board.is_file():
        return {
            "workspace": str(root),
            "mode": quality_mode,
            "gate": "b",
            "stage": stage,
            "passed": True,
            "warning": False,
            "skipped": True,
            "reason": "missing_gate_b_board",
            "note": "B 板缺失的判定见 two_gate_stage；B 板在场时这里跑 B 组全量检查。",
            "issues": [],
        }
    if "gate" not in _checker_parameters():
        return {
            "workspace": str(root),
            "mode": quality_mode,
            "gate": "b",
            "stage": stage,
            "passed": True,
            "warning": False,
            "skipped": True,
            "reason": "checker_without_gate_support",
            "note": "当前 design_board_checker 不认识 gate 参数，B 组检查未执行。",
            "issues": [],
        }
    return check_design_board(str(root), quality_mode, gate="b")


def run_checks(
    workspace: str,
    language: str = "python",
    timeout: int = 300,
    evidence_mode: str = "standard",
    quality_mode: str = "standard",
    online_source_materials: bool = False,
    stage: str = DEFAULT_STAGE,
) -> dict:
    root = Path(workspace)
    stage = (stage or DEFAULT_STAGE).lower()
    if stage not in KNOWN_STAGES:
        stage = DEFAULT_STAGE
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
    # 双闸门：A 板（框架）与 B 板（方案择定）各自全量校验，跨板硬门槛由 two_gate_stage 判。
    _safe("design_board_checker", checks, lambda: _design_board_gate_a(root, quality_mode))
    _safe("design_board_gate_b", checks, lambda: _design_board_gate_b(root, quality_mode, stage))
    _safe("two_gate_stage", checks, lambda: _two_gate_stage(root, quality_mode, stage))
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
    # 决策产物硬门：与 award_readiness 同属“交付结论可复核”这一组，缺失即失败（strict 家族）。
    _safe("decision_artifacts", checks, lambda: _check_decision_artifacts(root, quality_mode))
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
        "stage": stage,
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
    parser.add_argument(
        "--stage",
        default=DEFAULT_STAGE,
        choices=list(STAGE_CHOICES),
        help=(
            "final=整题一次交付的终验（主仓库唯一的语义）：A 板 schema v2 时必须有已确认的 "
            "B 板，B 板在场时跑 B 组全量检查。按小问交付的 --stage question 属于分支特性，"
            "主仓库不提供。"
        ),
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
            args.stage,
        )
        output(result)
        sys.exit(0 if result["passed"] else 1)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
