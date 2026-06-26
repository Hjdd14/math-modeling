#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试运行器：运行所有测试并生成汇总报告"""

import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(SKILL_DIR, "tests")


def main():
    """运行所有测试"""
    test_files = [
        "test_data_analyzer.py",
        "test_brief_validator.py",
        "test_code_runner.py",
        "test_figure_checker.py",
        "test_latex_validator.py",
        "test_consistency_checker.py",
        "test_consensus_system.py",
        "test_e2e_workflow.py",
        "test_performance.py",
        "test_skill_docs.py",
        "test_input_parser.py",
        "test_state_manager.py",
        "test_pipeline_check.py",
        "test_evidence_checker.py",
        "test_quality_tools.py",
        "test_workflow_runner.py",
        "test_eval_files.py",
        "test_matlab_support.py",
        "test_open_source_readiness.py",
        "test_doctor.py",
    ]

    results = []
    for test_file in test_files:
        print(f"\n{'='*60}")
        print(f"Running: {test_file}")
        print("="*60)
        test_path = os.path.join(TESTS_DIR, test_file)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
            capture_output=True, text=True, cwd=SKILL_DIR
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        results.append((test_file, result.returncode))

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, r in results if r == 0)
    failed = sum(1 for _, r in results if r != 0)
    print(f"Total: {len(results)} test files")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed tests:")
        for name, r in results:
            if r != 0:
                print(f"  - {name}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
