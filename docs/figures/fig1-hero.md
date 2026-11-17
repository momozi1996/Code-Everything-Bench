# Figure 1 · Hero 品牌横幅

## 定位

论文首页顶部横幅（对标 GameCraft 站点 banner 与其 Overview 大数字区）。作用：3 秒内让读者知道这是"什么的基准、多大、测什么"。

## 信息要素（全部上墙）

| 要素 | 内容 | 数据来源 |
|---|---|---|
| 一句话 | *Can agents deliver and verify what real users actually ask for?* | 与正式标题逐字一致；首次出现用全称 `Code-Everything Bench (CE-Bench)` |
| 大数字 ×3 | **111** tasks · **8** domains · **8** shared assertions | 实测（cases.jsonl / 归并 / L0 套件）|
| 副徽章 | Single-File · Runtime State Probe · Contamination-Split | 设计差异点 |
| 视觉主体 | 一个单文件 HTML 产物的浏览器窗口示意（file:// 直开、无 CDN 标注）| 论文主张：产物即交付 |

## 布局规格

```
┌────────────────────────────────────────────────────────┐
│  Code-Everything Bench (CE-Bench)                      │
│  Can agents deliver and verify what real users         │
│  actually ask for?                                     │
│                                                        │
│  ┌─────┐   ┌─────┐   ┌──────┐                          │
│  │ 111 │   │  8  │   │  8   │   ← 大号数字 + 小字标签  │
│  │tasks│   │dom. │   │assert│                          │
│  └─────┘   └─────┘   └──────┘                          │
│                                                        │
│  [浏览器窗口插画：单文件 HTML 运行中]                    │
│                                                        │
│  ● Single-File  ● Runtime State Probe  ● Contamination │
└────────────────────────────────────────────────────────┘
```

## 正式绘图指引

- 尺寸：2100 × 700 px（@2x），投稿单栏宽自适应
- 风格：浅色底（期刊印刷），主色沿用站点品牌色；浏览器窗口用真实截图（枯山水 case-085 运行画面）加标注层
- 数字用衬线粗体（期刊惯例）；徽章用胶囊形
- 禁止：渐变、3D 效果、emoji

## 状态

- [ ] mermaid 不适用（版面图）
- [ ] 等真实运行截图（2 题跑通后）
