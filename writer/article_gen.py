"""
記事・投稿文生成モジュール
- NOTE記事（長文）
- Xツイート / スレッド
"""
import json
import yaml
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from writer.ollama_client import chat, stream_chat
from db.schema import get_conn

CONFIG = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
MODEL  = CONFIG["ollama"]["model_quality"]

WRITER_SYSTEM = """あなたは農業×AIロボット分野の専門ライターです。
読者は農業従事者・農業法人の経営者・AI/ロボット技術者・農業スタートアップ関係者です。
- 日本語で書く
- 技術的に正確で、実用的な内容にする
- 読みやすく、具体例を入れる
- NOTE の書式（markdown）で書く"""

def generate_note_article(
    title: str,
    outline: list[str],
    is_paid: bool = False,
    extra_context: str = "",
) -> str:
    outline_text = "\n".join(f"- {o}" for o in outline)
    paid_instruction = """
※ この記事は有料設定します。
  - 無料部分（〜300文字）: 問題提起・読者の関心を引く導入
  - 有料部分: 具体的な実装手順・データ・ノウハウ
  という構成にしてください。無料/有料の境界を「---ここから有料---」で明示。
""" if is_paid else ""

    prompt = f"""
## 記事タイトル
{title}

## 構成メモ
{outline_text}

{paid_instruction}

## 追加コンテキスト
{extra_context}

## 指示
上記に基づいてNOTE記事を書いてください。
- 1500〜3000字程度
- 見出し（##）を使って構成する
- 冒頭に読者の課題感に共感する導入文を置く
- 末尾にまとめと次回予告を入れる
- タグ提案（#）を末尾に5個つける
"""
    return chat(prompt, MODEL, WRITER_SYSTEM)

def generate_x_tweets(
    topic: str,
    count: int = 3,
    style: str = "知識共有",  # 知識共有|問い掛け|事例紹介|実況
) -> list[str]:
    style_map = {
        "知識共有": "「〇〇を知っていますか？」形式。有益な情報を短く伝える。",
        "問い掛け": "読者に問いかけてエンゲージメントを高める。返信を促す。",
        "事例紹介": "具体的な成果・数字・ビフォーアフターを示す。",
        "実況": "今やっていることをリアルタイムで共有する。臨場感を出す。",
    }

    prompt = f"""
## テーマ
{topic}

## スタイル
{style}: {style_map.get(style, '')}

## 要件
- {count}件のツイートを生成
- 各140文字以内（日本語）
- 農業×AIロボット分野の発信者として
- ハッシュタグを2〜3個末尾につける
- 番号付きリスト形式で出力（例: 1. テキスト...）
- 絵文字を適度に使ってOK
"""
    response = chat(prompt, MODEL, WRITER_SYSTEM)
    # 番号付きリストをパース
    tweets = []
    for line in response.split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ". " in line:
            tweet = line.split(". ", 1)[1].strip()
            if tweet:
                tweets.append(tweet)
    return tweets[:count]

def generate_x_thread(topic: str, num_posts: int = 5) -> list[str]:
    """スレッド形式（連続ツイート）"""
    prompt = f"""
## テーマ
{topic}

## 指示
{num_posts}個の連続ツイート（スレッド）を作成してください。
- 1投目: 興味を引く導入・結論の予告
- 2〜{num_posts-1}投目: 具体的な内容・ステップ
- {num_posts}投目: まとめ＋フォロー/いいねの呼びかけ
- 各140文字以内
- 「1/{num_posts}」のような番号を入れる
- 農業×AIロボット分野のアカウントとして
- 各ツイートを「---」で区切って出力
"""
    response = chat(prompt, MODEL, WRITER_SYSTEM)
    parts = [p.strip() for p in response.split("---") if p.strip()]
    return parts[:num_posts]

def save_draft(
    platform: str,
    content_type: str,
    body: str,
    title: str = "",
    tags: list = None,
    strategy_note: str = "",
) -> int:
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO content_drafts
        (platform, content_type, title, body, tags, strategy_note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        platform, content_type, title, body,
        json.dumps(tags or [], ensure_ascii=False),
        strategy_note,
    ))
    conn.commit()
    draft_id = cur.lastrowid
    conn.close()
    return draft_id

def list_drafts(platform: str = None, status: str = "draft") -> list[dict]:
    conn = get_conn()
    q = "SELECT id, platform, content_type, title, status, created_at FROM content_drafts WHERE status=?"
    params = [status]
    if platform:
        q += " AND platform=?"
        params.append(platform)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [
        {"id": r[0], "platform": r[1], "type": r[2],
         "title": r[3], "status": r[4], "created": r[5]}
        for r in rows
    ]
