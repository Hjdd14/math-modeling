#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威竞赛资料库与案例检索检查测试"""

import json
import re
import shutil
from pathlib import Path

from tools import case_retrieval_checker
from tools import source_registry_checker
from tools import writer_prompt_checker


SKILL_DIR = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_case_retrieval(source_competition: str, problem_type: str) -> dict:
    return {
        "problem_domain": problem_type,
        "matched_problem_types": [problem_type, "优化调度"],
        "matched_cases": [
            {
                "rank": 1,
                "source_competition": source_competition,
                "year": "2024",
                "problem_id": "A",
                "problem_type": problem_type,
                "similarity_reason": "题目领域、数据结构和约束形式相近。",
                "borrowable_methods": ["baseline 对照", "约束可行性检查"],
                "cannot_copy_risks": ["公开案例只能提炼方法结构，不能照搬模型或结论。"],
                "validation_needed": ["小例 oracle", "敏感性分析"],
            }
        ],
        "candidate_methods": ["baseline", "robustness_check"],
        "cannot_copy_risks": ["数据口径不同会导致模型不匹配。"],
    }


def test_competition_source_registry_has_authoritative_tiers_and_required_fields():
    registry = read_json(SKILL_DIR / "references" / "competition_sources.json")
    tiers = registry["tiers"]

    assert len(tiers["tier_a"]) >= 7
    assert len(tiers["tier_b"]) >= 7

    tier_a_names = "\n".join(item["name"] for item in tiers["tier_a"])
    for keyword in ["高教社杯", "研究生", "统计建模", "MathorCup", "电工", "深圳杯", "COMAP"]:
        assert keyword in tier_a_names

    tier_b_names = "\n".join(item["name"] for item in tiers["tier_b"])
    for keyword in ["APMCM", "五一", "认证杯", "华中杯", "中青杯", "华数杯", "数维杯"]:
        assert keyword in tier_b_names

    required_fields = {
        "name",
        "tier",
        "organizer",
        "official_url",
        "years_covered",
        "case_material_type",
        "trust_notes",
    }
    for tier_name, sources in tiers.items():
        assert isinstance(sources, list), tier_name
        for source in sources:
            assert required_fields <= set(source), source.get("name")
            assert source["tier"] == tier_name
            assert str(source["official_url"]).startswith("http")
            assert source["years_covered"]
            assert source["case_material_type"]
            assert source["trust_notes"]


def test_award_playbook_contains_ten_problem_types_and_forty_sourced_method_cards():
    playbook = (SKILL_DIR / "references" / "award_playbook.md").read_text(encoding="utf-8")
    required_problem_types = [
        "优化调度",
        "预测统计",
        "图网络",
        "随机仿真",
        "物理机理",
        "电力电工",
        "统计调查",
        "多目标鲁棒",
        "机器学习混合",
        "政策决策",
    ]
    for problem_type in required_problem_types:
        assert f"### {problem_type}" in playbook

    cards = re.findall(r"^#### 方法卡\s+.+?(?=^#### 方法卡\s+|^### |\Z)", playbook, flags=re.M | re.S)
    assert len(cards) >= 40

    required_labels = ["来源比赛", "年份", "题号", "适用条件", "误用风险", "推荐验证", "来源链接"]
    for card in cards:
        for label in required_labels:
            assert f"- {label}：" in card or f"- {label}:" in card


def test_source_registry_checker_passes_repository_and_rejects_unsourced_method_card(tmp_path):
    result = source_registry_checker.check_source_registry(str(SKILL_DIR), mode="excellence")

    assert result["passed"] is True
    assert result["tier_counts"]["tier_a"] >= 7
    assert result["tier_counts"]["tier_b"] >= 7
    assert result["method_cards_checked"] >= 40

    shutil.copytree(SKILL_DIR / "references", tmp_path / "references")
    playbook = tmp_path / "references" / "award_playbook.md"
    playbook.write_text(
        playbook.read_text(encoding="utf-8")
        + "\n\n#### 方法卡 TEST-无来源\n"
        + "- 来源比赛：未知比赛\n"
        + "- 年份：2024\n"
        + "- 题号：A\n"
        + "- 适用条件：临时测试。\n"
        + "- 误用风险：无来源链接。\n"
        + "- 推荐验证：baseline。\n",
        encoding="utf-8",
    )

    bad = source_registry_checker.check_source_registry(str(tmp_path), mode="excellence")

    assert bad["passed"] is False
    assert any(issue["code"] == "unsourced_method_card" for issue in bad["issues"])


