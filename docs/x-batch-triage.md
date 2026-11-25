# 2026-11-25 新题批次 · 纳入门槛判定（triage，未改动任何正式文件）

生成：`2026-11-25T16:19:39+08:00` · 来源：owner 提供的两段 markdown 表格 · 共 **115** 条

> 这是 **只读分级**。本脚本只写 `data/corpus/x_batch_2026-11-25_triage.jsonl`
> 和本报告，不触碰 manifest / packs / taxonomy / catalog / results。

## 判定依据（沿用 CE-Bench 既有合约）

1. **必须有逐字 verbatim prompt**。节选（「全文见原帖回复」）、作者转述、
   步骤叙述、标题式截断都不是可复现任务。
2. **交付物必须能由单文件 HTML 承载**。`generate.py` 用 `extract_html()`
   抽取产物；MP4 / GIF / Blender 工程 / React+Vite 项目 / 原生 App
   无法进入现有评分链路。
3. **去重**：完全相同 prompt 剔除（批内重复已标注）。语义近似题
   （如 A-05/A-06/A-12 鹈鹕系列、H-68/H-69 指环王、H-34/H-63 木塔）
   需人工复核，哈希去重抓不到。
4. `MIN_PROMPT_CHARS = 80` 原用于过滤「只有标题/截图、没有 prompt」的行。
   短但完整的指令仍是可复现任务，单列为 `short` 档，由 owner 决定是否纳入。

## 总量

| 档位 | 题数 | 说明 |
|---|---:|---|
| **strict**（完整 ≥80 字符 + 单文件 HTML + 去重） | **53** | 直接符合现有 extended 门槛 |
| **short**（短但完整 verbatim + 单文件 HTML） | **31** | 放宽 80 字符门槛才纳入 |
| **reject** | **31** | 见下表 |
| 合计 | 115 | |

### 三种可选尺度

| 尺度 | 新纳入 | 全库题数 | 代价 |
|---|---:|---:|---|
| A 严格：只收 strict | +53 | 233 | 最稳，短题全部留在语料 |
| B 标准：strict + short | +84 | 264 | 需正式放宽 80 字符门槛并标注 `short_verbatim` |
| C 保守：CV² 均匀化只挑最补薄标签的 ~25 题 | +25 | 205 | 分布最稳，但会舍弃大量新题 |

> **落盘结果（2026-11-25，事后补记）**：owner 选择了 **B 尺度**，上表
> `+84 → 264` 是**去重前的预测值**。正式导入时按既有 prompt-hash 质量门槛
> 剔除了 6 条与 180 题库完全重复的源帖（`A-01`, `A-12`, `A-13`, `A-19`,
> `A-22`, `A-24`，它们本来就在库里），因此**实际新增 78 题 → 全库 258 题**
> （Extended 147）。这不是少收新题，而是不把同一 prompt 计两次。逐条结果见
> `docs/x-batch-import-report.md`。

**分布警告**：这批题几乎全部落在 `3d / 游戏 / 动画 / 生成艺术 / CSS`，
而当前最薄的 primary 是「工具 16 / 前端 16」、最薄 track 是 `composite 15`、
最薄 tech 是 `code2deck 8 / code2world 15`。按尺度 B 全量纳入会显著
**恶化** CV² 均匀度（上一轮 111→180 刚把 primary max/min 从 2.88 压到 1.81）。

## 拒绝原因分布

| 原因 | 题数 |
|---|---:|
| 节选 / 全文未公开 | 11 |
| 交付物不是单文件 HTML（BMK 评分链路无法承载） | 11 |
| 标题式截断 | 5 |
| 转述 / 步骤叙述，非逐字 prompt | 3 |
| 与批内其他题重复 | 1 |

## 分组明细

### A 类第一批（A-01~A-31，有 Prompt 原文 + 有效果） — 31 条

