#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建模方案决策板 HTML 视图渲染：单文件、零外链、可离线打开。

`design_board.json` 是唯一真实来源，本模块只负责把它渲染成分发给用户看、可打印的
**单文件 HTML**。渲染是纯函数：同一份 board（且 `rendered_at` 固定）得到逐字节相同的
输出，不写任何文件、不访问网络。

零外链约定（硬性）
------------------
1. 不引用任何外部资源：没有 `<link>`、没有 `<script src>`、没有 `@import`、没有外部
   字体；字体栈只用系统字体，图标用 Unicode 字符或内联 SVG。
2. :func:`render_html` 返回前会用自己的输出做一次体检：

   - 命中 :data:`FORBIDDEN_EXTERNAL` 任一片段 → ``ValueError``（列出命中片段附近文本）；
   - ``<style>`` 块里出现 ``@import`` / ``url(`` → ``ValueError``；
   - 输出超过 :data:`MAX_INLINE_BYTES` → ``ValueError``（说明内联了不该内联的东西）。

3. 为了让"来源备注/候选名里带 URL"的板也能正常渲染，:func:`_e` 会把用户文本里的
   ``http://`` / ``https://`` / ``//cdn`` 的冒号、斜杠写成 HTML 实体（``&#58;`` /
   ``&#47;``）：浏览器里显示仍是原样的 URL，源码中不再含可触发外链的前缀。静态资源
   同样零外链，所以这层"打码"只影响源码字面，不影响可读性。

导图
----
`mindmap.source` 是 mermaid ``graph LR`` / ``graph TD`` 源码。本模块自带一个极简解析器
加分层 BFS 布局，直接产出内联 SVG（圆角矩形节点 + 正交折线箭头 + 纯 CSS 淡入动画），
**不依赖 mermaid 的 JS**。解析失败时退化成 ``<pre>`` 原样展示源码，绝不抛异常。

自测方式见仓库 ``.tmp_html_test/`` 下的临时脚本（不入库）。
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# 模块级常量：自检口径 + 文案
# ---------------------------------------------------------------------------

#: 自检用：单文件 HTML 超过这个字节数，说明内联了不该内联的东西（图片 base64、脚本等）。
MAX_INLINE_BYTES = 400_000

#: 零外链自检：输出里出现任一片段即判失败。
FORBIDDEN_EXTERNAL = ("http://", "https://", "//cdn", "<link", "<script src")

#: CSS 自检：``<style>`` 块里出现即判失败（外部资源 / 内嵌资源引用）。
FORBIDDEN_CSS = ("@import", "url(")

#: 磁盘 HTML 里的提交 token 占位符；`serve` 每次请求替换成一次性真 token。
#: 直接双击打开文件时它保持字面量，所以离线页面无法通过服务端校验——这是有意的。
SUBMIT_TOKEN_TEXT = "__MM_SUBMIT_TOKEN__"

#: 页脚免责声明（逐字保留，避免视图被当成唯一真实来源）。
FOOTER_TEXT = (
    "本文件由 design_board.json 渲染生成，不是唯一真实来源。"
    "修改请改 JSON 或 xlsx 后重新渲染。"
)

#: 用户文本里需要"打码"成 HTML 实体的外链前缀，避免触发零外链自检。
_DEFANG_PAIRS: tuple[tuple[str, str], ...] = (
    ("https://", "https&#58;//"),
    ("http://", "http&#58;//"),
    ("//cdn", "&#47;/cdn"),
)

#: 推荐度 → 徽章文案 / 徽章配色 / 导图节点配色。
TIER_LABELS: dict[str, str] = {
    "recommended": "推荐",
    "alternative": "备选",
    "backup": "备选",
    "rejected": "不推荐",
    "excluded": "不推荐",
}
TIER_BADGE_KIND: dict[str, str] = {
    "recommended": "ok",
    "alternative": "muted",
    "backup": "muted",
    "rejected": "danger",
    "excluded": "danger",
    "unknown": "muted",
}
TIER_MAP_KIND: dict[str, str] = {
    "recommended": "rec",
    "alternative": "alt",
    "backup": "alt",
    "rejected": "rej",
    "excluded": "rej",
    "unknown": "alt",
}
TIER_SHORT: dict[str, str] = {
    "recommended": "推荐",
    "alternative": "备选",
    "backup": "备选",
    "rejected": "不推荐",
    "excluded": "不推荐",
    "unknown": "",
}

#: 严重度 → 中文 / 徽章配色。
SEVERITY_LABELS: dict[str, str] = {"low": "低", "medium": "中", "high": "高"}
SEVERITY_BADGE_KIND: dict[str, str] = {"low": "muted", "medium": "warn", "high": "danger"}

#: 导图方向 → 中文说明。
MAP_DIRECTION_TEXT: dict[str, str] = {
    "LR": "LR（从左到右）",
    "RL": "RL（从右到左）",
    "TD": "TD（自上而下）",
    "TB": "TD（自上而下）",
    "BT": "BT（自下而上）",
}

#: 导航锚点：与各 section 的 id 一一对应。
NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("overview", "速览"),
    ("map", "导图"),
    ("options", "待决项"),
    ("compare", "对比表"),
    ("locked", "已锁定"),
    ("sources", "来源"),
    ("submit", "你的决策"),
)


#: 闸门标识 → 页面文案。页头必须醒目写出"这是 A 闸门 / B 闸门"，避免两板的
#: 确认码与回执目录被混用（契约 §10 风险表："渲染页显著标注 A/B"）。
GATE_LABELS: dict[str, str] = {"a": "A 闸门", "b": "B 闸门"}
GATE_SUBTITLES: dict[str, str] = {
    "a": "框架与探索边界 · 不锁定模型选型",
    "b": "方案择定 · 建议不是评委结论",
}
GATE_EYEBROWS: dict[str, str] = {
    "a": "Math Modeling · Phase 0.5 · Design Gate A",
    "b": "Math Modeling · Phase 1.5 · Design Gate B",
}
GATE_LEADS: dict[str, str] = {
    "a": "这是 AI 在写任何代码之前提交的题意框架：题目读对了吗、高严重度假设接受吗、"
    "要探索哪些范式（paradigm_set）。本板不锁定模型选型——具体用哪个模型由 B 闸门择定。",
    "b": "这是 AI 在选定模型之前提交的选型建议：每个候选的分数、维度分、优缺点、"
    "为什么不建议，以及工具实跑的多组数据对比。选定权在你；本页不是评委审查（评委在 Phase 4）。",
}

#: 按闸门组织的导航锚点（与各 section 的 id 一一对应）。
NAV_LINKS_GATE_A: tuple[tuple[str, str], ...] = (
    ("overview", "速览"),
    ("map", "导图"),
    ("paradigm", "范式集合"),
    ("options", "候选项"),
    ("compare", "对比表"),
    ("locked", "不锁定"),
    ("sources", "来源"),
    ("submit", "你的决策"),
)
NAV_LINKS_GATE_B: tuple[tuple[str, str], ...] = (
    ("overview", "速览"),
    ("advice", "建议与分数"),
    ("data", "数据对比"),
    ("compare", "候选对比"),
    ("locked", "你的选定"),
    ("sources", "来源"),
    ("submit", "你的决策"),
)

#: 闸门专用样式。只在板里显式声明了 gate 时追加，旧板 CSS 一字不改（逐字节回归）。
_GATE_CSS = """
.gate-banner{
  display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 16px;
  padding:12px 16px;border-radius:var(--radius);
  border:1px solid var(--brand-border);background:var(--brand-soft);
}
.gate-banner.gate-b{border-color:var(--warn-border);background:var(--warn-bg)}
.gate-banner .gb-tag{
  font-weight:700;letter-spacing:.02em;padding:2px 12px;border-radius:var(--pill);
  background:var(--brand);color:var(--brand-ink);font-size:13px;
}
.gate-banner.gate-b .gb-tag{background:var(--warn);color:#1b1f24}
.gate-banner .gb-text{font-size:13.5px;color:var(--text-2)}
.gate-flag{
  display:inline-flex;align-items:center;padding:2px 10px;border-radius:var(--pill);
  border:1px solid var(--brand);color:var(--brand);font-size:12px;font-weight:700;
  letter-spacing:.04em;
}
@media (prefers-color-scheme:dark){.gate-flag{border-color:var(--brand-border);color:var(--link)}}
.gate-flag.gate-b{border-color:var(--warn-border);color:var(--warn-ink)}
.score{
  display:inline-flex;align-items:baseline;gap:2px;font-family:var(--mono);
  white-space:nowrap;
}
.score b{font-size:16px;font-weight:700;color:var(--text)}
.score span{font-size:11.5px;color:var(--text-3)}
.pc{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}
@media (max-width:760px){.pc{grid-template-columns:1fr}}
.pc ul{margin:6px 0 0;padding-left:18px}
.pc li{margin:2px 0;font-size:13.5px;color:var(--text-2)}
.pc-pro{border-left:3px solid var(--accent-border);padding-left:10px}
.pc-con{border-left:3px solid var(--danger-border);padding-left:10px}
.pc-pro b{color:var(--accent)}
.pc-con b{color:var(--danger)}
.adv{
  border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);
  padding:12px 14px;margin:10px 0;
}
.adv-rec{border-color:var(--accent-border);background:var(--accent-bg)}
.adv-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:4px}
.adv-head h4{margin:0;font-size:14.5px}
.why-not{margin-top:10px;padding:10px 12px;border-radius:var(--radius-sm);
  background:var(--danger-bg);border:1px solid var(--danger-border)}
.why-not b{color:var(--danger)}
.why-not ul{margin:6px 0 0;padding-left:18px}
.when-better{margin-top:8px;padding:10px 12px;border-radius:var(--radius-sm);
  background:var(--surface-2);border:1px dashed var(--border-strong);font-size:13.5px}
.when-better b{color:var(--brand)}
.dims{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.dims .dim{
  font-family:var(--mono);font-size:11.5px;padding:1px 8px;border-radius:var(--pill);
  border:1px solid var(--border);background:var(--surface-2);color:var(--text-2);
}
.row-base td{background:var(--surface-2);font-style:italic}
.slice-head{margin:16px 0 8px;font-weight:650;font-size:14px;color:var(--text-2)}
.paradigm-family{
  font-family:var(--mono);font-size:11.5px;padding:1px 8px;border-radius:var(--pill);
  border:1px solid var(--brand-border);color:var(--brand);background:var(--brand-soft);
}
.cost-low{color:var(--accent);font-weight:650}
.cost-medium{color:var(--warn-ink);font-weight:650}
.cost-high{color:var(--danger);font-weight:650}
.pick-mark{color:var(--accent);font-weight:700}
"""

# ---------------------------------------------------------------------------
# 内联样式表（零外链：无 @import、无 url()、无外部字体）
# ---------------------------------------------------------------------------

_CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  color-scheme:light dark;
  --brand:#1f4e79;
  --brand-ink:#ffffff;
  --brand-soft:#eaf1f8;
  --brand-border:#bcd2e8;
  --link:#1f4e79;
  --accent:#2e7d32;
  --accent-bg:#e8f4ea;
  --accent-border:#a5d6a7;
  --danger:#c62828;
  --danger-bg:#fdecea;
  --danger-border:#efb8b3;
  --warn:#b26a00;
  --warn-ink:#8a5200;
  --warn-bg:#fff4e0;
  --warn-border:#e8c98a;
  --bg:#f7f8fa;
  --surface:#ffffff;
  --surface-2:#f2f4f7;
  --zebra:#f8f9fb;
  --hover:#eef3f9;
  --text:#1b1f24;
  --text-2:#4b5563;
  --text-3:#6b7280;
  --border:#e2e6eb;
  --border-strong:#c8ced6;
  --gray-1:#6b7280;--gray-2:#8b949e;--gray-3:#aab2bd;--gray-4:#d3d9e0;--gray-5:#eef1f4;
  --radius:12px;--radius-sm:8px;--pill:999px;--maxw:1120px;
  --shadow:0 1px 3px rgba(0,0,0,.06),0 8px 24px rgba(0,0,0,.04);
  --shadow-sm:0 1px 2px rgba(0,0,0,.05);
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",
         "Hiragino Sans GB",sans-serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,"SF Mono","Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --brand:#1f4e79;
    --brand-soft:#16283a;
    --brand-border:#2f4c6b;
    --link:#7fb3dd;
    --accent:#81c784;
    --accent-bg:#16281a;
    --accent-border:#356b39;
    --danger:#ef7b74;
    --danger-bg:#2b1a1a;
    --danger-border:#6d3430;
    --warn:#e0a458;
    --warn-ink:#f0be7e;
    --warn-bg:#2c2418;
    --warn-border:#6b5326;
    --bg:#0f1419;
    --surface:#1a2029;
    --surface-2:#222b36;
    --zebra:#1d242e;
    --hover:#243040;
    --text:#e6e6e6;
    --text-2:#b6bec9;
    --text-3:#98a2af;
    --border:#2a3441;
    --border-strong:#3d4a59;
    --gray-1:#98a2af;--gray-2:#8b949e;--gray-3:#6f7883;--gray-4:#465160;--gray-5:#2c3542;
    --shadow:0 1px 3px rgba(0,0,0,.45),0 8px 24px rgba(0,0,0,.3);
    --shadow-sm:0 1px 2px rgba(0,0,0,.35);
  }
}
html{scroll-behavior:smooth}
body{
  margin:0;padding:0 0 48px;background:var(--bg);color:var(--text);
  font-family:var(--font);font-size:15px;line-height:1.75;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
h1,h2,h3,h4{font-family:var(--font);color:var(--text)}
h1{font-size:28px;line-height:1.35;margin:0 0 12px;font-weight:700;letter-spacing:-.01em}
h2{font-size:20px;line-height:1.4;margin:0;font-weight:650}
h3{font-size:16px;line-height:1.5;margin:0;font-weight:650}
p{margin:0 0 10px}
p:last-child{margin-bottom:0}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:var(--mono);font-size:.92em}
:focus-visible{outline:2px solid var(--link);outline-offset:2px;border-radius:4px}
.sr-only{
  position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0,0,0,0);white-space:nowrap;border:0;
}
.skip{
  position:absolute;left:-9999px;top:8px;z-index:100;background:var(--surface);
  border:1px solid var(--border-strong);border-radius:var(--radius-sm);
  padding:8px 14px;font-size:13.5px;box-shadow:var(--shadow);
}
.skip:focus{left:16px}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}

/* ---------- 顶栏 ---------- */
.topbar{
  position:sticky;top:0;z-index:30;border-bottom:1px solid var(--border);
  background:var(--surface);
  background:color-mix(in srgb,var(--surface) 88%,transparent);
}
.topbar-inner{
  max-width:var(--maxw);margin:0 auto;padding:9px 28px;
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
}
.tb-brand{font-size:14px;font-weight:650;letter-spacing:-.01em}
.tb-sep{width:1px;height:16px;background:var(--border-strong);flex:none}
.spacer{flex:1 1 auto}
.pill{
  display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:var(--pill);
  border:1px solid var(--border-strong);background:var(--surface-2);
  color:var(--text-2);font-size:12.5px;white-space:nowrap;
}
.pill-code{font-family:var(--mono);font-size:12px;letter-spacing:.04em}
.pill-code b{color:var(--text);font-weight:700;letter-spacing:.08em}
@media (prefers-color-scheme:dark){.topbar{background:#1a2029}}

/* ---------- 页头 ---------- */
.hero{padding:40px 0 8px}
.eyebrow{
  font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--text-3);margin-bottom:10px;font-weight:600;
}
.lede{color:var(--text-2);font-size:15px;margin:0;max-width:82ch}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;align-items:center}
.hero-src{color:var(--text-3);font-size:13px;margin-top:10px}
.jump{
  display:flex;flex-wrap:wrap;gap:6px;align-items:center;
  margin-top:18px;padding-top:14px;border-top:1px dashed var(--border);
  font-size:13px;color:var(--text-3);
}
.jump-label{font-weight:600;margin-right:2px}
.jump a{
  padding:3px 11px;border-radius:var(--pill);border:1px solid var(--border);
  background:var(--surface);color:var(--text-2);font-size:13px;line-height:1.6;
}
.jump a:hover{border-color:var(--brand-border);color:var(--link);text-decoration:none;background:var(--brand-soft)}

/* ---------- 通用块 ---------- */
section{margin-top:40px;scroll-margin-top:72px}
.sec-head{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.sec-num{
  font-family:var(--mono);font-size:12px;color:var(--text-3);flex:none;
  border:1px solid var(--border-strong);border-radius:6px;padding:1px 7px;
}
.sec-hint{color:var(--text-3);font-size:13px;margin-left:auto}
.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);
}
.pad{padding:20px 22px}
.sub-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:22px 0 10px}
.sub-head:first-child{margin-top:0}
.sub-head .mono{color:var(--text-3);font-size:12.5px}
.muted{color:var(--text-3)}
.mono{font-family:var(--mono)}
.cell-sub{color:var(--text-3);font-size:12.5px;margin-top:2px;font-weight:400}

/* ---------- 徽章 / 芯片 ---------- */
.badge{
  display:inline-flex;align-items:center;gap:5px;padding:2px 10px;border-radius:var(--pill);
  font-size:12px;font-weight:600;line-height:1.6;border:1px solid transparent;
  white-space:nowrap;vertical-align:middle;
}
.badge-ok{background:var(--accent-bg);color:var(--accent);border-color:var(--accent-border)}
.badge-brand{background:var(--brand-soft);color:var(--link);border-color:var(--brand-border)}
.badge-warn{background:var(--warn-bg);color:var(--warn-ink);border-color:var(--warn-border)}
.badge-danger{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-border)}
.badge-muted{background:var(--surface-2);color:var(--text-2);border-color:var(--border-strong)}
.badge-mono{font-family:var(--mono);font-size:11.5px;letter-spacing:.02em}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{
  display:inline-flex;align-items:baseline;gap:5px;padding:2px 9px;border-radius:6px;
  background:var(--surface);border:1px solid var(--border-strong);
  font-family:var(--mono);font-size:12px;color:var(--text-2);line-height:1.7;
}
.chip b{color:var(--text);font-weight:600}
.chip i{font-style:normal;color:var(--text-3)}

