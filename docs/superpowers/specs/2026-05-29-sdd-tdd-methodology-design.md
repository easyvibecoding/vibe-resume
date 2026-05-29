# SDD / TDD Methodology Signal (+ fix: bare `spec` miscategorized as testing)

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#44](https://github.com/easyvibecoding/vibe-resume/issues/44)
**Milestone**: 0.12.0
**Epic**: competency signals — extends the `AgenticSignals` surface from #43.

## 背景與動因

開發**方法論**(Spec-Driven Development、Test-Driven Development)是有意義的資深/agentic 競爭力,但目前未表面化,且 SDD 還被**主動誤分類**:`classifier.py` 的 TESTING regex 含裸 `\bspec\b`,讓 spec-driven 工作(`specs/`、`spec.md`、OpenSpec、Spec-Kit)被算成 **testing** 活動 —— 既灌水 testing%,又零 SDD 信號(雙重錯)。

## 目標

1. **修 bug**:收緊 TESTING regex,裸 `spec` 不再 match(改用 `\.spec\.` / `_spec` 等測試專屬形)。
2. **SDD 偵測**:新增 `AgenticSignals.sdd`(OpenSpec / Spec-Kit / spec-driven / 規格驅動 / Spec-Kit 產物 / `specs/<x>/` 樹)。
3. **TDD 偵測**:新增 `AgenticSignals.tdd`,要求方法論證據(`test-driven`/`tdd`/`red-green`/failing-test-first),與「有測試」(TESTING category)區分。
4. enrich hint 擴充,讓 enricher 能據實寫出方法論 bullet。

## 非目標

- **不**新增 classifier `Category.SDD`(會擾動 `capability_breadth`/headline 評分);方法論屬 competency,放 `AgenticSignals`(與 #43/#48 同 surface)。
- 不做 commit 順序分析(test-before-impl ordering)— 用文字證據即可,排序分析留後續。
- 不引入新依賴。

## 架構

### 1. classifier TESTING regex 收緊 — `src/vibe_resume/core/classifier.py`

把 TESTING rule(現含 `\bspec\b`)改寫為個別 word-bound、移除裸 spec、加緊縮的測試專屬 token:

```python
(Category.TESTING, re.compile(
    r"(?:\bpytest\b|\bvitest\b|\bjest\b|\bunittest\b|\bmocha\b|\bcypress\b"
    r"|\bplaywright\b|smoke\s*test|\.spec\.|_spec\b|\btests?\b|測試)")),
```

→ `spec.md` / `specs/` / `OpenSpec` / `規格驅動` 不再進 testing;`foo.spec.ts` / `pytest` / `tests/` 仍是 testing。

### 2. `AgenticSignals` 擴充 — `src/vibe_resume/core/schema.py`

```python
sdd: bool = False     # Spec-Driven Development (OpenSpec / Spec-Kit / specs tree)
tdd: bool = False     # Test-Driven Development (methodology evidence, not mere test presence)
```

### 3. aggregator `_agentic_signals` 加偵測

於既有 `_agentic_signals(acts, group_name)` 內,為每組組一個 blob(`summary` + `keywords` + `files_touched`,lower)並比對:

- **sdd**:blob 配 `openspec` / `spec[-_ ]?kit` / `spec-driven` / `規格驅動`,**或** 任一 `files_touched` basename ∈ {`spec.md`,`plan.md`,`tasks.md`,`data-model.md`,`constitution.md`},**或** 路徑配 `(?:^|/)specs/[^/]+/`。
- **tdd**:blob 配 `test-driven` / `\btdd\b` / `red[-/ ]green` / `failing\s+test` / `write\s+a\s+failing\s+test`。
- `sdd`/`tdd` 納入「任一信號才建 `AgenticSignals`」的判斷(只有 sdd/tdd 的 group 也會有 signals)。

(blob 來源與 `_infer_tech` 一致:`summary`、`keywords`、`files_touched`。)

### 4. enrich hint 擴充 — `enricher.py`

在 `_build_prompt` 既有 agentic-signals 區塊增列:
- `sig.sdd` → "drove spec-driven development (OpenSpec / Spec-Kit): spec → plan → tasks → implementation"
- `sig.tdd` → "practices test-driven development (failing test first)"

仍 never invent。

## 測試計畫

- **classifier**(`tests/test_classifier.py`):
  - `"refined the specs/auth/spec.md per OpenSpec"` → 含 SDD 字眼但**不**含 TESTING category(裸 spec 不再 match)
  - `"foo.spec.ts"` / `"ran pytest"` / `"added tests"` → 仍含 TESTING
  - `"規格驅動開發"` → 不含 TESTING
- **aggregator**(`tests/test_aggregator.py`):
  - summary 含 `openspec` → `sig.sdd is True`
  - `files_touched=["specs/auth/spec.md"]` → sdd True
  - summary 含 `test-driven` → `sig.tdd is True`
  - 一般 group → sdd/tdd False;只有 sdd 的 group → `agentic_signals` 非 None
- **enricher**(`tests/test_enricher.py`):group `agentic_signals.sdd=True` → prompt 含 "spec-driven development";`tdd=True` → 含 "test-driven development"。

## 安全與非破壞

`sdd`/`tdd` 為新增 optional 布林(預設 False),向後相容。只讀既有活動文字/檔名,不連網、不抓檔內容。regex 收緊只縮小 TESTING 命中(修正灌水),不影響其他 category。enrich hint 維持 no-fabrication。