strict 6 · short 14 · reject 11

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| A-01 | FPS 关卡 + 3D 打砖块（两条提示词） | strict | 可拆为 2 题：FPS 全文完整，打砖块为中文短句 |
| A-02 | 90 秒日式动画短片（蒸汽机车变机器人） | **reject** | 节选 / 全文未公开 |
| A-03 | Getting There 14 章绘本旅程游戏 | **reject** | 转述 / 步骤叙述，非逐字 prompt |
| A-04 | 发布首日三个可抄作业案例 | **reject** | 与批内其他题重复 |
| A-05 | 火星上骑单车的鹈鹕 SVG | short | — |
| A-06 | 游戏控制器骑自行车再骑鹈鹕 SVG | short | — |
| A-07 | 照片 → 湖畔古堡 3D 单页 | short | 需上传一张照片；纯文输入无法复现 |
| A-08 | 体素赛车短片 30-40 秒单页 HTML | short | — |
| A-09 | 雨后的罗马斗兽场（无外部资产） | short | 提示词仅一句，其余要求隐含在作者固定出片规范 |
| A-10 | 几分钟从零产出的可玩 3D 游戏 | short | — |
| A-11 | Otherwhere 可交互程序化 3D 世界 | short | — |
| A-12 | 鹈鹕骑自行车 SVG 四模型横评 | short | 与 A-05/A-06 同主题但为不同 prompt |
| A-13 | 黎明埃及神庙群（挖掘/昼夜/墓室解谜） | strict | — |
| A-14 | 日本像素风街角 | short | — |
| A-15 | 飞行中的 Tesla Roadster 主题 3D 游戏 | short | — |
| A-16 | 四模型同题 3D 车祸 | short | — |
| A-17 | 樱花树环绕的日式 3D 房屋 | short | — |
| A-18 | 交互式 3D 喷气发动机剖切 | short | — |
| A-19 | 日式樱花山谷（河流/红桥/宝塔/4 机位/3 氛围） | strict | — |
| A-20 | 火山岛 Blender 代码建模（禁下载模型贴图） | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| A-21 | 三桅木帆船单页 HTML + 程序化配乐 | strict | — |
| A-22 | 《昆仑》60 秒概念片 | strict | 允许 CDN 引入 Three.js 官方扩展 |
| A-23 | 开放式「让我惊讶」3D 题 | short | — |
| A-24 | Sol/Astra/Terra 同题 WebGL 四连测 | strict | 两条示例 prompt（海带森林 / 电车），可拆 |
| A-25 | 宝可梦 SAR/UR 全息闪卡 3D 悬浮 GIF | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| A-26 | 13 个切镜的动画角色预告 | **reject** | 节选 / 全文未公开 |
| A-27 | Tide Atlas 镜海探索游戏 | **reject** | 节选 / 全文未公开 |
| A-28 | Gullwatch Isle 可探索 3D 海岛城堡 | **reject** | 节选 / 全文未公开 |
| A-29 | Bloom Pool 水面花池同题横评 | **reject** | 节选 / 全文未公开 |
| A-30 | Neon 调度 Hydrogen 蜂群做 V12 发动机 | **reject** | 转述 / 步骤叙述，非逐字 prompt |
| A-31 | TITAN 6×6 装甲怪兽卡车 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |

### G.4.A 第二批（A-33~A-36，含评论区 Prompt） — 4 条

strict 2 · short 0 · reject 2

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| A-33 | 15 秒发布会级广告动效（Gemini 4 Neon） | **reject** | 节选 / 全文未公开 |
| A-34 | 「九重天宫」电影级 Three.js + GLSL 场景 | strict | 中英双语完整提示词 |
| A-35 | 《烟雨江南：雨巷八重境》Three.js 短片 | strict | 允许 CDN 引入 Three.js |
| A-36 | 一条 Prompt 生成单文件 Canvas 射击游戏 | **reject** | 转述 / 步骤叙述，非逐字 prompt |

### H.1 Vibe3D 纯文输入（H-01~H-32） — 32 条