/* ---------- 确认码卡片 ---------- */
.confirm{margin-top:26px;overflow:hidden}
.confirm-bar{height:4px;background:var(--brand)}
.confirm-inner{
  display:grid;grid-template-columns:minmax(300px,1fr) minmax(280px,1.05fr);
  gap:26px;padding:22px 24px;
}
.confirm-main{min-width:0}
.confirm-kicker{
  font-size:12px;letter-spacing:.1em;color:var(--text-3);
  text-transform:uppercase;font-weight:600;margin-bottom:10px;
}
.code-row{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 12px}
.code-char{
  width:46px;height:58px;display:inline-flex;align-items:center;justify-content:center;
  font-family:var(--mono);font-size:30px;font-weight:700;letter-spacing:.06em;
  background:var(--brand);color:#fff;border-radius:10px;box-shadow:var(--shadow-sm);
}
.code-none{
  display:inline-flex;align-items:center;font-family:var(--mono);font-size:20px;
  color:var(--text-2);border:1px dashed var(--border-strong);border-radius:10px;
  padding:12px 18px;background:var(--surface-2);
}
.confirm-note{color:var(--text-2);font-size:13.5px;margin:0}
.confirm-note strong{color:var(--danger);font-weight:700}
.confirm-side{border-left:1px solid var(--border);padding-left:24px;min-width:0}
.confirm-side .kv{grid-template-columns:84px 1fr}
.confirm-hint{margin-top:12px;padding-top:12px;border-top:1px dashed var(--border)}

/* ---------- 键值表 ---------- */
.kv{display:grid;grid-template-columns:92px 1fr;gap:4px 14px;font-size:13.5px;margin:0}
.kv dt{color:var(--text-3)}
.kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
.kv-wide{grid-template-columns:132px 1fr}
.risk{color:var(--danger)}
.okmark{color:var(--accent);font-weight:700}
.nowrap{white-space:nowrap}
.hash{font-family:var(--mono);font-size:11.5px;word-break:break-all;color:var(--text-2)}
.num{font-family:var(--mono);font-size:12.5px}

/* ---------- 提示条 ---------- */
.callout{
  display:flex;gap:12px;padding:13px 16px;border-radius:var(--radius-sm);
  border:1px solid var(--border);background:var(--surface-2);
  font-size:13.5px;color:var(--text-2);margin-bottom:12px;
}
.callout:last-child{margin-bottom:0}
.callout-ok{background:var(--accent-bg);border-color:var(--accent-border);color:var(--text)}
.callout-warn{background:var(--warn-bg);border-color:var(--warn-border)}
.callout-danger{background:var(--danger-bg);border-color:var(--danger-border)}
.callout-brand{background:var(--brand-soft);border-color:var(--brand-border)}
.callout b{color:var(--text)}
.callout-title{font-size:14px;color:var(--text);font-weight:650;margin-bottom:3px}
.alert-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.alert-head b{font-size:14px}
.alert-sub{font-size:13px;color:var(--text-2);margin:6px 0 0}
.empty{
  padding:16px 18px;border:1px dashed var(--border-strong);border-radius:var(--radius-sm);
  color:var(--text-3);font-size:13.5px;background:var(--surface);
}
.pending-list{margin:4px 0 0;padding-left:20px}
.pending-list li{margin:2px 0}
.qlist{margin:0 0 14px;padding-left:20px;color:var(--text-2);font-size:14px}
.qlist li{margin:2px 0}

/* ---------- 表格（斑马纹 + hover；窄屏转卡片） ---------- */
.table-wrap{
  overflow:hidden;border:1px solid var(--border);border-radius:var(--radius);
  background:var(--surface);box-shadow:var(--shadow);margin-bottom:16px;
}
.table-wrap:last-child{margin-bottom:0}
table.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:13.5px;min-width:660px}
table.tbl caption{
  caption-side:top;text-align:left;padding:14px 16px 0;
  font-size:13px;color:var(--text-3);
}
table.tbl th{
  background:var(--brand);color:var(--brand-ink);text-align:left;font-weight:600;
  padding:10px 14px;white-space:nowrap;font-size:13px;letter-spacing:.01em;
}
table.tbl th:first-child{border-top-left-radius:var(--radius)}
table.tbl th:last-child{border-top-right-radius:var(--radius)}
table.tbl td{
  padding:10px 14px;border-top:1px solid var(--border);vertical-align:top;
  overflow-wrap:anywhere;
}
table.tbl td[data-label="编号"],table.tbl td[data-label="tier"]{white-space:nowrap}
table.tbl tbody tr:nth-child(even) td{background:var(--zebra)}
table.tbl tbody tr:hover td{background:var(--hover)}
table.tbl tbody tr.row-rec td{background:var(--accent-bg)}
table.tbl tbody tr.row-rec:hover td{background:var(--accent-bg)}
table.tbl tbody tr.row-rec td:first-child{box-shadow:inset 3px 0 0 var(--accent)}
table.tbl td.nowrap{white-space:nowrap}

/* ---------- 小问 + 候选卡片 ---------- */
.q-block{margin-bottom:28px}
.q-block:last-child{margin-bottom:0}
.q-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px}
.q-id{
  font-family:var(--mono);font-size:12.5px;font-weight:700;color:var(--brand-ink);
  background:var(--brand);padding:1px 9px;border-radius:6px;letter-spacing:.02em;
}
.q-goal{color:var(--text-2);font-size:13.5px;margin:4px 0 0;max-width:88ch}
.q-meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px}
.q-comment{margin:10px 0 0}
.q-comment{margin-top:10px}
.opts{display:grid;gap:14px;margin-top:14px}
.opt{
  position:relative;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);padding:16px 18px;
  transition:border-color .15s ease,box-shadow .15s ease;
}
.opt:hover{border-color:var(--border-strong)}
.opt.picked{
  border-color:var(--accent);
  box-shadow:0 0 0 1px var(--accent-border),var(--shadow);
}
.opt.picked::after{
  content:"当前选择";position:absolute;top:-11px;right:16px;
  background:var(--accent);color:#fff;font-size:11.5px;font-weight:700;
  padding:2px 10px;border-radius:var(--pill);letter-spacing:.02em;
}
@media (prefers-color-scheme:dark){.opt.picked::after{color:#0f1419}}
.opt-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.opt-id{font-family:var(--mono);font-size:12px;color:var(--text-3);font-weight:600}
.opt-name{font-size:15.5px;font-weight:650;margin:0}
.opt-why{color:var(--text-2);font-size:14px;margin:0 0 12px}
.trial{
  margin-top:12px;padding:12px 14px;border-radius:var(--radius-sm);
  background:var(--surface-2);border:1px solid var(--border);
}
.trial-head{
  display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;
  font-size:12.5px;color:var(--text-2);margin-bottom:9px;
}
.trial-head b{color:var(--text);font-weight:650}
.trial-sample{color:var(--text-2)}
.trial-secs{font-family:var(--mono);color:var(--text-2);margin-left:auto}
.trial-cmd{
  display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;
  margin-top:10px;font-size:12px;color:var(--text-2);
}
.trial .muted{color:var(--text-2)}
.trial-cmd code{
  font-family:var(--mono);font-size:12px;background:var(--surface);
  border:1px solid var(--border);border-radius:5px;padding:2px 8px;
  color:var(--text-2);word-break:break-all;
}
.src{
  display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  margin-top:12px;padding-top:11px;border-top:1px dashed var(--border);
  font-size:12.5px;color:var(--text-3);
}
.src-note{color:var(--text-3);overflow-wrap:anywhere}
.src-unverified{color:var(--danger)}

/* ---------- 导图 ---------- */
.map-scroll{overflow-x:auto;padding:14px 6px 8px;-webkit-overflow-scrolling:touch}
svg.map{display:block;margin:0 auto;max-width:none;height:auto}
.map-meta{
  display:flex;gap:18px;flex-wrap:wrap;padding:0 22px 10px;
  font-size:12.5px;color:var(--text-3);
}
.map-hint{display:none;color:var(--text-3);font-size:12px}
@media (max-width:900px){.map-hint{display:inline}}
.legend{
  display:flex;gap:18px;flex-wrap:wrap;padding:0 22px 18px;
  font-size:12.5px;color:var(--text-3);
}
.legend i{
  display:inline-block;width:12px;height:12px;border-radius:4px;
  margin-right:6px;vertical-align:-2px;border:1px solid var(--border-strong);
}
.legend i.dashed{border-style:dashed;background:var(--surface-2)}
.legend i.root{background:var(--brand);border-color:var(--brand)}
.legend i.rec{background:var(--accent-bg);border-color:var(--accent)}
.legend i.alt{background:var(--surface-2);border-color:var(--border-strong)}
.map-fallback{
  margin:0;padding:16px 20px;background:var(--surface-2);font-family:var(--mono);
  font-size:12px;line-height:1.7;color:var(--text-2);white-space:pre-wrap;
  word-break:break-word;border-top:1px solid var(--border);
}
.mm-node-box{fill:var(--surface-2);stroke:var(--border-strong);stroke-width:1.4}
.mm-label{fill:var(--text);font-family:var(--font);font-size:13px;font-weight:600}
.mm-sub{fill:var(--text-3);font-family:var(--font);font-size:10.5px}
.mm-root .mm-node-box{fill:var(--brand);stroke:var(--brand)}
.mm-root .mm-label{fill:#ffffff}
.mm-root .mm-sub{fill:#d6e4f0}
.mm-rec .mm-node-box{fill:var(--accent-bg);stroke:var(--accent);stroke-width:2}
.mm-rec .mm-label{fill:var(--accent)}
.mm-rec .mm-sub{fill:var(--accent)}
.mm-rej .mm-node-box{stroke-dasharray:5 3}
.mm-chosen .mm-node-box{stroke-width:2.6}
.mm-edge{fill:none;stroke:var(--border-strong);stroke-width:1.4}
.mm-arrow{fill:var(--border-strong)}
.mm-anim{animation:mmIn .42s cubic-bezier(.22,.7,.3,1) both}
@keyframes mmIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* ---------- 折叠区 ---------- */
details{
  border:1px solid var(--border);border-radius:var(--radius-sm);
  background:var(--surface);margin-top:12px;
}
details summary{
  cursor:pointer;padding:12px 16px;font-size:13.5px;color:var(--text-2);
  list-style:none;display:flex;align-items:center;gap:8px;user-select:none;
}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"\\25B8";color:var(--gray-2);transition:transform .15s ease}
details[open] summary::before{transform:rotate(90deg)}
details[open] summary{color:var(--text);border-bottom:1px solid var(--border)}
details .inner{padding:14px 16px}
details .inner .table-wrap{box-shadow:none}

/* ---------- 页脚 ---------- */
footer{
  margin-top:48px;padding:18px 0 40px;border-top:1px solid var(--border);
  font-size:12.5px;color:var(--text-3);line-height:1.8;
}
footer code{color:var(--text-2)}
.foot-meta{margin-top:6px}
.backtop{margin-top:10px;display:inline-block;font-size:12.5px}

/* ---------- 响应式：<900px 表格转卡片 ---------- */
@media (max-width:900px){
  .wrap{padding:0 18px}
  .topbar-inner{padding:8px 16px}
  h1{font-size:22px}
  h2{font-size:18px}
  .hero{padding-top:28px}
  .confirm-inner{grid-template-columns:1fr;gap:18px}
  .confirm-side{border-left:0;padding-left:0;border-top:1px solid var(--border);padding-top:16px}
  .kv{grid-template-columns:80px 1fr}
  .kv-wide{grid-template-columns:100px 1fr}
  .table-wrap{overflow:visible;border:0;box-shadow:none;background:transparent;border-radius:0}
  table.tbl{display:block;min-width:0;font-size:13.5px}
  table.tbl caption{padding:0 0 8px}
  table.tbl thead{display:none}
  table.tbl tbody,table.tbl tr,table.tbl td{display:block;width:100%}
  table.tbl tr{
    background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
    box-shadow:var(--shadow-sm);margin-bottom:10px;padding:4px 0;overflow:hidden;
  }
  table.tbl td{border-top:0;padding:7px 14px}
  table.tbl td::before{
    content:attr(data-label);display:block;color:var(--text-3);
    font-size:12px;font-weight:600;margin-bottom:1px;
  }
  table.tbl td[data-label=""]::before{display:none}
  table.tbl tbody tr:nth-child(even) td,
  table.tbl tbody tr:hover td,
  table.tbl tbody tr.row-rec:hover td{background:transparent}
  table.tbl tbody tr.row-rec{background:var(--accent-bg);border-color:var(--accent-border)}
  table.tbl tbody tr.row-rec td:first-child{box-shadow:none}
}

/* ---------- 减少动效 ---------- */
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *,*::before,*::after{
    animation-duration:.001ms !important;animation-iteration-count:1 !important;
    transition-duration:.001ms !important;
  }
  .mm-anim{animation:none !important;opacity:1 !important;transform:none !important}
}

/* ---------- 打印 ---------- */
@media print{
  :root{
    --bg:#ffffff;--surface:#ffffff;--surface-2:#f6f7f9;--zebra:#fafbfc;--hover:transparent;
    --text:#111111;--text-2:#333333;--text-3:#555555;--border:#cccccc;--border-strong:#999999;
    --shadow:none;--shadow-sm:none;--brand:#1f4e79;--brand-soft:#eef4fa;--brand-border:#b9cde1;
    --link:#1f4e79;--accent:#2e7d32;--accent-bg:#eef7ef;--accent-border:#a5d6a7;
    --danger:#b3261e;--danger-bg:#fdecea;--danger-border:#e3b3ae;
    --warn:#8a5200;--warn-ink:#8a5200;--warn-bg:#fff4e0;--warn-border:#e6c98f;
    color-scheme:light;
  }
  body{padding:0;font-size:11.5pt;line-height:1.6;background:#fff;color:#111}
  .wrap{max-width:none;padding:0}
  .topbar,.jump,.skip,.backtop,.no-print{display:none !important}
  .hero{padding-top:0}
  section{margin-top:18px;page-break-inside:auto}
  .card,.opt,.trial,.callout,.confirm,.table-wrap,table.tbl tr,details{
    page-break-inside:avoid;break-inside:avoid;
  }
  h1,h2,h3{page-break-after:avoid;break-after:avoid}
  h1{font-size:20pt}
  h2{font-size:14pt}
  h3{font-size:12pt}
  a{color:inherit;text-decoration:none}
  .table-wrap{overflow:visible;border-radius:0}
  table.tbl{min-width:0}
  .mm-anim{animation:none !important;opacity:1 !important;transform:none !important}
  .map-scroll{overflow:visible}
  details{border-color:#bbbbbb}
  details summary{color:#333}
  /* 兜底：即使浏览器的 beforeprint 钩子不可用，也尽量把折叠区内容摊开 */
  details:not([open]) > *:not(summary){display:block !important}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}

/* ===== 决策提交区（serve 通道 / 离线下载降级） ===== */
.submit-panel{border:1px solid var(--border);border-radius:14px;padding:18px 20px;background:var(--surface);box-shadow:var(--shadow)}
.submit-panel h3{margin:0 0 4px;font-size:17px}
.submit-panel .sp-hint{margin:0 0 14px;color:var(--text-3);font-size:13px;line-height:1.6}
.sp-q{border-top:1px dashed var(--border);padding:14px 0}
.sp-q:first-of-type{border-top:0;padding-top:2px}
.sp-q-title{font-weight:650;font-size:14px;margin-bottom:8px}
.sp-opts{display:flex;flex-wrap:wrap;gap:8px}
.sp-opt{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--border);border-radius:999px;padding:6px 13px;cursor:pointer;font-size:13px;background:var(--bg);transition:border-color .15s,background .15s}
.sp-opt:hover{border-color:var(--accent)}
.sp-opt input{accent-color:var(--accent);margin:0}
.sp-opt.on{border-color:var(--accent);background:var(--accent-bg);font-weight:600}
.sp-opt .sp-tier{font-size:11px;color:var(--text-3);font-weight:400}
.sp-comment{width:100%;box-sizing:border-box;margin-top:10px;min-height:58px;resize:vertical;border:1px solid var(--border);border-radius:10px;padding:9px 11px;font:inherit;font-size:13px;background:var(--bg);color:var(--text)}
.sp-comment:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.sp-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:16px;padding-top:14px;border-top:1px solid var(--border)}
.sp-btn{border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:10px;padding:9px 20px;font:inherit;font-weight:650;font-size:14px;cursor:pointer}
.sp-btn:hover{filter:brightness(1.06)}
.sp-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sp-btn.ghost{background:transparent;color:var(--accent)}
.sp-btn:disabled{opacity:.55;cursor:not-allowed;filter:none}
.sp-status{font-size:13px;line-height:1.6;color:var(--text-3)}
.sp-status.ok{color:var(--accent)}
.sp-status.err{color:var(--danger)}
.sp-mode{font-size:12px;color:var(--text-3);margin-left:auto}
.sp-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--text-3);margin-right:5px;vertical-align:1px}
.sp-dot.live{background:#2e7d32}
.sp-dot.offline{background:#c62828}
@media (max-width:900px){.sp-opt{flex:1 1 auto;justify-content:center}.sp-mode{margin-left:0;width:100%}}
@media print{.submit-panel{break-inside:avoid}.sp-actions,.sp-mode{display:none}}
"""

#: 极少量内联 JS：打印展开 + 决策提交（不依赖任何外部库、不发外部请求）。
#:
#: 提交有两条路径，自动探测：
#:   1. 页面由 ``design_board.py serve`` 提供 → ``POST /api/submit`` 写回执；
#:   2. 直接双击打开本地文件 → 提交必然失败（file:// 下 fetch 直接被拦），
#:      自动降级为下载 ``design_board_submission.json``，交给人跑 ``ingest``。
#:
#: 选择与批注即时存 ``localStorage``（键含 board_id），刷新/误关不丢。
#: 所有网络目标都是**同源相对路径**，所以不会产生任何外链。
_INLINE_SCRIPT = """
(function () {
  "use strict";

  /* ---------- 打印时展开折叠区 ---------- */
  var opened = [];
  function expandAll() {
    opened = [];
    var list = document.querySelectorAll("details:not([open])");
    for (var i = 0; i < list.length; i++) {
      list[i].open = true;
      opened.push(list[i]);
    }
  }
  function restoreAll() {
    for (var i = 0; i < opened.length; i++) { opened[i].open = false; }
    opened = [];
  }
  window.addEventListener("beforeprint", expandAll);
  window.addEventListener("afterprint", restoreAll);

  /* ---------- 决策提交 ---------- */
  var panel = document.querySelector(".submit-panel");
  if (!panel) { return; }

  var boardId = panel.getAttribute("data-board-id") || "board";
  var token = panel.getAttribute("data-token") || "";
  var storeKey = "mm-design-board::" + boardId;
  var statusEl = panel.querySelector("[data-mm-status]");
  var modeEl = panel.querySelector("[data-mm-mode]");
  var dotEl = panel.querySelector("[data-mm-dot]");
  var submitBtn = panel.querySelector("[data-mm-submit]");
  var downloadBtn = panel.querySelector("[data-mm-download]");
  var resetBtn = panel.querySelector("[data-mm-reset]");
  var online = false;

  function setStatus(text, kind) {
    if (!statusEl) { return; }
    statusEl.textContent = text || "";
    statusEl.className = "sp-status" + (kind ? " " + kind : "");
  }
  function setMode(isOnline, text) {
    online = isOnline;
    if (modeEl) { modeEl.textContent = text; }
    if (dotEl) { dotEl.className = "sp-dot " + (isOnline ? "live" : "offline"); }
  }

  function readState() {
    var state = { decisions: {}, comments: {}, updated_at: null };
    try {
      var raw = window.localStorage.getItem(storeKey);
      if (raw) {
        var parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          state.decisions = parsed.decisions || {};
          state.comments = parsed.comments || {};
          state.updated_at = parsed.updated_at || null;
        }
      }
    } catch (err) { /* localStorage 被禁用：静默降级为不暂存 */ }
    return state;
  }

  function writeState(state) {
    state.updated_at = new Date().toISOString();
    try {
      window.localStorage.setItem(storeKey, JSON.stringify(state));
    } catch (err) { /* 隐私模式下写不进去，不影响提交 */ }
  }

  function collect() {
    var decisions = {};
    var groups = panel.querySelectorAll(".sp-q");
    for (var i = 0; i < groups.length; i++) {
      var qid = groups[i].getAttribute("data-question");
      var picked = groups[i].querySelector("input[type=radio]:checked");
      if (qid && picked) { decisions[qid] = picked.value; }
    }
    var comments = {};
    var areas = panel.querySelectorAll(".sp-comment");
    for (var j = 0; j < areas.length; j++) {
      var cq = areas[j].getAttribute("data-question");
      var text = (areas[j].value || "").trim();
      if (cq && text) { comments[cq] = text; }
    }
    return { decisions: decisions, comments: comments };
  }

  function buildEnvelope() {
    var picked = collect();
    var decisions = [];
    for (var qid in picked.decisions) {
      if (Object.prototype.hasOwnProperty.call(picked.decisions, qid)) {
        decisions.push({ question_id: qid, option_id: picked.decisions[qid] });
      }
    }
    var comments = [];
    for (var cq in picked.comments) {
      if (Object.prototype.hasOwnProperty.call(picked.comments, cq)) {
        comments.push({ question_id: cq, text: picked.comments[cq] });
      }
    }
    var nonce = "";
    try {
      if (window.crypto && window.crypto.getRandomValues) {
        var buf = new Uint8Array(16);
        window.crypto.getRandomValues(buf);
        for (var k = 0; k < buf.length; k++) {
          nonce += ("0" + buf[k].toString(16)).slice(-2);
        }
      }
    } catch (err) { nonce = String(Date.now()); }
    return {
      board_id: boardId,
      at: new Date().toISOString(),
      receipt_origin: online ? "browser-submit" : "file-download",
      nonce: nonce,
      user_edited: true,
      decisions: decisions,
      comments: comments
    };
  }

  function restoreToForm() {
    var state = readState();
    var groups = panel.querySelectorAll(".sp-q");
    for (var i = 0; i < groups.length; i++) {
      var qid = groups[i].getAttribute("data-question");
      var want = state.decisions[qid];
      if (!want) { continue; }
      var labels = groups[i].querySelectorAll(".sp-opt");
      for (var j = 0; j < labels.length; j++) {
        var radio = labels[j].querySelector("input[type=radio]");
        if (radio && radio.value === want) {
          radio.checked = true;
          labels[j].classList.add("on");
        } else {
          labels[j].classList.remove("on");
        }
      }
    }
    var areas = panel.querySelectorAll(".sp-comment");
    for (var k = 0; k < areas.length; k++) {
      var cq = areas[k].getAttribute("data-question");
      if (state.comments[cq]) { areas[k].value = state.comments[cq]; }
    }
    if (state.updated_at) {
      setStatus("已恢复上次未提交的暂存（" + state.updated_at.slice(0, 19).replace("T", " ") + "）");
    }
  }

  /* 任何改动都即时暂存 */
  panel.addEventListener("change", function (ev) {
    var target = ev.target;
    if (target && target.type === "radio") {
      var labels = panel.querySelectorAll(".sp-opt");
      for (var i = 0; i < labels.length; i++) {
        var radio = labels[i].querySelector("input[type=radio]");
        labels[i].classList.toggle("on", !!(radio && radio.checked));
      }
    }
    writeState(collect());
  });
  panel.addEventListener("input", function (ev) {
    if (ev.target && ev.target.className && ev.target.className.indexOf("sp-comment") >= 0) {
      writeState(collect());
    }
  });

  function download(envelope) {
    var blob = new Blob([JSON.stringify(envelope, null, 2)], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "__MM_SUBMISSION_FILE__";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    setStatus(
      "离线模式：已下载 __MM_SUBMISSION_FILE__。请把它交给 AI 运行 " +
      "python tools/design_board.py ingest --workspace .__MM_GATE_ARG__ --from __MM_SUBMISSION_FILE__",
      "ok"
    );
  }

  function post(envelope) {
    setStatus("正在提交…");
    if (submitBtn) { submitBtn.disabled = true; }
    fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-MM-Token": token },
      body: JSON.stringify(envelope)
    }).then(function (res) {
      return res.json().then(function (payload) { return { ok: res.ok, payload: payload }; });
    }).then(function (out) {
      if (!out.ok || !out.payload || !out.payload.ok) {
        var msg = (out.payload && out.payload.error) || "服务器拒绝了这次提交";
        if (submitBtn) { submitBtn.disabled = false; }
        setStatus("提交失败：" + msg, "err");
        return;
      }
      var result = out.payload.result || {};
      var detail = (result.changes || []).length + " 项改动，第 " + result.round + " 轮";
      if (result.user_edited === false) { detail = "本轮无改动（第 " + result.round + " 轮）"; }
      setStatus(
        "提交成功：" + detail + "；连续无修改轮次 " + result.no_change_rounds +
        "（≥2 轮后可让用户本人执行 confirm --apply）",
        "ok"
      );
      try { window.localStorage.removeItem(storeKey); } catch (err) {}
      if (submitBtn) { submitBtn.disabled = false; }
    }).catch(function () {
      if (submitBtn) { submitBtn.disabled = false; }
      setMode(false, "离线（下载 JSON 兜底）");
      download(envelope);
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", function () {
      var envelope = buildEnvelope();
      if (!envelope.decisions.length) {
        setStatus("请至少为一个问题选择一个方案", "err");
        return;
      }
      if (online) { post(envelope); } else { download(envelope); }
    });
  }
  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () { download(buildEnvelope()); });
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      try { window.localStorage.removeItem(storeKey); } catch (err) {}
      setStatus("已清除本地暂存（看板里的既有选择不受影响）", "ok");
    });
  }

  /* 探测是否由本地服务器提供：file:// 下 fetch 会被拦，直接进离线模式 */
  restoreToForm();
  if (window.location.protocol === "file:") {
    setMode(false, "离线（下载 JSON 兜底）");
  } else {
    fetch("/api/ping", { cache: "no-store" }).then(function (res) {
      return res.json();
    }).then(function (payload) {
      if (payload && payload.ok) {
        setMode(true, "已连接本地服务器");
        if (payload.confirmed) {
          setStatus("本板已确认；改选会生成新一轮回执，需要重新确认。");
        }
      } else {
        setMode(false, "离线（下载 JSON 兜底）");
      }
    }).catch(function () {
      setMode(false, "离线（下载 JSON 兜底）");
    });
  }
})();
"""


# ---------------------------------------------------------------------------
# 文本 / 转义辅助
# ---------------------------------------------------------------------------


def _as_list(value: object) -> list[Any]:
    """把任意 JSON 值规整成 list（非 list 返回空列表）。"""
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict:
    """把任意 JSON 值规整成 dict（非 dict 返回空字典）。"""
    return value if isinstance(value, dict) else {}


def _present(value: object) -> bool:
    """判断字段是否有实际内容（None / 空串 / 空容器都算没有）。"""
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, dict, set)):
        return len(value) > 0
    return True


def _num_text(value: int | float) -> str:
    """数字转文本：整数不带小数点，浮点用最紧凑表示。"""
    if isinstance(value, bool):  # 防御：bool 是 int 子类
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:g}"


def _text(value: object) -> str:
    """把任意 JSON 值转成可读纯文本（**不转义**；渲染前一律走 :func:`_e`）。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return _num_text(value)
    if isinstance(value, (list, tuple)):
        return "、".join(item for item in (_text(item) for item in value) if item)
    if isinstance(value, dict):
        if not value:
            return ""
        return "；".join(f"{key}：{_text(item)}" for key, item in value.items())
    return str(value)


