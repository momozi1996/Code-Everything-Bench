# Feishu markdown import report

Source: `Opus 5.5 和 gpt6 astra，gpt6.1 _6.2 sol ,fable5.5 ，gemini4,k3.1-pro 提示词（X）.md` (1907 lines).

## Parsing

- Table rows scanned: **934**
- Rows with a verbatim fenced Prompt: **329**
- Rows skipped (demo/screenshot/title only, no verbatim prompt): **605**

A row is admissible only when its Prompt column contains a fenced code
block. Title-only rows (B-class demos, the 9x28 'candidate pool' tables)
are deliberately excluded: a paraphrase is not a runnable task prompt.

## De-duplication against pinned corpus

- Distinct prompt hashes already in `data/corpus/cases.jsonl`: **273**
- `already_in_corpus`: **269**
- `duplicate_within_md`: **33**
- `new` (verbatim prompt not present in the corpus): **27**
- of those, with a runnable `.html` demo link: **0**

### New prompts by section

- 9: 4. GPT-6.1 Sol（A-16 ~ A-24）
- 6: 2. GPT-6.2 Sol（A-05 ~ A-10，灰度期，按作者自述标注）
- 4: 5. 本轮案例明细（站点解析用规范表）
- 4: 1. Claude Fable 5.2（A-01 ~ A-04）
- 4: 3. Kimi K3.1 Pro（A-11 ~ A-15）

## Output

- `data/corpus/feishu_md_records.jsonl` — 329 records with verbatim prompts.

Downstream: `scripts/expand_tasks.py` uses the `new` records plus
prompt-bearing corpus records that were dropped by the original
`.html`-only funnel, and selects tasks by label scarcity.