strict 30 · short 0 · reject 2

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| H-01 | 2030 月球中国基地建设场景 | strict | — |
| H-02 | 还原星际穿越五维空间 | strict | — |
| H-03 | 三体：舰队太阳系对峙 | strict | — |
| H-04 | 三体 二向箔降维打击→梵高星空 | strict | — |
| H-05 | 云球：球体 3D Agent 生态世界 | strict | — |
| H-06 | 鬼灭之刃：无限城非欧空间 | strict | — |
| H-07 | 爆款梵高 Three.js 连续小镇（英文） | **reject** | 节选 / 全文未公开 |
| H-08 | 中文改写爆款梵高 Three.js 小镇 | **reject** | 节选 / 全文未公开 |
| H-09 | 珍珠项链（写实 3D 商品展示） | strict | — |
| H-10 | 纯 CSS 四季变换场景动画 | strict | — |
| H-11 | 流浪地球｜行星发动机点火 | strict | — |
| H-12 | 阿凡达｜潘多拉悬浮哈利路亚群山 | strict | — |
| H-13 | 2001 太空漫游｜黑色方碑与星门 | strict | — |
| H-14 | 指环王｜魔多末日火山与索伦巨眼 | strict | — |
| H-15 | 复仇者联盟｜纽约大战传送门 | strict | — |
| H-16 | 哈尔的移动城堡｜机械行走城堡 | strict | — |
| H-17 | 星际｜土星环旋转环形空间站 | strict | — |
| H-18 | 进击的巨人｜超大型巨人破墙 | strict | — |
| H-19 | 银河护卫队｜Knowhere 天神族头颅 | strict | — |
| H-20 | 攻壳机动队｜赛博朋克全息雨夜都市 | strict | — |
| H-21 | 哈利波特｜霍格沃茨与摄魂怪黑雾 | strict | — |
| H-22 | 千与千寻｜海上列车镜面水面（Canvas 2D） | strict | — |
| H-23 | EVA｜第三次冲击生命之树红色粒子 | strict | — |
| H-24 | 你的名字｜彗星分裂坠落夜空 | strict | — |
| H-25 | 黑客帝国｜数字雨矩阵代码雨 | strict | — |
| H-26 | 咒术回战｜无量空处领域展开网格 | strict | — |
| H-27 | 天气之子｜穿透云层光柱与反转雨水 | strict | — |
| H-28 | 哪吒｜混天绫漫天翻涌红莲火焰 | strict | — |
| H-29 | 纯 CSS 海边日落潮汐涨落 | strict | — |
| H-30 | 纯 CSS 萤火森林夜晚 | strict | — |
| H-31 | 纯 CSS 樱花飘落山坡 | strict | — |
| H-32 | 纯 CSS 篝火夜晚露营 | strict | — |

### H.1 Vibe3D 续（H-33~H-59） — 27 条

strict 9 · short 10 · reject 8

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| H-33 | 超写实旧金山金门大桥 3D 体验 | strict | 允许使用 imagegen 生成初始资产，需标注 |
| H-34 | 交互式 3D 还原山西应县木塔 | strict | — |
| H-35 | 一艘可完全探索的星舰 | short | — |
| H-36 | 3D Rubik's Cube 自动求解 | strict | 单 HTML + CDN |
| H-37 | Solar System Explorer 单页应用 | strict | — |
| H-38 | 3D 交互圣诞树 R3F 7000 实例 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-39 | 3D 乐高拼砖沙盒 | short | — |
| H-40 | 纯 SVG 等距互动岛屿地图 | short | — |
| H-41 | 太阳系模拟器 N 体数值积分 | short | — |
| H-42 | 浏览器内 3D CAD 编辑器 + STL 导出 | short | — |
| H-43 | WebGL 流体模拟（节拍同步） | short | — |
| H-44 | 3D 椋鸟群飞 boids + 手势 + 生成式配乐 | short | — |
| H-45 | 3D 体素玩具箱应用 | short | — |
| H-46 | Biome Lab 程序化生态沙盒 | strict | — |
| H-47 | React 程序化 3D 城市生成器 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-48 | twigl 新哥特式塔楼城市着色器 | short | shader 片段，可由单文件 HTML 承载 |
| H-49 | R3F 产品查看器 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-50 | Three.js 粒子背景 5000 粒子 | strict | 单 HTML + CDN |
| H-51 | Three.js 等距场景射线拾取 | strict | 单 HTML |
| H-52 | Three.js 点云场景 | strict | 单 HTML + CDN |
| H-53 | R3F 后处理传送门平面 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-54 | 「城市命脉」Metaball 数据艺术 | short | — |
| H-55 | GARGANTUA 黑洞 Schwarzschild 光线追踪 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-56 | 「海的尽头」WebGPU/TSL 程序化海洋 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-57 | 赛博朋克大都会 Web-Swing 3D 游戏 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |
| H-58 | 推理芯片四十二年周期交互研究网页 | strict | 需真实产业数据，可按 mock 数据处理 |
| H-59 | THE IMPACT No.01 3D 复古打字机 | **reject** | 交付物不是单文件 HTML（BMK 评分链路无法承载） |

