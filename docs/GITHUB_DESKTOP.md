# GitHub Desktop Setup

本仓库是标准 Git 仓库，可通过 GitHub Desktop 添加并发布。GitHub Desktop 不会自动上传，发布操作需手动点击 `Publish repository`。

## 添加到 GitHub Desktop

1. 打开 GitHub Desktop。
2. 选择 `File` -> `Add local repository...` 或 `File` -> `Clone repository...`。
3. 选择本仓库的克隆路径（例如 `~/.claude/skills/math-modeling`）。
4. 添加后确认分支为 `main`。
5. 如需上传，点击 GitHub Desktop 的 `Publish repository`。上传前建议复查 `.gitignore`。

## 上传前检查

```powershell
git status --short
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
```

## 不应上传的本地文件

这些文件/目录已被 `.gitignore` 排除：

- `audit_memory.md`：本地审查记忆
- `runs/`：本地运行工作区
- `.pytest_cache/`：测试缓存
- `__pycache__/`：Python 编译缓存
- `.codegraph/`：本地代码索引
- `.omo/`：OpenCode 运行状态
- `*.bak`：备份文件

## 仓库基础

- 默认分支：`main`
- License：MIT
- CI：`.github/workflows/ci.yml`
- Issue templates：`.github/ISSUE_TEMPLATE/`
- PR template：`.github/pull_request_template.md`
- Dependabot：`.github/dependabot.yml`
