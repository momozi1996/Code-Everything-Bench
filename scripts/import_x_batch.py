#!/usr/bin/env python3
"""Materialise the 2026-11-25 X / Vibe3D prompt batch into CE-Bench.

Owner supplied two markdown tables (A-01..A-36 and H-01..H-80) and chose
"scale B": admit the 84 rows that have a *complete verbatim prompt* and a
deliverable that a single-file HTML artifact can carry, including the 31 short
(<80 chars) but complete instructions (tagged `short_verbatim`).

`scripts/triage_x_batch.py` is the read-only gate that produced the admit list.
This script:

  * de-duplicates by normalised prompt hash against Core-111 + the existing
    Extended-147 corpus and within the batch,
  * derives `code2Tags` / `domains` with the SAME `expand_tasks.infer_tags`
    and `DOMAIN_MAP` used by the 111->180 expansion (no invented labels),
  * assigns `primaryCategory` by task nature (a human annotation, as in the
    upstream corpus),
  * writes a versioned corpus file `data/corpus/x_batch_2026-11-25.jsonl`,
  * APPENDS the new tasks to `tasks/manifest_extended.json` (Core-111 is never
    touched, the original 69 entries are preserved verbatim),
  * writes `docs/x-batch-import-report.md`.

It does NOT create packs, assertions, taxonomy or catalogues — those are
produced by the existing scripts, run afterwards:
    python3 scripts/build_task_packs.py --extended-only --keep-assertions
    python3 scripts/generate_assertions.py --task <new-id>   (per new task)
    python3 scripts/build_catalog.py

Usage:  python3 scripts/import_x_batch.py [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.expand_tasks import (  # noqa: E402
    infer_tags, norm_tech, tracks_from, DOMAIN_MAP, PRIMARY_KEYS,
)

CORPUS_FILES = [
    ROOT / "data" / "corpus" / "cases.jsonl",
    ROOT / "data" / "corpus" / "extension.jsonl",
]
OUT_CORPUS = ROOT / "data" / "corpus" / "x_batch_2026-11-25.jsonl"
OUT_REPORT = ROOT / "docs" / "x-batch-import-report.md"
TRIAGE = ROOT / "data" / "corpus" / "x_batch_2026-11-25_triage.jsonl"
EXT_MANIFEST = ROOT / "tasks" / "manifest_extended.json"

BATCH = "2026-11-25"
SOURCE_ORIGIN = "x_batch_2026-11-25"

# One record per admitted row. `short=True` marks a complete verbatim prompt
# below the 80-char extended-set floor (owner-approved `short_verbatim` tier).
# `primary` is a human annotation from the task's nature; tech/track labels are
# derived mechanically from the prompt text, never hand-assigned.
RECORDS: list[dict] = [
    # ---------------------------------------------------------------- A1 --
    dict(sid="A-01", title="FPS 关卡（AAA 级写实小场景）", model="Claude Fable 5.2",
         author="@vista8", url="https://x.com/vista8/status/2120383046239285264",
         date="2026-11-11", primary="游戏", short=False,
         note="同帖另有「3D 打砖块」短提示词；按一题一 prompt 只保留 FPS 段，另一段记在此处：开发一个 最炫酷、道具玩法最有意思的 3D 打砖块游戏，支持 ai 也支持双人对战，也支持传统经典打砖块",
         prompt="""you should also build me a FPS. Insanely detailed quality pls, something that looks visually like it can keep up with AAA. Make it small in scope (like a tiny level) but otherwise impressive photorealistic graphics"""),
    dict(sid="A-05", title="火星上骑单车的鹈鹕（SVG）", model="GPT-6.2 Sol",
         author="@mspd4100", url="https://x.com/mspd4100/status/2119680610222686458",
         date="2026-11-09", primary="生成艺术", short=True,
         note="", prompt="""我做个svg的鹈鹕在火星上骑单车的动画，要精美细腻有特色，不要被Claude Opus比下去了"""),
    dict(sid="A-06", title="游戏控制器骑自行车，再骑鹈鹕（SVG）", model="GPT-6.2 Sol",
         author="@SongyuKite", url="https://x.com/SongyuKite/status/2119729206888145162",
         date="2026-11-09", primary="生成艺术", short=True,
         note="", prompt="""做一个SVG 动画
游戏控制器骑着自行车，骑着鹈鹕，骑着自行车下面有只 鹈鹕。"""),
    dict(sid="A-07", title="照片 → 湖畔古堡 3D 单页 HTML", model="GPT-6.2 Sol",
         author="@cfenghub", url="https://x.com/cfenghub/status/2119736756585074976",
         date="2026-11-09", primary="3D", short=True,
         note="原帖输入含一张古堡照片；纯文输入下由模型自行想象古堡形态，参考图不随题提供。",
         prompt="""用THree.js还原图片里的古堡"""),
    dict(sid="A-08", title="体素赛车短片（30-40 秒，单页 HTML）", model="GPT-6.2 Sol",
         author="@cfenghub", url="https://x.com/cfenghub/status/2120024150114713936",
         date="2026-11-10", primary="动画", short=True,
         note="", prompt="""Three.js + InstancedMesh 拍一支体素赛车动画，30-40秒，交付一个单页HTML"""),
    dict(sid="A-09", title="雨后的罗马斗兽场（无任何外部资产）", model="GPT-6.2 Sol",
         author="@cfenghub", url="https://x.com/cfenghub/status/2120069654437921152",
         date="2026-11-10", primary="3D", short=True,
         note="提示词仅一句，其余要求隐含在作者固定出片规范里；本 bench 按字面执行。",
         prompt="""用 three.js+GLSL+Blender"""),
    dict(sid="A-10", title="几分钟从零产出的可玩 3D 游戏", model="GPT-6.2 Sol",
         author="@TheAstrayDev", url="https://x.com/TheAstrayDev/status/2121975150685901040",
         date="2026-11-15", primary="游戏", short=True,
         note="", prompt="""make me an awesome game using Three.js."""),
    dict(sid="A-11", title="《Otherwhere》可交互程序化 3D 世界", model="Kimi K3.1 Pro",
         author="@shitunote", url="https://x.com/shitunote/status/2115076399895826533",
         date="2026-10-27", primary="3D", short=True,
         note="官方预发布素材原句，可视为最小可复现基线。",
         prompt="""Build a complex procedural 3D scene in Three.js"""),
    dict(sid="A-12", title="鹈鹕骑自行车（SVG + H5 展示）四模型横评", model="Kimi K3.1 Pro",
         author="@xueyu1125", url="https://x.com/xueyu1125/status/2117951147239682360",
         date="2026-11-04", primary="生成艺术", short=True,
         note="与 A-05/A-06 同主题族，但为不同逐字 prompt；哈希去重不视为重复。",
         prompt="""生成一个svg动画：鹈鹕骑自行车，用H5给我展示下"""),
    dict(sid="A-13", title="黎明埃及神庙群（挖掘/昼夜/墓室解谜）", model="Kimi K3.1 Pro",
         author="@sakatayasha", url="https://x.com/sakatayasha/status/2114330266986799169",
         date="2026-10-25", primary="3D", short=False, note="",
         prompt="""a full interactive Three.js Egyptian temple complex at dawn

