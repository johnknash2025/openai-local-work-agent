"""
X (Twitter) トレンド調査 - Playwright ブラウザ自動化
APIキー不要でトレンドツイートを収集・分析する
"""
import json
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn

def scrape_x_trends(topics: list[str], max_per_topic: int = 20) -> int:
    """X のキーワード検索でツイートを収集してDBに保存"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [error] playwright がインストールされていません: pip install playwright && playwright install chromium")
        return 0

    conn = get_conn()
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        page = ctx.new_page()

        for topic in topics:
            print(f"  X調査中: {topic}")
            try:
                import urllib.parse
                q = urllib.parse.quote(f"{topic} lang:ja")
                url = f"https://x.com/search?q={q}&src=typed_query&f=top"
                page.goto(url, timeout=30000)
                page.wait_for_timeout(3000)

                # ログインを求められる場合はスキップ
                if "login" in page.url.lower() or page.query_selector("[data-testid='LoginForm']"):
                    print(f"  [warn] X はログインが必要です。ゲストモードで試みます...")
                    # ゲストモードでの検索URLに変更
                    page.goto(f"https://x.com/search?q={q}&src=typed_query", timeout=30000)
                    page.wait_for_timeout(3000)

                # ツイートを取得
                tweets_collected = 0
                scroll_count = 0
                seen_urls = set()

                while tweets_collected < max_per_topic and scroll_count < 5:
                    tweet_articles = page.query_selector_all("article[data-testid='tweet']")

                    for article in tweet_articles:
                        if tweets_collected >= max_per_topic:
                            break
                        try:
                            # テキスト取得
                            text_el = article.query_selector("[data-testid='tweetText']")
                            if not text_el:
                                continue
                            text = text_el.inner_text()

                            # ユーザー名
                            user_el = article.query_selector("[data-testid='User-Name'] a")
                            username = user_el.get_attribute("href").strip("/") if user_el else ""

                            # URL (ツイートリンク)
                            time_el = article.query_selector("time")
                            tweet_url = ""
                            if time_el:
                                link_el = time_el.query_selector("xpath=..")
                                if link_el:
                                    tweet_url = "https://x.com" + (link_el.get_attribute("href") or "")

                            if tweet_url in seen_urls:
                                continue
                            seen_urls.add(tweet_url)

                            # いいね数
                            like_el = article.query_selector("[data-testid='like'] span")
                            likes = 0
                            if like_el:
                                try:
                                    likes = _parse_count(like_el.inner_text())
                                except Exception:
                                    pass

                            # リツイート数
                            rt_el = article.query_selector("[data-testid='retweet'] span")
                            retweets = 0
                            if rt_el:
                                try:
                                    retweets = _parse_count(rt_el.inner_text())
                                except Exception:
                                    pass

                            conn.execute("""
                                INSERT OR IGNORE INTO researched_articles
                                (platform, url, title, author, tags, likes, views, comments)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                "x",
                                tweet_url,
                                text[:200],
                                username,
                                json.dumps([topic], ensure_ascii=False),
                                likes,
                                0,
                                retweets,
                            ))
                            total += 1
                            tweets_collected += 1

                        except Exception:
                            pass

                    conn.commit()

                    # スクロールで追加読み込み
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                    scroll_count += 1

            except Exception as e:
                print(f"  [warn] X scrape topic={topic}: {e}")

            time.sleep(1)

        browser.close()

    conn.close()
    return total


def _parse_count(text: str) -> int:
    """'1.2K' → 1200, '34' → 34"""
    text = text.strip().replace(",", "")
    if not text:
        return 0
    if text.endswith("K"):
        return int(float(text[:-1]) * 1000)
    if text.endswith("M"):
        return int(float(text[:-1]) * 1_000_000)
    try:
        return int(text)
    except ValueError:
        return 0


def analyze_x_trends(topics: list[str]) -> dict:
    """DB内のXツイートを分析"""
    conn = get_conn()
    result = {}
    for topic in topics:
        rows = conn.execute("""
            SELECT title, likes, comments
            FROM researched_articles
            WHERE platform='x' AND tags LIKE ?
            ORDER BY likes DESC
            LIMIT 20
        """, (f'%{topic}%',)).fetchall()

        if not rows:
            continue

        texts = [r[0] for r in rows]
        likes = [r[1] for r in rows]

        result[topic] = {
            "top_tweets": texts[:5],
            "avg_likes": round(sum(likes) / len(likes), 1) if likes else 0,
            "total": len(rows),
        }
    conn.close()
    return result
