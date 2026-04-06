"""
NOTE スクレイパー
- トレンド記事・タグ別人気記事を取得
- 読者層プロファイリング（エンゲージメント分析）
"""
import httpx
import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn

BASE = "https://note.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_tag_articles(tag: str, page: int = 1) -> list[dict]:
    """タグ別人気記事を取得 (NOTE API v3)"""
    import urllib.parse
    q = urllib.parse.quote(tag)
    url = f"{BASE}/api/v3/searches?context=note&q={q}&page={page}&sort=like"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        notes = r.json().get("data", {}).get("notes", {}).get("contents", [])
        return notes
    except Exception as e:
        print(f"  [warn] tag={tag}: {e}")
        return []

def fetch_creator_stats(username: str) -> dict:
    """クリエイターの統計を取得"""
    url = f"{BASE}/api/v2/creators/{username}"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("data", {})
    except Exception as e:
        print(f"  [warn] creator={username}: {e}")
        return {}

def fetch_creator_articles(username: str, page: int = 1) -> list[dict]:
    """クリエイターの記事一覧を取得"""
    url = f"{BASE}/api/v2/creators/{username}/contents?kind=note&page={page}"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("data", {}).get("contents", [])
    except Exception as e:
        print(f"  [warn] creator articles={username}: {e}")
        return []

def scrape_and_store(topics: list[str], pages: int = 2) -> int:
    """トピックリストで記事を収集してDBに保存"""
    conn = get_conn()
    total = 0
    for topic in topics:
        print(f"  調査中: #{topic}")
        for page in range(1, pages + 1):
            articles = fetch_tag_articles(topic, page)
            for a in articles:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO researched_articles
                        (platform, url, title, author, tags, likes, views, comments)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        "note",
                        f"{BASE}/n/{a.get('key','')}",
                        a.get("name", ""),
                        a.get("user", {}).get("urlname", ""),
                        json.dumps([topic], ensure_ascii=False),
                        a.get("like_count", a.get("likeCount", 0)),
                        a.get("noteViewCount", a.get("viewCount", 0)),
                        a.get("comment_count", a.get("commentsCount", 0)),
                    ))
                    total += 1
                except Exception:
                    pass
            conn.commit()
            time.sleep(0.8)
    conn.close()
    return total

def analyze_top_articles(limit: int = 20) -> list[dict]:
    """DB内の人気記事を分析して傾向を返す"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT title, author, tags, likes, views, comments
        FROM researched_articles
        WHERE platform='note'
        ORDER BY likes DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [
        {"title": r[0], "author": r[1], "tags": r[2],
         "likes": r[3], "views": r[4], "comments": r[5]}
        for r in rows
    ]

def analyze_audience(topics: list[str]) -> dict:
    """
    トピック別にエンゲージメント率・人気タイトルパターンを分析する。
    返す情報:
      - top_titles: いいね上位タイトル
      - avg_likes: 平均いいね
      - high_engagement_ratio: エンゲージメント高い記事の割合
      - title_patterns: よく使われる言葉
    """
    conn = get_conn()
    result = {}
    for topic in topics:
        rows = conn.execute("""
            SELECT title, likes, views, comments
            FROM researched_articles
            WHERE platform='note' AND tags LIKE ?
            ORDER BY likes DESC
            LIMIT 30
        """, (f'%{topic}%',)).fetchall()

        if not rows:
            continue

        titles = [r[0] for r in rows]
        likes  = [r[1] for r in rows]
        views  = [r[2] or 1 for r in rows]
        eng    = [l / v for l, v in zip(likes, views)]

        result[topic] = {
            "top_titles": titles[:5],
            "avg_likes": round(sum(likes) / len(likes), 1),
            "avg_engagement": round(sum(eng) / len(eng) * 100, 2),
            "total_articles": len(rows),
        }
    conn.close()
    return result
