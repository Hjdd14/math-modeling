#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""solution_tests.py 生成工具"""

import argparse
import json
import sys
from pathlib import Path


PYTHON_TEST_TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 solution_test_generator.py 生成的建模代码契约测试"""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_solution_script_exists():
    assert (ROOT / "solution.py").exists()


def test_required_outputs_exist():
    required = [
        "results/output.csv",
        "results/summary.json",
        "results/validation_summary.json",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert missing == []


def test_validation_summary_contains_required_sections():
    data = load_json("results/validation_summary.json")
    required = [
        "baseline_comparison",
        "oracle_tests",
        "solver_cross_checks",
        "sensitivity_analysis",
        "invariants",
        "failure_modes",
        "constraint_residuals",
        "optimality_gap",
        "multi_start",
        "random_seed_stability",
        "bootstrap_confidence_interval",
        "perturbation_stability",
    ]
    missing = [key for key in required if key not in data]
    assert missing == []


def test_constraint_invariants_pass():
    data = load_json("results/validation_summary.json")
    invariants = data.get("invariants", [])
    assert invariants, "validation_summary.json must record constraint invariants"
    failed = [item for item in invariants if isinstance(item, dict) and item.get("passed") is False]
    assert failed == []


def test_oracle_checks_pass():
    data = load_json("results/validation_summary.json")
    oracle_tests = data.get("oracle_tests", data.get("known_case_tests", []))
    assert oracle_tests, "small-scale oracle or known-case tests are required"
    failed = [item for item in oracle_tests if isinstance(item, dict) and item.get("passed") is False]
    assert failed == []


def test_baseline_not_worse_than_required_threshold():
    data = load_json("results/validation_summary.json")
    baseline = data.get("baseline_comparison", {})
    assert baseline, "baseline comparison is required"
    assert baseline.get("passed") is True
    if "baseline_value" in baseline and "model_value" in baseline:
        tolerance = float(baseline.get("tolerance", 0))
        higher_is_better = baseline.get("higher_is_better", True)
        if higher_is_better:
            assert float(baseline["model_value"]) + tolerance >= float(baseline["baseline_value"])
        else:
            assert float(baseline["model_value"]) <= float(baseline["baseline_value"]) + tolerance


def test_random_seed_stability_recorded():
    data = load_json("results/validation_summary.json")
    stability = data.get("random_seed_stability", {})
    assert stability, "random seed stability evidence is required"
    seeds = stability.get("seeds", [])
    assert isinstance(seeds, list) and len(seeds) >= 3
    assert stability.get("passed") is not False


def test_multi_start_runs_recorded():
    data = load_json("results/validation_summary.json")
    multi_start = data.get("multi_start", {})
    assert multi_start, "multi-start evidence is required"
    runs = int(multi_start.get("runs", 0))
    assert runs >= 3
    assert multi_start.get("passed") is not False


def test_bootstrap_confidence_level_recorded():
    data = load_json("results/validation_summary.json")
    interval = data.get("bootstrap_confidence_interval", {})
    assert interval, "bootstrap confidence interval evidence is required"
    level = float(interval.get("level", 0))
    assert level >= 0.95
    assert float(interval.get("lower", 0)) <= float(interval.get("upper", 0))
    assert interval.get("passed") is not False


def test_model_spec_exists_and_has_core_sections():
    spec_path = ROOT / "model_spec.json"
    assert spec_path.exists()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for key in ["variables", "objective", "constraints", "parameters", "data_fields", "validation_plan"]:
        assert key in spec


def test_solution_runs_without_error():
    result = subprocess.run(
        [sys.executable, str(ROOT / "solution.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
'''


MATLAB_TEST_TEMPLATE = '''% 由 solution_test_generator.py 生成的 MATLAB 检查清单
% 在 MATLAB 中运行 solution.m 后确认:
% 1. results/output.csv 存在
% 2. results/summary.json 存在
% 3. results/validation_summary.json 包含 baseline、oracle、交叉验证、敏感性与鲁棒性字段
% 4. 随机种子稳定性至少 3 个 seeds，多初值至少 3 次，bootstrap 置信水平至少 0.95
% 5. model_spec.json 与 symbol_table.json 已同步
'''


def output(result: dict):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def error(message: str, code: int = 1):
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def generate_solution_tests(workspace: str, language: str = "python", out: str | None = None) -> dict:
    root = Path(workspace)
    if language not in {"python", "matlab"}:
        raise ValueError("language 必须是 python 或 matlab")
    out_path = Path(out) if out else root / ("solution_tests.py" if language == "python" else "solution_tests.m")
    if not out_path.is_absolute():
        out_path = root / out_path
    template = PYTHON_TEST_TEMPLATE if language == "python" else MATLAB_TEST_TEMPLATE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template, encoding="utf-8")
    return {
        "workspace": str(root),
        "language": language,
        "path": str(out_path),
        "passed": True,
        "generated": True,
    }


def main():
    parser = argparse.ArgumentParser(description="生成 solution_tests.py / solution_tests.m 契约测试")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--language", default="python", choices=["python", "matlab"])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    try:
        result = generate_solution_tests(args.workspace, args.language, args.out)
        output(result)
    except Exception as exc:
        error(str(exc))


if __name__ == "__main__":
    main()
