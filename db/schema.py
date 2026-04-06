"""SQLite スキーマ初期化"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS researched_articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    platform    TEXT NOT NULL,          -- 'note' | 'x'
    url         TEXT UNIQUE,
    title       TEXT,
    author      TEXT,
    tags        TEXT,                   -- JSON array
    likes       INTEGER DEFAULT 0,
    views       INTEGER DEFAULT 0,
    comments    INTEGER DEFAULT 0,
    summary     TEXT,                   -- LLMによる要約
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,      -- 'note' | 'x'
    content_type    TEXT,               -- 'article' | 'tweet' | 'thread'
    title           TEXT,
    body            TEXT NOT NULL,
    tags            TEXT,               -- JSON array
    strategy_note   TEXT,               -- なぜこの内容か
    status          TEXT DEFAULT 'draft', -- draft|reviewed|published|rejected
    scheduled_at    TIMESTAMP,
    published_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS published_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id        INTEGER REFERENCES content_drafts(id),
    platform        TEXT NOT NULL,
    post_url        TEXT,
    published_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         INTEGER REFERENCES published_posts(id),
    platform        TEXT NOT NULL,
    likes           INTEGER DEFAULT 0,
    views           INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    reposts         INTEGER DEFAULT 0,
    followers_delta INTEGER DEFAULT 0,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audience_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    topic           TEXT,
    follower_range  TEXT,               -- 'micro' | 'mid' | 'large'
    interests       TEXT,               -- JSON array
    engagement_rate REAL,
    note            TEXT,
    analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    week        TEXT,                   -- 'YYYY-WXX'
    strategy    TEXT,                   -- LLM生成の戦略テキスト
    topics      TEXT,                   -- JSON array
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return DB_PATH

def get_conn():
    return sqlite3.connect(DB_PATH)

if __name__ == "__main__":
    p = init_db()
    print(f"DB initialized: {p}")