def _trial_value(value: object) -> str:
    """试算输出里的值：布尔沿用 JSON 字面量（true/false），其余走 :func:`_text`。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return _text(value)


def _seconds_text(value: object) -> str:
    """秒数转人类友好的耗时文案：毫秒级给 ms，秒级给 s。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    seconds = float(value)
    if seconds < 0:
        return ""
    if seconds == 0:
        return "0 ms"
    if seconds < 0.001:
        return f"{seconds * 1000:.3g} ms"
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.3g} s"


def _clip(value: object, limit: int = 60) -> str:
    """压缩空白并截断到 limit 个字符（保留省略号），用于摘要类展示。"""
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "…"


def _defang(text: str) -> str:
    """把外链前缀的冒号/斜杠写成实体，既保留可读性又不触发零外链自检。"""
    for needle, replacement in _DEFANG_PAIRS:
        text = text.replace(needle, replacement)
    return text


def _e(value: object) -> str:
    """统一转义入口：任意 JSON 值 → HTML 安全文本（含外链打码）。"""
    return _defang(html.escape(_text(value), quote=True))


def _attr(value: object) -> str:
    """属性值转义（与 :func:`_e` 同口径，引号已被打成实体）。"""
    return _e(value)


def _badge(label: str, kind: str = "muted", *, mono: bool = False) -> str:
    """生成一枚胶囊徽章；label 由调用方保证是纯文本（内部会转义）。"""
    extra = " badge-mono" if mono else ""
    return f'<span class="badge badge-{kind}{extra}">{_e(label)}</span>'


def _chip(key: object, value: object) -> str:
    """生成一枚 ``key=value`` 等宽芯片。"""
    return (
        f'<span class="chip"><i>{_e(key)}</i>=<b>{_e(value)}</b></span>'
    )


def _table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    caption: str = "",
    row_classes: Sequence[str] | None = None,
) -> str:
    """生成一张语义化表格（表头深蓝、斑马纹、窄屏由 CSS 转成卡片）。

    ``rows`` 里的单元格必须是**已经渲染好的安全 HTML**（用 :func:`_e` 逐段拼出来的），
    本函数只负责包壳与 ``data-label`` 标注（供窄屏卡片模式显示字段名）。
    """
    head_cells = "".join(f'<th scope="col">{_e(header)}</th>' for header in headers)
    body_rows: list[str] = []
    for index, row in enumerate(rows):
        row_class = ""
        if row_classes is not None and index < len(row_classes) and row_classes[index]:
            row_class = f' class="{_attr(row_classes[index])}"'
        cells: list[str] = []
        for position, cell in enumerate(row):
            label = headers[position] if position < len(headers) else ""
            cells.append(f'<td data-label="{_attr(label)}">{cell}</td>')
        body_rows.append(f"<tr{row_class}>" + "".join(cells) + "</tr>")
    caption_html = f'<caption class="sr-only">{_e(caption)}</caption>' if caption else ""
    return (
        '<div class="table-wrap"><table class="tbl">'
        f"{caption_html}<thead><tr>{head_cells}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
    )


# ---------------------------------------------------------------------------
# board 字段访问辅助（全部防御式：字段缺失 / 类型不对都不抛异常）
# ---------------------------------------------------------------------------


def _questions(board: dict) -> list[dict]:
    """取出 questions 里的对象项（跳过脏数据）。"""
    return [item for item in _as_list(board.get("questions")) if isinstance(item, dict)]


def _options(question: dict) -> list[dict]:
    """取出某题的 options 对象项。"""
    return [item for item in _as_list(question.get("options")) if isinstance(item, dict)]


def _find_option(question: dict, option_id: object) -> dict | None:
    """按 id 找某题里的候选；找不到返回 None。"""
    target = _text(option_id).strip()
    if not target:
        return None
    for option in _options(question):
        if _text(option.get("id")).strip() == target:
            return option
    return None


def _question_id(question: dict, index: int) -> str:
    """小问 id（缺失时退化成 Q{序号}）。"""
    value = _text(question.get("id")).strip()
    return value or f"Q{index + 1}"


def _option_id(option: dict, index: int) -> str:
    """候选 id（缺失时退化成 O{序号}）。"""
    value = _text(option.get("id")).strip()
    return value or f"O{index + 1}"


def _tier_key(value: object) -> str:
    """把 tier 归一化成 recommended / alternative / rejected / unknown。

    ``value`` 可以是 option 字典，也可以直接是 tier 字符串；同时容忍常见别名
    （rec / alt / backup / excluded / 中文"推荐/备选/不推荐"）。
    """
    raw = value.get("tier") if isinstance(value, dict) else value
    tier = _text(raw).strip().lower()
    if tier in ("recommended", "recommend", "rec", "primary", "推荐"):
        return "recommended"
    if tier in ("rejected", "reject", "excluded", "banned", "不推荐"):
        return "rejected"
    if tier in ("alternative", "alt", "backup", "secondary", "备选"):
        return "alternative"
    return "unknown"


def _board_confirmed(board: dict) -> bool:
    """判定整块板是否已确认。

    口径与 ``design_board_checker._board_confirmed`` 一致：顶层 ``confirmed`` 是布尔时
    以它为准；否则回退到"每题都 confirmed 为 true"。
    """
    top = board.get("confirmed")
    if isinstance(top, bool):
        return top
    questions = _questions(board)
    flags = [question.get("confirmed") is True for question in questions]
    return bool(flags) and all(flags)


def _render_time(board: dict) -> str:
    """生成时间。

    优先读 board 里的 ``rendered_at`` / ``generated_at``（便于让输出可复现）；
    都没有时才用当前本地时间。这样调用方想让渲染幂等，只要在 JSON 里钉一个时间戳即可。
    """
    for key in ("rendered_at", "generated_at"):
        raw = board.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 闸门判定与 gate b 的建议/范式取数
# ---------------------------------------------------------------------------


def _declared_gate(board: dict) -> str | None:
    """板里显式声明了 gate（a / b）才返回；旧板返回 None，走 legacy 渲染。"""
    raw = board.get("gate")
    if isinstance(raw, str) and raw.strip().lower() in GATE_LABELS:
        return raw.strip().lower()
    return None


def _resolve_gate(board: dict, gate: str | None) -> str | None:
    """渲染用闸门：板自报优先；否则只有显式 gate=b 才算 B 板。

    这样"旧 A 板 + gate=a"仍是 legacy 渲染（输出逐字节不变），而新 B 板即使
    忘了写 gate 字段也能按 B 板渲染。
    """
    declared = _declared_gate(board)
    if declared:
        return declared
    if isinstance(gate, str) and gate.strip().lower() == "b":
        return "b"
    return None


def _gate_banner(gate: str | None) -> str:
    """页头闸门横幅（醒目写出"这是 A 闸门 / B 闸门"）。"""
    if not gate:
        return ""
    label = GATE_LABELS.get(gate, gate)
    subtitle = GATE_SUBTITLES.get(gate, "")
    return (
        f'<div class="gate-banner gate-{_e(gate)}" role="note">'
        f'<span class="gb-tag">这是 {_e(label)}</span>'
        f'<span class="gb-text">{_e(subtitle)}</span></div>'
    )


def _gate_suffix(gate: str | None) -> str:
    """命令行里的闸门参数后缀：A 板为空串（保持旧文案），B 板为 --gate b。"""
    return " --gate b" if gate == "b" else ""


def _paradigms(question: dict) -> list[dict]:
    """某题的 paradigm_set 对象项（缺失/脏数据返回空列表）。"""
    return [item for item in _as_list(question.get("paradigm_set")) if isinstance(item, dict)]


def _has_paradigms(questions: Sequence[dict]) -> bool:
    """任意一题是否带范式集合（A 板 schema v2 才有）。"""
    return any(_paradigms(question) for question in questions)


def _explore_cost(paradigm: dict) -> tuple[str, str]:
    """探索成本：返回 (等级, 一句话说明)。"""
    cost = _as_dict(paradigm.get("explore_cost"))
    level = _text(cost.get("level")).strip().lower()
    note = _clip(cost.get("note"), 60)
    return level, note


def _cost_html(paradigm: dict) -> str:
    """探索成本单元格：等级上色 + 一句话说明。"""
    level, note = _explore_cost(paradigm)
    label = {"low": "低", "medium": "中", "high": "高"}.get(level, level or "未标")
    css = f"cost-{level}" if level in ("low", "medium", "high") else "muted"
    body = f'<span class="{css}">{_e(label)}</span>'
    if note:
        body += f'<div class="cell-sub">{_e(note)}</div>'
    return body


def _advice_for(board: dict, question: dict) -> dict:
    """某题的建议块：题内 advice 优先，其次板级 advice（单问 B 板的兼容写法）。"""
    advice = _as_dict(question.get("advice"))
    if advice:
        return advice
    return _as_dict(board.get("advice"))


def _advice_candidates(advice: dict) -> dict[str, dict]:
    """advice.candidates 按 option_id 建索引。"""
    index: dict[str, dict] = {}
    for item in _as_list(advice.get("candidates")):
        if not isinstance(item, dict):
            continue
        option_id = _text(item.get("option_id") or item.get("id")).strip()
        if option_id:
            index[option_id] = item
    return index


def _verdict_key(option: dict, candidate: dict | None = None) -> str:
    """建议结论归一化：recommended / not_recommended / unknown。"""
    raw = _text(option.get("verdict") or (candidate or {}).get("verdict")).strip().lower()
    if raw in ("recommended", "recommend"):
        return "recommended"
    if raw in ("not_recommended", "not-recommended", "rejected", "reject"):
        return "not_recommended"
    return "unknown"


def _verdict_badge(option: dict, candidate: dict | None = None) -> str:
    """建议徽章：建议采用（绿）/ 不建议（红）/ 未表态（灰）。"""
    key = _verdict_key(option, candidate)
    if key == "recommended":
        return _badge("🟢 建议采用", "ok")
    if key == "not_recommended":
        return _badge("⛔ 不建议", "danger")
    return _badge("⚪ 未表态", "muted")


def _score_of(option: dict, candidate: dict | None = None) -> object:
    """候选分数：option.score 优先，其次 advice candidate 里的 score。"""
    value = option.get("score")
    if value is None and candidate:
        value = candidate.get("score")
    return value


def _score_html(option: dict, candidate: dict | None = None) -> str:
    """分数单元格：大号数字 + /100。"""
    value = _score_of(option, candidate)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return '<span class="muted">—</span>'
    return f'<span class="score"><b>{_num_text(float(value))}</b><span>/100</span></span>'


