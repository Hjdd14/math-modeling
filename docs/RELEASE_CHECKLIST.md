# Release Checklist

发布到 GitHub 前逐项确认：

## 仓库文件

- [ ] `README.md` 描述正式版状态、安装、快速开始、并行 Agent 要求和验证命令。
- [ ] `LICENSE` 为 MIT License。
- [ ] `CHANGELOG.md` 有当前版本条目。
- [ ] `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md` 已存在。
- [ ] `.gitignore` 排除 `audit_memory.md`、`runs/`、缓存和备份文件。
- [ ] `.github/workflows/ci.yml` 能在 GitHub Actions 运行快速验证。
- [ ] `.github/ISSUE_TEMPLATE/`、`.github/pull_request_template.md` 和 `.github/dependabot.yml` 已存在。
- [ ] `docs/GITHUB_DESKTOP.md` 说明如何添加本地仓库但不上传。

## Skill 完整性

- [ ] `SKILL.md` 是短主入口，并明确要求读取 `references/workflow.md`。
- [ ] Phase 1 只生成 `final_solution.json` 和 `model_decision.md`。
- [ ] Phase 2 只生成 `writer_prompt.md` 等写作交接提示词，不生成正式写作正文。
- [ ] Phase 1、Phase 2/3、Phase 4 的并行 Agent gate 没有被 CLI 降级或替代。
- [ ] Phase 0 题意审计、Phase 1 baseline/动态专家、Phase 3 `validation_summary.json`、Phase 4 独立复现和 evidence check 均已记录。
- [ ] 权威资料库已记录：`references/competition_sources.json`、`references/award_playbook.md`、`tools/source_registry_checker.py`、`tools/source_freshness_checker.py`、`tools/source_material_reader.py` 和 `tools/case_retrieval_checker.py`。
- [ ] 奖项级交付产物已记录：`ambiguity_register.json`、`assumption_ledger.md`、`scoring_strategy.md`、`ablation_study.json`、`decision_insights.md`、`defense_questions.md`、`case_retrieval.json`、`model_selection_audit.json`、`optimization_certificate.json`、`uncertainty_budget.json`、`validation_profile.json`、`data_validation.json`、`statistical_validation.json`、`model_spec.json`、`data_schema.json`、`symbol_table.json`、`solver_strategy.json`、`solution_tests.py`、`figure_style.json`、`figure_storyboard.md`、`writer_prompt.md`、`innovation_register.json`、`judge_panel_review.json`、`compliance_record.json` 和 `reproducibility_manifest.json`。
- [ ] 问题拆解与评分策略 Agent、可视化设计 Agent、竞赛论文表现力 Agent、结果解释 Agent 和评委质询 Agent 没有被工具脚本替代。
- [ ] MATLAB 支持等级、模板、夹具和测试说明完整。

## 工具验证

```powershell
python tools/doctor.py --workspace .
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
python tools/pipeline_check.py --workspace tests/test_data --language python
python tools/pipeline_check.py --workspace tests/test_data --language python --evidence-mode strict
python tools/pipeline_check.py --workspace tests/test_data --language python --evidence-mode strict --quality-mode excellence
python tools/pipeline_check.py --workspace tests/test_data --language python --evidence-mode strict --quality-mode excellence --online-source-materials
python tools/source_registry_checker.py --skill-root . --mode excellence
python tools/source_freshness_checker.py --workspace . --mode excellence
python tools/source_material_reader.py --skill-root . --mode excellence --sample-documents 2
python tools/award_readiness_checker.py --workspace tests/test_data --mode excellence
python tools/case_retrieval_checker.py --workspace tests/test_data --mode excellence
python tools/writer_prompt_checker.py --workspace tests/test_data --mode excellence
python tools/mini_benchmark_checker.py --benchmark evals/mini_contest_benchmark.json --mode strict
python tools/mini_benchmark_runner.py --benchmark evals/mini_contest_benchmark.json --mode strict
python tools/workflow_runner.py resume --workspace tests/test_data --language python
Get-ChildItem workflows -Filter *.js | ForEach-Object { node --check $_.FullName }
```

可选：

```powershell
$env:RUN_MATLAB_TESTS = "1"; python -m pytest tests/test_matlab_support.py -q
```

说明：普通 CI 只运行离线 `source_freshness_checker.py`，不把联网 `source_material_reader.py` 作为 PR 硬门槛；发布前或人工复核前再运行联网深扫，避免外部网站临时故障造成误报。

## 发布前清理

- [ ] 不上传 `audit_memory.md`。
- [ ] 不上传 `runs/` 中的本地演示工作区。
- [ ] 不上传 `.pytest_cache/`、`__pycache__/` 或 `*.pyc`。
- [ ] 不上传含真实个人信息、未公开竞赛资料或商业数据的附件。
- [ ] 若包含示例，确保示例为合成数据或已获许可数据。
- [ ] `examples/quickstart/` 可生成 `problem_brief.md`。
- [ ] `examples/solved-python/` 不包含真实竞赛或个人数据，并能作为理想产物结构参考。

## 版本标记

- [ ] `CHANGELOG.md` 已更新。
- [ ] README 中版本和发布状态一致。
- [ ] Git tag 使用 `v1.0.0` 这样的语义化版本。