def test_source_registry_avoids_known_dead_or_tls_incompatible_urls():
    registry_text = (SKILL_DIR / "references" / "competition_sources.json").read_text(encoding="utf-8")
    playbook_text = (SKILL_DIR / "references" / "award_playbook.md").read_text(encoding="utf-8")
    combined = registry_text + "\n" + playbook_text

    for bad_url in [
        "https://tjjmds.ai-learning.net/",
        "https://tjjmds.ai-learning.net/dstz/37047.jhtml",
        "https://mcm.tzmcm.cn/index.html",
        "https://www.tzmcm.cn/index.html",
        "https://www.madio.net/forum-168-1.html",
        "https://www.cycmcm.com/",
        "https://www.nmmcm.org.cn/match_detail/38",
    ]:
        assert bad_url not in combined

    for reachable_url in [
        "http://tjjmds.ai-learning.net/",
        "http://tjjmds.ai-learning.net/dstz/37047.jhtml",
        "http://mcm.tzmcm.cn/index.html",
        "http://www.tzmcm.cn/index.html",
        "http://www.cycmcm.com/",
        "https://www.saikr.com/vse/57752",
    ]:
        assert reachable_url in combined


def test_case_retrieval_checker_accepts_electrical_source_match(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        "题目涉及电力系统、输电网络、电路约束和负荷预测，需要优化调度。",
        encoding="utf-8",
    )
    write_json(
        tmp_path / "case_retrieval.json",
        valid_case_retrieval("中国电机工程学会杯全国大学生电工数学建模竞赛", "电力电工"),
    )

    result = case_retrieval_checker.check_case_retrieval(str(tmp_path), mode="excellence")

    assert result["passed"] is True
    assert result["top_match"]["source_competition"].startswith("中国电机工程学会杯")


def test_case_retrieval_checker_rejects_electrical_problem_without_power_source(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        "题目涉及电网潮流、电磁场、电机控制和负荷调度。",
        encoding="utf-8",
    )
    write_json(
        tmp_path / "case_retrieval.json",
        valid_case_retrieval("COMAP MCM/ICM", "图网络"),
    )

    result = case_retrieval_checker.check_case_retrieval(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "domain_source_mismatch" for issue in result["issues"])


def test_case_retrieval_checker_rejects_survey_problem_without_statistics_source(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        "题目包含问卷调查、抽样设计、社会经济指标、统计推断和置信区间。",
        encoding="utf-8",
    )
    write_json(
        tmp_path / "case_retrieval.json",
        valid_case_retrieval("MathorCup 数学应用挑战赛", "机器学习混合"),
    )

    result = case_retrieval_checker.check_case_retrieval(str(tmp_path), mode="excellence")

    assert result["passed"] is False
    assert any(issue["code"] == "domain_source_mismatch" for issue in result["issues"])


def test_case_retrieval_checker_requires_mathorcup_for_big_data_problem(tmp_path):
    (tmp_path / "problem_brief.md").write_text(
        "题目包含平台用户行为日志、商品画像、行业大数据和业务指标预测。",
        encoding="utf-8",
    )
    write_json(
        tmp_path / "case_retrieval.json",
        valid_case_retrieval("COMAP MCM/ICM", "预测统计"),
    )

    bad = case_retrieval_checker.check_case_retrieval(str(tmp_path), mode="excellence")

    assert bad["passed"] is False
    assert any(issue["code"] == "domain_source_mismatch" for issue in bad["issues"])

    write_json(
        tmp_path / "case_retrieval.json",
        valid_case_retrieval("MathorCup 数学应用挑战赛及大数据竞赛", "机器学习混合"),
    )

    good = case_retrieval_checker.check_case_retrieval(str(tmp_path), mode="excellence")

    assert good["passed"] is True


def test_writer_prompt_checker_requires_handoff_not_formal_body(tmp_path):
    prompt = """
# 写作交接提示词

本 skill 不生成正式写作正文，只提供写作交接材料。

## 题目与评分
- problem_brief.md

## 模型主线
- final_solution.json

## 代码与结果
- results/validation_summary.json

## 图表证据
- figure_storyboard.md

## 验证证据
- judge_panel_review.json
- reproducibility_manifest.json

## 合规与风险
- compliance_record.json
- 风险提示与合规提示

## 后续写作/提交复核清单
- 匿名复核
- 引用复核
- AI 披露复核
- 页数复核
- 附件复核
- 代码复核
""".strip()
    (tmp_path / "writer_prompt.md").write_text(prompt, encoding="utf-8")

    result = writer_prompt_checker.check_writer_prompt(str(tmp_path), mode="excellence")

    assert result["passed"] is True

    (tmp_path / "writer_prompt.md").write_text("# 正文\n请直接写完整论文。", encoding="utf-8")
    bad = writer_prompt_checker.check_writer_prompt(str(tmp_path), mode="excellence")

    assert bad["passed"] is False
    assert any(issue["code"] == "writer_prompt_missing_boundary" for issue in bad["issues"])
