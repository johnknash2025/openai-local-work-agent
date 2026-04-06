"""
コンテンツ戦略立案モジュール
調査結果を受け取り、LLM がその週の戦略・記事テーマを提案する
"""
import json
import yaml
from pathlib import Path
from datetime import datetime
import sys
sys.path.append(str(Path(__file__).parent.parent))
from writer.ollama_client import chat
from db.schema import get_conn

CONFIG = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
MODEL  = CONFIG["ollama"]["model_fast"]

STRATEGY_SYSTEM = """あなたは農業×AIロボット分野の日本語コンテンツ戦略家です。
NOTE と X（旧Twitter）での情報発信で読者を増やし、
有料記事への転換（マネタイズ）を最大化するための戦略を立案します。
回答は必ず日本語で、具体的かつ実行可能な形で。"""

def build_weekly_strategy(audience_data: dict, top_articles: list) -> str:
    """週次コンテンツ戦略をLLMで生成"""
    top_summary = "\n".join([
        f"- 「{a['title']}」 ❤{a['likes']} 👁{a['views']}"
        for a in top_articles[:10]
    ])
    audience_summary = json.dumps(audience_data, ensure_ascii=False, indent=2)

    prompt = f"""
## 調査データ

### NOTE 人気記事（いいね順）
{top_summary}

### トピック別エンゲージメント分析
{audience_summary}

## あなたのプロフィール
{CONFIG['author_profile']}

## 今週の戦略を立案してください

以下の形式で出力してください：

### 今週のメインテーマ
（1行で）

### NOTE記事テーマ（1本）
- タイトル案：
- 想定読者：
- 無料 or 有料：（有料の場合は理由も）
- 構成メモ：（箇条書き3〜5点）

### X投稿テーマ（3日分、各3ツイート）
#### 月曜
- ツイート1：
- ツイート2：
- ツイート3：

#### 水曜
（同形式）

#### 金曜
（同形式）

### 読者拡大のためのアクション
（今週やるべき具体的な行動3つ）

### マネタイズ機会
（今週の記事で有料化できる部分と価格感）
"""
    return chat(prompt, MODEL, STRATEGY_SYSTEM)

def save_strategy(strategy_text: str, topics: list[str]) -> int:
    week = datetime.now().strftime("%Y-W%V")
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO strategy_log (week, strategy, topics)
        VALUES (?, ?, ?)
    """, (week, strategy_text, json.dumps(topics, ensure_ascii=False)))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id

def get_latest_strategy() -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT strategy FROM strategy_log ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None
