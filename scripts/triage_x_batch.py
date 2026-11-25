#!/usr/bin/env python3
"""Triage the 2026-11-25 X/Vibe3D prompt batch against CE-Bench admission rules.

The owner supplied two markdown tables (A-01..A-36 and H-01..H-80) on
2026-11-25. Before materialising ~100 task packs we must decide which rows can
actually be scored by this benchmark. This script is a **read-only triage**: it
writes a structured record per row plus a report, and does not touch any
manifest, pack, taxonomy or catalogue.

CE-Bench scoring contract (docs/benchmark-spec.md, scripts/expand_tasks.py):

  1. A task needs a *verbatim* prompt. Excerpts ("全文见原帖回复"), paraphrases
     ("I asked Fable for..."), truncated titles and author-written step lists
     are not reproducible tasks.
  2. `generate.py` extracts a single-file HTML artifact. Tasks whose deliverable
     is an MP4 / GIF / Blender .blend / React+Vite project / native app cannot
     be evaluated by this harness without changing its semantics.
  3. Duplicates are removed by normalised prompt hash (and flagged here by hand
     for near-duplicates).
  4. `MIN_PROMPT_CHARS = 80` is the existing extended-set gate, but it was
     designed to reject rows with *no* prompt at all. A short but complete
     instruction ("make me an awesome game using Three.js.") is still a valid
     verbatim task, so it is reported as a separate `short` tier.

Fields: id | group | title | artifact | pstate | chars | html | note
  pstate: F=full(>=80) S=short(<80, complete) E=excerpt P=paraphrase
          D=duplicate T=truncated
  html:   1 = single-file HTML can carry the deliverable, 0 = cannot

Usage:  python3 scripts/triage_x_batch.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = ROOT / "data" / "corpus" / "x_batch_2026-11-25_triage.jsonl"
OUT_REPORT = ROOT / "docs" / "x-batch-triage.md"

# id|group|title|artifact|pstate|chars|html|note
RAW = r"""
A-01|A1|FPS 关卡 + 3D 打砖块（两条提示词）|game|F|200|1|可拆为 2 题：FPS 全文完整，打砖块为中文短句
A-02|A1|90 秒日式动画短片（蒸汽机车变机器人）|mp4|E|600|0|节选；后续分镜约 5000 字符未给出；交付 MP4/Blender
A-03|A1|Getting There 14 章绘本旅程游戏|game|P|120|1|仅一句方向性转述，非提示词
A-04|A1|发布首日三个可抄作业案例|mix|D|200|1|FPS 段与 A-01 完全重复
A-05|A1|火星上骑单车的鹈鹕 SVG|svg|S|45|1|
A-06|A1|游戏控制器骑自行车再骑鹈鹕 SVG|svg|S|45|1|
A-07|A1|照片 → 湖畔古堡 3D 单页|3d|S|20|1|需上传一张照片；纯文输入无法复现
A-08|A1|体素赛车短片 30-40 秒单页 HTML|anim|S|65|1|
A-09|A1|雨后的罗马斗兽场（无外部资产）|3d|S|25|1|提示词仅一句，其余要求隐含在作者固定出片规范
A-10|A1|几分钟从零产出的可玩 3D 游戏|game|S|40|1|
A-11|A1|Otherwhere 可交互程序化 3D 世界|3d|S|48|1|
A-12|A1|鹈鹕骑自行车 SVG 四模型横评|svg|S|28|1|与 A-05/A-06 同主题但为不同 prompt
A-13|A1|黎明埃及神庙群（挖掘/昼夜/墓室解谜）|3d|F|160|1|
A-14|A1|日本像素风街角|art|S|70|1|
A-15|A1|飞行中的 Tesla Roadster 主题 3D 游戏|game|S|49|1|
A-16|A1|四模型同题 3D 车祸|anim|S|56|1|
A-17|A1|樱花树环绕的日式 3D 房屋|3d|S|61|1|
A-18|A1|交互式 3D 喷气发动机剖切|3d|S|55|1|
A-19|A1|日式樱花山谷（河流/红桥/宝塔/4 机位/3 氛围）|3d|F|165|1|
A-20|A1|火山岛 Blender 代码建模（禁下载模型贴图）|blender|F|88|0|交付 Blender 工程，非单文件 HTML
A-21|A1|三桅木帆船单页 HTML + 程序化配乐|3d|F|400|1|
A-22|A1|《昆仑》60 秒概念片|anim|F|350|1|允许 CDN 引入 Three.js 官方扩展
A-23|A1|开放式「让我惊讶」3D 题|3d|S|35|1|
A-24|A1|Sol/Astra/Terra 同题 WebGL 四连测|webgl|F|105|1|两条示例 prompt（海带森林 / 电车），可拆
A-25|A1|宝可梦 SAR/UR 全息闪卡 3D 悬浮 GIF|gif|F|1000|0|Python/OpenCV 输出 GIF，需上传原图
A-26|A1|13 个切镜的动画角色预告|anim|E|200|1|回复区在 "an oversized white" 处折叠截断
A-27|A1|Tide Atlas 镜海探索游戏|game|E|1200|1|全文约 4800 字符，仅公开开头
A-28|A1|Gullwatch Isle 可探索 3D 海岛城堡|3d|E|2000|0|全文约 21900 字符；Blender + Three.js
A-29|A1|Bloom Pool 水面花池同题横评|3d|E|1200|1|全文约 4000 字符，仅公开开头
A-30|A1|Neon 调度 Hydrogen 蜂群做 V12 发动机|3d|P|100|1|作者明说完整提示词由模型自己写，仅公开一句
A-31|A1|TITAN 6×6 装甲怪兽卡车|blender|F|140|0|bpy/Blender 程序化建模 + 单张参考图
A-33|A2|15 秒发布会级广告动效（Gemini 4 Neon）|anim|E|1200|1|全文约 2381 字符，仅截取前 1200
A-34|A2|「九重天宫」电影级 Three.js + GLSL 场景|3d|F|500|1|中英双语完整提示词
A-35|A2|《烟雨江南：雨巷八重境》Three.js 短片|anim|F|350|1|允许 CDN 引入 Three.js
A-36|A2|一条 Prompt 生成单文件 Canvas 射击游戏|game|P|350|1|作者给的是从零到一步骤叙述，非逐字单段 prompt
H-01|H1|2030 月球中国基地建设场景|3d|F|600|1|
H-02|H1|还原星际穿越五维空间|3d|F|600|1|
H-03|H1|三体：舰队太阳系对峙|3d|F|600|1|
H-04|H1|三体 二向箔降维打击→梵高星空|3d|F|600|1|
H-05|H1|云球：球体 3D Agent 生态世界|3d|F|600|1|
H-06|H1|鬼灭之刃：无限城非欧空间|3d|F|600|1|
H-07|H1|爆款梵高 Three.js 连续小镇（英文）|3d|E|1200|1|原文约 2643 字符，全文见飞书文档
H-08|H1|中文改写爆款梵高 Three.js 小镇|3d|E|1000|1|原文约 1861 字符，全文见飞书文档；与 H-07 为中英改写对
H-09|H1|珍珠项链（写实 3D 商品展示）|3d|F|500|1|
H-10|H1|纯 CSS 四季变换场景动画|css|F|300|1|
H-11|H1|流浪地球｜行星发动机点火|3d|F|600|1|
H-12|H1|阿凡达｜潘多拉悬浮哈利路亚群山|3d|F|600|1|
H-13|H1|2001 太空漫游｜黑色方碑与星门|3d|F|550|1|
H-14|H1|指环王｜魔多末日火山与索伦巨眼|3d|F|600|1|
H-15|H1|复仇者联盟｜纽约大战传送门|3d|F|600|1|
H-16|H1|哈尔的移动城堡｜机械行走城堡|3d|F|600|1|
H-17|H1|星际｜土星环旋转环形空间站|3d|F|550|1|
H-18|H1|进击的巨人｜超大型巨人破墙|3d|F|550|1|
H-19|H1|银河护卫队｜Knowhere 天神族头颅|3d|F|550|1|
H-20|H1|攻壳机动队｜赛博朋克全息雨夜都市|3d|F|550|1|
H-21|H1|哈利波特｜霍格沃茨与摄魂怪黑雾|3d|F|550|1|
H-22|H1|千与千寻｜海上列车镜面水面（Canvas 2D）|canvas|F|450|1|
H-23|H1|EVA｜第三次冲击生命之树红色粒子|canvas|F|450|1|
H-24|H1|你的名字｜彗星分裂坠落夜空|canvas|F|450|1|
H-25|H1|黑客帝国｜数字雨矩阵代码雨|canvas|F|400|1|
H-26|H1|咒术回战｜无量空处领域展开网格|canvas|F|450|1|
H-27|H1|天气之子｜穿透云层光柱与反转雨水|canvas|F|450|1|
H-28|H1|哪吒｜混天绫漫天翻涌红莲火焰|canvas|F|450|1|
H-29|H1|纯 CSS 海边日落潮汐涨落|css|F|350|1|
H-30|H1|纯 CSS 萤火森林夜晚|css|F|350|1|
H-31|H1|纯 CSS 樱花飘落山坡|css|F|350|1|
H-32|H1|纯 CSS 篝火夜晚露营|css|F|350|1|
H-33|H2|超写实旧金山金门大桥 3D 体验|3d|F|500|1|允许使用 imagegen 生成初始资产，需标注
H-34|H2|交互式 3D 还原山西应县木塔|3d|F|250|1|
H-35|H2|一艘可完全探索的星舰|3d|S|80|1|
H-36|H2|3D Rubik's Cube 自动求解|3d|F|170|1|单 HTML + CDN
H-37|H2|Solar System Explorer 单页应用|3d|F|250|1|
H-38|H2|3D 交互圣诞树 R3F 7000 实例|3d|F|130|0|React Three Fiber 单页应用，需构建，非单文件 HTML
H-39|H2|3D 乐高拼砖沙盒|3d|S|110|1|
H-40|H2|纯 SVG 等距互动岛屿地图|svg|S|110|1|
H-41|H2|太阳系模拟器 N 体数值积分|3d|S|130|1|
H-42|H2|浏览器内 3D CAD 编辑器 + STL 导出|3d|S|150|1|
H-43|H2|WebGL 流体模拟（节拍同步）|webgl|S|110|1|
H-44|H2|3D 椋鸟群飞 boids + 手势 + 生成式配乐|3d|S|130|1|
H-45|H2|3D 体素玩具箱应用|3d|S|130|1|
H-46|H2|Biome Lab 程序化生态沙盒|3d|F|900|1|
H-47|H2|React 程序化 3D 城市生成器|3d|F|900|0|React app，需构建与 mockup 先行，非单文件 HTML
H-48|H2|twigl 新哥特式塔楼城市着色器|webgl|S|60|1|shader 片段，可由单文件 HTML 承载
H-49|H2|R3F 产品查看器|3d|S|200|0|React 组件，非单文件 HTML
H-50|H2|Three.js 粒子背景 5000 粒子|3d|F|200|1|单 HTML + CDN
H-51|H2|Three.js 等距场景射线拾取|3d|F|200|1|单 HTML
H-52|H2|Three.js 点云场景|3d|F|200|1|单 HTML + CDN
H-53|H2|R3F 后处理传送门平面|3d|S|200|0|React 组件 + EffectComposer，非单文件 HTML
H-54|H2|「城市命脉」Metaball 数据艺术|viz|S|80|1|
H-55|H2|GARGANTUA 黑洞 Schwarzschild 光线追踪|webgl|F|1200|0|需本地 Three.js vendor、多文件项目与静态服务器
H-56|H2|「海的尽头」WebGPU/TSL 程序化海洋|webgl|F|900|0|交付 index.html + main.js 多文件，需 ES Modules
H-57|H2|赛博朋克大都会 Web-Swing 3D 游戏|game|F|900|0|需本地 Three.js 模块与大量素材、多文件项目
H-58|H2|推理芯片四十二年周期交互研究网页|viz|F|500|1|需真实产业数据，可按 mock 数据处理
H-59|H2|THE IMPACT No.01 3D 复古打字机|3d|F|1500|0|Vite + React + TS + R3F 工程，需 npm run build
H-60|H3|5 分钟 vibe coding 人体/骨骼/肌肉 3D 模型|3d|T|30|1|标题式截断，prompt 列同样截断
H-61|H3|Three.js 四季森林互动网站|3d|T|35|1|标题式截断
H-62|H3|把 PPT 变成可玩的 3D 微观实验室|3d|T|30|1|标题式截断
H-63|H3|交互式 3D 还原山西应县木塔|3d|T|30|1|标题式截断；与 H-34 同题
H-64|H3|约 5 万座 3D 球场镜头飞入座位|3d|T|30|1|标题式截断
H-65|H3|SpaceX Launch Atlas 交互式 3D 地球|viz|F|400|1|需 Launch Library 2 数据，可按 mock 处理
H-66|H3|1660 年新阿姆斯特丹历史地图复刻|3d|S|100|1|
H-67|H3|实时交互 3D 粒子银河系|3d|S|30|1|
H-68|H3|指环王开篇第一段 3D 动画|3d|S|40|1|
H-69|H3|指环王开篇第一段 Three.js 渲染|3d|S|30|1|与 H-68 近似同题
H-70|H3|音乐封面 3D 浏览器|3d|S|120|1|
H-71|H3|复刻 Karpathy 指环王 3D Demo 呈现桃花源记|3d|S|40|1|
H-72|H4|抖音沉浸式短视频信息流微信小程序|app|E|2000|0|PRD 节选（全文约 9445 字符）；原生小程序多文件工程
H-73|H4|申财有道 Android Jetpack Compose App|app|E|2000|0|PRD 节选（全文约 12159 字符）；Android 原生工程
H-74|H4|QQ for Mac SwiftUI 客户端|app|E|2000|0|PRD 节选（全文约 7936 字符）；macOS 原生工程
H-75|H5|Mini World 给 4 岁半孩子的小星球 3D 游戏|game|F|700|1|
H-76|H5|电动机工作原理 3D 动画（磁场/电子）|3d|F|150|1|单 HTML + CDN
H-77|H5|雨夜便利店街角微缩 3D 场景|3d|F|400|1|
H-78|H5|Sunset Bay 霓虹海岸驾驶游戏|game|S|110|1|
H-79|H5|3D 机甲展示 + 可玩射击网页游戏|game|F|250|1|允许搜索/软件生成资产，需标注
H-80|H5|云顶天宫像素方块中国寺庙 3D 世界|3d|F|500|1|
"""

GRP_LABEL = {
    "A1": "A 类第一批（A-01~A-31，有 Prompt 原文 + 有效果）",
    "A2": "G.4.A 第二批（A-33~A-36，含评论区 Prompt）",
    "H1": "H.1 Vibe3D 纯文输入（H-01~H-32）",
    "H2": "H.1 Vibe3D 续（H-33~H-59）",
    "H3": "H.1 Vibe3D 短题/截断区（H-60~H-71）",
    "H4": "H.2 Showcase 全栈 PRD（H-72~H-74）",
    "H5": "H.2 Showcase + H.3 脑暴（H-75~H-80）",
}

REJECT_STATES = {"E", "P", "D", "T"}
STATE_LABEL = {
    "F": "完整 verbatim（≥80 字符）", "S": "短但完整（<80 字符）",
    "E": "节选 / 全文未公开", "P": "转述 / 步骤叙述，非逐字 prompt",
    "D": "与批内其他题重复", "T": "标题式截断",
}


def main() -> int:
    rows = []
    for line in RAW.strip().splitlines():
        parts = line.split("|")
        if len(parts) != 8:
            raise SystemExit(f"bad row ({len(parts)} fields): {line}")
        rid, grp, title, artifact, pstate, chars, html, note = [p.strip() for p in parts]
        html_ok = html == "1"
        reject_reason = ""
        if pstate in REJECT_STATES:
            reject_reason = STATE_LABEL[pstate]
        elif not html_ok:
            reject_reason = "交付物不是单文件 HTML（BMK 评分链路无法承载）"
        rows.append({
            "id": rid, "group": grp, "title": title, "artifact": artifact,
            "pstate": pstate, "prompt_chars_estimate": int(chars),
            "html_carriable": html_ok, "note": note,
            "status": "reject" if reject_reason else "admit",
            "reject_reason": reject_reason,
            "tier": "strict" if pstate == "F" and html_ok else
                    ("short" if pstate == "S" and html_ok else "reject"),
        })

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    n = len(rows)
    strict = [r for r in rows if r["tier"] == "strict"]
    short = [r for r in rows if r["tier"] == "short"]
    rejected = [r for r in rows if r["status"] == "reject"]
    reasons = Counter(r["reject_reason"] for r in rejected)

    lines = [
        "# 2026-11-25 新题批次 · 纳入门槛判定（triage，未改动任何正式文件）", "",
        f"生成：`{datetime.now().astimezone().isoformat(timespec='seconds')}` · "
        f"来源：owner 提供的两段 markdown 表格 · 共 **{n}** 条", "",
        "> 这是 **只读分级**。本脚本只写 `data/corpus/x_batch_2026-11-25_triage.jsonl`",
        "> 和本报告，不触碰 manifest / packs / taxonomy / catalog / results。", "",
        "## 判定依据（沿用 CE-Bench 既有合约）", "",
        "1. **必须有逐字 verbatim prompt**。节选（「全文见原帖回复」）、作者转述、",
        "   步骤叙述、标题式截断都不是可复现任务。",
        "2. **交付物必须能由单文件 HTML 承载**。`generate.py` 用 `extract_html()`",
        "   抽取产物；MP4 / GIF / Blender 工程 / React+Vite 项目 / 原生 App",
        "   无法进入现有评分链路。",
        "3. **去重**：完全相同 prompt 剔除（批内重复已标注）。语义近似题",
        "   （如 A-05/A-06/A-12 鹈鹕系列、H-68/H-69 指环王、H-34/H-63 木塔）",
        "   需人工复核，哈希去重抓不到。",
        "4. `MIN_PROMPT_CHARS = 80` 原用于过滤「只有标题/截图、没有 prompt」的行。",
        "   短但完整的指令仍是可复现任务，单列为 `short` 档，由 owner 决定是否纳入。", "",
        "## 总量", "",
        "| 档位 | 题数 | 说明 |", "|---|---:|---|",
        f"| **strict**（完整 ≥80 字符 + 单文件 HTML + 去重） | **{len(strict)}** | 直接符合现有 extended 门槛 |",
        f"| **short**（短但完整 verbatim + 单文件 HTML） | **{len(short)}** | 放宽 80 字符门槛才纳入 |",
        f"| **reject** | **{len(rejected)}** | 见下表 |",
        f"| 合计 | {n} | |", "",
        "### 三种可选尺度", "",
        "| 尺度 | 新纳入 | 全库题数 | 代价 |", "|---|---:|---:|---|",
        f"| A 严格：只收 strict | +{len(strict)} | {180+len(strict)} | 最稳，短题全部留在语料 |",
        f"| B 标准：strict + short | +{len(strict)+len(short)} | {180+len(strict)+len(short)} | 需正式放宽 80 字符门槛并标注 `short_verbatim` |",
        "| C 保守：CV² 均匀化只挑最补薄标签的 ~25 题 | +25 | 205 | 分布最稳，但会舍弃大量新题 |", "",
        "**分布警告**：这批题几乎全部落在 `3d / 游戏 / 动画 / 生成艺术 / CSS`，",
        "而当前最薄的 primary 是「工具 16 / 前端 16」、最薄 track 是 `composite 15`、",
        "最薄 tech 是 `code2deck 8 / code2world 15`。按尺度 B 全量纳入会显著",
        "**恶化** CV² 均匀度（上一轮 111→180 刚把 primary max/min 从 2.88 压到 1.81）。", "",
        "## 拒绝原因分布", "",
        "| 原因 | 题数 |", "|---|---:|",
    ]
    for reason, cnt in reasons.most_common():
        lines.append(f"| {reason} | {cnt} |")
    lines += ["", "## 分组明细", ""]
    for grp in ("A1", "A2", "H1", "H2", "H3", "H4", "H5"):
        g = [r for r in rows if r["group"] == grp]
        lines += [
            f"### {GRP_LABEL[grp]} — {len(g)} 条", "",
            f"strict {sum(1 for r in g if r['tier']=='strict')} · "
            f"short {sum(1 for r in g if r['tier']=='short')} · "
            f"reject {sum(1 for r in g if r['status']=='reject')}", "",
            "| 编号 | 题目 | 档 | 原因 / 备注 |", "|---|---|---|---|",
        ]
        for r in g:
            tier = {"strict": "strict", "short": "short", "reject": "**reject**"}[r["tier"]]
            detail = r["reject_reason"] or r["note"] or "—"
            lines.append(f"| {r['id']} | {r['title']} | {tier} | {detail} |")
        lines.append("")

    lines += [
        "## 尚未做的（下一步按尺度执行）", "",
        "- 逐字 prompt 全文落盘到版本化语料（目前只存元数据与字符数估算）",
        "- 与现有 180 题做 prompt 哈希去重（含语义近似人工复核清单）",
        "- 三轴标签派生（`expand_tasks.py::infer_tags` / `DOMAIN_MAP`）+ CV² 排序",
        "- 生成 packs：`prompt.md` / `task.json` / `budget.json`（512000 / 120min）/",
        "  `assertions/task.json` / `meta_test.json` / `reference/SOURCE.md`",
        "- 重建 `manifest_extended.json` / `taxonomy.json` / `task-catalog.{html,md,csv}`",
        "- `selftest` 里的 `111 + 69 = 180` 硬编码需同步",
        "- 全量验证与扩题报告", "",
        "**注意**：题数一旦变更，论文手稿 / Overleaf 里 Core-111 与 180 题的 census",
        "口径需要相应重述（见 `docs/expansion-report.md` 的 Honesty notes）。", "",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"rows={n}  strict={len(strict)}  short={len(short)}  reject={len(rejected)}")
    print(f"scales: A=+{len(strict)} (->{180+len(strict)})  "
          f"B=+{len(strict)+len(short)} (->{180+len(strict)+len(short)})  C=+25 (->205)")
    print("reject reasons:", dict(reasons))
    print(f"wrote {OUT_JSONL.relative_to(ROOT)}")
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