sand dunes, dig and brush tools, day and night cycle, burial chamber puzzle, weather, torch, photo mode"""),
    dict(sid="A-14", title="日本像素风街角", model="Kimi K3.1 Pro",
         author="@gmi_cloud", url="https://x.com/gmi_cloud/status/2114877816311541921",
         date="2026-10-27", primary="生成艺术", short=True,
         note="", prompt="""creating a beautiful, highly detailed Japanese pixel-art street corner"""),
    dict(sid="A-15", title="飞行中的 Tesla Roadster 主题 3D 游戏", model="Kimi K3.1 Pro",
         author="@AbdoKerdawy", url="https://x.com/AbdoKerdawy/status/2115957714203332616",
         date="2026-10-30", primary="游戏", short=True,
         note="", prompt="""build a 3D game around the flying Tesla Roadster"""),
    dict(sid="A-16", title="四模型同题「3D 车祸」", model="GPT-6.1 Sol",
         author="@melvynx", url="https://x.com/melvynx/status/2111081760369107300",
         date="2026-10-16", primary="动画", short=True,
         note="", prompt="""Same prompt: build a 3D car crash. Max thinking for all"""),
    dict(sid="A-17", title="樱花树环绕的日式 3D 房屋", model="GPT-6.1 Sol",
         author="@dpratyush02", url="https://x.com/dpratyush02/status/2110347694447509797",
         date="2026-10-14", primary="3D", short=True,
         note="", prompt="""build a 3D Japanese house surrounded by cherry blossom trees"""),
    dict(sid="A-18", title="交互式 3D 喷气发动机剖切", model="GPT-6.1 Sol",
         author="@olezhavich", url="https://x.com/olezhavich/status/2112897791022264814",
         date="2026-10-21", primary="3D", short=True,
         note="", prompt="""build an interactive 3D jet engine cutaway in Three.js"""),
    dict(sid="A-19", title="日式樱花山谷（河流/红桥/宝塔/4 机位/3 氛围）", model="GPT-6.1 Sol",
         author="@daveeyyy_", url="https://x.com/daveeyyy_/status/2113298375479038323",
         date="2026-10-22", primary="3D", short=False, note="",
         prompt="""An interactive 3D Japanese cherry blossom valley, built from scratch in code. River, red bridge, pagoda, lanterns, 4 camera angles, 3 moods (blue hour, morning, rain)."""),
    dict(sid="A-21", title="三桅木帆船（单页 HTML + 程序化配乐）", model="GPT-6.1 Sol",
         author="@YFeng2022", url="https://x.com/YFeng2022/status/2120089605752193173",
         date="2026-11-10", primary="3D", short=False,
         note="作者回复区原文；23 分钟一次生成。",
         prompt="""用 HTML 和 Three.js 程序化制作一艘三桅木帆船。首屏从船尾斜侧完整展示弧形船壳、鼓风帆、索具和双层艉楼。夕阳透过帆布，在蓝绿海面铺出金色光路。船随涌浪起伏，尾流泛起白沫，远处有岛屿、慢云和海鸥。支持旋转、缩放、平移和自动巡游。配乐与环境声用 Python 合成（包含6/8拍的水手歌，以及木槌、风帆、海浪、海鸥、船钟和大炮的声音），全部封装进单个 HTML。船两边各6门火炮，火炮声音更加粗壮，激烈一些。点击后从前第一火炮挨个发送，火光要四射，屏幕要有抖动。船头灯亮起，在增加金色装饰、灯笼、骷髅旗。"""),
    dict(sid="A-22", title="《昆仑》60 秒概念片（1920×1080 / 30fps）", model="GPT-6.1 Sol",
         author="@YFeng2022", url="https://x.com/YFeng2022/status/2121583392089071970",
         date="2026-11-14", primary="动画", short=False,
         note="允许 CDN 引入 Three.js 及同版本官方扩展；本 bench 网络禁用，按单文件口径评测。",
         prompt="""创作《昆仑》1分钟概念片（无配音、保留诗意字幕），晴日雪峰开场，沿雪松间的石阶穿过山门，落到瑶池的荷花与倒影，沿云上石桥望向天墉城与飞瀑。片尾保留日光，转入淡青绿水墨。配乐重写为清朗的五声音阶旋律，由古琴和笛声领奏，过桥时弦乐抬升。鹤鸣、水滴、脚步和瀑布声随镜头进入。字体选用敦煌写经体、魏碑或瘦金体，颜色用古铜金或宣纸白，置于画面角落留白处。允许通过 CDN 引入 Three.js 及同版本官方扩展。建筑、纹理和其他素材全部通过代码生成，不加载外部模型或图片。"""),
    dict(sid="A-23", title="开放式「让我惊讶」3D 题（Sol vs Gemini 4 Carbon）", model="GPT-6.1 Sol",
         author="@cfenghub", url="https://x.com/cfenghub/status/2120723760500166712",
         date="2026-11-12", primary="3D", short=True,
         note="", prompt="""构建一个在 3D 中让我感到惊讶的东西，让我觉得你是一个 AGI 模型"""),
    dict(sid="A-24", title="WebGL 同题横评：水下海带森林", model="GPT-6.1 Sol",
         author="@teddyaisi", url="https://x.com/teddyaisi/status/2116847177800798575",
         date="2026-11-01", primary="3D", short=False,
         note="原帖另有一条示例「A WebGL tram rounding an elevated curve above a rainy neon night city.」，按一题一 prompt 未纳入。",
         prompt="""an underwater WebGL kelp forest, with broad leaves bending in the current and light filtering through them"""),
    # ---------------------------------------------------------------- A2 --
    dict(sid="A-34", title="「九重天宫」电影级 Three.js + GLSL 场景", model="GPT-6.2 Astra",
         author="@cfenghub", url="https://x.com/i/status/2123162154132242885",
         date="2026-11-19", primary="3D", short=False,
         note="评论区原文，含中英双语要求。",
         prompt="""天宫 / Heavenly Palace