### H.1 Vibe3D 短题/截断区（H-60~H-71） — 12 条

strict 1 · short 6 · reject 5

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| H-60 | 5 分钟 vibe coding 人体/骨骼/肌肉 3D 模型 | **reject** | 标题式截断 |
| H-61 | Three.js 四季森林互动网站 | **reject** | 标题式截断 |
| H-62 | 把 PPT 变成可玩的 3D 微观实验室 | **reject** | 标题式截断 |
| H-63 | 交互式 3D 还原山西应县木塔 | **reject** | 标题式截断 |
| H-64 | 约 5 万座 3D 球场镜头飞入座位 | **reject** | 标题式截断 |
| H-65 | SpaceX Launch Atlas 交互式 3D 地球 | strict | 需 Launch Library 2 数据，可按 mock 处理 |
| H-66 | 1660 年新阿姆斯特丹历史地图复刻 | short | — |
| H-67 | 实时交互 3D 粒子银河系 | short | — |
| H-68 | 指环王开篇第一段 3D 动画 | short | — |
| H-69 | 指环王开篇第一段 Three.js 渲染 | short | 与 H-68 近似同题 |
| H-70 | 音乐封面 3D 浏览器 | short | — |
| H-71 | 复刻 Karpathy 指环王 3D Demo 呈现桃花源记 | short | — |

### H.2 Showcase 全栈 PRD（H-72~H-74） — 3 条

strict 0 · short 0 · reject 3

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| H-72 | 抖音沉浸式短视频信息流微信小程序 | **reject** | 节选 / 全文未公开 |
| H-73 | 申财有道 Android Jetpack Compose App | **reject** | 节选 / 全文未公开 |
| H-74 | QQ for Mac SwiftUI 客户端 | **reject** | 节选 / 全文未公开 |

### H.2 Showcase + H.3 脑暴（H-75~H-80） — 6 条

strict 5 · short 1 · reject 0

| 编号 | 题目 | 档 | 原因 / 备注 |
|---|---|---|---|
| H-75 | Mini World 给 4 岁半孩子的小星球 3D 游戏 | strict | — |
| H-76 | 电动机工作原理 3D 动画（磁场/电子） | strict | 单 HTML + CDN |
| H-77 | 雨夜便利店街角微缩 3D 场景 | strict | — |
| H-78 | Sunset Bay 霓虹海岸驾驶游戏 | short | — |
| H-79 | 3D 机甲展示 + 可玩射击网页游戏 | strict | 允许搜索/软件生成资产，需标注 |
| H-80 | 云顶天宫像素方块中国寺庙 3D 世界 | strict | — |

## 尚未做的（下一步按尺度执行）

- 逐字 prompt 全文落盘到版本化语料（目前只存元数据与字符数估算）
- 与现有 180 题做 prompt 哈希去重（含语义近似人工复核清单）
- 三轴标签派生（`expand_tasks.py::infer_tags` / `DOMAIN_MAP`）+ CV² 排序
- 生成 packs：`prompt.md` / `task.json` / `budget.json`（512000 / 120min）/
  `assertions/task.json` / `meta_test.json` / `reference/SOURCE.md`
- 重建 `manifest_extended.json` / `taxonomy.json` / `task-catalog.{html,md,csv}`
- `selftest` 里的 `111 + 69 = 180` 硬编码需同步
- 全量验证与扩题报告

**注意**：题数一旦变更，论文手稿 / Overleaf 里 Core-111 与 180 题的 census
口径需要相应重述（见 `docs/expansion-report.md` 的 Honesty notes）。
