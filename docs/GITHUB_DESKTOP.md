# GitHub Desktop Setup

这个目录已经是本地 Git 仓库，可以直接添加到 GitHub Desktop。当前操作不会上传，也没有配置 remote。

## 添加到 GitHub Desktop

1. 打开 GitHub Desktop。
2. 选择 `File` -> `Add local repository...`。
3. 选择目录：

```text
C:\Users\PC\.claude\skills\math-modeling
```

4. 添加后确认分支为 `main`。
5. 如需上传，再手动点击 GitHub Desktop 的 `Publish repository`。上传前建议复查 `.gitignore`。

## 上传前检查

```powershell
git status --short
python -m compileall tools
python -m pytest tests -q
python tests/run_all_tests.py
```

## 不建议上传的本地文件

这些文件/目录已被 `.gitignore` 排除：

- `audit_memory.md`
- `runs/`
- `.pytest_cache/`
- `__pycache__/`
- `*.bak`

## 当前仓库基础

- 默认分支：`main`
- License：MIT
- CI：`.github/workflows/ci.yml`
- Issue templates：`.github/ISSUE_TEMPLATE/`
- PR template：`.github/pull_request_template.md`
- Dependabot：`.github/dependabot.yml`
