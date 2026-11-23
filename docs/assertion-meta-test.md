# Assertion meta-test — reference as oracle

tasks tested: 111 · reference passes every assertion: 86
tasks failing at least one L0 rule: 13
tasks failing at least one L1 assertion: 13
tasks that could not be fetched/testing failed: 0

> A reference that fails an assertion means the assertion is wrong, or the
> shared L0 contract does not apply to that task. Fix before publishing scores.

## L0 failures

| task | rule | evidence |
|---|---|---|
| b24-luna-2102509273393627524 | L0-01 Single file / no external resources | external references: external <link href>, CSS @import, remote CSS url(), known CDN domain |
| b24-luna-2102509273393627524 | L0-06 prefers-reduced-motion honoured | animation without reduced-motion branch |
| b24-sol-2102509273393627524 | L0-01 Single file / no external resources | external references: external <link href>, known CDN domain |
| b24-sol-2102509273393627524 | L0-06 prefers-reduced-motion honoured | animation without reduced-motion branch |
| b24-astra-2098841316591346006 | L0-08 Web Audio requires a user gesture | AudioContext starts without a gated gesture (autoplay risk) |
| case-010 | L0-06 prefers-reduced-motion honoured | animation without reduced-motion branch |
| case-001 | L0-01 Single file / no external resources | external references: external <script src>, external <link href>, known CDN domain |
| case-009 | L0-06 prefers-reduced-motion honoured | animation without reduced-motion branch |
| case-066 | L0-05 Animation uses requestAnimationFrame | animation present but driven by timer instead of rAF |
| case-076 | L0-05 Animation uses requestAnimationFrame | animation present but driven by timer instead of rAF |
| case-096 | L0-05 Animation uses requestAnimationFrame | animation present but driven by timer instead of rAF |
| case-097 | L0-05 Animation uses requestAnimationFrame | animation present but driven by timer instead of rAF |
| case-111 | L0-05 Animation uses requestAnimationFrame | animation present but driven by timer instead of rAF |
| x-2102665046568673765 | L0-01 Single file / no external resources | external references: external <link href> |
| gpt6-astra-2102565403109085669 | L0-01 Single file / no external resources | external references: external <script src> |

## L1 failures

| task | assertion | evidence |
|---|---|---|
| case-028 | L1-03 particle system referenced | pattern 'particle|粒子' absent |
| case-029 | L1-07 dom is touched at runtime | pattern 'document\\.(?:getElement|querySelector|body)' absent |
| case-001 | L1-04 drag/pointer interaction | pattern 'draggable|mousedown|pointerdown|touchstart' absent |
| case-043 | L1-02 3D rendering path | pattern 'perspective|transform\\s*:\\s*.*3d|THREE\\.|webgl' absent |
| case-054 | L1-07 dom is touched at runtime | pattern 'document\\.(?:getElement|querySelector|body)' absent |
| case-069 | L1-02 gradient fill used | pattern 'gradient\\(' absent |
| case-080 | L1-02 particle system referenced | pattern 'particle|粒子' absent |
| case-082 | L1-03 3D rendering path | pattern 'perspective|transform\\s*:\\s*.*3d|THREE\\.|webgl' absent |
| case-098 | L1-01 inline svg artwork present | pattern '<svg\\b' absent |
| case-105 | L1-03 gradient fill used | pattern 'gradient\\(' absent |
| case-109 | L1-03 3D rendering path | pattern 'perspective|transform\\s*:\\s*.*3d|THREE\\.|webgl' absent |
| case-114 | L1-03 particle system referenced | pattern 'particle|粒子' absent |
| gpt6-sol-2102665046568673765 | L1-03 WebGL context requested | pattern 'getContext\\(\\s*[\'\\"]webgl' absent |

