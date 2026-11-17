# Figure specifications

Six figures, one file each. Every file follows the same five-part structure:
**placement → mermaid draft → element-level layout spec → data provenance →
production drawing instructions**. Mermaid renders directly on GitHub; the
final journal assets are vector PDF/PNG produced from these specs.

| File | Figure | Paper section | Benchmarked against |
|---|---|---|---|
| [`fig1-hero.md`](fig1-hero.md) | Fig 1 hero banner | front page / website | project-site banner |
| [`fig2-overview.md`](fig2-overview.md) | Fig 2 overview | §1 | GameCraft **Figure 2** |
| [`fig3-problem-definition.md`](fig3-problem-definition.md) | Fig 3 problem definition | §3 | GameCraft **Figure 3** |
| [`fig4-construction-pipeline.md`](fig4-construction-pipeline.md) | Fig 4 construction funnel | §4 | — (ours only) |
| [`fig5-evaluation-pipeline.md`](fig5-evaluation-pipeline.md) | Fig 5 evaluation pipeline | §5 | GameCraft **Figure 5** |
| [`fig6-main-results.md`](fig6-main-results.md) | Fig 6 main results (2×2) | §7–§8 | — (ours only) |

See [`../figure-audit.md`](../figure-audit.md) for the element-by-element parity
check against the reference figures and the release checklist.

**Current state:** all six are complete specifications with mermaid drafts and
placeholder result slots `[R#]`. No figure contains a fabricated model score.
Final rendering happens after the first evaluation run.
