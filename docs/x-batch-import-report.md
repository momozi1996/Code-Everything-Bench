# 2026-11-25 新题批次 · 导入报告

生成：`2026-11-25T17:36:21+08:00` · 尺度：**B（owner 确认）**

## 结果

- 提供：**115** 行（A-01~A-36 + H-01~H-80）
- 纳入门槛判定通过：**84**（triage `docs/x-batch-triage.md`）
- 与现有 180 题 prompt 哈希重复剔除：**6** ['A-01', 'A-12', 'A-13', 'A-19', 'A-22', 'A-24']
- 批内重复剔除：**0** —
- **实际新增：78** 题 → Extended 147 题，全库 **258** 题（Core-111 未改动）

- `full` / `short_verbatim`：**48 / 30**

## 标签派生（沿用 expand_tasks.py，未发明标签）

| 轴 | 新增题分布 |
|---|---|
| primary（人工按题目性质标注） | {'生成艺术': 13, '3D': 35, '动画': 5, '游戏': 7, '网页': 6, '可视化': 6, '工具': 4, '前端': 2} |
| track（`DOMAIN_MAP`） | {'animation-video': 32, 'svg-art': 3, 'game': 8, '3d': 66, 'frontend': 62, 'audio': 2, 'visualization': 13} |
| tech（`infer_tags`） | {'code2svg': 3, 'code2video': 32, 'code2game': 8, 'code23d': 66, 'code2html': 62, 'code2frontend': 47, 'code2world': 9, 'code2audio': 2, 'code2viz': 4, 'code2css': 12, 'code2canvas': 9} |

> **诚实说明**：这批题几乎全部落在 3D / 游戏 / 动画 / 生成艺术，
> 而当前最薄的 primary 是「工具 / 前端」、最薄 track 是 `composite`、
> 最薄 tech 是 `code2deck / code2world`。按尺度 B 全量纳入会
> **恶化**三轴 CV² 均匀度（111→180 时 primary max/min 从 2.88 压到 1.81）。
> 这是 owner 明确选择的代价，未做任何 CV² 剪枝或标签硬凑。

## 诚实性边界

- 全部新增题 `reference_kind=post-only`、`has_reference_oracle=false`、
  `meta_test_applicable=false`；`meta_test=N/A` 不进 PASS 分母。
- `assertions/meta_test.json` 写 `not_applicable_no_reference`。
- 无第三方可运行产物被 vendored；仅有逐字 prompt、作者、原帖链接、日期。
- A-07（需输入照片）、A-22 / A-35（允许 CDN）在 CE-Bench 离线单文件口径下
  由模型程序化生成内容，偏差已写入 `admission_note`。
- 语义近似题（A-05 / A-06 鹈鹕族、H-68 / H-69 指环王族）逐字 prompt 不同，
  哈希去重不剔除；如需按语义合并须人工复核。
- 被拒 31 条的逐条原因见 `docs/x-batch-triage.md`，其原文未写入语料。

## 产物与已完成的链路（2026-11-25 收尾）

- `data/corpus/x_batch_2026-11-25.jsonl` — 78 条版本化语料（已在 `.gitignore` 白名单）
- `data/corpus/x_batch_2026-11-25_triage.jsonl` — 115 行只读分级记录
- `tasks/manifest_extended.json` — 追加 78 条（原有 69 条原样保留，Core-111 未动）
- `scripts/triage_x_batch.py` / `scripts/import_x_batch.py` — 可复现
- `tasks/x25-*/` — 78 个新题 pack（prompt / task / budget 512000·120 /
  mutations / reference / assertions / meta_test）
- 78 套 L1 断言：`generate_assertions.py --batch 2026-11-25`（min=max=8，全部达标）
- 78 个 `meta_test.json`：`status=not_applicable_no_reference`
- `tasks/taxonomy.json`（258）、`docs/task-catalog.{html,md,csv}`（258 题）、
  `docs/results-dashboard.html`（tasks=258）全部重建
- `build_task_packs.py` 修为幂等：refresh 不再重置 `assertion_target` /
  `full_measurement`，旧 69 个 pack 保持零 diff
- `generate_assertions.py` 新增 `--batch`，避免覆盖旧 Extended-69 断言
- `build_catalog.py` / `build_task_packs.py` 接入新语料文件；
  `build_results_dashboard.py` 层级下拉改为动态计数
- 口径文档同步：`README.md`、`tasks/README.md`、`config/README.md`、
  `docs/benchmark-spec.md`、`docs/expansion-report.md`、
  `docs/harness-matrix.md`、`docs/assertion-review.md`

> **论文口径**：Overleaf 手稿的 headline census 仍是 **Core-111**（§4.1 的
> 739→111 漏斗、IRT、power analysis 均以 111 为论证基础，不能机械替换）。
> 已在 `main.tex` 补一段题库版本说明，注明公开题库为 258 题、Extended-147
> 不进入 headline 指标与 meta-test 分母。
