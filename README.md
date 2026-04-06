# OpenAI Local Work Agent

OpenAI 系エージェントを主担当として運用する、ローカル仕事エージェント基盤です。

この repo は Claude Code 側で作られた `local-content-agent` を土台に、次の用途へ広げた別リポジトリです。

- Gemma / Ollama を使ったローカルタスク実行
- research / writing / ops の汎用 worker
- 収益化向け `idea / offer / repurpose / character` worker
- 実行ごとの `runs/` 記録
- 成果物の `artifacts/` 保存
- 既存の note / X 向けコンテンツ生成フローの互換保持

## Positioning

- この repo: OpenAI 側の主担当 repo
- 元 repo: Claude Code 側の履歴を残す専用 repo
- 方針: ローカル優先、Secrets 非同梱、Ollama/Gemma 基準

## Setup

```bash
cd ~/github/openai-local-work-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml
```

必要なら `config.yaml` のモデルを手元の Ollama 環境に合わせて変更してください。

## Main Commands

```bash
python main.py models
python main.py workers
python main.py task-init
python main.py task examples/tasks/research_physical_ai.json
python main.py task examples/tasks/ops_local_agent_runbook.json
python main.py task examples/tasks/find_article_angles.json
python main.py task examples/tasks/build_paid_note_offer.json
python main.py task examples/tasks/design_local_ai_vtuber.json
```

## Generic Task Flow

1. `examples/tasks/*.json` を参考に task を作る
2. `python main.py task ...` で worker を実行する
3. 結果は `artifacts/` に保存される
4. 実行メタデータは `runs/<run_id>/` に残る

## Available Workers

- `research`: リサーチメモ、比較、検証計画
- `writing`: 記事草案、仕様書、提案書
- `ops`: runbook、手順書、運用チェックリスト
- `idea`: 売れるテーマ、企画、ネタ出し
- `offer`: 有料商品、価格仮説、販売導線
- `repurpose`: 1つの結果を複数媒体へ転用
- `character`: AI VTuber、AI creator、人格設計

## Local Model Defaults

- fast: `gemma4:e2b`
- quality: `gemma4:26b`

`writer/ollama_client.py` は legacy content flow と generic runtime の両方で共有しています。

## Legacy Compatibility

元の content automation コマンドも残しています。

```bash
python main.py research
python main.py strategy
python main.py opportunity
python main.py auto
python main.py drafts
```

ただし、この repo の主役は `task runner` です。収益化記事生成は 1 ワークフローとして扱います。

## Revenue Direction

この repo は SaaS 専用ではありません。現在の優先候補は次です。

- 技術記事の有料販売
- 実測データや検証ノートの販売
- GitHub / X / note への転用自動化
- AI creator / AI VTuber の企画設計と運用補助

最短で回すなら、まず次の3つです。

- `find_article_angles.json`
- `build_paid_note_offer.json`
- `repurpose_sim_result.json`

## Directory Guide

- `agent_runtime/`: 汎用 task / worker / runner
- `examples/tasks/`: サンプル task
- `automation/`: 旧 content pipeline
- `writer/`, `research/`, `publisher/`: 旧 content workflow の構成要素
- `artifacts/`: 生成物
- `runs/`: 実行ログ
