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
        "MATLAB",
        "python -m pytest tests -q",
        "references/workflow.md",
        "正式版",
    ]
    for phrase in required_phrases:
        assert phrase in readme


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
