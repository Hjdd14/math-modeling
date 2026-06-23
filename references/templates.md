# 数学建模模板

## problem_brief.md

```markdown
# 数学建模题目简报

## 1. 题目原文

## 2. 求解目标

## 3. 已知条件与参数

## 4. 约束条件

## 5. 附件数据

## 6. 输出要求

## 7. 评分标准（如有）
```

## modeling_report.md

```markdown
# [问题标题] 数学建模报告

## 1. 问题描述

## 2. 模型假设

## 3. 符号说明

## 4. 模型建立

## 5. 模型求解

## 6. 模型验证

## 7. 模型评价
```

## Python solution.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数学建模 Python 实现"""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import pandas as pd


RESULTS_DIR = Path("results")


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def main():
    ensure_results_dir()
    # 1. 参数设置
    # 2. 数据输入
    # 3. 模型构建
    # 4. 求解计算
    # 5. 结果输出
    result = pd.DataFrame([{"item": "objective", "value": 0.0}])
    result.to_csv(RESULTS_DIR / "output.csv", index=False, encoding="utf-8-sig")
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps({"status": "ok"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 6. 可视化
    plt.figure(figsize=(6, 4), dpi=300)
    plt.plot([0, 1], [0, 1])
    plt.xlabel("x")
    plt.ylabel("value")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "result_main.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
```

## MATLAB solution.m

```matlab
%% 数学建模 MATLAB 实现
clear; clc; close all;

resultsDir = "results";
if ~exist(resultsDir, "dir")
    mkdir(resultsDir);
end

% 1. 参数设置
item = ["objective"]';
value = [0]';

% 2. 结果输出
T = table(item, value);
writetable(T, fullfile(resultsDir, "output.csv"));

% 3. 摘要输出
summaryFile = fullfile(resultsDir, "summary.json");
fid = fopen(summaryFile, "w");
fprintf(fid, '{"status":"ok"}');
fclose(fid);

% 4. 可视化
fig = figure("Visible", "off");
plot([0 1], [0 1], "LineWidth", 2);
xlabel("x");
ylabel("value");
grid on;
exportgraphics(fig, fullfile(resultsDir, "result_main.png"), "Resolution", 300);
close(fig);
```

## modeling_memory.md

```markdown
# 数学建模过程记忆文档

## 基本信息
- 当前阶段：
- 编程语言：

## Phase 0: 题目与数据提取

## Phase 1: 并行建模共识

## Phase 2/3: 并行文档与代码

## Phase 4: 并行审查与验证

## Phase 5: 归档

## 更新日志
```