用 Three.js + GLSL 写一个单页 HTML，实时渲染电影级宏大的"九重天宫"：云海、琼楼玉宇、体积光与天光氛围由你自行设计并程序化生成（不依赖外部资源），配镜头运镜与右侧控制面板（可调时间、光照、云量、镜头、画质等参数），追求震撼的史诗感与极致画面细节。
Write a single-page HTML with Three.js + GLSL that renders a real-time, cinematic, epic "Nine-Tiered Heavenly Palace": design and procedurally generate the sea of clouds, celestial architecture, volumetric light and atmosphere yourself (no external assets), with camera movement and a control panel (time of day, lighting, cloud density, camera, quality, etc.), aiming for breathtaking epic scale and extreme visual detail."""),
    dict(sid="A-35", title="《烟雨江南：雨巷八重境》Three.js 短片", model="GPT-6.2 Astra",
         author="@YFeng2022", url="https://x.com/i/status/2122213756952351017",
         date="2026-11-16", primary="动画", short=False,
         note="允许 CDN 引入 Three.js；本 bench 网络禁用，按单文件口径评测。",
         prompt="""提示词：请使用 Three.js 创作一个视频，足以表达它对技术与美的理解。一位美女的女孩在雨天地里撑着伞翩翩起舞，雨水与女孩、伞一起共舞。场景也要有变化，要卡点，每次重拍后，场景进行更换 一共有8个场景，每个场景都是氛围感拉满，诉说关于雨中浪漫的故事。时间2分钟以内。不要旁白配音可以写字幕。允许通过 CDN 引入 Three.js 及同版本官方扩展。建筑、纹理和其他素材全部通过代码生成，不加载外部模型或图片。"""),
    # ---------------------------------------------------------------- H1 --
    dict(sid="H-01", title="2030 月球中国基地建设场景", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成一个完整独立的Three.js交互式3D单文件HTML，可直接在浏览器打开。 场景：2030年月球表面，正在施工建设的中国月球科研基地，包含月面着陆器、模块化居住舱、太阳能阵列、月球车、机械臂作业平台，远处轨道运行中国新一代空间站；背景是深邃璀璨宇宙星空，大量恒星，地球悬挂在月球地平线，月球地表布满陨石坑，灰色月壤地貌。 交互：鼠标拖拽旋转相机，滚轮缩放，WASD漫游移动相机，可以靠近观察基地建筑细节；可切换昼夜光照。 美术：写实硬科幻，电影级PBR材质，真实宇宙光照，月面冷灰色调，金属舱体带有国产标识，太空环境深邃黑暗，恒星闪烁。 技术：Three.js，OrbitControls，环境光+点光源，星空粒子系统，不需要外部资源，全部内置，自包含HTML文件，无外部依赖。 输出完整可运行代码，包含简单UI面板可以切换视角，禁止占位注释，所有模型基础几何体组合实现，保证场景完整可渲染。"""),
    dict(sid="H-02", title="还原星际穿越五维空间", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。 场景：还原《星际穿越》五维超立方体Tesseract空间，无限递归堆叠的无数方形房间，时间以空间维度可视化，无数重复房间向无限远方延伸，漂浮柔和蓝色金色辉光，空间扭曲，光线折射畸变，深邃虚空背景。 交互：鼠标拖拽旋转相机，滚轮缩放，WASD自由穿梭飞行在五维空间内部，相机可以飞向无限重复的房间阵列，感受空间无限嵌套效果。 美术：电影氛围感，蓝金冷霓虹辉光，体积光，景深模糊，迷幻超现实，无重力漂浮感，光影流动。 技术：Three.js，OrbitControls，大量实例化网格实现无限递归房间，后期辉光bloom效果，粒子星光，全部资源内置，单文件HTML，不引入外部模型。 输出完整可运行代码，支持速度调节滑块UI，保证视觉冲击，渲染出无限纵深的五维错觉。"""),
    dict(sid="H-03", title="三体：三体舰队与人类太阳系舰队对峙", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接打开。
场景：太阳系深空，宏大宇宙对峙场面。一侧是人类联合太空舰队，成千上万艘人类战舰集群排布；另一侧三体远征三体舰队，巨大水滴探测器先导，庞大三体战舰阵列；背景太阳散发耀眼光晕，远处可见木星土星行星，浩瀚星空。双方舰队隔着宇宙虚空遥遥对峙，战争前夕压抑氛围。
交互：鼠标拖拽旋转，滚轮缩放，WASD飞行漫游，可以拉近观察战舰集群，相机可以拉远展示整个太阳系尺度宏大场面。
美术：硬核太空科幻，冷金属战舰，太阳强光眩光，宇宙黑暗深空，宏大史诗电影构图，规模感极强，大量舰船实例化批量生成。
技术：Three.js + OrbitControls，bloom辉光，太阳点光源，行星球体，粒子星空系统，全部几何体构建，无外部资源，单文件HTML。
输出完整可运行代码，附带简易UI可以切换远近视角，突出两军对峙压迫感。"""),
    dict(sid="H-04", title="三体 二向箔降维打击：太阳系坍缩为梵高星空", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：三体二向箔降维打击特效。太阳系所有行星、恒星正在被二维化；巨大二维化平面向外扩散，三维天体不断坍缩消融卷入二维平面；被降维的区域化为梵高《星月夜》漩涡流动油画纹理，星空旋转扭曲，一边是残存三维宇宙，一边是梵高油画质感二维平面，强烈视觉对比。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD飞行，可观察二向箔扩散动画，可暂停/播放降维动画。
美术：史诗悲剧科幻，一边写实宇宙天体，一边流动漩涡油画笔触色彩，强烈风格碰撞，流光弥散，动态演化特效。
技术：Three.js，Shader自定义着色器实现二维化消融过渡效果，bloom后期，粒子星空，动画时间轴，全部内置，单文件HTML。
输出完整可运行代码，增加UI按钮控制播放重置降维过程，重点实现三维物体向梵高星空图案坍缩转化的视觉效果。"""),
    dict(sid="H-05", title="云球：完整球体 3D Agent 生态世界", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接打开。
场景：科幻《云球》设定，一颗完整巨型球形人造星球，球体表面拥有完整大陆、海洋、山脉、城市、自然地貌；星球表面生存大量小型AI‑Agent角色，生物、人形个体在地表自主游走活动，形成完整生态社会；外层包裹薄光晕大气层，悬浮在外太空黑色宇宙之中，四周繁星。
交互：鼠标拖拽旋转星球，滚轮缩放，WASD环绕飞行，可以放大观察星球表面Agent个体活动；可以开关Agent运动。
美术：软科幻，细腻行星地表，昼夜光照，大气层辉光，大量微型Agent实例，生机勃勃的人造球体世界。
技术：Three.js，球体地形噪声生成，实例化Mesh实现大量Agent，简单自主运动逻辑写在代码内，大气层shader，星空粒子，单文件自包含HTML，无外部资源。
输出完整可运行代码，简易UI控制Agent开启关闭，重点实现球体全域可浏览、实体Agent自主活动的生态感。"""),
    dict(sid="H-06", title="鬼灭之刃：无限城 3D 交互空间", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：鬼灭之刃无限城，诡异无限错乱的日式和洋混合城堡空间，建筑空间不断扭曲翻转，楼梯、走廊、房间颠倒、倾斜、上下交错，空间非欧几里得，空间结构不断动态变化；暗红色诡异环境光，日式纸门、木廊、灯笼，朦胧雾气，黑暗诡秘氛围，远处无尽延伸错乱建筑。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD在无限城内部漫游穿行，建筑缓慢动态扭曲形变。
美术：暗黑和风奇幻，暗红主色调，灯笼暖光点光源，雾气景深，诡异悬疑氛围感，空间错乱超现实。
技术：Three.js，OrbitControls，实例化建筑组件，简单动画实现空间翻转扭曲，雾效，bloom，全部几何体搭建，单文件HTML，无外部模型。
输出完整可运行代码，UI可调节空间扭曲速度，重点做出无限城空间错乱、永无止境迷宫的体验。"""),
    dict(sid="H-09", title="珍珠项链（写实 3D 商品展示）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成单文件独立Three.js HTML页面，不引入任何外部资源、图片纹理，全部几何体与材质程序化生成。
在视口中心渲染一条写实的3D珍珠项链模型。
功能要求：
1. 项链为闭合环形链条，由一颗颗带有珠光的珍珠球体，以及珍珠之间细小金色金属链节组成。珍珠使用具备彩虹晕彩的珍珠贝母材质，柔和次表面发光；表面带有细微自然凹凸瑕疵，不能是完美光滑塑料球体。
2. 开启轨道相机交互：鼠标拖拽可以环绕旋转项链，鼠标滚轮缩放；禁止平移相机。
3. 布置三点摄影棚柔和布光：主光、补光、轮廓光，柔和环境漫反射，最大化表现珍珠的珠光晕彩效果；背景为中性深灰渐变，干净商品展示风格。
4. 鼠标无操作时，项链整体沿竖直轴缓慢自动旋转；用户拖拽鼠标手动旋转时停止自动旋转；鼠标松开闲置后恢复自动旋转。
5. 不要任何UI、文字、按钮。使用Import Map锁定固定Three.js版本。全部代码放在单个HTML文件。
性能：几何体轻量化，保证浏览器流畅运行。输出一份完整可直接运行的HTML文件。"""),
    dict(sid="H-10", title="纯 CSS 实现「四季变换」场景动画", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""请根据如下的要求生成一个html代码（一个代码文件），代码放在```html
 xxx
```中给出：纯 CSS 实现一个「四季变换」场景动画。一棵树作为中心主体，通过一个 20 秒的动画循环展示四季：春天→树上冒出嫩绿色小叶和粉色花朵，蝴蝶飞舞；夏天→叶片茂密深绿，阳光灿烂，知了的声波纹；秋天→叶片变黄变红并逐片飘落到地面；冬天→树枝光秃，雪花飘落覆盖地面和树枝。背景天空颜色和太阳/月亮位置随季节平滑过渡。地面和环境随季节变色。"""),
    dict(sid="H-11", title="流浪地球｜行星发动机点火，地球飞出太阳系", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：流浪地球名场面，完整地球地表排布上万台巨型行星发动机，发动机喷射高耸蓝色等离子火焰尾焰，整颗地球在宇宙深空推进航行，近距离可以看见亚洲大陆发动机集群，远处木星巨大气态行星悬浮，木星大红斑清晰可见，浩瀚布满恒星的宇宙星空背景。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD自由飞行漫游，可以拉近观察单台发动机喷射细节，也可以拉远俯瞰整颗地球航行；UI按钮可开关发动机点火动画。
美术：硬核国产科幻电影质感，PBR金属岩石材质，等离子焰流光效，宇宙深邃黑暗，恒星闪烁，宏大悲壮史诗氛围。
技术：Three.js，OrbitControls，粒子系统实现等离子喷射，bloom辉光后期，行星噪声地形，全部使用基础几何体实例化实现，无外部模型资源，自包含单文件HTML。
输出完整可运行代码，禁止占位注释，保证发动机喷射动画、地球航行运动效果可正常渲染。"""),
    dict(sid="H-12", title="阿凡达｜潘多拉悬浮哈利路亚群山", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：阿凡达潘多拉星球，大量反重力哈利路亚悬浮山漂浮在空中，山体岩石带有发光蓝色荧光矿脉，山间垂落巨型瀑布，地面是茂密发光荧光外星植物森林，云海云雾缭绕，巨大气态行星在天空悬挂，漫天星辰。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD自由穿梭飞行，可飞入群山缝隙之间，近距离观赏发光植被；UI滑块调节雾气浓度。
美术：梦幻外星自然科幻，高饱和度蓝绿荧光色调，体积雾，柔和漫反射光影，奇幻空灵氛围感。
技术：Three.js，OrbitControls，bloom辉光，噪声生成山体，粒子实现瀑布水雾，雾效系统，全部内置几何体，无外部资源，单文件HTML。
输出完整可运行代码，悬浮山体保持无重力漂浮，荧光植物带有微弱呼吸闪烁动画。"""),
    dict(sid="H-13", title="2001 太空漫游｜黑色方碑 Monolith 与星门穿越", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：2001太空漫游名场面，神秘漆黑光滑黑色方碑Monolith伫立在太空虚空，方碑表面完全无划痕反光；触发星门穿越特效，周围空间发生色彩扭曲畸变，高速流动彩色粒子流向远方无限延伸，宇宙深空背景。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD飞行漫游；UI按钮触发星门穿越动画，相机跟随进入跃迁效果。
美术：极简冷峻复古科幻，低饱和度，强烈明暗对比，神秘肃穆，迷幻跃迁流光视觉。
技术：Three.js，OrbitControls，自定义着色器实现空间扭曲，bloom后期，粒子高速流动系统，全部基础几何体构建，单文件自包含HTML，无外部资源。
输出完整可运行代码，方碑保持完美镜面反光，星门跃迁动画流畅可触发。"""),
    dict(sid="H-14", title="指环王｜魔多末日火山与索伦巨眼", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：指环王魔多末世场景，荒芜焦黑魔多荒原，地面流淌滚烫岩浆，中央高耸末日火山持续喷发熔岩火光，高空悬浮巨大燃烧的索伦之眼，眼球缓慢转动，乌云翻滚，暗红色昏暗天空，远方破碎山脉。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD自由飞行，可以靠近火山口，仰望高空索伦巨眼；UI可调节火山喷发强度。
美术：暗黑中土奇幻史诗，熔岩橙红与暗黑对比，浓烟雾气，压抑毁灭氛围感。
技术：Three.js，OrbitControls，粒子实现岩浆喷发浓烟，bloom辉光，噪声生成荒漠地形，全部几何体搭建，单文件HTML，无外部模型。
输出完整可运行代码，索伦眼球自带缓慢转动动画，火山喷发粒子持续动态输出。"""),
    dict(sid="H-15", title="复仇者联盟｜纽约大战奇塔瑞传送门", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：复仇者联盟纽约大战，三维曼哈顿城市楼宇，城市上空撕开巨大扭曲空间传送门，外星奇塔瑞战舰源源不断从传送门涌出，城市多处爆炸火光，碎片飞溅，乌云城市夜景，城市灯火。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD飞行，可俯瞰全城，靠近传送门观察战舰涌出；UI开关传送门开启关闭。
美术：现代超级英雄电影质感，夜晚霓虹城市，爆炸火光辉光，空间撕裂扭曲特效，激烈战斗氛围。
技术：Three.js，OrbitControls，自定义shader传送门扭曲效果，实例化生成战舰集群，粒子爆炸火光，程序化城市建筑，单文件HTML，无外部资源。
输出完整可运行代码，传送门持续吐出战舰，爆炸粒子动态生效。"""),
    dict(sid="H-16", title="哈尔的移动城堡｜行走的机械移动城堡", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。 场景：哈尔的移动城堡，巨大拼接复古机械城堡，多条粗壮机械金属腿，外壳混杂锈迹金属、砖石、烟囱，烟囱冒出滚滚蒸汽，城堡在起伏绿色荒野地貌缓慢行走，远处层叠云层与远山。 交互：鼠标拖拽旋转相机，滚轮缩放，WASD环绕飞行观察城堡；UI可以开启/关闭城堡行走动画。 美术：吉卜力复古奇幻工业风，做旧金属锈迹材质，柔和天光，温暖童话末世氛围感。 技术：Three.js，OrbitControls，骨骼动画逻辑实现机械腿行走，粒子蒸汽烟雾，噪声荒野地形，bloom，全部几何体拼接，单文件HTML。 输出完整可运行代码，机械腿循环行走，城堡整体向前移动，烟囱持续冒出蒸汽粒子。"""),
    dict(sid="H-17", title="星际｜土星环巨型旋转环形空间站", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：浩瀚宇宙，巨大旋转环形人造空间站，环形结构内部拥有人造山川、湖泊、森林，依靠自转模拟重力；空间站外侧壮丽土星与宽大土星环悬浮背景，四周璀璨星空星云。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD自由飞行，可以飞到环内部浏览人造地表，也可以远距离观看土星全景。
美术：硬科幻写实风格，巨大尺度感，柔和星球光晕，宇宙深空静谧宏大。
技术：Three.js，OrbitControls，实例化构建环形建筑，噪声生成环内地形，bloom辉光，星空粒子系统，单文件自包含HTML，无外部模型。
输出完整可运行代码，空间站持续自转，环内光照跟随旋转变化。"""),
    dict(sid="H-18", title="进击的巨人｜超大型巨人破墙", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：进击的巨人，巨型高墙围城都市，60米超大型巨人伫立墙体外侧，全身升腾滚滚高温白色蒸汽，墙体大块碎石崩裂崩塌，碎石向下坠落，城镇废墟，阴沉灰暗天空。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD漫游；UI按钮触发巨人破墙崩塌动画。
美术：暗黑末日动漫写实，灰暗冷色调，压迫毁灭氛围，大量蒸汽烟雾。
技术：Three.js，OrbitControls，粒子蒸汽与碎石坠落，程序化墙体建筑，bloom，单文件HTML，全部几何体搭建。
输出完整可运行代码，巨人持续释放蒸汽，墙体碎裂坠落动画可以触发播放。"""),
    dict(sid="H-19", title="银河护卫队｜Knowhere 天神族头颅空间站", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：宇宙深空漂浮一颗死去天神族巨大颅骨，颅骨内部空腔改造为城市空间站，洞窟内部布满建筑、码头、霓虹灯光，空间站外部停靠小型飞船，远方多彩星云与行星环绕。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD飞行，可以飞入颅骨内部城市，远距离观察整颗头颅。
美术：漫威太空科幻，内部赛博朋克霓虹灯光，宇宙星云绚烂色彩，宏大诡谲尺度感。
技术：Three.js，OrbitControls，实例化内部建筑，粒子星云，bloom辉光，单文件HTML，基础几何体组合构造颅骨形态，无外部资源。
输出完整可运行代码，颅骨内部灯光闪烁，飞船缓慢漂浮巡航。"""),
    dict(sid="H-20", title="攻壳机动队｜赛博朋克全息雨夜都市", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。
场景：雨夜赛博朋克未来都市，密集高耸摩天大楼，湿漉漉反光街道，漫天漂浮破碎半透明彩色全息广告投影，浓雾弥漫，霓虹蓝紫粉灯光，雨水持续下落。
交互：鼠标拖拽旋转相机，滚轮缩放，WASD在楼宇之间穿梭飞行；UI调节降雨强度。
美术：赛博朋克电影质感，高对比霓虹，潮湿反光材质，雨夜朦胧雾气，迷离都市氛围。
技术：Three.js，OrbitControls，粒子雨水系统，shader实现全息半透明破碎投影，雾效，bloom后期，程序化生成楼房，单文件HTML。
输出完整可运行代码，雨水持续下落，全息投影碎片漂浮闪烁。"""),
    dict(sid="H-21", title="哈利波特｜霍格沃茨城堡与摄魂怪黑雾来袭", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""生成完整独立Three.js交互式3D单文件HTML，浏览器直接运行。 场景：夜晚湖畔霍格沃茨魔法城堡，城堡灯火点点，背靠黑色山林，湖面倒映月光；大量摄魂怪化作流动黑色迷雾集群，从森林方向缓缓向城堡飘来，漂浮幽灵光点，清冷月光夜空。 交互：鼠标拖拽旋转相机，滚轮缩放，WASD漫游；UI开关摄魂怪进攻动画。 美术：暗黑奇幻魔法风格，冷蓝色月光，黑雾朦胧，神秘压抑氛围感。 技术：Three.js，OrbitControls，粒子系统实现摄魂怪黑雾，湖面反射shader，雾效，bloom，程序化城堡山体，单文件HTML。 输出完整可运行代码，黑雾集群缓慢向城堡移动，湖面月光倒影动态。"""),
    dict(sid="H-22", title="千与千寻｜海上列车镜面水面（Canvas 2D）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML、CSS、原生Canvas，禁止引入Three.js、外部JS库、外部图片资源。
2D动画场景：还原千与千寻海上列车经典名场面，一望无际的镜面感平静海面，老式蒸汽列车平稳行驶在海面之上，水面完整反射列车、云朵与黄昏天空，天空云层缓慢流动，水面生成细碎柔和波纹。
交互：鼠标在画布上移动，会扰动局部水面波纹，产生涟漪扩散效果。
美术风格：吉卜力治愈动画质感，柔和黄昏暖色调，低饱和度，光影通透静谧。
技术约束：全部绘制逻辑写在Canvas内，CSS负责页面布局，零外部依赖，直接浏览器打开即可运行。
输出完整可运行代码，确保列车行驶、云朵流动、水面倒影、鼠标波纹交互全部正常生效，不要占位注释。"""),
    dict(sid="H-23", title="EVA｜第三次冲击 生命之树红色粒子", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML、CSS、原生Canvas，禁止引入Three.js、外部JS库、外部图片资源。
2D动画场景：EVA第三次冲击名场面，巨大暗红色生命之树轮廓缓缓浮现，海量红色半透明粒子向四面八方爆炸扩散飞舞，背景浮现破碎环形宗教符文，整体氛围悲壮、迷幻、充满毁灭感。
交互：鼠标点击画布，触发完整冲击粒子爆发动画，可重复点击重播。
美术风格：高对比红黑主色调，复古动画颗粒质感，粒子带有淡出发光效果。
技术约束：Canvas实现粒子系统，CSS关键帧辅助背景动画，无外部资源，单文件自包含。
输出完整可运行代码，点击触发冲击特效，粒子生命周期、消散逻辑完整可用。"""),
    dict(sid="H-24", title="你的名字｜彗星分裂坠落夜空", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML、CSS、原生Canvas，禁止引入Three.js、外部JS库、外部图片资源。
2D动画场景：你的名场面，夜晚小镇上空，巨型彗星在空中分裂成两大块，拖拽长长的发光炽热尾焰划过漆黑夜空，大量流星碎片四散坠落，地面是万家灯火的沉睡小镇。
交互：鼠标滚轮可以调节彗星飞行移动速度。
美术风格：新海诚动画光影，深邃夜空，柔和辉光光晕，画面干净唯美。
技术约束：Canvas绘制彗星主体与粒子尾迹，CSS实现星空背景动画，零外部依赖。
输出完整可运行代码，彗星分裂、尾焰拖尾、碎片坠落、滚轮调速交互全部生效。"""),
    dict(sid="H-25", title="黑客帝国｜数字雨矩阵代码雨", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML、CSS、原生Canvas，禁止引入Three.js、外部JS库、外部图片资源。
2D动画场景：黑客帝国经典矩阵数字雨效果，大量日文片假名、数字、符号从上高速向下坠落，字符明暗闪烁，部分字符高亮发光，纯黑色背景，赛博朋克冷峻氛围。
交互：鼠标在画布移动，局部区域字符下落速度、字符密度跟随鼠标位置发生变化。
美术风格：经典矩阵绿黑配色，高对比度，极简赛博风格。
技术约束：Canvas完成字符渲染下落逻辑，无外部依赖。
输出完整可运行代码，数字雨持续循环渲染，鼠标交互逻辑正常工作。"""),
    dict(sid="H-26", title="咒术回战｜无量空处 领域展开网格", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML、CSS、原生Canvas，禁止引入Three.js、外部JS库、外部图片资源。
2D动画场景：咒术回战无量空处领域展开，无限向远方延伸的透视白色网格平面，空间持续发生波动畸变，网格顶点扭曲扰动，营造虚无、空旷、静止的领域空间感。
交互：鼠标拖拽画布，会带动网格发生空间扭曲形变。
美术风格：极简灰白配色，干净空旷，低饱和度，虚无压迫的领域氛围感。
技术约束：Canvas绘制透视网格，顶点数组做扰动动画，无外部资源。
输出完整可运行代码，网格无限延伸动画、鼠标拖拽扭曲交互完整可用。"""),
    dict(sid="H-27", title="天气之子｜穿透云层的光柱，漂浮雨水反转", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件 HTML，仅使用 HTML、CSS、原生 Canvas，禁止引入 Three.js、外部 JS 库、外部图片资源。 2D 动画场景：天气之子名场面，厚重乌云云层裂开缝隙，巨大金色光柱穿透云层倾泻而下，一部分雨滴正常下落，另一部分雨水粒子反向向上漂浮飞舞，城市远景朦胧。 交互：鼠标点击切换下雨 / 雨之奇迹反转两种粒子模式。 美术风格：新海诚光影，通透柔光，蓝灰冷调搭配金色光柱。 技术约束：Canvas 粒子系统，CSS 云层动画，零外部依赖。 输出完整可运行代码，光柱效果、双向雨水粒子、点击切换交互正常。"""),
    dict(sid="H-28", title="哪吒｜混天绫漫天翻涌，红莲火焰扩散", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=False,
         note="", prompt="""生成完整独立单文件 HTML，仅使用 HTML、CSS、原生 Canvas，禁止引入 Three.js、外部 JS 库、外部图片资源。 2D 动画场景：哪吒名场面，火红混天绫绸带在画面中漫天盘旋翻涌流动，大片红莲火焰波纹向外一圈圈扩散，火星碎屑四处飘散。 交互：鼠标位置牵引混天绫流动轨迹。 美术风格：国漫浓烈红橙火焰色调，绸带飘逸柔滑，火焰光晕浓烈。 技术约束：Canvas 贝塞尔曲线绘制绸带，粒子实现火焰火星，无外部资源。 输出完整可运行代码，绸带动态缠绕、火焰扩散、鼠标牵引交互生效。"""),
    dict(sid="H-29", title="纯 CSS 海边日落潮汐涨落", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML + CSS，禁止JavaScript、外部图片与第三方库。 纯CSS动画实现海边日落潮汐场景，周期25秒无限循环。海平面潮水缓缓涨潮退潮；天空从橙红日落，过渡到紫蓝色夜晚；太阳缓缓沉入海平面；海浪用CSS transform模拟往复拍打岸边；远处简约帆船随海浪上下浮动；海面有波光闪烁。 交互：鼠标hover暂停动画。 美术：简约治愈插画，色彩柔和渐变。 全部动画由CSS keyframes完成，不写任何JS代码，单文件浏览器直接运行，输出完整可运行代码。"""),
    dict(sid="H-30", title="纯 CSS 萤火森林夜晚", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML + CSS，禁止JavaScript、外部图片与第三方库。
纯CSS动画幽暗森林场景，深色树木剪影，大量萤火虫光点随机漂浮闪烁，林间薄雾缓慢流动，月光从树冠缝隙洒下，草丛轻微随风摆动。动画周期18秒循环。
交互：鼠标移入画布，萤火虫会向鼠标位置飞舞。
美术：静谧夜晚奇幻氛围感，低饱和度暗调，柔和发光光晕。
全部运动闪烁效果只用CSS keyframes、transform、opacity实现，禁止JS，输出完整可运行代码。"""),
    dict(sid="H-31", title="纯 CSS 樱花飘落山坡", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML + CSS，禁止JavaScript、外部图片与第三方库。
纯CSS动画春日山坡场景，山坡上一棵巨大樱花树，大量粉白色樱花花瓣持续随风飘落，花瓣旋转、漂移；远处平缓山丘，渐变淡蓝色天空，云朵缓慢横向移动。22秒循环动画。
交互：鼠标hover，花瓣飘落速度减慢。
美术：日系清新卡通画风，柔和马卡龙配色。
所有飘落、云朵运动全部CSS keyframes实现，禁止JS，输出完整可运行代码。"""),
    dict(sid="H-32", title="纯 CSS 篝火夜晚露营", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""生成完整独立单文件HTML，仅使用HTML + CSS，禁止JavaScript、外部图片与第三方库。
纯CSS动画露营夜景，画面中心一堆篝火，火焰上下跳动、火星向上飘散；旁边简易帐篷剪影；远处山林剪影，星空星星明暗闪烁。篝火火光带动周围环境亮度周期性明暗变化。周期16秒循环。
交互：点击（CSS:active）放大篝火火焰。
美术：夜晚暖黄火光氛围感，暗色调背景。
火焰跳动、火星飘散、星星闪烁全部使用CSS动画，禁止JS，输出完整可运行代码。"""),
    # ---------------------------------------------------------------- H2 --
    dict(sid="H-33", title="超写实的旧金山金门大桥交互式 3D 体验", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="原帖允许使用 imagegen 生成初始资产；CE-Bench 离线口径下由模型程序化生成，偏差已记录。",
         prompt="""创建一个超写实的旧金山金门大桥交互式3D体验,允许我自由飞翔环绕。环境需包含真实的照明、水体、雾气、大气效果、悬索、车流、周边海岸线及城市背景,并具备电影级的尺度感和细节。让我能通过直觉式的飞行控制和多视角(包括近距离结构穿梭和大场景俯瞰)平滑地进行场景导航。核心要求是真实感、沉浸感和视觉忠实度。在测试运行时,务必从多个距离和角度环绕大桥飞行,验证导航的平稳性与稳定性,并确保场景无论远近都极具说服力。你可以利用imagegen技能生成建模所需的初始资产。视觉效果绝不能有任何"方块感"或"廉价感",必须达到高保真、极度平滑、逼近真实照片的质感。桥面上应有真实的车辆通行。不必急于求成,如果需要,即使耗时一小时也可以。请不断迭代,直至完美。"""),
    dict(sid="H-34", title="交互式 3D 还原山西应县木塔", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""用网页实现一个交互式3D模型,精准还原山西应县木塔(佛宫寺释迦塔)。要求:基于真实历史结构(八角形、五层六擔明五暗四九层、双套筒结构、大量斗拱细节);使用Three.js/Bakylon.js/Model-Viewer等WebGL技术;支持鼠标/触屏旋转、缩放、平移,可点击查看每层结构;风格写实,突出木质纹理和榫卯、斗拱细节;兼容主流浏览器,加载流畅,添加简单光影和环境效果。"""),
    dict(sid="H-35", title="一艘可完全探索的星舰", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=True,
         note="", prompt="""用 Three.js 构建一个游戏的演示版本，一艘可完全探索的星舰，配备可操作的驾驶舱、船员舱、从真实舷窗外漂过的行星、动态光照、睡眠/进食互动等功能。"""),
    dict(sid="H-36", title="3D Rubik's Cube simulation（自动求解）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="游戏", short=False,
         note="", prompt="""Create a single HTML file containing a fully functional 3D Rubik's Cube simulation using Three.js (via CDN). The cube must be able to automatically solve itself."""),
    dict(sid="H-37", title="Solar System Explorer 单页应用", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="网页", short=False,
         note="", prompt="""Create a single-page app in a single HTML file with the following requirements:
- Name: Solar System Explorer
- Goal: Visualize planets orbiting the sun.
- Features: Click planets for info, orbit speed control, and, drag to rotate, zoom in/out.
- The UI should be dark-themed and interactive."""),
    dict(sid="H-39", title="3D 乐高拼砖沙盒", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="游戏", short=True,
         note="", prompt="""用 Three.js 构建一个网页 3D 乐高拼砖沙盒：积木可拖拽放置、旋转、更换颜色，具备精确的网格吸附与碰撞检测，不允许积木重叠；支持轨道相机、撤销/重做与作品本地保存。"""),
    dict(sid="H-40", title="纯 SVG 等距互动岛屿地图", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=True,
         note="", prompt="""生成一张等距（isometric）风格的纯 SVG 互动岛屿地图：岛上分四大主题区域（如火山、森林、港口、雪山），点击区域一键平滑缩放进入并展示细节，支持拖拽浏览与返回全景；全部图形用 SVG 绘制，不用位图。"""),
    dict(sid="H-41", title="太阳系模拟器（N 体数值积分）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=True,
         note="", prompt="""构建一个浏览器内的太阳系模拟器：不要硬编码轨道参数，而是从万有引力第一性原理出发做 N 体数值积分推导行星运动；提供时间加速、行星聚焦视角，并基于模拟结果预测并标注未来的日食发生时间；用 Three.js 或 Canvas 实现，附简短物理说明面板。"""),
    dict(sid="H-42", title="浏览器内 3D CAD 编辑器 + STL 导出", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="工具", short=True,
         note="", prompt="""开发一个浏览器内的 3D CAD 编辑器：支持基本体建模（拉伸、布尔、倒角）、参数面板、场景树与 STL 导出（可 3D 打印）；内置一个 AI copilot 输入框，能把自然语言指令转成建模操作（本地规则实现即可）；最后用它建出一个完整的可打印模型作为演示。"""),
    dict(sid="H-43", title="WebGL 流体模拟（节拍同步）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=True,
         note="", prompt="""写一个网页流体模拟（WebGL 着色器实现的流体或粒子流体）：加载一段音乐后做节拍检测，让流体的扰动、颜色脉冲与镜头推拉严格同步到节拍；提供音乐上传、粒子密度与配色方案控制。"""),
    dict(sid="H-44", title="3D 椋鸟群飞 boids + 手势 + 生成式配乐", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=True,
         note="", prompt="""用 Three.js 实现 3D 椋鸟群飞（murmuration）模拟：数千只鸟的 boids 群体算法；接入摄像头手势追踪（如 MediaPipe Hands），用手的位置驱动鸟群聚散；再配一段随鸟群运动实时变化的生成式配乐（Web Audio 合成）。"""),
    dict(sid="H-45", title="3D 体素玩具箱应用", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="工具", short=True,
         note="", prompt="""构建一个 3D 体素（voxel）玩具箱应用：可逐格搭建、拆解、重混体素模型，提供调色板换色、镜像与图层工具，轨道相机与光影渲染；内置 2-3 个示例模型（小房子、小动物）供拆解重组；支持导出截图。"""),
    dict(sid="H-46", title="Biome Lab 程序化生态沙盒", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="工具", short=False,
         note="", prompt="""Build “Biome Lab,” a procedural ecosystem sandbox that runs entirely in the browser. The main view is a living 3D terrarium containing terrain, water, plants, and a few simple animal populations. Let users adjust rainfall, temperature, terrain height, water level, and species balance, then immediately see the ecosystem respond.

Use deterministic procedural rules rather than an external API or large dataset. Changes should affect plant coverage, water, animal counts, colors, and ambient motion, with compact charts showing population and environmental trends. Include useful presets, a seed control, pause and play, reset, and randomize. The result should feel like a visual experiment, not a scientific dashboard.

Keep the simulation understandable and performant rather than biologically exhaustive. Support desktop and mobile, run build and lint, and verify presets, controls, reset, and sustained animation in the browser with no console errors or major frame-rate issues."""),
    dict(sid="H-48", title="twigl 新哥特式塔楼城市着色器", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="生成艺术", short=True,
         note="", prompt="""创建一个视觉上有趣的着色器，可以在 twigl-dot-app 中运行，让它像一座无限的新哥特式塔楼城市，部分淹没在风暴洋中，伴有大浪。"""),
    dict(sid="H-50", title="Three.js 粒子背景（5000 粒子 + bloom）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="前端", short=False,
         note="", prompt="""Three.js particle background scene. 5000 particles, mouse position attraction effect, bloom glow shader, responsive canvas, auto resize, maintain 60fps. Single HTML file via CDN."""),
    dict(sid="H-51", title="Three.js 等距场景射线拾取", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="前端", short=False,
         note="", prompt="""Three.js isometric scene with raycasting. Click 3D cubes to trigger color change. Ambient + directional lighting, orbit controls, fog effect, antialiased renderer."""),
    dict(sid="H-52", title="Three.js 点云场景", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=False,
         note="", prompt="""Three.js point cloud scene loaded from JSON coordinate data. Instanced points, adjustable point size, color mapping based on point attribute, orbit controls, frustum culling, adaptive rendering. CDN standalone HTML."""),
    dict(sid="H-54", title="「城市命脉」Metaball 数据艺术", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=True,
         note="", prompt="""我想开发一个名为'城市命脉'的Web数据艺术作品。它能将城市预算和人口统计数据，通过动态、流动的液态隐喻（Metaball）进行可视化，讲述数据背后的故事。"""),
    dict(sid="H-58", title="推理芯片四十二年周期交互研究网页", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=False,
         note="原帖要求真实产业数据与可点击钻取来源；CE-Bench 离线口径下按 mock 数据处理，偏差已记录。",
         prompt="""写一个关于推理芯片行业 42 年周期（1985–2026）的深度研究交互网页。把历史切成六个窗口——FPGA 创立、光通信繁荣与崩塌、安静的十年、TPU 点火、短缺与并购超级周期、当前 AI 周期——重建每轮"需求点火→重复下单→产能到达→行业出清"的共同机制。包含 26 张可交互图表：四十二年墙图时间线、14 家公司生命线、HBM 与 CoWoS 产能、Top-4 资本开支压力表、机制矩阵、情景树；右侧数据面板随章节联动。结论落在 Base（2025→2028E 约 2.5 倍）/ Conservative / Contraction 三种情景，附 +14% 资本开支增速的 kill switch 与八个可证伪触发器。编辑级排版，每张图可点击钻取数据来源。"""),
    # ---------------------------------------------------------------- H3 --
    dict(sid="H-65", title="SpaceX Launch Atlas 交互式 3D 地球", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="可视化", short=False,
         note="原帖要求 Launch Library 2 真实数据；CE-Bench 离线口径下按 mock 数据处理。",
         prompt="""Build SpaceX Launch Atlas — an interactive 3D globe in the browser. 708 real SpaceX launches, March 2006 → July 2026, pulled from Launch Library 2. 4 sites mapped: Cape Canaveral 465, Vandenberg 216, Starbase 22, Omelek 5. Every rocket family: Falcon 9 669, Starship 22, Falcon Heavy 12, Falcon 1 5, plus 11 failures. 20 years of launches replayed in ~75 seconds — live counters, launch beams firing off the globe, color-coded by rocket. React 19 + TypeScript + Three.js, GLSL shaders on the GPU, NASA Blue Marble texture, NASA-style UI."""),
    dict(sid="H-66", title="1660 年新阿姆斯特丹历史地图复刻", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=True,
         note="", prompt="""Create New Amsterdam in 1660 (current day New York City) based on real historical maps, doing its own research"""),
    dict(sid="H-67", title="实时交互 3D 粒子银河系", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=True,
         note="", prompt="""用Three.js创建一个实时交互的3D粒子银河系"""),
    dict(sid="H-68", title="指环王开篇第一段 3D 动画", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="动画", short=True,
         note="与 H-69 语义近似但逐字 prompt 不同，哈希去重不剔除。",
         prompt="""将《指环王》开篇第一段用Three.js制作成3D动画，预算100万token"""),
    dict(sid="H-69", title="指环王开篇第一段 Three.js 渲染", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="动画", short=True,
         note="与 H-68 语义近似但逐字 prompt 不同，哈希去重不剔除。",
         prompt="""用Three.js把《指环王》开篇第一段渲染出来"""),
    dict(sid="H-70", title="音乐封面 3D 浏览器", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="工具", short=True,
         note="", prompt="""做一个音乐封面 3D 浏览器。先做数据层，准备专辑名、封面、歌手和曲目列表，用本地 JSON。先把内容跑通，别急着调动画。再做 3D 封面墙。"""),
    dict(sid="H-71", title="复刻 Karpathy 指环王 3D Demo 呈现桃花源记", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=True,
         note="", prompt="""复刻Karpathy《指环王》3D Demo，用3D方式呈现《桃花源记》"""),
    # ---------------------------------------------------------------- H5 --
    dict(sid="H-75", title="Mini World 给 4 岁半孩子的小星球 3D 游戏", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="游戏", short=False,
         note="", prompt="""Let’s create a game called Mini World. It’s a 3D world exploration game with a beautiful, high-quality graphic interface, designed to be fun and easy to play for my four-and-a-half-year-old son. You should be able to zoom in and zoom out. From far away, the world looks like a small ball, but inside it has different regions to explore. One region can look like a forest, another can be a desert, and there can also be oceans where the character can swim around. The game has to feel fun and playable, with a character who can travel around different parts of the world, explore different environments, and discover things along the way. Please treat making this work properly as the main goal. It should be beautifully designed and thoroughly tested in a loop so that the movement, zooming, exploration, swimming, environments, controls, and overall experience all work smoothly together. Keep testing and improving it until everything is working reliably and the game feels polished, intuitive, and enjoyable for a young child."""),
    dict(sid="H-76", title="电动机工作原理 3D 动画（磁场/电子）", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""Create a very realistic animation of how an electric motor works showing everything clearly even the magnetic field, electrons etc. Single HTML file. Use any libs via CDN."""),
    dict(sid="H-77", title="雨夜便利店街角微缩 3D 场景", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""请制作一个雨夜便利店街角小场景，以第三视角观察整个场景，整体像一个可以自由拖拽、旋转、缩放观看的微缩三维模型 / 小型景观，没有任何UI界面元素。地面为一个完整的正方形底座，所有元素都搭建在这个底座上，构图紧凑、层次清晰，整体呈现出小巧、精致、可收藏的模型感。画面风格为三渲二，强调浓厚的日式二次元动画氛围，材质表现干净，轮廓明确，色彩柔和但富有夜景霓虹的层次感。场景主体是一处日式便利店街角，便利店位于底座的视觉中心，外部有典型的日式街角元素：便利店招牌、玻璃橱窗、自动门、屋檐雨棚、门口地垫、自动贩卖机、自行车、雨伞架、垃圾桶、路灯、电线杆、电线、路牌、街角护栏、停车位、排水沟、积水路面、反光斑马线、小巷入口、空调外机、小型公告栏或海报栏等。街道不需要太大，但要有明确的街角转折感，像日本动画里常见的夜晚社区一角。"""),
    dict(sid="H-78", title="Sunset Bay 霓虹海岸驾驶游戏", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="游戏", short=True,
         note="", prompt="""build "Sunset Bay", a neon Florida-style coastal city in Three.js, fully playable, everything procedural, no external assets"""),
    dict(sid="H-79", title="3D 机甲展示 + 可玩射击网页游戏", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="游戏", short=False,
         note="原帖允许搜索/软件生成资产；CE-Bench 离线口径下由模型程序化生成，偏差已记录。",
         prompt="""请你帮我做一个3D机甲的炫酷展示凭条，包括一个精细的、包含精细纹理贴图的3D机甲，以及拆解的不同模块的设计和设计原理图。所有的结果生成后可以用网页的形式来呈现。你可以用搜索和一些软件来实现目标，以完成质量为主要目标。我想你进一步，基于这个机甲模型，开发一个3D网页设计游戏，机甲支持短暂跳跃飞行，支持射击，不同武器切换和瞄准发射。请保证游戏可玩。"""),
    dict(sid="H-80", title="云顶天宫：浮空岛上的中国寺庙像素方块世界", model="Vibe3D 纯文输入",
         author="owner collection", url="", date="2026-11-25", primary="3D", short=False,
         note="", prompt="""Build an interactive pixel-block 3D world centered on a Chinese temple. Place the temple on an isolated floating island surrounded by pink cherry-blossom trees, waterfalls and a layered mountain panorama. Make all major pieces readable and editable in code, choose the composition without asking follow-up questions, and add a simple day/night switch that changes sky, lighting, shadows and water color. Include orbit, zoom and reset controls and make the scene run smoothly in a browser."""),
]


