"""
公開記事の反応データ収集（スクレイピング）
X はAPI不要でnoteは公開APIを使用
"""
import httpx
import json
import time
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn
from writer.ollama_client import chat
import yaml

CONFIG = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
MODEL  = CONFIG["ollama"]["model_fast"]
BASE   = "https://note.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

def collect_note_stats(username: str) -> list[dict]:
    """自分のNOTE記事のいいね・ビューを収集"""
    url = f"{BASE}/api/v2/creators/{username}/contents?kind=note&page=1"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        articles = r.json().get("data", {}).get("contents", [])
        stats = []
        for a in articles:
            stats.append({
                "url":      f"{BASE}/n/{a.get('key','')}",
                "title":    a.get("name", ""),
                "likes":    a.get("likeCount", 0),
                "views":    a.get("noteViewCount", 0),
                "comments": a.get("commentsCount", 0),
            })
        return stats
    except Exception as e:
        print(f"  [error] collect_note_stats: {e}")
        return []

def analyze_with_llm(stats: list[dict], strategy: str = "") -> str:
    """収集した反応データをLLMで分析してインサイトを返す"""
    stats_text = "\n".join([
        f"- 「{s['title']}」 ❤{s['likes']} 👁{s.get('views',0)} 💬{s['comments']}"
        for s in sorted(stats, key=lambda x: x['likes'], reverse=True)[:10]
    ])
    prompt = f"""
## 自分の記事の反応データ
{stats_text}

## 今週の戦略（参考）
{strategy[:500] if strategy else '未設定'}

## 分析してください
1. 何が受けていて、何が受けていないか
2. いいねが多い記事の共通点
3. 次の記事・投稿への改善提案（3点）
4. フォロワー増加のために今すぐできること
"""
    return chat(prompt, MODEL, "あなたはSNSマーケティング分析の専門家です。農業×AIロボット分野の発信者のデータを分析します。")

def save_analytics(post_id: int, platform: str, data: dict):
    conn = get_conn()
    conn.execute("""
        INSERT INTO analytics (post_id, platform, likes, views, comments, reposts)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (post_id, platform,
          data.get("likes", 0), data.get("views", 0),
          data.get("comments", 0), data.get("reposts", 0)))
    conn.commit()
    conn.close()
