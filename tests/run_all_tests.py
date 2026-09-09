#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试运行器：运行所有测试并生成汇总报告"""

import glob
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(SKILL_DIR, "tests")


def discover_test_files():
    """按 glob 发现测试文件。

    此前这里是一份手工维护的 25 条清单，没有任何测试守护它与实际文件同步，
    新增 test_*.py 会被本编排器静默跳过。改为 glob 后不可能漏测。
    """
    paths = sorted(glob.glob(os.path.join(TESTS_DIR, "test_*.py")))
    return [os.path.basename(path) for path in paths]


def main():
    """运行所有测试"""
    test_files = discover_test_files()
    if not test_files:
        print(f"No test files discovered under {TESTS_DIR}", file=sys.stderr)
        sys.exit(1)
    print(f"Discovered {len(test_files)} test files under tests/")

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