def norm_hash(prompt: str) -> str:
    return hashlib.md5(re.sub(r"\s+", " ", prompt).strip().encode("utf-8")).hexdigest()


def known_hashes() -> set[str]:
    out: set[str] = set()
    for p in CORPUS_FILES:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                pr = r.get("prompt") or ""
                if pr.strip():
                    out.add(norm_hash(pr))
    return out


def corpus_record(r: dict) -> dict:
    prompt = r["prompt"].strip()
    tags = norm_tech(infer_tags(prompt + " " + r["title"]))
    if not tags:
        tags = ["code2frontend", "code2html"]
    primary = r["primary"] if r["primary"] in PRIMARY_KEYS else "工具"
    published = f"{r['date']}T00:00:00+00:00" if r["date"] else ""
    return {
        "id": f"x25-{r['sid']}",
        "number": None,
        "modelId": "",
        "modelLabel": r["model"],
        "sourceSection": f"X batch {BATCH}",
        "title": r["title"],
        "originalTitle": r["title"],
        "author": r["author"],
        "xUrl": r["url"],
        "links": [],
        "prompt": prompt,
        "promptHash": norm_hash(prompt),
        "note": (r["note"] or "verbatim prompt from owner-supplied markdown table; "
                 "no third-party runnable artifact pinned"),
        "evidence": "post-only",
        "categories": [],
        "primaryCategory": primary,
        "promptStatus": "short_verbatim" if r["short"] else "full",
        "collection": "",
        "collectionIndex": None,
        "failed": False,
        "rank": None,
        "relatedCaseIds": [],
        "addedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "publishedAt": published,
        "dateLabel": r["date"],
        "image": "",
        "mediaCaption": "",
        "video": "",
        "mediaSources": [],
        "demoUrl": "",
        "dateDisplay": r["date"],
        "containPreview": False,
        "code2Tags": tags,
        "code2Signals": {"derived_by": "scripts/expand_tasks.py::infer_tags",
                         "batch": BATCH},
        "contentLicense": "CC-BY-NC-4.0",
        "licenseNote": "Third-party community prompt; attribution recorded, no artifact vendored.",
        "attribution": {"creator": r["author"], "sourceUrl": r["url"]},
    }


