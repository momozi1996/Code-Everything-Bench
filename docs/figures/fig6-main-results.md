# Figure 6 · 主结果图（论文命脉；GameCraft 无对应图）

## 定位

`manuscript.md` **§7.1 Results** 的主图，也是全文的标志性图：**M1 × M2 散点**。一张图判定核心命题——生成与验收是否不对称。两种结局都可发表（判定见 §8.3，预期方向已移入 Appendix B），但图的规格与两种图注在跑批前定死，防止数据出来后"往好看的方向调整呈现"。对应的数据表是正文 **Table 9**。

## 结构：2 × 2 四联图

```
┌────────────────────────┬────────────────────────┐
│ (a) 主散点             │ (b) 校准曲线           │
│  X: Pass@Budget (M1)   │  X: 自评完成度 s       │
│  Y: 缺陷检测 F1 (M2)   │  Y: 实际通过率         │
│  每点一个 agent 配置    │  对角线 = 完美校准     │
│  气泡大小 = Cost        │  点偏离方向 = 过/欠自信│
├────────────────────────┼────────────────────────┤
│ (c) 失败分类堆叠条      │ (d) 按域雷达           │
│  X: 配置（排序）        │  8 域 × 顶 3 配置      │
│  Y: D1–D6 计数         │  每域 Pass@Budget     │
│  颜色 = D1–D6          │  （域色板同 Figure 2） │
└────────────────────────┴────────────────────────┘
```

## (a) 主散点——规格细节

| 要素 | 规格 | 理由 |
|---|---|---|
| 每点 | 一个 agent 配置（harness × model）| 延续 §6.1 单元定义 |
| X | Pass@Budget（0–100%，bootstrap CI 用横误差棒）| 主指标 |
| Y | 缺陷检测 F1（纵误差棒）| 验收构念 |
| 气泡面积 | Cost-to-Pass（美元/token）| 第三个维度塞进同一张图 |
| 点色 | 开源/闭源（两色）或厂商色 | |
| 参考线 | y = x 对角虚线 + r / τ 数值标注 | 读者无需查正文即见相关性 |
| 离群标注 | "高生成低验收"象限的点带配置名标签 | **这就是"能写出自己检查不出来的代码"的具象化** |
| 判定带 | H3 阈值 r < 0.5 区域浅色底纹 | 阈值可视化，防"事后调阈值"质疑 |
| 显著性 | 配对检验字母组（a/b/c）标在点旁 | 同组内不排序（§6.3）|

## (b) 校准曲线——RQ5a

- 对角线 = 完美校准；各配置一条校准折线（ECE 数值标注）
- 预期形态：强配置的曲线系统性压在对角线下方（过度自信）
- 若 H4 成立，图注："ECE 与生成得分 Spearman ρ = −X"

## (c) 失败分类堆叠——对应 §8.4

- 每配置一根堆叠条，六段 = D1–D6 未检出缺陷数
- 直接回答"哪个配置在哪些失败类型上盲"
- 颜色 = D1–D6 六色（与 Figure 5 缺陷分类图例一致）

## (d) 域雷达——外部效度

- 8 域 × Top-3 配置，域色板沿用 Figure 2 环形图
- 展示"域 × 配置"交互（RQ4 的可视化）

## 图注模板（预登记；跑批前定稿，两种结局只许二选一）

> **变体 A · 主张成立（偏离对角线）**
> Figure 6. Generation versus verification across `[N]` agent configurations on CE-Frozen (111 tasks, three repetitions each). Each point is one harness × model configuration; horizontal and vertical bars are bootstrap 95% CIs, and bubble area is Cost-to-Pass. Configurations X and Y are statistically indistinguishable on generation (Cliff's δ = `[δ_G]`, paired p = `[p_G]`) but differ on verification (δ = `[δ_V]`, p = `[p_V]`). The pooled correlation is r = `[r]` (95% CI `[lo, hi]`), Kendall τ = `[τ]`. Letters denote significance groups from paired Wilcoxon tests with Holm correction; no ordering is implied within a group. Panels: (b) calibration curves with ECE; (c) undetected defects by class D1–D6; (d) per-domain Pass@Budget for the top three configurations.

> **变体 B · 主张不成立（沿对角线）**
> Figure 6. Generation versus verification across `[N]` agent configurations on CE-Frozen (111 tasks, three repetitions each). Points lie close to the diagonal: the pooled correlation is r = `[r]` (95% CI `[lo, hi]`), Kendall τ = `[τ]`, so the pre-registered asymmetry hypothesis H3 is not supported. We report this as a negative result; the measurement framework and the benchmark are unaffected. Error bars are bootstrap 95% CIs; letters denote significance groups. Panels (b)–(d) as in variant A.

**约束**：两个变体除结果数字与结论句外，结构、坐标轴、色板、误差棒、显著性标注**完全一致**。不得因结局不同而增删面板或改变点色语义。变体选择由 `analysis/fig6.R` 依据预登记判据自动完成，不人工干预。

## 数据来源

- 全部来自 results/ 跑批 CSV（2027-03）
- (a)(b) 可在 5 配置跑批后先出草图，12 配置后定稿
- 每个数字由 `analysis/` 脚本生成；正文 §7 的 `[R3]`/`[R8]` 与本图同源

## 正式绘图指引

- 工具：R ggplot2 或 Python matplotlib/seaborn（**必须脚本生成**，杜绝手绘——可复现性是期刊要求）
- 尺寸：双栏全宽 ~180mm × 140mm；四联各 ~88mm
- CI 误差棒必须有；显著性字母组标在 (a) 点旁
- 色板：色盲安全（Okabe-Ito 或 viridis 衍生）；域色板全论文统一
- 图注模板见上一节；判定与降级路径见 manuscript Appendix B

## 状态

- [x] 规格 + 布局
- [x] 两种图注模板（预登记）
- [ ] 脚本（analysis/fig6.R）
- [ ] 数据（2027-03 跑批后）
