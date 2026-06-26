#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开源发布就绪度测试"""

from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (SKILL_DIR / path).read_text(encoding="utf-8")


def test_required_open_source_files_exist():
    required = [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        ".gitignore",
        "docs/RELEASE_CHECKLIST.md",
        "docs/PORTABILITY.md",
        "docs/GITHUB_DESKTOP.md",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/dependabot.yml",
        ".github/workflows/ci.yml",
    ]
    missing = [path for path in required if not (SKILL_DIR / path).exists()]
    assert missing == []


def test_readme_documents_portable_skill_usage():
    readme = read_text("README.md")
    required_phrases = [
        "math-modeling",
        "并行 Agent",
        "workflow_runner.py",
        "pipeline_check.py",
        "doctor.py",
        "evidence_checker.py",
        "validation_summary.json",
        "MATLAB",
        "python -m pytest tests -q",
        "references/workflow.md",
        "examples/quickstart",
        "正式版",
    ]
    for phrase in required_phrases:
        assert phrase in readme
    assert "input_parser.py parse" not in readme
    assert "input_parser.py brief" in readme


def test_mit_license_and_changelog_version():
    license_text = read_text("LICENSE")
    changelog = read_text("CHANGELOG.md")
    assert "MIT License" in license_text
    assert "Permission is hereby granted" in license_text
    assert "1.0.0" in changelog


def test_gitignore_excludes_local_memory_runs_and_caches():
    gitignore = read_text(".gitignore")
    for pattern in ["audit_memory.md", "runs/", "__pycache__/", ".pytest_cache/", "*.bak"]:
        assert pattern in gitignore


def test_dependency_files_cover_runtime_and_fixture_imports():
    requirements = read_text("requirements.txt")
    pyproject = read_text("pyproject.toml")
    required_packages = ["pandas", "openpyxl", "numpy", "Pillow", "matplotlib", "scipy", "pypdf", "python-docx"]
    for package in required_packages:
        assert package in requirements
    for package in ["pandas", "openpyxl", "numpy", "Pillow", "matplotlib", "scipy", "pypdf", "python-docx"]:
        assert package in pyproject


def test_public_quickstart_example_exists():
    required = [
        "examples/quickstart/README.md",
        "examples/quickstart/problem.md",
        "examples/quickstart/production_data.csv",
    ]
    missing = [path for path in required if not (SKILL_DIR / path).exists()]
    assert missing == []
    example_readme = read_text("examples/quickstart/README.md")
    assert "input_parser.py brief" in example_readme
    assert "workflow_runner.py scaffold" in example_readme