def manifest_entry(rec: dict, r: dict) -> dict:
    return {
        "task_id": rec["id"],
        "title": rec["title"],
        "model_label": rec["modelLabel"],
        "code2_tags": rec["code2Tags"],
        "domains": tracks_from(rec["code2Tags"]),
        "prompt_status": rec["promptStatus"],
        "evidence_level": "B",
        "prompt_chars": len(rec["prompt"]),
        "published_at": rec["publishedAt"],
        "demo_url": "",
        "source_post_url": rec["xUrl"],
        "author": rec["author"],
        "license": rec["contentLicense"],
        "failed": False,
        "related_case_ids": [],
        "contamination_split": None,
        "set": "extended",
        "source_origin": SOURCE_ORIGIN,
        "batch": BATCH,
        "source_sid": r["sid"],
        "prompt_tier": "short_verbatim" if r["short"] else "full",
        "reference_kind": "post-only",
        "has_reference_oracle": False,
        "meta_test_applicable": False,
        "quality_gate": (
            "complete verbatim prompt (short_verbatim tier allowed by owner on "
            "2026-11-25); deliverable carryable by a single-file HTML artifact; "
            "no truncated excerpt, no paraphrase, no duplicate prompt hash"),
        "admission_note": (
            "Admitted on verbatim-prompt evidence only, under the owner-approved "
            "scale B (short but complete instructions included). No third-party "
            "runnable artifact is pinned, so the reference-oracle meta-test does "
            "not apply; L0/L1 assertions still evaluate each generated artifact."
            + (" Original post requires an input image / CDN dependency; under "
               "CE-Bench's offline single-file contract the model supplies the "
               "content procedurally." if r["sid"] in {"A-07", "A-22", "A-35"} else "")
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    triage = {}
    if TRIAGE.is_file():
        triage = {r["id"]: r for r in (
            json.loads(l) for l in TRIAGE.read_text(encoding="utf-8").splitlines() if l.strip())}
    admitted_ids = {k for k, v in triage.items() if v["status"] == "admit"}
    supplied = {r["sid"] for r in RECORDS}
    missing = admitted_ids - supplied
    extra = supplied - admitted_ids
    if missing or extra:
        print(f"triage/record mismatch: missing={sorted(missing)} extra={sorted(extra)}",
              file=sys.stderr)
        return 2

    known = known_hashes()
    seen: set[str] = set()
    records: list[dict] = []
    pairs: list[tuple[dict, dict]] = []
    dup_existing: list[str] = []
    dup_within: list[str] = []
    for r in RECORDS:
        h = norm_hash(r["prompt"])
        if h in known:
            dup_existing.append(r["sid"])
            continue
        if h in seen:
            dup_within.append(r["sid"])
            continue
        seen.add(h)
        rec = corpus_record(r)
        records.append(rec)
        pairs.append((r, rec))

    entries = [manifest_entry(rec, r) for r, rec in pairs]

    tiers = Counter(e["prompt_tier"] for e in entries)
    prim = Counter(rec["primaryCategory"] for rec in records)
    tracks = Counter(t for rec in records for t in tracks_from(rec["code2Tags"]))
    tech = Counter(t for rec in records for t in rec["code2Tags"])

    print(f"supplied={len(RECORDS)}  admitted={len(records)}  "
          f"dup_vs_existing={len(dup_existing)} {dup_existing}  "
          f"dup_within_batch={len(dup_within)} {dup_within}")
    print(f"tiers={dict(tiers)}")
    print(f"primary={dict(prim)}")
    print(f"tracks={dict(tracks)}")
    print(f"tech={dict(tech)}")

    if args.dry_run:
        print("(dry-run; nothing written)")
        return 0

    OUT_CORPUS.write_text(
        "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in records),
        encoding="utf-8")

    em = json.loads(EXT_MANIFEST.read_text(encoding="utf-8"))
    existing_ids = {t["task_id"] for t in em["tasks"]}
    assert not (existing_ids & {e["task_id"] for e in entries}), "task id collision"
    em["tasks"] = em["tasks"] + entries
    em["task_count"] = len(em["tasks"])
    em["total_task_count"] = 111 + len(em["tasks"])
    em["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    em["batches"] = sorted(set([*(em.get("batches") or ["2026-11-23"]), BATCH]))
    em["admission"]["short_verbatim_tier"] = (
        "Owner-approved 2026-11-25: a complete verbatim prompt shorter than "
        "80 chars is admissible with prompt_status=short_verbatim; the 80-char "
        "floor was designed to reject rows with NO prompt, not short instructions.")
    em["selection"] = (
        "2026-11-23: greedy minimising three-axis CV^2 (69 tasks). "
        "2026-11-25: owner-approved scale B — admit every row with a complete "
        "verbatim prompt whose deliverable a single-file HTML can carry "
        "(scripts/triage_x_batch.py), duplicates removed by prompt hash. "
        "No CV^2 pruning was applied to this batch; see honesty notes.")
    EXT_MANIFEST.write_text(json.dumps(em, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    lines = [
        "# 2026-11-25 新题批次 · 导入报告", "",
        f"生成：`{em['generated_at']}` · 尺度：**B（owner 确认）**", "",
        "## 结果", "",
        f"- 提供：**115** 行（A-01~A-36 + H-01~H-80）",
        f"- 纳入门槛判定通过：**84**（triage `docs/x-batch-triage.md`）",
        f"- 与现有 180 题 prompt 哈希重复剔除：**{len(dup_existing)}** {dup_existing or '—'}",
        f"- 批内重复剔除：**{len(dup_within)}** {dup_within or '—'}",
        f"- **实际新增：{len(entries)}** 题 → Extended {em['task_count']} 题，"
        f"全库 **{em['total_task_count']}** 题（Core-111 未改动）", "",
        f"- `full` / `short_verbatim`：**{tiers.get('full', 0)} / {tiers.get('short_verbatim', 0)}**", "",
        "## 标签派生（沿用 expand_tasks.py，未发明标签）", "",
        "| 轴 | 新增题分布 |", "|---|---|",
        f"| primary（人工按题目性质标注） | {dict(prim)} |",
        f"| track（`DOMAIN_MAP`） | {dict(tracks)} |",
        f"| tech（`infer_tags`） | {dict(tech)} |", "",
        "> **诚实说明**：这批题几乎全部落在 3D / 游戏 / 动画 / 生成艺术，",
        "> 而当前最薄的 primary 是「工具 / 前端」、最薄 track 是 `composite`、",
        "> 最薄 tech 是 `code2deck / code2world`。按尺度 B 全量纳入会",
        "> **恶化**三轴 CV² 均匀度（111→180 时 primary max/min 从 2.88 压到 1.81）。",
        "> 这是 owner 明确选择的代价，未做任何 CV² 剪枝或标签硬凑。", "",
        "## 诚实性边界", "",
        "- 全部新增题 `reference_kind=post-only`、`has_reference_oracle=false`、",
        "  `meta_test_applicable=false`；`meta_test=N/A` 不进 PASS 分母。",
        "- `assertions/meta_test.json` 写 `not_applicable_no_reference`。",
        "- 无第三方可运行产物被 vendored；仅有逐字 prompt、作者、原帖链接、日期。",
        "- A-07（需输入照片）、A-22 / A-35（允许 CDN）在 CE-Bench 离线单文件口径下",
        "  由模型程序化生成内容，偏差已写入 `admission_note`。",
        "- 语义近似题（A-05/A-06/A-12 鹈鹕族、H-68/H-69 指环王族、H-34/H-63 木塔）",
        "  逐字 prompt 不同，哈希去重不剔除；如需按语义合并须人工复核。",
        "- 被拒 31 条的逐条原因见 `docs/x-batch-triage.md`，其原文未写入语料。", "",
        "## 产物", "",
        f"- `{OUT_CORPUS.relative_to(ROOT)}` — {len(records)} 条版本化语料",
        "- `tasks/manifest_extended.json` — 追加（原有 69 条原样保留）",
        "- `scripts/triage_x_batch.py` / `scripts/import_x_batch.py` — 可复现", "",
        "下一步：`build_task_packs.py --extended-only` → 新题断言 → 写 meta_test →",
        "`build_catalog.py` → 全量验证。", "",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_CORPUS.relative_to(ROOT)} ({len(records)} records)")
    print(f"wrote {EXT_MANIFEST.relative_to(ROOT)} ({em['task_count']} extended, "
          f"{em['total_task_count']} total)")
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