def _dims_html(candidate: dict, rubric: dict) -> str:
    """维度分芯片组：按评分口径顺序输出 key=score(w=权重)。"""
    scores = _as_dict(candidate.get("dimension_scores"))
    if not scores:
        return '<span class="muted">—</span>'
    chips: list[str] = []
    seen: list[str] = []
    for dimension in _as_list(rubric.get("dimensions")):
        if not isinstance(dimension, dict):
            continue
        key = _text(dimension.get("id")).strip()
        if not key:
            continue
        seen.append(key)
        weight = dimension.get("weight")
        label = f"{key}={_num_text(scores.get(key)) if isinstance(scores.get(key), (int, float)) else '—'}"
        if isinstance(weight, (int, float)) and not isinstance(weight, bool):
            label += f"(w={weight:g})"
        chips.append(f'<span class="dim">{_e(label)}</span>')
    for key, value in scores.items():
        if key not in seen:
            chips.append(f'<span class="dim">{_e(f"{key}={value}")}</span>')
    return f'<div class="dims">{"".join(chips)}</div>'


def _bullet_list(value: object) -> list[str]:
    """把 JSON 数组压成非空字符串列表（用于 pros / cons / why_not）。"""
    items: list[str] = []
    for item in _as_list(value):
        text = _text(item).strip()
        if text:
            items.append(text)
    return items


# ---------------------------------------------------------------------------
# 内联 SVG 导图：mermaid graph LR / TD 极简解析器
# ---------------------------------------------------------------------------

#: 单张导图最多画多少个节点；超过就退化为纯文本（避免一次渲染出几百 KB 的 SVG）。
_MAP_MAX_NODES = 120
#: 节点文本换行宽度（"单位"：全角字符算 2，半角算 1）。
_MAP_WRAP_UNITS = 20
#: 节点最多画几行文字（超出用省略号）。
_MAP_MAX_LINES = 3
#: 节点尺寸与间距（SVG 用户单位）。
_MAP_MIN_WIDTH = 116.0
_MAP_MAX_WIDTH = 224.0
_MAP_PAD = 26.0
_MAP_COL_GAP = 66.0
_MAP_ROW_GAP = 22.0
_MAP_TD_ROW_GAP = 34.0
_MAP_CORNER_RADIUS = 10.0
_MAP_ELBOW_RADIUS = 11.0

_GRAPH_HEADER_RE = re.compile(
    r"^\s*(?:graph|flowchart)\s+(?P<dir>LR|RL|TD|TB|BT)\s*;?\s*$", re.IGNORECASE
)
_ARROW_RE = re.compile(r"\s*(?:-->|--->|==>|-\.->|---|--x|--o)\s*")
_NODE_ID_RE = re.compile(r"^(?P<id>[A-Za-z0-9_][\w.\-]*|[\u4e00-\u9fff][\w.\-\u4e00-\u9fff]*)")
_NODE_SHAPE_RE = re.compile(
    r"^(?P<open>\[\[|\{\{|\(\(|\[|\(|\{)(?P<label>.*?)(?P<close>\]\]|\}\}|\)\)|\]|\)|\})?$",
    re.DOTALL,
)
_EDGE_LABEL_RE = re.compile(r"\|[^|]*\|")
_NODE_CLASS_RE = re.compile(r":::[\w\-]+$")
_BR_RE = re.compile(r"(?i)<br\s*/?>")
_MAP_SKIP_PREFIXES = (
    "classdef",
    "class",
    "style",
    "linkstyle",
    "subgraph",
    "direction",
    "click",
    "acctitle",
    "accdescr",
    "%%",
)


class _MindmapError(ValueError):
    """导图源码无法解析成图形（外部会降级为 ``<pre>`` 纯文本，不向上抛）。"""


@dataclass
class _MapNode:
    """导图节点：解析出的原始信息 + 布局过程中算出的几何信息。"""

    key: str
    label: str
    lines: list[str] = field(default_factory=list)
    kind: str = "alt"  # root / rec / alt / rej
    sub: str = ""
    chosen: bool = False
    level: int = 0
    width: float = 0.0
    height: float = 0.0
    x: float = 0.0
    y: float = 0.0


@dataclass
class _MapGraph:
    """解析后的有向图（节点保持源码出现顺序，边已去重、去自环）。"""

    direction: str
    nodes: list[_MapNode]
    edges: list[tuple[str, str]]


def _char_units(char: str) -> int:
    """单个字符的显示宽度单位：东亚全宽字符算 2，其它算 1。"""
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _text_units(text: str) -> int:
    """字符串的显示宽度单位合计。"""
    return sum(_char_units(char) for char in text)


def _wrap_line(text: str, max_units: int) -> list[str]:
    """按显示宽度硬折行（中文场景下比按单词折行更可控）。"""
    lines: list[str] = []
    current: list[str] = []
    used = 0
    for char in text:
        width = _char_units(char)
        if current and used + width > max_units:
            lines.append("".join(current))
            current = [char]
            used = width
        else:
            current.append(char)
            used += width
    if current:
        lines.append("".join(current))
    return lines or [""]


def _node_lines(label: str) -> list[str]:
    """把节点标签拆成最多 ``_MAP_MAX_LINES`` 行，超长部分用省略号收尾。"""
    segments = [segment.strip() for segment in _BR_RE.split(_text(label)) if segment.strip()]
    if not segments:
        return [""]
    lines: list[str] = []
    truncated = False
    for segment in segments:
        for wrapped in _wrap_line(segment, _MAP_WRAP_UNITS):
            if len(lines) >= _MAP_MAX_LINES:
                truncated = True
                break
            lines.append(wrapped)
        if truncated:
            break
    if not lines:
        lines = [""]
    if truncated:
        last = lines[-1]
        while last and _text_units(last) > _MAP_WRAP_UNITS - 2:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _parse_node_token(token: str) -> tuple[str, str] | None:
    """解析 ``ID`` / ``ID[标签]`` / ``ID(标签)`` / ``ID{标签}``；失败返回 None。"""
    token = token.strip()
    if not token:
        return None
    match = _NODE_ID_RE.match(token)
    if not match:
        return None
    node_key = match.group("id")
    rest = token[match.end():].strip()
    rest = _NODE_CLASS_RE.sub("", rest).strip()
    if not rest:
        return node_key, ""
    shape = _NODE_SHAPE_RE.match(rest)
    if not shape:
        return None
    label = (shape.group("label") or "").strip()
    if len(label) >= 2 and label[0] == label[-1] and label[0] in ("'", '"'):
        label = label[1:-1].strip()
    return node_key, label


