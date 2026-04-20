# 陳柏翰（Alex Chen）
_資深 AI 輔助軟體工程師_

- Email: alex.chen.demo@example.com
- 所在地: 荷蘭阿姆斯特丹
- GitHub: github.com/alex-chen-demo
- LinkedIn: linkedin.com/in/alex-chen-demo

> **目標職位**：Staff Software Engineer（Platform / Developer Tooling）

## 個人簡介

7 年後端系統實戰經驗。以 Claude Code、Cursor 為日常配對夥伴,交付速度提升 3 倍。近一年聚焦於把 LLM 使用軌跡轉為工程產出的內部工具建置。

## 工作經歷

### 2023-06 – 至今　Example BV　Senior Software Engineer

- 設計並維運每日 420 萬請求的串流 token gateway(p99 延遲 180ms)
- 主導 monolith 架構拆分為 12 個 Kubernetes 服務,部署時間由 42 分鐘縮短至 6 分鐘
- 導入 AI 輔助 code review 流程,PR 來回輪次降低約 35%

## 重點專案

_彙整自 Claude Code / Cursor / Copilot / git,共 8 個專案(2025-09-15 – 2026-04-18,AI 輔助 session 共 312 次;近 30 日活躍 22/30 天,最長連續 11 天)。主要領域:後端、前端、DevOps、測試基礎建設。_

### internal-token-gateway — 142 sessions(活躍 38 天)
_主力工具 Claude Code,Go + Kubernetes + Redis_

- 打造具自適應 backpressure 的 SSE 串流 proxy,throughput 較原 HTTP/1.1 翻倍
- 實作 token bucket rate limiter 並支援 per-org overrides,由上游濫用造成的告警週均減少 3 次
- 建立涵蓋 14 種 failure mode 的整合測試框架(先前無任何結構化測試)

### ops-runbook-bot — 68 sessions(活躍 21 天)
_主力工具 Cursor,TypeScript + LangGraph + Slack API_

- 出貨能獨立處理 40% P2 事故的 oncall 輔助機器人
- 在建議行動前強制比對 Grafana 指標,作為抑制幻覺的守門機制

### design-system-v2 — 53 sessions(活躍 18 天)
_Claude Code 與 Copilot 雙軌並行,React + Radix UI + Tailwind_

- 將 86 個元件遷移至通過 a11y 審計的 primitives,Lighthouse 無障礙分數由 74 上升至 97
- 手寫 codemod 自動改寫 1,240 處下游 import,無任何手動修正

## 學歷

- 2015 – 2019　國立臺灣大學　資訊工程學士

## 語言能力

- 繁體中文(母語)
- 英文(流利,專業工作語言)
- 荷蘭文(日常會話 B1)

## 技術棧

Go、Python、TypeScript、React、Kubernetes、PostgreSQL、Redis、gRPC、OpenTelemetry、Terraform、GitHub Actions
