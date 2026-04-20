# Sample outputs

These are **illustrative samples** of what `vibe-resume render` produces, using a
fake persona ("Alex Chen, Senior AI-assisted Software Engineer") with activity
data typical of 6–12 months of Claude Code + Cursor usage.

They show locale-specific structural differences. Your actual output is
generated from *your* AI-tool history and `profile.yaml`, so content will
differ — but the layout, section order, and locale idioms match these samples.

| Locale | Sample | Distinctives |
|---|---|---|
| `en_EU` | [resume.en_EU.md](resume.en_EU.md) | Europass labelled personal-info list, CEFR language grades |
| `ja_JP` | [resume.ja_JP.md](resume.ja_JP.md) | 職務経歴書 Markdown form (DOCX render emits the JIS Z 8303 履歴書 grid separately) |
| `zh_TW` | [resume.zh_TW.md](resume.zh_TW.md) | 繁中名詞片語、中英技術詞混排、年資用民國換算可選 |

## Generating your own

```bash
uv run vibe-resume extract           # scan local AI-tool state (1–3 min first run)
uv run vibe-resume aggregate         # group activity by project
uv run vibe-resume enrich --locale en_EU     # LLM writes achievements in locale-appropriate style
uv run vibe-resume render -f md --locale en_EU   # → data/resume_history/resume_vNNN_en_EU.md
uv run vibe-resume render --all-locales          # fan out across all 10 locales
```

To batch-produce every locale like this sample set:

```bash
for loc in en_EU ja_JP zh_TW de_DE fr_FR; do
  uv run vibe-resume enrich --locale "$loc"
  uv run vibe-resume render -f all --locale "$loc"
done
```
