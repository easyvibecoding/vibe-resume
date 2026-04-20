# アレックス・チェン（Alex Chen）
_シニア AI 活用ソフトウェアエンジニア_

- メール: alex.chen.demo@example.com
- 所在地: オランダ・アムステルダム
- GitHub: github.com/alex-chen-demo
- LinkedIn: linkedin.com/in/alex-chen-demo

> **応募職種**: スタッフソフトウェアエンジニア（プラットフォーム／開発者ツール）

## 自己紹介

7 年間プロダクション環境のバックエンドを構築。Claude Code / Cursor を日常的なペアプログラミングパートナーとして活用し、出荷速度を 3 倍に改善。近年は LLM 利用実績をエンジニアリング成果として可視化する内部ツールに注力。

## 職務経歴

### 2023-06 – 現在　Example BV　シニアソフトウェアエンジニア

- 1 日 420 万リクエストのストリーミングトークンゲートウェイの設計・運用（p99 レイテンシ 180ms）
- モノリスから 12 サービスの Kubernetes 基盤への移行を主導。デプロイ時間を 42 分 → 6 分に短縮
- AI 支援レビューワークフローの整備。PR 往復回数を約 35% 削減

## 主要プロジェクト

_Claude Code / Cursor / Copilot / git から 8 プロジェクト分を集計（2025-09-15 〜 2026-04-18、AI 支援セッション 312 回、直近 30 日は 22/30 日稼働、最長連続 11 日）。主な領域: バックエンド、フロントエンド、DevOps、テスト基盤。_

### internal-token-gateway — 142 セッション（稼働 38 日）
_Claude Code 主導、Go + Kubernetes + Redis_

- バックプレッシャ適応型の SSE ストリーミングプロキシを構築。HTTP/1.1 実装比でスループット 2 倍
- 組織単位の上限を設定可能なトークンバケット方式レートリミッタを導入。上流濫用起因のページ警報を週 3 件削減
- 14 種の障害シナリオを網羅する統合テスト基盤を整備（導入前は構造化テスト無し）

### ops-runbook-bot — 68 セッション（稼働 21 日）
_Cursor 主導、TypeScript + LangGraph + Slack API_

- P2 インシデントの 40% を人手介入なく解決するオンコール支援 Bot を出荷
- Grafana メトリクスとの突合による幻覚抑止ガードを実装

### design-system-v2 — 53 セッション（稼働 18 日）
_Claude Code + Copilot 並列、React + Radix UI + Tailwind_

- 86 コンポーネントをアクセシビリティ監査済みプリミティブへ移行。Lighthouse A11y スコア 74 → 97
- 輸入宣言書き換え用 codemod を実装。1,240 箇所の下流利用に対し手修正ゼロで適用

## 学歴

- 2015 – 2019　国立台湾大学　情報工学士

## 言語

- 繁体字中国語（母語）
- 英語（ビジネスレベル）
- オランダ語（日常会話）

## 技術スタック

Go / Python / TypeScript / React / Kubernetes / PostgreSQL / Redis / gRPC / OpenTelemetry / Terraform / GitHub Actions

---

**📄 Note**: The DOCX output for `ja_JP` emits the **JIS Z 8303 履歴書 grid form** in
addition to this 職務経歴書 markdown. Run `vibe-resume render -f all --locale ja_JP`
to produce both. Photo path is taken from `profile.photo_path`.