def _parse_mermaid(source: str) -> _MapGraph:
    """解析 mermaid ``graph LR/TD`` 源码。

    支持：

    - ``A[标签] --> B[标签]``（也认 ``==>`` / ``-.->`` / ``---`` 等箭头写法）
    - ``A[标签]`` 孤立节点
    - ``graph LR`` / ``graph TD``（兼容 ``RL`` / ``BT``，``TB`` 视作 ``TD``）
    - 忽略 ``classDef`` / ``class`` / ``style`` / ``subgraph`` / ``end`` 等非图形语句
    - 标签里的中文、空格、``<br/>``

    解析不出来时抛 :class:`_MindmapError`，由调用方降级展示源码。
    """
    direction = "LR"
    ordered_keys: list[str] = []
    nodes: dict[str, _MapNode] = {}
    edges: list[tuple[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    saw_header = False

    for raw in source.splitlines():
        line = raw.strip().rstrip(";").strip()
        if not line:
            continue
        header = _GRAPH_HEADER_RE.match(line)
        if header:
            direction = header.group("dir").upper()
            if direction == "TB":
                direction = "TD"
            saw_header = True
            continue
        lowered = line.lower()
        if lowered == "end" or lowered.startswith(tuple(_MAP_SKIP_PREFIXES)):
            continue
        cleaned = _EDGE_LABEL_RE.sub("", line)
        tokens = [token.strip() for token in _ARROW_RE.split(cleaned)]
        tokens = [token for token in tokens if token]
        if not tokens:
            continue
        parsed: list[tuple[str, str]] = []
        for token in tokens:
            node = _parse_node_token(token)
            if node is None:
                raise _MindmapError(f"无法识别的导图语句：{_clip(raw.strip(), 80)}")
            parsed.append(node)
        for node_key, label in parsed:
            if node_key not in nodes:
                nodes[node_key] = _MapNode(key=node_key, label=label or node_key)
                ordered_keys.append(node_key)
            elif label and nodes[node_key].label == node_key:
                nodes[node_key].label = label
        for left, right in zip(parsed, parsed[1:]):
            pair = (left[0], right[0])
            if pair[0] == pair[1] or pair in seen_edges:
                continue
            seen_edges.add(pair)
            edges.append(pair)

    if not nodes:
        raise _MindmapError("导图源码里没有任何节点")
    if not saw_header and not edges and len(nodes) == 1:
        # 只有一行、没有 graph 头也没有边：多半不是 mermaid 图，宁可降级也别硬画
        raise _MindmapError("没有找到 graph 头部，也没有任何连线")
    if len(nodes) > _MAP_MAX_NODES:
        raise _MindmapError(f"节点数 {len(nodes)} 超过上限 {_MAP_MAX_NODES}，已退化为纯文本")
    return _MapGraph(
        direction=direction,
        nodes=[nodes[key] for key in ordered_keys],
        edges=edges,
    )


def _assign_levels(graph: _MapGraph) -> tuple[dict[str, int], set[str]]:
    """从入度 0 的根节点做分层 BFS，给每个节点定层级。

    环里的节点 BFS 走不到，统一放到最后一层；边保持原样（回边画成弧线）。
    """
    adjacency: dict[str, list[str]] = {node.key: [] for node in graph.nodes}
    indegree: dict[str, int] = {node.key: 0 for node in graph.nodes}
    for source_key, target_key in graph.edges:
        if source_key in adjacency and target_key in adjacency:
            adjacency[source_key].append(target_key)
            indegree[target_key] += 1

    roots = [node.key for node in graph.nodes if indegree[node.key] == 0]
    if not roots:
        roots = [graph.nodes[0].key]
    level: dict[str, int] = {key: 0 for key in roots}
    queue: deque[str] = deque(roots)
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour not in level:
                level[neighbour] = level[current] + 1
                queue.append(neighbour)

    max_level = max(level.values()) if level else 0
    for node in graph.nodes:
        if node.key not in level:
            level[node.key] = max_level + 1
        node.level = level[node.key]
    return level, set(roots)


def _apply_map_kinds(graph: _MapGraph, board: dict, roots: set[str]) -> None:
    """给节点上色语义：根节点深蓝、推荐绿、不推荐虚线、当前选择粗描边。"""
    option_meta: dict[str, tuple[dict, dict, bool]] = {}
    question_meta: dict[str, dict] = {}
    for index, question in enumerate(_questions(board)):
        question_meta[_question_id(question, index).strip().lower()] = question
        choice = _text(question.get("user_choice")).strip()
        for option_index, option in enumerate(_options(question)):
            option_id = _option_id(option, option_index).strip()
            if not option_id:
                continue
            option_meta[option_id.lower()] = (question, option, choice == option_id)

    root_keys = {key.strip().lower() for key in roots}
    for node in graph.nodes:
        key = node.key.strip().lower()
        head = node.label.split()[0].strip("：:·-—") if node.label.split() else ""
        matched = option_meta.get(key) or (option_meta.get(head.lower()) if head else None)
        if matched is not None:
            _question, option, chosen = matched
            tier = _tier_key(option)
            node.kind = TIER_MAP_KIND.get(tier, "alt")
            parts = [TIER_SHORT.get(tier, "")]
            if chosen:
                parts.append("✓ 已选")
            node.sub = " · ".join(part for part in parts if part)
            node.chosen = chosen
            continue
        if node.level == 0 and key in root_keys:
            node.kind = "root"
            node.sub = ""
            continue
        question = question_meta.get(key)
        if question is not None:
            node.kind = "alt"
            node.sub = f"{len(_options(question))} 个候选"
            continue
        node.kind = "alt"
        node.sub = ""


def _size_map_nodes(graph: _MapGraph) -> None:
    """按标签折行结果算每个节点的宽高。"""
    for node in graph.nodes:
        node.lines = _node_lines(node.label)
        widest = max((_text_units(line) for line in node.lines), default=0)
        node.width = max(_MAP_MIN_WIDTH, min(_MAP_MAX_WIDTH, 30.0 + widest * 7.5))
        node.height = 16.0 + 17.0 * len(node.lines) + (15.0 if node.sub else 0.0)


def _position_map(graph: _MapGraph, level: dict[str, int]) -> tuple[int, int]:
    """按方向排布节点坐标，返回画布宽高（整数，便于写进 SVG 属性）。"""
    groups: dict[int, list[_MapNode]] = {}
    for node in graph.nodes:
        groups.setdefault(level[node.key], []).append(node)
    order = sorted(groups)

    if graph.direction in ("LR", "RL"):
        column_widths = [max(node.width for node in groups[key]) for key in order]
        column_heights = [
            sum(node.height for node in groups[key]) + _MAP_ROW_GAP * (len(groups[key]) - 1)
            for key in order
        ]
        tallest = max(column_heights)
        cursor = _MAP_PAD
        for index, key in enumerate(order):
            y = _MAP_PAD + (tallest - column_heights[index]) / 2.0
            for node in groups[key]:
                node.x = cursor + (column_widths[index] - node.width) / 2.0
                node.y = y
                y += node.height + _MAP_ROW_GAP
            cursor += column_widths[index] + _MAP_COL_GAP
        width = sum(column_widths) + _MAP_COL_GAP * (len(order) - 1) + 2 * _MAP_PAD
        height = tallest + 2 * _MAP_PAD
    else:
        row_heights = [max(node.height for node in groups[key]) for key in order]
        row_widths = [
            sum(node.width for node in groups[key]) + _MAP_ROW_GAP * (len(groups[key]) - 1)
            for key in order
        ]
        widest = max(row_widths)
        cursor = _MAP_PAD
        for index, key in enumerate(order):
            x = _MAP_PAD + (widest - row_widths[index]) / 2.0
            for node in groups[key]:
                node.x = x
                node.y = cursor + (row_heights[index] - node.height) / 2.0
                x += node.width + _MAP_ROW_GAP
            cursor += row_heights[index] + _MAP_TD_ROW_GAP
        width = widest + 2 * _MAP_PAD
        height = sum(row_heights) + _MAP_TD_ROW_GAP * (len(order) - 1) + 2 * _MAP_PAD

    # RL / BT 是"把整幅图镜像"，节点坐标镜像后，边的走向仍然按方向算，不必再改路由。
    if graph.direction == "RL":
        for node in graph.nodes:
            node.x = width - node.x - node.width
    elif graph.direction == "BT":
        for node in graph.nodes:
            node.y = height - node.y - node.height
    return max(int(round(width)), 260), max(int(round(height)), 160)


def _fmt(value: float) -> str:
    """SVG 数字格式化：去掉无意义的小数尾巴。"""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _orth_h(x1: float, y1: float, x2: float, y2: float) -> str:
    """水平进出的正交折线（H-V-H），拐角带圆角。"""
    sign_x = 1.0 if x2 > x1 else -1.0
    sign_y = 1.0 if y2 > y1 else -1.0
    middle = (x1 + x2) / 2.0
    radius = max(
        0.0,
        min(_MAP_ELBOW_RADIUS, abs(x2 - x1) / 2.0, abs(y2 - y1) / 2.0),
    )
    return (
        f"M{_fmt(x1)},{_fmt(y1)} "
        f"H{_fmt(middle - sign_x * radius)} "
        f"Q{_fmt(middle)},{_fmt(y1)} {_fmt(middle)},{_fmt(y1 + sign_y * radius)} "
        f"V{_fmt(y2 - sign_y * radius)} "
        f"Q{_fmt(middle)},{_fmt(y2)} {_fmt(middle + sign_x * radius)},{_fmt(y2)} "
        f"H{_fmt(x2)}"
    )


def _orth_v(x1: float, y1: float, x2: float, y2: float) -> str:
    """垂直进出的正交折线（V-H-V），拐角带圆角。"""
    sign_x = 1.0 if x2 > x1 else -1.0
    sign_y = 1.0 if y2 > y1 else -1.0
    middle = (y1 + y2) / 2.0
    radius = max(
        0.0,
        min(_MAP_ELBOW_RADIUS, abs(y2 - y1) / 2.0, abs(x2 - x1) / 2.0),
    )
    return (
        f"M{_fmt(x1)},{_fmt(y1)} "
        f"V{_fmt(middle - sign_y * radius)} "
        f"Q{_fmt(x1)},{_fmt(middle)} {_fmt(x1 + sign_x * radius)},{_fmt(middle)} "
        f"H{_fmt(x2 - sign_x * radius)} "
        f"Q{_fmt(x2)},{_fmt(middle)} {_fmt(x2)},{_fmt(middle + sign_y * radius)} "
        f"V{_fmt(y2)}"
    )


def _curve_h(x1: float, y1: float, x2: float, y2: float, flow: float) -> str:
    """水平方向的回边（目标在流向的反侧）：用三次贝塞尔绕出去。"""
    offset = 46.0 * flow
    return (
        f"M{_fmt(x1)},{_fmt(y1)} "
        f"C{_fmt(x1 + offset)},{_fmt(y1)} {_fmt(x2 - offset)},{_fmt(y2)} {_fmt(x2)},{_fmt(y2)}"
    )


def _curve_v(x1: float, y1: float, x2: float, y2: float, flow: float) -> str:
    """垂直方向的回边：同样用三次贝塞尔绕出去。"""
    offset = 46.0 * flow
    return (
        f"M{_fmt(x1)},{_fmt(y1)} "
        f"C{_fmt(x1)},{_fmt(y1 + offset)} {_fmt(x2)},{_fmt(y2 - offset)} {_fmt(x2)},{_fmt(y2)}"
    )


def _edge_path(source: _MapNode, target: _MapNode, direction: str) -> str:
    """算一条边的 ``<path d="...">``：正向走正交折线，回边走弧线。"""
    if direction in ("LR", "RL"):
        flow = 1.0 if direction == "LR" else -1.0
        if direction == "LR":
            x1, x2 = source.x + source.width, target.x
        else:
            x1, x2 = source.x, target.x + target.width
        y1 = source.y + source.height / 2.0
        y2 = target.y + target.height / 2.0
        if (x2 - x1) * flow > 2.0:
            if abs(y2 - y1) < 0.5:
                return f"M{_fmt(x1)},{_fmt(y1)} L{_fmt(x2)},{_fmt(y2)}"
            return _orth_h(x1, y1, x2, y2)
        return _curve_h(x1, y1, x2, y2, flow)

    flow = 1.0 if direction == "TD" else -1.0
    if direction == "TD":
        y1, y2 = source.y + source.height, target.y
    else:
        y1, y2 = source.y, target.y + target.height
    x1 = source.x + source.width / 2.0
    x2 = target.x + target.width / 2.0
    if (y2 - y1) * flow > 2.0:
        if abs(x2 - x1) < 0.5:
            return f"M{_fmt(x1)},{_fmt(y1)} L{_fmt(x2)},{_fmt(y2)}"
        return _orth_v(x1, y1, x2, y2)
    return _curve_v(x1, y1, x2, y2, flow)


def _build_map_svg(graph: _MapGraph, width: int, height: int) -> str:
    """把排好版的节点/边拼成内联 SVG（纯 CSS 控制配色与淡入动画）。"""
    keyed = {node.key: node for node in graph.nodes}
    parts: list[str] = [
        f'<svg class="map" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="mm-title">',
        f'<title id="mm-title">{_e("模型结构思维导图：" + graph.direction)}</title>',
        '<defs><marker id="mm-arrow" markerWidth="8" markerHeight="8" '
        'refX="7" refY="4" orient="auto">'
        '<path class="mm-arrow" d="M0,0 L8,4 L0,8 z"/></marker></defs>',
    ]

    edge_parts: list[str] = []
    for index, (source_key, target_key) in enumerate(graph.edges):
        source = keyed.get(source_key)
        target = keyed.get(target_key)
        if source is None or target is None:
            continue
        delay = 30 + min(index, 12) * 30
        path = _edge_path(source, target, graph.direction)
        edge_parts.append(
            f'<path class="mm-edge mm-anim" style="animation-delay:{delay}ms" '
            f'marker-end="url(#mm-arrow)" d="{path}"/>'
        )
    parts.append(f'<g class="mm-edges">{"".join(edge_parts)}</g>')

    node_parts: list[str] = []
    for index, node in enumerate(graph.nodes):
        delay = 60 + min(index, 20) * 55
        classes = ["mm-node", "mm-anim"]
        if node.kind in ("root", "rec", "rej"):
            classes.append(f"mm-{node.kind}")
        if node.chosen:
            classes.append("mm-chosen")
        center_x = node.x + node.width / 2.0
        fragments = [
            f'<g class="{" ".join(classes)}" style="animation-delay:{delay}ms">',
            f'<rect class="mm-node-box" x="{_fmt(node.x)}" y="{_fmt(node.y)}" '
            f'width="{_fmt(node.width)}" height="{_fmt(node.height)}" '
            f'rx="{_fmt(_MAP_CORNER_RADIUS)}"/>',
        ]
        baseline = node.y + 24.0
        for line in node.lines:
            fragments.append(
                f'<text class="mm-label" x="{_fmt(center_x)}" y="{_fmt(baseline)}" '
                f'text-anchor="middle">{_e(line)}</text>'
            )
            baseline += 17.0
        if node.sub:
            sub_baseline = node.y + 24.0 + 17.0 * (len(node.lines) - 1) + 14.0
            fragments.append(
                f'<text class="mm-sub" x="{_fmt(center_x)}" y="{_fmt(sub_baseline)}" '
                f'text-anchor="middle">{_e(node.sub)}</text>'
            )
        fragments.append("</g>")
        node_parts.append("".join(fragments))
    parts.append(f'<g class="mm-nodes">{"".join(node_parts)}</g>')
    parts.append("</svg>")
    return "".join(parts)


def _map_legend(graph: _MapGraph) -> str:
    """导图图例（颜色表达含义时必须有图例）。"""
    items = [
        '<span><i class="root"></i>根节点 / 题目</span>',
        '<span><i class="rec"></i>推荐方案</span>',
        '<span><i class="alt"></i>备选 · 小问 · 验证</span>',
        '<span><i class="alt dashed"></i>不推荐</span>',
    ]
    if any(node.chosen for node in graph.nodes):
        items.append("<span>粗描边 = 当前选择</span>")
    return "".join(items)


def _render_mindmap(board: dict) -> str:
    """渲染导图卡片：能解析就画 SVG，解析失败就退化成源码 ``<pre>``。"""
    mindmap = _as_dict(board.get("mindmap"))
    source = _text(mindmap.get("source")).strip()
    if not source:
        return (
            '<div class="card"><div class="pad"><div class="empty">'
            "决策板没有提供 <code>mindmap.source</code>，无法绘制结构导图；"
            "请先在 design_board.json 里补一段 mermaid <code>graph LR</code> 源码再重新渲染。"
            "</div></div></div>"
        )
    try:
        graph = _parse_mermaid(source)
        level, roots = _assign_levels(graph)
        _apply_map_kinds(graph, board, roots)
        _size_map_nodes(graph)
        width, height = _position_map(graph, level)
        svg = _build_map_svg(graph, width, height)
    except Exception as exc:  # 导图必须能降级：任何布局/解析异常都不能把整页渲染拖崩
        reason = _clip(f"{type(exc).__name__}: {exc}", 180)
        return (
            '<div class="card">'
            '<div class="pad"><div class="callout callout-warn" style="margin:0">'
            "<div><b>导图没能画成图形，已退化为源码。</b><br>"
            f"原因：{_e(reason)}<br>"
            "修好 <code>mindmap.source</code>（mermaid <code>graph LR</code> / "
            "<code>graph TD</code>）后重新渲染即可恢复图形版。"
            "</div></div></div>"
            f'<pre class="map-fallback">{_e(source)}</pre>'
            "</div>"
        )

    direction_text = MAP_DIRECTION_TEXT.get(graph.direction, graph.direction)
    meta = (
        f"<span>{len(graph.nodes)} 个节点</span>"
        f"<span>{len(graph.edges)} 条连线</span>"
        f"<span>方向 {_e(direction_text)}</span>"
        '<span class="map-hint">← 左右滑动查看完整导图</span>'
    )
    return (
        '<div class="card">'
        f'<div class="map-scroll">{svg}</div>'
        f'<div class="map-meta">{meta}</div>'
        f'<div class="legend">{_map_legend(graph)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# 小区块渲染辅助：徽章 / 试算 / 来源 / 状态
# ---------------------------------------------------------------------------


def _tier_badge(option: dict) -> str:
    """候选的推荐度徽章（recommended=绿 / alternative=灰 / rejected=红）。"""
    tier = _tier_key(option)
    if tier == "unknown":
        return _badge("待评估", "muted")
    symbol = {"recommended": "🟢 ", "alternative": "⚪ ", "rejected": "⛔ "}.get(tier, "")
    return _badge(symbol + TIER_LABELS[tier], TIER_BADGE_KIND[tier])


def _status_badges(question: dict) -> str:
    """小问状态徽章组：已锁定 / 已确认 / 已选择 / 待选择。"""
    badges: list[str] = []
    if question.get("user_locked") is True:
        badges.append(_badge("🔒 已锁定", "warn"))
    if question.get("confirmed") is True:
        badges.append(_badge("✅ 已确认", "ok"))
    if _present(question.get("user_choice")):
        if not badges:
            badges.append(_badge("已选择", "brand"))
    else:
        badges.append(_badge("待选择", "muted"))
    return "".join(badges)


def _option_heading(option: dict, index: int) -> str:
    """候选标题（HTML）：``O1 名称``，名称缺失时给出占位。"""
    option_id = _option_id(option, index)
    name = _text(option.get("name")).strip() or "（未命名方案）"
    return f'<span class="opt-id">{_e(option_id)}</span><h4 class="opt-name">{_e(name)}</h4>'


def _option_title_text(option: dict, index: int) -> str:
    """候选标题（纯文本），用于表格/锁定区。"""
    option_id = _option_id(option, index)
    name = _text(option.get("name")).strip() or "（未命名方案）"
    return f"{option_id} · {name}"


def _source_ref(option: dict) -> dict:
    """取 source_ref（非 dict 一律当空）。"""
    return _as_dict(option.get("source_ref"))


def _source_headline(source: dict) -> str:
    """来源摘要：``方法卡 · OPT-01``。"""
    kind = _text(source.get("type")).strip() or "未标类型"
    ref = _text(source.get("ref")).strip() or "未编号"
    return f"{kind} · {ref}"


def _verified_badge(source: dict) -> str:
    """来源核验状态徽章。"""
    verified = source.get("verified")
    if verified is True:
        return _badge("✓ 已核验", "ok")
    if verified is False:
        return _badge("⚠ 未核验", "danger")
    return _badge("核验未登记", "muted")


def _dependencies_text(option: dict) -> str:
    """依赖展示：列表拼接；空列表明确写"无额外依赖"。"""
    dependencies = option.get("dependencies")
    if isinstance(dependencies, (list, tuple)):
        items = [_text(item).strip() for item in dependencies if _text(item).strip()]
        return "、".join(items) if items else "无额外依赖"
    if isinstance(dependencies, str) and dependencies.strip():
        return dependencies.strip()
    return "无额外依赖"


def _trial_output_chips(output: object, limit: int = 6) -> str:
    """把 ``mini_trial.output`` 渲染成 key=value 芯片组。"""
    if isinstance(output, dict) and output:
        entries = list(output.items())
        chips = "".join(_chip(key, _trial_value(value)) for key, value in entries[:limit])
        extra = len(entries) - limit
        if extra > 0:
            chips += f'<span class="chip"><i>…</i>另 {extra} 项</span>'
        return f'<div class="chips">{chips}</div>'
    if isinstance(output, (list, tuple)) and output:
        return f'<div class="chips">{_chip("output", _clip(output, 48))}</div>'
    if _present(output):
        return f'<div class="chips">{_chip("output", _clip(output, 64))}</div>'
    return ""


def _trial_inline(option: dict) -> str:
    """对比表里的紧凑试算摘要：``objective=2175 · x_a=20 · 4.27 ms``。"""
    trial = _as_dict(option.get("mini_trial"))
    if not trial:
        return '<span class="muted">未试算</span>'
    bits: list[str] = []
    output = trial.get("output")
    if isinstance(output, dict) and output:
        bits.append(
            "、".join(
                f"{key}={_trial_value(value)}" for key, value in list(output.items())[:3]
            )
        )
    elif _present(output):
        bits.append(_clip(output, 40))
    seconds = _seconds_text(trial.get("seconds"))
    if seconds:
        bits.append(seconds)
    if not bits:
        return '<span class="muted">未试算</span>'
    return f'<span class="mono">{_e(" · ".join(bits))}</span>'


def _trial_block(option: dict) -> str:
    """候选卡片底部的试算证据块（口径 / 数值芯片 / 耗时 / 复跑命令）。"""
    trial = option.get("mini_trial")
    if not isinstance(trial, dict) or not trial:
        return (
            '<div class="trial"><div class="trial-head"><b>试算证据</b>'
            '<span class="trial-sample">未提供 mini_trial</span></div>'
            '<div class="muted">候选缺少试算记录：评委很可能追问"为什么没验证"。'
            "建议补一次真实的小规模试算，并给出可复跑命令。</div></div>"
        )
    head: list[str] = ["<b>试算证据</b>"]
    sample = _clip(trial.get("sample"), 60)
    if sample:
        head.append(f'<span class="trial-sample">样本：{_e(sample)}</span>')
    seconds = _seconds_text(trial.get("seconds"))
    if seconds:
        head.append(f'<span class="trial-secs">⏱ {_e(seconds)}</span>')
    chips = _trial_output_chips(trial.get("output"))
    if not chips:
        chips = '<div class="muted">试算未记录 output 数值</div>'
    command = _text(trial.get("reproduce_cmd")).strip()
    command_html = ""
    if command:
        command_html = (
            '<div class="trial-cmd"><span>复跑</span>'
            f"<code>{_e(command)}</code></div>"
        )
    return (
        f'<div class="trial"><div class="trial-head">{"".join(head)}</div>'
        f"{chips}{command_html}</div>"
    )


def _source_block(option: dict) -> str:
    """候选卡片底部的来源块（类型 / 编号 / tier / 核验状态 / 备注）。"""
    source = _source_ref(option)
    if not source:
        return (
            '<div class="src">'
            f'{_badge("未登记来源", "warn")}'
            '<span class="src-note">候选没有 source_ref：无法追溯方法出处，'
            "评委会追问依据。</span></div>"
        )
    fragments = [
        _badge(_text(source.get("tier")).strip() or "tier 未标", "muted", mono=True),
        f'<span class="mono">{_e(_source_headline(source))}</span>',
        _verified_badge(source),
    ]
    note = _clip(source.get("note"), 90)
    if note:
        fragments.append(f'<span class="src-note">{_e(note)}</span>')
    if source.get("verified") is False:
        reason = _text(source.get("unverified_reason")).strip()
        fragments.append(
            f'<span class="src-unverified">未核验原因：'
            f"{_e(_clip(reason, 90) if reason else '（未填写 unverified_reason）')}</span>"
        )
    return f'<div class="src">{"".join(fragments)}</div>'


def _source_cell(option: dict) -> str:
    """对比表里的来源单元格：紧凑等宽编号 + tier + 核验标记（完整类型放在 tooltip）。

    列宽有限，这里只放"能定位到哪张方法卡"的最小信息；来源类型/备注在候选卡片和
    07 来源速查里完整呈现。
    """
    source = _source_ref(option)
    if not source:
        return '<span class="muted">未登记来源</span>'
    kind = _text(source.get("type")).strip() or "未标类型"
    reference = _text(source.get("ref")).strip() or "未编号"
    headline = f"{kind} · {reference}"
    fragments = [
        f'<span class="mono nowrap" title="{_attr(headline)}">{_e(reference)}</span>'
    ]
    tier = _text(source.get("tier")).strip()
    if tier:
        fragments.append(f'<span class="muted">· {_e(tier)}</span>')
    verified = source.get("verified")
    if verified is True:
        fragments.append('<span class="okmark" title="来源已核验">✓</span>')
    elif verified is False:
        fragments.append('<span class="badge badge-danger">未核验</span>')
    return " ".join(fragments)


# ---------------------------------------------------------------------------
# 页面骨架：顶栏 / 页头 / 确认码
# ---------------------------------------------------------------------------


def _page_title(board: dict, title: str | None) -> str:
    """页面主标题：显式 title > problem_summary.title > 兜底文案。"""
    if isinstance(title, str) and title.strip():
        return title.strip()
    summary = _as_dict(board.get("problem_summary"))
    value = _text(summary.get("title")).strip()
    return value or "建模方案决策板"


def _render_topbar(board: dict, gate: str | None = None) -> str:
    """吸顶状态条：品牌 + 闸门标识 + 确认状态 + 轮次 + 确认码。"""
    confirmed = _board_confirmed(board)
    status = _badge("✅ 已确认", "ok") if confirmed else _badge("⏳ 待确认", "warn")
    revision = board.get("revision")
    round_text = ""
    if isinstance(revision, int) and not isinstance(revision, bool) and revision > 0:
        round_text = f'<span class="pill">第 {revision} 轮</span>'
    code = _text(board.get("confirm_code")).strip()
    code_html = (
        f'<span class="pill pill-code">确认码 <b>{_e(code)}</b></span>'
        if code
        else '<span class="pill pill-code">确认码 <b>未生成</b></span>'
    )
    gate_html = ""
    if gate:
        label = GATE_LABELS.get(gate, gate)
        gate_html = f'<span class="gate-flag gate-{_attr(gate)}">这是 {_e(label)}</span>'
    return (
        '<div class="topbar"><div class="topbar-inner">'
        '<span class="tb-brand">建模方案决策板</span>'
        f"{gate_html}"
        f'<span class="tb-sep" aria-hidden="true"></span>{status}{round_text}'
        '<span class="spacer"></span>'
        f"{code_html}"
        "</div></div>"
    )


def _render_hero(
    board: dict,
    page_title: str,
    *,
    gate: str | None = None,
    nav: Sequence[tuple[str, str]] = NAV_LINKS,
) -> str:
    """页头：闸门横幅、标题、状态徽章、revision、生成时间、题目来源与锚点导航。"""
    confirmed = _board_confirmed(board)
    meta: list[str] = []
    meta.append(_badge("✅ 已确认", "ok") if confirmed else _badge("⏳ 待确认", "warn"))
    revision = board.get("revision")
    if isinstance(revision, int) and not isinstance(revision, bool) and revision > 0:
        meta.append(f'<span class="pill">第 {revision} 轮</span>')
    meta.append(f'<span class="pill">生成时间 {_e(_render_time(board))}</span>')
    board_id = _text(board.get("board_id")).strip()
    if board_id:
        meta.append(f'<span class="pill">决策板 {_e(board_id)}</span>')
    language = _text(board.get("language")).strip()
    if language:
        meta.append(f'<span class="pill">语言 {_e(language)}</span>')

    summary = _as_dict(board.get("problem_summary"))
    source_text = _text(summary.get("source")).strip()
    source_html = (
        f'<p class="hero-src">题目来源：{_e(_clip(source_text, 120))}</p>'
        if source_text
        else ""
    )
    links = "".join(f'<a href="#{anchor}">{_e(label)}</a>' for anchor, label in nav)
    eyebrow = GATE_EYEBROWS.get(gate, "Math Modeling · Phase 0.5 · Design Gate") if gate else (
        "Math Modeling · Phase 0.5 · Design Gate"
    )
    lede = GATE_LEADS.get(gate) if gate else (
        "这是 AI 在写任何代码之前提交的建模决策：每个小问的候选算法、"
        "真实试算数值、主要风险与方法来源。选定权在你——页面上的选择与批注需要你确认后，"
        "才会进入建模阶段。"
    )
    return (
        '<header class="hero">'
        f'<div class="eyebrow">{_e(eyebrow)}</div>'
        f"{_gate_banner(gate)}"
        f"<h1>{_e(page_title)}</h1>"
        f'<p class="lede">{_e(lede)}</p>'
        f'<div class="meta">{"".join(meta)}</div>'
        f"{source_html}"
        f'<nav class="jump" aria-label="跳到"><span class="jump-label">跳到：</span>{links}</nav>'
        "</header>"
    )


def _render_confirm(board: dict, gate: str | None = None) -> str:
    """确认码卡片：4 位大号码 + "AI 不得代填"说明 + 来源与状态。"""
    confirmed = _board_confirmed(board)
    suffix = _gate_suffix(gate)
    gate_label = GATE_LABELS.get(gate, "") if gate else ""
    code = _text(board.get("confirm_code")).strip()
    hash_value = _text(board.get("board_sha256")).strip()

    if code:
        chars = "".join(f'<span class="code-char">{_e(char)}</span>' for char in code[:8])
        code_html = f'<div class="code-row" role="group" aria-label="确认码">{chars}</div>'
    else:
        code_html = '<div class="code-row"><span class="code-none">未生成</span></div>'

    state = _badge("✅ 已确认", "ok") if confirmed else _badge("⏳ 待确认", "warn")
    if hash_value and "placeholder" not in hash_value.lower():
        hash_cell = f'<span class="mono">{_e(hash_value[:12])}…</span>'
    elif hash_value:
        hash_cell = f'<span class="mono">{_e(hash_value[:24])}</span> {_badge("占位值", "warn")}'
    else:
        hash_cell = '<span class="muted">尚未计算</span>'

    confirmed_at = _text(board.get("confirmed_at")).strip()
    confirmed_by = _text(board.get("confirmed_by")).strip()
    receipt_origin = _text(board.get("receipt_origin")).strip()
    if confirmed:
        receipt = " · ".join(part for part in (confirmed_by or "未知确认人", confirmed_at or "时间未知", receipt_origin) if part)
    else:
        receipt = "尚未确认"

    if not code:
        hint = (
            "确认码尚未生成：先运行 "
            f"<code>python tools/design_board.py render --workspace .{_e(suffix)}</code>，"
            "render 会计算 board_sha256 并把 4 位确认码写回 JSON，重新打开本页即可看到。"
        )
    elif confirmed:
        hint = (
            f"{_e(gate_label)}已确认：该闸门已开，AI 可以继续下一步。"
            if gate
            else "确认已完成：闸门已开，AI 可以进入建模阶段。"
        )
    else:
        hint = (
            "核对完本页内容后，<b>由你本人</b>在终端运行 "
            f"<code>python tools/design_board.py confirm --workspace .{_e(suffix)} --apply</code> "
            "并输入上面的 4 位码；AI 不得代跑此命令。"
        )

    rows = [
        f"<dt>状态</dt><dd>{state}</dd>",
        f"<dt>确认码来源</dt><dd>board_sha256 前 4 位（大写）· {hash_cell}</dd>",
        f"<dt>确认回执</dt><dd>{_e(receipt)}</dd>",
    ]
    return (
        '<section class="confirm card" id="confirm" aria-labelledby="confirm-h">'
        '<div class="confirm-bar" aria-hidden="true"></div>'
        '<div class="confirm-inner">'
        '<div class="confirm-main">'
        f'<div class="confirm-kicker" id="confirm-h">确认码 · CONFIRM CODE'
        f'{" · " + _e(gate_label) if gate_label else ""}</div>'
        f"{code_html}"
        '<p class="confirm-note"><strong>AI 不得代填此码</strong>；'
        "确认后才会进入建模阶段。</p>"
        "</div>"
        '<div class="confirm-side">'
        f'<dl class="kv">{"".join(rows)}</dl>'
        f'<div class="confirm-hint"><p class="confirm-note muted">{hint}</p></div>'
        "</div>"
        "</div>"
        "</section>"
    )


# ---------------------------------------------------------------------------
# 01 结论速览 / 02 模型结构 / 03 待决项
# ---------------------------------------------------------------------------


def _section(number: str, anchor: str, heading: str, body: str, *, hint: str = "") -> str:
    """统一的 section 外壳（编号 + 锚点 + 可选提示）。"""
    hint_html = f'<span class="sec-hint">{_e(hint)}</span>' if hint else ""
    return (
        f'<section id="{anchor}" aria-labelledby="{anchor}-h">'
        f'<div class="sec-head"><span class="sec-num">{_e(number)}</span>'
        f'<h2 id="{anchor}-h">{_e(heading)}</h2>{hint_html}</div>'
        f"{body}</section>"
    )


def _render_overview(
    board: dict,
    questions: list[dict],
    number: str = "01",
    gate: str | None = None,
) -> str:
    """01 结论速览：每题当前选择的紧凑表格 + 题目小问清单。

    B 板把"一句话理由"换成"总分 + 建议"：选型看的是分数与建议结论。
    """
    summary = _as_dict(board.get("problem_summary"))
    parts: list[str] = []
    summary_questions = [item for item in _as_list(summary.get("questions")) if _present(item)]
    if summary_questions:
        listed = "".join(f"<li>{_e(_text(item))}</li>" for item in summary_questions)
        parts.append(f'<ul class="qlist">{listed}</ul>')

    if not questions:
        parts.append(
            '<div class="empty">决策板里没有 questions：请先在 design_board.json 里'
            "为至少一个小问生成 2 个以上候选方案。</div>"
        )
        return _section(number, "overview", "结论速览", "".join(parts), hint="3 秒读完")

    rows: list[list[str]] = []
    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        goal = _clip(question.get("goal"), 46)
        chosen = _find_option(question, question.get("user_choice"))
        if chosen is None:
            chosen_cell = '<span class="muted">（尚未选择）</span>'
        else:
            option_id = _text(chosen.get("id")).strip()
            name = _text(chosen.get("name")).strip() or "（未命名方案）"
            chosen_cell = f'<b>{_e(option_id)} · {_e(name)}</b>'
        id_cell = f'<b class="mono">{_e(question_id)}</b>'
        if goal:
            id_cell += f'<div class="cell-sub">{_e(goal)}</div>'
        if gate == "b":
            candidate = _advice_candidates(_advice_for(board, question)).get(
                _text(chosen.get("id")).strip(), {}
            ) if chosen else {}
            rows.append([
                id_cell,
                chosen_cell,
                _score_html(chosen, candidate) if chosen else '<span class="muted">—</span>',
                _verdict_badge(chosen, candidate) if chosen else '<span class="muted">—</span>',
                _status_badges(question),
            ])
            continue
        rationale = _clip(chosen.get("rationale"), 60) if chosen else ""
        rationale_cell = _e(rationale) if rationale else '<span class="muted">—</span>'
        rows.append([id_cell, chosen_cell, rationale_cell, _status_badges(question)])

    if gate == "b":
        table = _table(
            ["题号", "选定方案", "总分", "建议", "状态"],
            rows,
            caption="结论速览：每个小问当前选定的方案",
        )
    else:
        table = _table(
            ["题号", "选定方案", "一句话理由", "状态"],
            rows,
            caption="结论速览：每个小问当前选定的方案",
        )
    parts.append(table)
    return _section(number, "overview", "结论速览", "".join(parts), hint="3 秒读完")


def _render_pending_callout(board: dict) -> str:
    """board 级附加待决项（``pending_decisions``），没有就返回空串。"""
    pending = [item for item in _as_list(board.get("pending_decisions")) if _present(item)]
    if not pending:
        return ""
    items = "".join(f"<li>{_e(_clip(_text(item), 160))}</li>" for item in pending)
    return (
        '<div class="callout callout-warn"><div>'
        f"<b>附加待决项（{len(pending)} 项）</b>"
        f'<ul class="pending-list">{items}</ul>'
        "</div></div>"
    )


def _render_question_block(question: dict, index: int) -> str:
    """单个小问：目标 + 状态徽章 + 用户批注 + 候选卡片组。"""
    question_id = _question_id(question, index)
    goal = _text(question.get("goal")).strip() or "（未填写 goal）"
    options = _options(question)
    meta = _status_badges(question)
    meta += f'<span class="pill">{len(options)} 个候选</span>'

    fragments = [
        '<div class="q-block">',
        f'<div class="q-head"><span class="q-id">{_e(question_id)}</span>'
        f"<h3>{_e(goal)}</h3></div>",
        f'<div class="q-meta">{meta}</div>',
    ]
    comment = _text(question.get("user_comment")).strip()
    if comment:
        fragments.append(
            '<div class="callout callout-brand q-comment"><div>'
            f"<b>你的批注</b><br>{_e(comment)}</div></div>"
        )
    fragments.append('<div class="opts">')
    for option_index, option in enumerate(options):
        fragments.append(_render_option_card(question, option, option_index))
    fragments.append("</div></div>")
    return "".join(fragments)


def _render_option_card(question: dict, option: dict, index: int) -> str:
    """一张候选卡片：推荐度 / 理由 / 复杂度·依赖·风险 / 试算 / 来源。"""
    option_id = _option_id(option, index)
    chosen = _text(question.get("user_choice")).strip() == option_id
    locked = question.get("user_locked") is True

    tags = [_tier_badge(option)]
    if locked:
        tags.append(_badge("🔒 已锁定", "warn"))
    rationale = _text(option.get("rationale")).strip() or "（未给出选择理由）"

    rows = [
        f"<dt>复杂度</dt><dd>{_e(_text(option.get('complexity')).strip() or '未给出')}</dd>",
        f"<dt>依赖</dt><dd>{_e(_dependencies_text(option))}</dd>",
        f"<dt>主要风险</dt><dd class=\"risk\">{_e(_text(option.get('risk')).strip() or '未给出')}</dd>",
    ]
    classes = "opt picked" if chosen else "opt"
    aria = f"候选 {option_id}：{_text(option.get('name')).strip() or '未命名方案'}"
    return (
        f'<article class="{classes}" aria-label="{_attr(aria)}">'
        f'<div class="opt-top">{_option_heading(option, index)}{"".join(tags)}</div>'
        f'<p class="opt-why">{_e(rationale)}</p>'
        f'<dl class="kv">{"".join(rows)}</dl>'
        f"{_trial_block(option)}"
        f"{_source_block(option)}"
        "</article>"
    )


def _render_options(
    board: dict,
    questions: list[dict],
    number: str = "03",
    gate: str | None = None,
) -> str:
    """03 待决项：附加待决项 + 每题候选卡片组。"""
    parts = [_render_pending_callout(board)]
    if not questions:
        parts.append(
            '<div class="empty">没有可比较的候选方案：请在 design_board.json 的 questions'
            "里补上每个小问的 options（至少“推荐 + 备选”两个）。</div>"
        )
    elif gate == "a" and not any(_options(question) for question in questions):
        # A 板 schema v2：候选留空是合法的，选型在 B 闸门。
        parts.append(
            '<div class="empty">A 闸门不列模型候选：本板只确认题意框架与待探索范式集合，'
            "具体模型在 B 闸门（Phase 1.5）对比后由你择定。</div>"
        )
    else:
        parts.extend(_render_question_block(question, index) for index, question in enumerate(questions))
    hint = "AI 只提供对比，选择权在你"
    return _section(number, "options", "待决项与候选方案", "".join(parts), hint=hint)


# ---------------------------------------------------------------------------
# 04 候选方案对比表 / 05 已锁定
# ---------------------------------------------------------------------------


def _render_compare(
    board: dict,
    questions: list[dict],
    number: str = "04",
    gate: str | None = None,
) -> str:
    """04 候选方案对比表：A 板看推荐度与风险，B 板看分数与专属指标。"""
    if not questions:
        return _section(
            number,
            "compare",
            "候选方案对比",
            '<div class="empty">没有候选方案可对比。</div>',
            hint="推荐项整行浅绿",
        )
    if gate == "b":
        return _render_compare_gate_b(board, questions, number)
    parts: list[str] = [
        '<p class="muted" style="font-size:13px;margin-bottom:14px">'
        "先看推荐度与主要风险，再核对试算是否为真实数值（应附复跑命令）。"
        "浅绿行 = AI 推荐项，不代表最终选择。</p>"
    ]
    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        goal = _clip(question.get("goal"), 70)
        parts.append(
            f'<div class="sub-head"><span class="mono">{_e(question_id)}</span>'
            f"<h3>{_e(goal or '（未填写 goal）')}</h3></div>"
        )
        rows: list[list[str]] = []
        row_classes: list[str] = []
        for option_index, option in enumerate(_options(question)):
            option_id = _option_id(option, option_index)
            name = _text(option.get("name")).strip() or "（未命名方案）"
            chosen = _text(question.get("user_choice")).strip() == option_id
            mark = "✓ " if chosen else ""
            rows.append([
                f'<b class="mono">{_e(option_id)}</b> {_e(name)}'
                + (f' <span class="badge badge-ok">✓ 已选</span>' if chosen else ""),
                _tier_badge(option),
                _e(_clip(option.get("complexity"), 42) or "—"),
                f'<span class="risk">{_e(_clip(option.get("risk"), 46) or "—")}</span>',
                _trial_inline(option),
                _source_cell(option),
            ])
            row_classes.append("row-rec" if _tier_key(option) == "recommended" else "")
        parts.append(
            _table(
                ["方案", "推荐度", "复杂度", "主要风险", "试算", "来源"],
                rows,
                caption=f"{question_id} 的候选方案对比",
                row_classes=row_classes,
            )
        )
    hint = f"共 {len(questions)} 题"
    return _section(number, "compare", "候选方案对比", "".join(parts), hint=hint)


def _render_compare_gate_b(board: dict, questions: list[dict], number: str) -> str:
    """B 板的候选对比表：建议结论 + 总分 + 专属指标 + 试算回溯。"""
    parts: list[str] = [
        '<p class="muted" style="font-size:13px;margin-bottom:14px">'
        "总分来自建议 Agent；专属指标（own）只在同一候选的不同切片之间可比，"
        "横向比较只看可比层（见「数据对比」）。浅绿行 = 建议项，不代表最终选择。</p>"
    ]
    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        goal = _clip(question.get("goal"), 70)
        advice = _advice_for(board, question)
        candidates = _advice_candidates(advice)
        rubric = _as_dict(advice.get("scoring_rubric"))
        parts.append(
            f'<div class="sub-head"><span class="mono">{_e(question_id)}</span>'
            f"<h3>{_e(goal or '（未填写 goal）')}</h3></div>"
        )
        rows: list[list[str]] = []
        row_classes: list[str] = []
        for option_index, option in enumerate(_options(question)):
            option_id = _option_id(option, option_index)
            name = _text(option.get("name")).strip() or "（未命名方案）"
            candidate = candidates.get(option_id, {})
            chosen = _text(question.get("user_choice")).strip() == option_id
            own = _as_dict(candidate.get("own"))
            own_text = "、".join(f"{key}={_text(value)}" for key, value in own.items()) or "—"
            refs = _bullet_list(candidate.get("evidence_refs"))
            rows.append([
                f'<b class="mono">{_e(option_id)}</b> {_e(name)}'
                + (f' <span class="badge badge-ok">✓ 已选</span>' if chosen else ""),
                _verdict_badge(option, candidate),
                _score_html(option, candidate),
                _dims_html(candidate, rubric),
                f'<span class="mono">{_e(_clip(own_text, 46))}</span>',
                f'<span class="mono">{_e(_clip(refs[0], 46)) if refs else "—"}</span>',
            ])
            row_classes.append("row-rec" if _verdict_key(option, candidate) == "recommended" else "")
        parts.append(
            _table(
                ["方案", "建议", "总分", "维度分", "专属指标", "回溯"],
                rows,
                caption=f"{question_id} 的候选方案对比（B 闸门）",
                row_classes=row_classes,
            )
        )
    hint = f"共 {len(questions)} 题"
    return _section(number, "compare", "候选方案对比", "".join(parts), hint=hint)


def _render_locked(questions: list[dict], number: str = "05", gate: str | None = None) -> str:
    """05 已锁定：user_locked == true 的项，明确"AI 不得推翻"。

    A 板（schema v2）**不再承载模型选型**，因此整节改为"本板不锁定模型选型"空态；
    旧板（未声明 gate）保持原样，避免既有样例逐字节漂移。
    """
    if gate == "a":
        return _render_locked_gate_a(questions, number)
    locked = [question for question in questions if question.get("user_locked") is True]
    if not locked:
        return _section(
            number,
            "locked",
            "已锁定事项",
            '<div class="empty">暂无锁定项（所有 <code>user_locked</code> 均为 false）。</div>',
            hint="AI 不得推翻",
        )
    callout = (
        '<div class="callout callout-warn"><div><b>以下事项 AI 不得推翻。</b>'
        "若要变更，必须回到决策板重新走一轮并重新确认；AI 不得自行改选。</div></div>"
    )
    rows: list[list[str]] = []
    # 保留原始小问序号，避免"id 缺失时按筛选后序号退化成 Q1"这种误导
    for index, question in enumerate(questions):
        if question.get("user_locked") is not True:
            continue
        question_id = _question_id(question, index)
        chosen = _find_option(question, question.get("user_choice"))
        if chosen is None:
            choice_cell = '<span class="muted">（锁定但未选择）</span>'
        else:
            choice_cell = (
                f'<b>{_e(_text(chosen.get("id")).strip())} · '
                f'{_e(_text(chosen.get("name")).strip() or "（未命名方案）")}</b>'
            )
        comment = _clip(question.get("user_comment"), 100)
        rows.append([
            f'<b class="mono">{_e(question_id)}</b>',
            f"{_e(_text(question.get('goal')).strip() or '（未填写 goal）')}",
            choice_cell,
            _e(comment) if comment else '<span class="muted">—</span>',
            _badge("AI 不得推翻", "warn"),
        ])
    table = _table(
        ["小问", "锁定项", "你的选择", "你的批注", "声明"],
        rows,
        caption="已锁定事项：AI 不得推翻",
    )
    hint = f"{len(locked)} 项"
    return _section(number, "locked", "已锁定事项", callout + table, hint=hint)


def _render_locked_gate_a(questions: list[dict], number: str) -> str:
    """A 板的"不锁定"空态：A 闸门只确认框架与范式集合，不锁模型选型。"""
    offending = [question for question in questions if question.get("user_locked") is True]
    body = (
        '<div class="empty"><b>本板不锁定模型选型。</b><br>'
        "A 闸门只确认题意框架、高严重度假设与待探索范式集合；具体用哪个模型由 "
        "B 闸门（Phase 1.5）择定。任何 user_locked 都会被 checker 判为 "
        "<code>gate_a_user_locked_forbidden</code>。</div>"
    )
    if offending:
        ids = "、".join(_question_id(question, index) for index, question in enumerate(questions)
                        if question.get("user_locked") is True)
        body += (
            '<div class="callout callout-danger"><div>'
            f"<b>检测到 {len(offending)} 项 user_locked: true（{_e(ids)}）。</b><br>"
            "A 板必须把它们改回 false，否则闸门判不通过。</div></div>"
        )
    return _section(number, "locked", "本板不锁定模型选型", body, hint="A 闸门不选型")


def _render_paradigm(board: dict, questions: list[dict], number: str = "02") -> str:
    """A 板新增：待探索范式集合（范式 / 方法族 / 来源 / 探索成本 / 为什么探索）。"""
    parts: list[str] = [
        '<p class="muted" style="font-size:13px;margin-bottom:14px">'
        "这是探索边界，不是最终方案：只有 paradigm_selection 里的范式才会进入 Phase 1 "
        "五视角深挖；具体模型在 B 闸门比较后由你择定。</p>"
    ]
    if not _has_paradigms(questions):
        parts.append(
            '<div class="empty">本板没有 paradigm_set（旧板 schema）。'
            "A 闸门 schema v2 要求每问 3–5 个待探索范式，并在 paradigm_selection 里勾选子集。</div>"
        )
        return _section(number, "paradigm", "待探索范式集合", "".join(parts), hint="A 闸门不选型")

    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        goal = _clip(question.get("goal"), 70)
        paradigms = _paradigms(question)
        if not paradigms:
            continue
        selection = [_text(item).strip() for item in _as_list(question.get("paradigm_selection"))]
        selection = [item for item in selection if item]
        parts.append(
            f'<div class="sub-head"><span class="mono">{_e(question_id)}</span>'
            f"<h3>{_e(goal or '（未填写 goal）')}</h3></div>"
        )
        if selection:
            chips = "".join(
                f'<span class="pick-mark">✓ {_e(item)}</span>' for item in selection
            )
            parts.append(f'<p class="muted" style="font-size:13px">已选范式：{chips}</p>')
        else:
            parts.append(
                '<p class="muted" style="font-size:13px">已选范式：'
                '<span class="badge badge-warn">尚未选择</span> '
                "paradigm_selection 为空，请在回执里勾选（≥2 项且至少含 1 个异质族）。</p>"
            )
        rows: list[list[str]] = []
        families: dict[str, int] = {}
        for paradigm in paradigms:
            family = _text(paradigm.get("family")).strip()
            families[family] = families.get(family, 0) + 1
        for paradigm in paradigms:
            paradigm_id = _text(paradigm.get("paradigm_id")).strip() or "—"
            name = _text(paradigm.get("name")).strip() or "（未命名范式）"
            family = _text(paradigm.get("family")).strip() or "未标"
            source = _as_dict(paradigm.get("source_ref"))
            tier = _text(source.get("tier")).strip()
            picked = paradigm_id in selection
            id_cell = f'<b class="mono">{_e(paradigm_id)}</b>'
            if picked:
                id_cell += ' <span class="pick-mark">✓</span>'
            source_cell = (
                f'<span class="mono">{_e(_source_headline(source))}</span>'
                + (f' <span class="muted">· {_e(tier)}</span>' if tier else "")
                + " "
                + _verified_badge(source)
            )
            rows.append([
                id_cell,
                f'<b>{_e(name)}</b>',
                f'<span class="paradigm-family">{_e(family)}</span>',
                source_cell,
                _cost_html(paradigm),
                _e(_clip(paradigm.get("why_explore"), 120) or "—"),
            ])
        parts.append(
            _table(
                ["范式", "名称", "方法族", "来源 / tier / 核验", "探索成本", "为什么探索"],
                rows,
                caption=f"{question_id} 的待探索范式集合",
            )
        )
        if len(families) <= 1 and len(paradigms) >= 2:
            parts.append(
                '<div class="callout callout-warn"><div>'
                "<b>方法族过于单一。</b>每问至少要有一个 family 与其余不同（契约 §4 硬规则 4），"
                "否则五视角会收敛到同一条思路。</div></div>"
            )
        parts.append("")
    hint = f"{len(questions)} 题"
    return _section(number, "paradigm", "待探索范式集合", "".join(parts), hint=hint)


def _render_advice(board: dict, questions: list[dict], number: str = "02") -> str:
    """B 板核心：候选分数与维度分、每模型 pros/cons、why_not 与 when_better。"""
    parts: list[str] = []
    advice_any = next((_advice_for(board, question) for question in questions if _advice_for(board, question)), {})
    is_judge = advice_any.get("is_judge_panel")
    disclaimer = _text(advice_any.get("disclaimer")).strip()
    if not advice_any:
        parts.append(
            '<div class="callout callout-warn"><div><b>本板没有嵌入 advice。</b><br>'
            "B 板应当把 model_advice.json 的内容嵌进每题 advice，"
            "否则分数、优缺点与数据对比都无从核对。</div></div>"
        )
    else:
        parts.append(
            '<div class="callout callout-warn"><div>'
            '<b>这是选型建议，不是评委审查。</b>'
            f"{(' ' + _e(disclaimer)) if disclaimer else ''}"
            f"<br>{_badge('评委审查在 Phase 4', 'muted', mono=True)}</div></div>"
        )
        if is_judge is True:
            parts.append(
                '<div class="callout callout-danger"><div>'
                "<b>advice 自称评委结论（is_judge_panel=true）。</b><br>"
                "B 板只是选型建议，checker 会判 advice_is_not_judge_panel。</div></div>"
            )

    rubric = _as_dict(advice_any.get("scoring_rubric"))
    dimensions = _as_list(rubric.get("dimensions"))
    if dimensions:
        rubric_rows: list[list[str]] = []
        for dimension in dimensions:
            if not isinstance(dimension, dict):
                continue
            weight = dimension.get("weight")
            rubric_rows.append([
                f'<span class="mono">{_e(_text(dimension.get("id")).strip() or "—")}</span>',
                _e(_text(dimension.get("name")).strip() or "—"),
                _e(f"{weight:g}" if isinstance(weight, (int, float)) and not isinstance(weight, bool) else "—"),
            ])
        parts.append(
            _table(
                ["维度", "名称", "权重"],
                rubric_rows,
                caption="建议 Agent 的评分口径",
            )
        )

    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        goal = _clip(question.get("goal"), 70)
        advice = _advice_for(board, question)
        candidates = _advice_candidates(advice)
        options = _options(question)
        parts.append(
            f'<div class="sub-head"><span class="mono">{_e(question_id)}</span>'
            f"<h3>{_e(goal or '（未填写 goal）')}</h3></div>"
        )
        if not options:
            parts.append('<div class="empty">本题没有候选项（B 板要求 5–8 个候选）。</div>')
            continue
        score_rows: list[list[str]] = []
        row_classes: list[str] = []
        for option_index, option in enumerate(options):
            option_id = _option_id(option, option_index)
            candidate = candidates.get(option_id, {})
            chosen = _text(question.get("user_choice")).strip() == option_id
            name = _text(option.get("name")).strip() or "（未命名方案）"
            origin = _text(candidate.get("origin") or option.get("origin")).strip() or "—"
            paradigm_id = _text(candidate.get("paradigm_id") or option.get("paradigm_id")).strip() or "—"
            score_rows.append([
                f'<b class="mono">{_e(option_id)}</b> {_e(name)}'
                + (f' <span class="badge badge-ok">✓ 已选</span>' if chosen else ""),
                _verdict_badge(option, candidate),
                _score_html(option, candidate),
                _dims_html(candidate, rubric),
                f'<span class="mono">{_e(origin)}</span>',
                f'<span class="mono">{_e(paradigm_id)}</span>',
            ])
            row_classes.append("row-rec" if _verdict_key(option, candidate) == "recommended" else "")
        parts.append(
            _table(
                ["方案", "建议", "总分", "维度分", "来源视角", "范式"],
                score_rows,
                caption=f"{question_id} 的候选分数",
                row_classes=row_classes,
            )
        )
        for option_index, option in enumerate(options):
            option_id = _option_id(option, option_index)
            candidate = candidates.get(option_id, {})
            if not candidate:
                continue
            parts.append(_render_advice_card(option, candidate, option_id))
        note = _text(advice.get("aggregate_note")).strip()
        if note:
            parts.append(
                '<div class="callout callout-brand"><div>'
                f"<b>汇总说明</b><br>{_e(note)}</div></div>"
            )
    hint = "分数不是评委结论"
    return _section(number, "advice", "建议与评分", "".join(parts), hint=hint)


def _render_advice_card(option: dict, candidate: dict, option_id: str) -> str:
    """单个候选的建议卡片：pros / cons / why_not / when_better / 证据。"""
    name = _text(option.get("name")).strip() or "（未命名方案）"
    verdict = _verdict_key(option, candidate)
    classes = "adv adv-rec" if verdict == "recommended" else "adv"
    pros = _bullet_list(candidate.get("pros"))
    cons = _bullet_list(candidate.get("cons"))
    why_not = _bullet_list(candidate.get("why_not"))
    when_better = _text(candidate.get("when_better")).strip()
    evidence = _bullet_list(candidate.get("evidence_refs"))

    body: list[str] = [
        f'<div class="adv-head">{_verdict_badge(option, candidate)}'
        f'<h4><span class="mono">{_e(option_id)}</span> · {_e(name)}</h4>'
        f"{_score_html(option, candidate)}</div>"
    ]
    if pros or cons:
        body.append('<div class="pc">')
        body.append(
            '<div class="pc-col pc-pro"><b>优点</b>'
            + (f'<ul>{"".join(f"<li>{_e(item)}</li>" for item in pros)}</ul>' if pros else
               '<div class="muted" style="font-size:13px">未给出优点</div>')
            + "</div>"
        )
        body.append(
            '<div class="pc-col pc-con"><b>缺点</b>'
            + (f'<ul>{"".join(f"<li>{_e(item)}</li>" for item in cons)}</ul>' if cons else
               '<div class="muted" style="font-size:13px">未给出缺点</div>')
            + "</div>"
        )
        body.append("</div>")
    if why_not:
        body.append(
            '<div class="why-not"><b>为什么不建议</b><ul>'
            + "".join(f"<li>{_e(item)}</li>" for item in why_not)
            + "</ul></div>"
        )
    if when_better:
        body.append(
            f'<div class="when-better"><b>什么情况下它更好</b><br>{_e(when_better)}</div>'
        )
    if evidence:
        chips = "".join(f'<span class="chip"><i>证据</i>=<b>{_e(item)}</b></span>' for item in evidence)
        body.append(f'<div class="chips" style="margin-top:8px">{chips}</div>')
    return f'<article class="{classes}">{"".join(body)}</article>'


def _render_data_comparison(board: dict, questions: list[dict], number: str = "03") -> str:
    """B 板：多组数据对比（可比层列的横向对比 + 专属层 + baseline 参照行）。"""
    parts: list[str] = [
        '<p class="muted" style="font-size:13px;margin-bottom:14px">'
        "可比层（comparable）是唯一允许横向比较的层；专属层（own）只在同一候选的不同切片之间可比。"
        "baseline 行只作参照，不占候选名额。</p>"
    ]
    rendered = False
    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        advice = _advice_for(board, question)
        comparison = _as_dict(advice.get("data_comparison"))
        rows = [row for row in _as_list(comparison.get("rows")) if isinstance(row, dict)]
        baseline = _as_dict(comparison.get("baseline_row")) or None
        if not rows and not baseline:
            continue
        rendered = True
        parts.append(
            f'<div class="sub-head"><span class="mono">{_e(question_id)}</span>'
            f"<h3>{_e(_clip(question.get('goal'), 70) or '（未填写 goal）')}</h3></div>"
        )
        columns = [_text(item).strip() for item in _as_list(comparison.get("comparable_columns"))]
        columns = [item for item in columns if item]
        pool = rows + ([baseline] if baseline else [])
        if not columns:
            for row in pool:
                for key in _as_dict(row.get("comparable")):
                    if key not in columns:
                        columns.append(key)
        slice_ids: list[str] = []
        for row in pool:
            slice_id = _text(row.get("slice_id")).strip()
            if slice_id and slice_id not in slice_ids:
                slice_ids.append(slice_id)
        for slice_id in slice_ids:
            table_rows: list[list[str]] = []
            row_classes: list[str] = []
            for row in rows:
                if _text(row.get("slice_id")).strip() != slice_id:
                    continue
                comparable = _as_dict(row.get("comparable"))
                own = _as_dict(row.get("own"))
                option_id = _text(row.get("option_id")).strip() or "—"
                chosen = _text(question.get("user_choice")).strip() == option_id
                table_rows.append([
                    f'<b class="mono">{_e(option_id)}</b>'
                    + (' <span class="badge badge-ok">✓ 已选</span>' if chosen else ""),
                    *[
                        _e(_text(comparable.get(column)) or "—") if column in comparable
                        else '<span class="muted">—</span>'
                        for column in columns
                    ],
                    "、".join(f"{_e(key)}={_e(value)}" for key, value in own.items()) or "—",
                    f'<span class="mono">{_e(_text(row.get("trials_ref")).strip() or "—")}</span>',
                ])
                row_classes.append("")
            if baseline and _text(baseline.get("slice_id")).strip() == slice_id:
                comparable = _as_dict(baseline.get("comparable"))
                table_rows.append([
                    f'{_e(_text(baseline.get("option_id")).strip() or "baseline")}（参照）',
                    *[
                        _e(_text(comparable.get(column)) or "—") if column in comparable
                        else '<span class="muted">—</span>'
                        for column in columns
                    ],
                    "—",
                    '<span class="muted">—</span>',
                ])
                row_classes.append("row-base")
            parts.append(f'<div class="slice-head">切片 {_e(slice_id)}</div>')
            parts.append(
                _table(
                    ["候选", *columns, "专属指标（own）", "回溯"],
                    table_rows,
                    caption=f"{question_id} 在切片 {slice_id} 上的实测数据",
                    row_classes=row_classes,
                )
            )
    if not rendered:
        parts.append(
            '<div class="empty">本板未嵌入 data_comparison：请先由 perspective_trial_runner '
            "产出 perspective_trials.json，再由 model_advice_builder 生成多组数据对比。</div>"
        )
    return _section(number, "data", "多组数据对比（工具实跑）", "".join(parts), hint="可比层才可横比")


# ---------------------------------------------------------------------------
# 06 题意歧义 / 07 来源速查
# ---------------------------------------------------------------------------


def _render_ambiguities(board: dict, number: str = "06") -> str:
    """06 未解决的题意歧义：红色警示卡片；已解决的收进折叠区。"""
    summary = _as_dict(board.get("problem_summary"))
    ambiguities = [item for item in _as_list(summary.get("key_ambiguities")) if isinstance(item, dict)]
    unresolved = [item for item in ambiguities if item.get("resolved") is not True]
    resolved = [item for item in ambiguities if item.get("resolved") is True]

    if not ambiguities:
        return _section(
            number,
            "ambiguities",
            "题意歧义",
            '<div class="empty">题意审计没有登记歧义项。若题目里确有可分叉的表述，'
            "建议回到 Phase 0 题意审计补录后再确认。</div>",
            hint="0 项待确认",
        )

    parts: list[str] = []
    for position, item in enumerate(unresolved, start=1):
        ambiguity_id = _text(item.get("id")).strip() or f"A{position}"
        severity_key = _text(item.get("severity")).strip().lower()
        severity = SEVERITY_LABELS.get(severity_key, severity_key or "未标")
        severity_badge = _badge(
            f"严重度 {severity}", SEVERITY_BADGE_KIND.get(severity_key, "muted")
        )
        issue = _text(item.get("issue")).strip() or "（未填写 issue）"
        assumed = _text(item.get("assumed_as")).strip()
        resolution = _text(item.get("resolution")).strip()
        assumption_html = ""
        if assumed:
            assumption_html = f'<p class="alert-sub">当前暂按：<b>{_e(assumed)}</b></p>'
        elif resolution:
            assumption_html = f'<p class="alert-sub">当前写法：<b>{_e(resolution)}</b></p>'
        confirm_badge = (
            _badge("需你确认", "warn") if item.get("needs_user_confirm") is not False else ""
        )
        parts.append(
            '<div class="callout callout-danger"><div>'
            '<div class="alert-head">'
            f'{_badge("未解决", "danger")}<b>{_e(ambiguity_id)}</b>'
            f"{severity_badge}{confirm_badge}</div>"
            f'<div class="alert-title">{_e(issue)}</div>'
            f"{assumption_html}"
            '<p class="alert-sub">若你的理解与上面不同，请在确认前告诉 AI；'
            "确认之后再改假设会推翻已经写下的模型。</p>"
            "</div></div>"
        )
    if not unresolved:
        parts.append(
            '<div class="callout callout-ok"><div>'
            f"<b>没有未解决的题意歧义</b>：{len(ambiguities)} 项均已记录结论。</div></div>"
        )
    if resolved:
        rows = []
        for position, item in enumerate(resolved, start=1):
            ambiguity_id = _text(item.get("id")).strip() or f"A{position}"
            severity_key = _text(item.get("severity")).strip().lower()
            rows.append([
                f'<b class="mono">{_e(ambiguity_id)}</b>',
                _e(SEVERITY_LABELS.get(severity_key, severity_key or "未标")),
                _e(_text(item.get("issue")).strip() or "—"),
                _e(
                    _text(item.get("resolution")).strip()
                    or _text(item.get("assumed_as")).strip()
                    or "—"
                ),
            ])
        table = _table(["编号", "严重度", "问题", "结论"], rows, caption="已解决的题意歧义")
        parts.append(
            "<details><summary>已解决的歧义 "
            f"{len(resolved)} 项（展开看结论）</summary>"
            f'<div class="inner">{table}</div></details>'
        )
    hint = f"{len(unresolved)} 项待确认" if unresolved else "全部已解决"
    return _section(number, "ambiguities", "题意歧义", "".join(parts), hint=hint)


def _render_sources(
    questions: list[dict],
    number: str = "07",
    gate: str | None = None,
) -> str:
    """07 来源速查：把所有候选的 source_ref 汇总成折叠表格。

    A 板的候选通常为空（选型在 B 闸门），来源挂在 paradigm_set 上，
    因此 A 板同时汇总范式来源，避免"来源速查一片空白"的误导。
    """
    rows: list[list[str]] = []
    if gate == "a":
        for index, question in enumerate(questions):
            question_id = _question_id(question, index)
            for paradigm in _paradigms(question):
                source = _as_dict(paradigm.get("source_ref"))
                note = _clip(source.get("note"), 70)
                if source.get("verified") is False:
                    reason = _text(source.get("unverified_reason")).strip()
                    prefix = f"未核验原因：{_clip(reason, 50)}" if reason else "未核验原因：未填写"
                    note = f"{prefix}；{note}" if note else prefix
                paradigm_id = _text(paradigm.get("paradigm_id")).strip() or "—"
                name = _text(paradigm.get("name")).strip() or "（未命名范式）"
                rows.append([
                    f'<span class="mono">{_e(question_id)}</span>',
                    f"{_e(paradigm_id)} {_e(name)} {_badge('范式', 'brand')}",
                    _e(_text(source.get("type")).strip() or "—"),
                    _e(_text(source.get("ref")).strip() or "—"),
                    _e(_text(source.get("tier")).strip() or "—"),
                    _verified_badge(source) if source else '<span class="muted">—</span>',
                    _e(note) if note else '<span class="muted">—</span>',
                ])
    for index, question in enumerate(questions):
        question_id = _question_id(question, index)
        for option_index, option in enumerate(_options(question)):
            source = _source_ref(option)
            note = _clip(source.get("note"), 70)
            if source.get("verified") is False:
                reason = _text(source.get("unverified_reason")).strip()
                prefix = f"未核验原因：{_clip(reason, 50)}" if reason else "未核验原因：未填写"
                note = f"{prefix}；{note}" if note else prefix
            rows.append([
                f'<span class="mono">{_e(question_id)}</span>',
                _e(_option_title_text(option, option_index)),
                _e(_text(source.get("type")).strip() or "—"),
                _e(_text(source.get("ref")).strip() or "—"),
                _e(_text(source.get("tier")).strip() or "—"),
                _verified_badge(source) if source else '<span class="muted">—</span>',
                _e(note) if note else '<span class="muted">—</span>',
            ])
    if not rows:
        body = '<div class="empty">暂无来源登记（所有候选都没有 source_ref）。</div>'
        return _section(number, "sources", "来源速查", body, hint="默认折叠")
    table = _table(
        ["小问", "方案", "来源类型", "编号", "tier", "核验", "备注"],
        rows,
        caption="所有候选的来源汇总",
    )
    count_text = f"{len(rows)} 个候选" if not gate else f"{len(rows)} 项"
    body = (
        "<details><summary>展开："
        f"{count_text}的来源类型、编号、tier 与核验状态"
        "（默认折叠，避免淹没正文）</summary>"
        f'<div class="inner">{table}'
        '<p class="muted" style="font-size:12.5px;margin-top:10px">'
        "来源只提供“方法启发”，不复制原作品正文；"
        "未核验（verified=false）的方案在正文里会额外标红，不能当作已查证依据。</p>"
        "</div></details>"
    )
    return _section(number, "sources", "来源速查", body, hint="默认折叠")


# ---------------------------------------------------------------------------
# 08 板信息与轮次历史 / 页脚
# ---------------------------------------------------------------------------


def _change_text(change: dict) -> str:
    """把一条 ``history.changes[]`` 压成一句人话。"""
    path = _text(change.get("path")).strip() or "（未记录路径）"
    operation = _text(change.get("op")).strip()
    old = _clip(change.get("from"), 24)
    new = _clip(change.get("to"), 24)
    value = _clip(change.get("value"), 24)
    if operation == "added":
        return f"{path}：新增「{value or '（空）'}」"
    if operation == "removed":
        return f"{path}：删除「{old or '（空）'}」"
    if operation == "updated":
        return f"{path}：「{old or '（空）'}」→「{new or '（空）'}」"
    if old and new:
        return f"{path}：{old} → {new}"
    if new:
        return f"{path}：→ {new}"
    if old:
        return f"{path}：{old} →（空）"
    return path


def _render_meta(board: dict, number: str = "08") -> str:
    """08 板信息与轮次历史（折叠）：把唯一真实来源的关键字段摊开备查。"""
    hash_value = _text(board.get("board_sha256")).strip()
    if not hash_value:
        hash_cell = '<span class="muted">尚未计算（先运行 render）</span>'
    elif "placeholder" in hash_value.lower():
        hash_cell = f'<span class="hash">{_e(hash_value)}</span> {_badge("占位值", "warn")}'
    else:
        hash_cell = f'<span class="hash">{_e(hash_value)}</span> {_badge("已写入", "ok")}'

    pending = _as_list(board.get("pending_decisions"))
    rows = [
        f"<dt>决策板 ID</dt><dd>{_e(_text(board.get('board_id')).strip() or '未登记')}</dd>",
        f"<dt>schema_version</dt><dd>{_e(_text(board.get('schema_version')).strip() or '未登记')}</dd>",
        f"<dt>语言</dt><dd>{_e(_text(board.get('language')).strip() or '未登记')}</dd>",
        f"<dt>revision</dt><dd>{_e(_text(board.get('revision')).strip() or '0')}</dd>",
        f"<dt>连续无修改轮次</dt><dd>{_e(_text(board.get('no_change_rounds')).strip() or '0')}</dd>",
        f"<dt>board_sha256</dt><dd>{hash_cell}</dd>",
        f"<dt>创建时间</dt><dd>{_e(_text(board.get('created_at')).strip() or '未登记')}</dd>",
        f"<dt>确认时间</dt><dd>{_e(_text(board.get('confirmed_at')).strip() or '尚未确认')}</dd>",
        f"<dt>确认人 / 通道</dt><dd>{_e(_text(board.get('confirmed_by')).strip() or '—')}"
        f" / {_e(_text(board.get('receipt_origin')).strip() or '—')}</dd>",
        f"<dt>回执 nonce</dt><dd>{_e(_text(board.get('receipt_nonce')).strip() or '—')}</dd>",
        f"<dt>附加待决项</dt><dd>{len(pending)} 项</dd>",
    ]

    history = [item for item in _as_list(board.get("history")) if isinstance(item, dict)]
    history_html = ""
    if history:
        table_rows: list[list[str]] = []
        for position, record in enumerate(history, start=1):
            round_no = record.get("round")
            round_text = f"第 {_text(round_no)} 轮" if _present(round_no) else f"#{position}"
            at = _text(record.get("at")).strip() or "—"
            edited = record.get("user_edited")
            if edited is True:
                edited_cell = _badge("有改动", "brand")
            elif edited is False:
                edited_cell = _badge("无改动", "ok")
            else:
                edited_cell = '<span class="muted">—</span>'
            changes = [item for item in _as_list(record.get("changes")) if isinstance(item, dict)]
            if changes:
                summaries = "<br>".join(_e(_change_text(change)) for change in changes)
            else:
                summaries = '<span class="muted">无改动</span>'
            table_rows.append([
                _e(round_text),
                f'<span class="mono">{_e(at)}</span>',
                edited_cell,
                summaries,
            ])
        history_html = _table(
            ["轮次", "时间", "是否有改动", "改动摘要"],
            table_rows,
            caption="轮次历史",
        )
    else:
        history_html = '<div class="empty">暂无轮次历史（第一次渲染）。</div>'

    inner = f'<dl class="kv kv-wide">{"".join(rows)}</dl><div style="margin-top:16px">{history_html}</div>'
    return _section(
        number,
        "meta",
        "决策板元信息与轮次历史",
        f"<details><summary>展开：唯一真实来源的关键字段与每轮回执摘要</summary>"
        f'<div class="inner">{inner}</div></details>',
        hint="默认折叠",
    )


def _render_submit_panel(
    board: dict,
    questions: list[dict],
    number: str = "09",
    gate: str | None = None,
) -> str:
    """决策提交区：每题一组单选项 + 批注框 + 提交按钮。

    页面在两种环境下都能用：

    - **有本地服务器**（``design_board.py serve``）：提交后直接 POST 回执，写入
      ``design_rounds/round_NNN.json``，页面显示轮次与改动摘要；
    - **无服务器**（直接双击打开 file:// 页面）：POST 必然失败，自动降级为下载
      ``design_board_submission.json``，再由人跑 ``ingest --from`` 读回。

    选项与批注即时写进 ``localStorage``（键按 ``board_id`` 区分），刷新或误关页面不丢。
    磁盘上的 HTML 里 token 是字面量占位符，由 ``serve`` 每次请求替换成真 token；
    直接打开文件时它不会被替换，POST 也就必然被服务器拒绝——这是有意的。
    """
    board_id = _text(board.get("board_id")).strip()
    confirmed = _board_confirmed(board)

    blocks: list[str] = []
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue
        qid = _text(question.get("id")).strip() or f"Q{index + 1}"
        goal = _text(question.get("goal")).strip()
        current = _text(question.get("user_choice")).strip()
        options = [opt for opt in _as_list(question.get("options")) if isinstance(opt, dict)]
        if not options:
            continue

        radios: list[str] = []
        for pos, option in enumerate(options):
            oid = _text(option.get("id")).strip() or f"O{pos + 1}"
            name = _text(option.get("name")).strip() or oid
            tier = _text(option.get("tier")).strip().lower()
            verdict = _verdict_key(option)
            tier_short = TIER_SHORT.get(tier, "") or {
                "recommended": "建议",
                "not_recommended": "不建议",
            }.get(verdict, "")
            checked = " checked" if oid == current else ""
            on_class = " on" if oid == current else ""
            tier_html = f'<span class="sp-tier">{_e(tier_short)}</span>' if tier_short else ""
            score = _score_of(option)
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                tier_html += f'<span class="sp-tier mono">{_e(_num_text(float(score)))}</span>'
            radios.append(
                f'<label class="sp-opt{on_class}" data-option="{_e(oid)}">'
                f'<input type="radio" name="mm-{_e(qid)}" value="{_e(oid)}"{checked}>'
                f"<span>{_e(name)}</span>{tier_html}"
                "</label>"
            )

        comment = _text(question.get("user_comment")).strip()
        blocks.append(
            f'<div class="sp-q" data-question="{_e(qid)}">'
            f'<div class="sp-q-title">{_e(qid)} · {_e(goal[:90])}</div>'
            f'<div class="sp-opts" role="radiogroup" aria-label="{_e(qid)} 候选方案">'
            + "".join(radios)
            + "</div>"
            f'<textarea class="sp-comment" data-question="{_e(qid)}" '
            'placeholder="给这个选择写一句批注（可留空）：例如「要求同时给出 LP 下界与 gap」">'
            f"{_e(comment)}</textarea>"
            "</div>"
        )

    if not blocks:
        if gate == "a":
            # A 板 schema v2 允许 options 为空：这时页面上没有可选项，
            # 但要把"范式集合在哪里确认"说清楚，避免以为页面坏了。
            return _section(
                number,
                "submit",
                "你的决策（范式集合）",
                '<div class="empty">本板没有模型候选项（A 闸门不选型）：'
                "要确认的是 paradigm_set 里勾选的范式子集（paradigm_selection）。"
                "请在终端核对后运行 confirm；若你要增删范式，改 JSON 后重新 render 再确认。</div>",
                hint="A 闸门只确认框架与范式",
            )
        return ""

    confirmed_note = (
        '<p class="sp-hint">本板已确认。若你改了选择，提交会生成新一轮回执，'
        "需要重新走一次确认；改选本身不改变方案哈希，AI 改了候选内容才会。</p>"
        if confirmed
        else '<p class="sp-hint">选好每题方案、写清批注后点提交。'
        "连续两轮不改动即可进入人工确认；确认码必须由你本人在终端输入，AI 不能代填。</p>"
    )

    return _section(
        number,
        "submit",
        "你的决策（在页面上直接选）",
        f'<div class="submit-panel" data-board-id="{_e(board_id)}"'
        f' data-token="{_e(SUBMIT_TOKEN_TEXT)}">'
        "<h3>提交回执</h3>"
        f"{confirmed_note}"
        + "".join(blocks)
        + '<div class="sp-actions">'
        '<button type="button" class="sp-btn" data-mm-submit>提交选择</button>'
        '<button type="button" class="sp-btn ghost" data-mm-download>下载回执 JSON</button>'
        '<button type="button" class="sp-btn ghost" data-mm-reset>清除本地暂存</button>'
        '<span class="sp-status" data-mm-status role="status" aria-live="polite"></span>'
        '<span class="sp-mode"><span class="sp-dot" data-mm-dot></span>'
        '<span data-mm-mode>检测中…</span></span>'
        "</div></div>",
        hint="也可以走 Excel / 命令行 ingest，三条通道等价",
    )


def _render_footer() -> str:
    """页脚：明确本 HTML 只是视图，不是唯一真实来源。"""
    return (
        "<footer>"
        f"<p>{_e(FOOTER_TEXT)}</p>"
        '<p class="foot-meta">本页零外链、可离线打开；打印时会自动展开折叠区。'
        "视图与 <code>design_board.json</code> 不一致时，一律以 JSON 为准。</p>"
        '<p class="backtop"><a href="#top">↑ 回到顶部</a></p>'
        "</footer>"
    )


# ---------------------------------------------------------------------------
# 自检 + 总装
# ---------------------------------------------------------------------------


def _style_block(markup: str) -> str:
    """取出 ``<style>`` 块内容（用于单独扫描 CSS 级外链）。"""
    match = re.search(r"<style>(?P<css>.*?)</style>", markup, re.DOTALL)
    return match.group("css") if match else ""


def _self_check(markup: str) -> None:
    """对渲染结果做零外链与体积体检，不通过直接抛 ``ValueError``。

    检查项：

    1. 输出里不得出现 :data:`FORBIDDEN_EXTERNAL` 任一片段（外链前缀 / ``<link`` /
       ``<script src``），命中就带上下文片段报错；
    2. ``<style>`` 块里不得出现 ``@import`` / ``url(``；
    3. 全文 UTF-8 字节数不得超过 :data:`MAX_INLINE_BYTES`。

    "外链"定义为会让浏览器再去取一次外部资源的引用。用户文本里出现的裸 URL 已经在
    :func:`_e` 里被打码成 HTML 实体（显示不变、源码不再含前缀），因此正常内容不会
    误伤；这里兜住的是模板/CSS 被改坏、或有人偷偷塞外部资源的情况。
    """
    hits: list[str] = []
    for token in FORBIDDEN_EXTERNAL:
        position = markup.find(token)
        if position < 0:
            continue
        start = max(0, position - 48)
        end = min(len(markup), position + len(token) + 48)
        snippet = re.sub(r"\s+", " ", markup[start:end]).strip()
        hits.append(f"{token!r} 附近：…{snippet}…")

    style = _style_block(markup)
    for token in FORBIDDEN_CSS:
        if token in style:
            hits.append(f"<style> 内出现 {token!r}（禁止外部或内嵌资源引用）")

    if hits:
        raise ValueError("HTML 输出违反零外链约束：" + "；".join(hits))

    size = len(markup.encode("utf-8"))
    if size > MAX_INLINE_BYTES:
        raise ValueError(
            f"HTML 输出 {size} 字节，超过 MAX_INLINE_BYTES={MAX_INLINE_BYTES}；"
            "通常说明内联了不该内联的内容（图片 base64 / 脚本 / 超长数据）。"
        )


def _nav_for(gate: str, board: dict, questions: list[dict]) -> tuple[tuple[str, str], ...]:
    """按闸门给出导航锚点（只列真正会渲染出来的小节）。"""
    if gate == "b":
        nav = list(NAV_LINKS_GATE_B)
        if _text(_as_dict(board.get("mindmap")).get("source")).strip():
            nav.insert(1, ("map", "导图"))
        return tuple(nav)
    return NAV_LINKS_GATE_A


def render_html(
    board: dict,
    *,
    title: str | None = None,
    gate: str | None = None,
    submission_name: str | None = None,
) -> str:
    """把 design_board 渲染成单文件 HTML 字符串（含 ``<!DOCTYPE html>`` 与内联 ``<style>``）。

    参数
    ----
    board:
        ``design_board.json`` 解析后的字典。字段缺失或类型不对都不会抛异常（按"没有"
        处理），只有 ``board`` 本身不是 dict 才会抛 ``TypeError``。
    title:
        覆盖页面主标题；缺省用 ``problem_summary.title``，再缺省用"建模方案决策板"。

    返回
    ----
    完整的 HTML 文本：零外链、可离线打开、可打印、跟随系统深浅色、窄屏自适应。
    输出在"同一份 board + 同一个生成时间"下逐字节稳定（生成时间优先取 board 里的
    ``rendered_at`` / ``generated_at``，都没有才用当前时间）。

    异常
    ----
    ``ValueError``：零外链自检或体积自检不通过（详见 :func:`_self_check`）。
    """
    if not isinstance(board, dict):
        raise TypeError("board 必须是 dict（design_board.json 的解析结果）")

    # 固定在这一次渲染里只取一次时间，避免多处调用跨秒导致同一次输出内部不一致。
    view = dict(board)
    view["rendered_at"] = _render_time(board)

    mode = _resolve_gate(view, gate)
    questions = _questions(view)
    page_title = _page_title(view, title)
    document_title = page_title if "决策板" in page_title else f"{page_title} · 建模方案决策板"
    if mode:
        document_title = f"{document_title}（{GATE_LABELS.get(mode, mode)}）"
    nav = _nav_for(mode, view, questions) if mode else NAV_LINKS
    css = _CSS + (_GATE_CSS if mode else "")
    script = _INLINE_SCRIPT.replace(
        "__MM_SUBMISSION_FILE__",
        submission_name or "design_board_submission.json",
    ).replace("__MM_GATE_ARG__", _gate_suffix(mode))

    head = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(document_title)}</title>\n"
        f"<style>{css}</style>\n"
        "</head>"
    )
    counter = iter(range(1, 100))

    def num() -> str:
        """小节编号（按渲染顺序自增，插入新节时不必手改后续编号）。"""
        return f"{next(counter):02d}"

    if mode == "b":
        sections: list[str] = [_render_overview(view, questions, number=num(), gate="b")]
        if _text(_as_dict(view.get("mindmap")).get("source")).strip():
            sections.append(
                _section(
                    num(),
                    "map",
                    "模型结构总览",
                    _render_mindmap(view),
                    hint="题目 → 小问 → 候选 → 验证",
                )
            )
        sections.extend([
            _render_advice(view, questions, number=num()),
            _render_data_comparison(view, questions, number=num()),
            _render_compare(view, questions, number=num(), gate="b"),
            _render_locked(questions, number=num(), gate="b"),
            _render_ambiguities(view, number=num()),
            _render_sources(questions, number=num()),
            _render_meta(view, number=num()),
            _render_submit_panel(view, questions, number=num(), gate="b"),
        ])
    elif mode == "a":
        sections = [
            _render_overview(view, questions, number=num(), gate="a"),
            _section(
                num(),
                "map",
                "模型结构总览",
                _render_mindmap(view),
                hint="题目 → 小问 → 范式 → 候选 → 验证",
            ),
            _render_paradigm(view, questions, number=num()),
            _render_options(view, questions, number=num(), gate="a"),
            _render_compare(view, questions, number=num(), gate="a"),
            _render_locked(questions, number=num(), gate="a"),
            _render_ambiguities(view, number=num()),
            _render_sources(questions, number=num(), gate="a"),
            _render_meta(view, number=num()),
            _render_submit_panel(view, questions, number=num(), gate="a"),
        ]
    else:
        # legacy 版式：与改造前逐字节一致（样例 design-board-sample 是回归锚）
        sections = [
            _render_overview(view, questions),
            _section(
                "02",
                "map",
                "模型结构总览",
                _render_mindmap(view),
                hint="题目 → 小问 → 候选 → 验证",
            ),
            _render_options(view, questions),
            _render_compare(view, questions),
            _render_locked(questions),
            _render_ambiguities(view),
            _render_sources(questions),
            _render_meta(view),
            _render_submit_panel(view, questions),
        ]

    body = "\n".join(
        [
            '<body id="top">',
            '<a class="skip" href="#main">跳到正文</a>',
            _render_topbar(view, mode),
            '<main id="main" class="wrap">',
            _render_hero(view, page_title, gate=mode, nav=nav),
            _render_confirm(view, mode),
            *sections,
            _render_footer(),
            "</main>",
            f"<script>{script}</script>",
            "</body>",
            "</html>",
            "",
        ]
    )
    markup = f"{head}\n{body}"
    _self_check(markup)
    return markup


__all__ = ["MAX_INLINE_BYTES", "FORBIDDEN_EXTERNAL", "render_html"]

