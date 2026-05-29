# Multi-Agent Orchestration Signal

**Date**: 2026-05-29
**Author**: easyvibecoding
**Status**: Approved decisions, pending writing-plans
**Issue**: [#48](https://github.com/easyvibecoding/vibe-resume/issues/48)
**Milestone**: 0.13.0
**Epic**: competency signals — extends the `AgenticSignals` surface (#43/#44).

## 背景與動因

多代理 **orchestration**(subagent 委派、parallel fan-out、supervisor/worker、fan-out→synthesize→adversarial-verify pipeline、Agent SDK / workflow scripting)是最強的*資深* agentic 信號之一,但目前只被折進泛用的 `agent-tooling %`(classifier 的 `sub-agent` / `workflow orchestration` 命中都歸 agent-tooling)。設計 N-agent pipeline 的成熟度,「用 agent 寫 code」看不出來。

## 目標

1. `AgenticSignals.orchestration: list[str]` — 偵測到的 distinct orchestration 型態標籤。
2. aggregator 從活動 blob + `skills_used` 偵測型態;區分 orchestration **design**(有 pattern)與單代理 prompting(無)。
3. enrich hint 表面化,讓 enricher 寫出 orchestration bullet(含 verification-stage 資深標註)。

## 非目標

- **不**抓 max fan-out 寬度(文字數字解析不可靠;留後續)。
- **不**動 classifier `AGENT_TOOLING` regex(orchestration 改由 `AgenticSignals` 表面化,不再只折進百分比)。
- 不引入新依賴。

## 架構

### 1. `AgenticSignals` 擴充 — `schema.py`

```python
orchestration: list[str] = Field(default_factory=list)
# distinct patterns: subagents / fan-out / supervisor-worker / verify-pipeline
#                    / workflow-script / agent-sdk
```

### 2. aggregator `_agentic_signals` 加偵測

於既有迴圈(已有 blob + skills_used),用一張 pattern 表掃描:

| tag | blob regex | skills_used 命中 |
|---|---|---|
| `subagents` | `sub-?agent` | `subagent-driven-development` |
| `fan-out` | `fan-?out` \| `parallel\s+agents` | `dispatching-parallel-agents` |
| `supervisor-worker` | `supervisor` \| `worker\s+topolog` \| `supervisor.{0,12}worker` | — |
| `verify-pipeline` | `adversarial.{0,20}verif` \| `judge\s+panel` \| `verify.{0,12}pipeline` \| `synthesi[sz]e` | — |
| `workflow-script` | `workflow\s+script` \| `workflow\s+orchestrat` \| `self-pac(?:e|ing)` | — |
| `agent-sdk` | `agent\s+sdk` | — |

收集到的 tags 以**固定順序**(上表序)去重輸出 `orchestration`。納入「任一信號才建 `AgenticSignals`」判斷與 return。

實作:模組常數 `_ORCHESTRATION_PATTERNS: list[tuple[str, re.Pattern]]`(blob 規則)+ `_ORCH_SKILL_TAGS: dict[str, str]`(skill 名 → tag)。在迴圈內對每個 activity 的 blob 比對、對 `skills_used` 比對,累積 `set`;最後依固定順序整理成 list。

### 3. enrich hint — `enricher.py`

在 `_build_prompt` 既有 agentic-signals 區塊增列:
- `sig.orchestration` 非空 → "designed multi-agent orchestration (`<tags>`): e.g. fan-out → synthesize → adversarial-verify"
- 若含 `verify-pipeline` → 句尾加 "(with a verification/judge stage)" 點明資深信號

仍 never invent。

## 測試計畫

- **aggregator**(`tests/test_aggregator.py`):
  - blob `"used a sub-agent to do X"` → orchestration 含 `subagents`
  - `extra.skills_used=["dispatching-parallel-agents"]` → 含 `fan-out`
  - blob `"adversarial verify with a judge panel"` → 含 `verify-pipeline`
  - blob `"built a workflow script (self-pacing)"` → 含 `workflow-script`;`"agent sdk"` → `agent-sdk`
  - 多型態 → 依固定順序;純單代理 blob(無 pattern、其他皆空)→ `_agentic_signals` 回 None
- **schema**(`tests/test_schema.py`):`orchestration` 預設 `[]` + round-trip
- **enricher**(`tests/test_enricher.py`):`orchestration=["fan-out","verify-pipeline"]` → prompt 含 "multi-agent orchestration" + tags + "verification"

## 安全與非破壞

`orchestration` 新增 optional list(預設空),向後相容。只讀既有活動文字 + `skills_used`,不連網。enrich hint 維持 no-fabrication。
