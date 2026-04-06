"""
X (Twitter) 投稿 Playwright 自動化
APIキー不要でブラウザ操作による投稿

使用前に環境変数を設定:
  export X_EMAIL=your@email.com
  export X_USERNAME=yourusername
  export X_PASSWORD=yourpassword

または config.yaml の x.email / x.username / x.password に記載
"""
import os
import sys
import time
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn

BASE = "https://x.com"
SESSION_PATH = "/tmp/x_session.json"


def _get_credentials() -> tuple[str, str, str]:
    import yaml
    config = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
    xconf = config.get("x", {})
    email    = os.environ.get("X_EMAIL")    or xconf.get("email", "")
    username = os.environ.get("X_USERNAME") or xconf.get("username", "")
    password = os.environ.get("X_PASSWORD") or xconf.get("password", "")
    return email, username, password


def login(page, email: str, username: str, password: str) -> bool:
    """X にログイン（2段階の入力フロー）"""
    page.goto(f"{BASE}/i/flow/login", timeout=30000)
    page.wait_for_timeout(2000)

    try:
        # Step 1: メールアドレスまたはユーザー名
        email_input = page.wait_for_selector("input[autocomplete='username']", timeout=8000)
        email_input.fill(email or username)
        page.click("button:has-text('次へ')")
        page.wait_for_timeout(1500)

        # 電話番号/ユーザー名確認ステップ（出る場合あり）
        unusual_input = page.query_selector("input[data-testid='ocfEnterTextTextInput']")
        if unusual_input:
            unusual_input.fill(username)
            page.click("button:has-text('次へ')")
            page.wait_for_timeout(1500)

        # Step 2: パスワード
        pw_input = page.wait_for_selector("input[name='password']", timeout=8000)
        pw_input.fill(password)
        page.click("button[data-testid='LoginForm_Login_Button']")
        page.wait_for_timeout(3000)

        if "home" in page.url or page.query_selector("[data-testid='tweetButtonInline']"):
            return True

        print("  [warn] ログイン後にホームに遷移しませんでした")
        return False

    except Exception as e:
        print(f"  [error] X ログイン失敗: {e}")
        page.screenshot(path="/tmp/x_login_error.png")
        return False


def post_tweet(text: str, headless: bool = False) -> bool:
    """単一ツイートを投稿"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [error] pip install playwright && playwright install chromium")
        return False

    email, username, password = _get_credentials()
    if not password:
        print("  [error] X_PASSWORD が設定されていません")
        return False

    success = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        # セッション復元を試みる
        if Path(SESSION_PATH).exists():
            ctx = browser.new_context(storage_state=SESSION_PATH, locale="ja-JP")
        else:
            ctx = browser.new_context(locale="ja-JP")

        page = ctx.new_page()
        page.goto(f"{BASE}/home", timeout=30000)
        page.wait_for_timeout(2000)

        # 未ログインなら再ログイン
        if "login" in page.url or not page.query_selector("[data-testid='tweetButtonInline']"):
            if not login(page, email, username, password):
                browser.close()
                return False
            ctx.storage_state(path=SESSION_PATH)

        try:
            # ツイートボックスをクリック
            tweet_box = page.wait_for_selector(
                "[data-testid='tweetTextarea_0']", timeout=10000
            )
            tweet_box.click()
            page.wait_for_timeout(500)
            page.keyboard.type(text, delay=20)
            page.wait_for_timeout(500)

            # 文字数チェック (X の制限は 280 文字)
            if len(text) > 280:
                print(f"  [warn] ツイートが{len(text)}文字です（制限280文字）。切り詰めます")

            # 投稿ボタン
            send_btn = page.wait_for_selector(
                "button[data-testid='tweetButtonInline']", timeout=5000
            )
            send_btn.click()
            page.wait_for_timeout(2000)
            success = True
            print("  ✓ ツイート投稿完了")

        except Exception as e:
            print(f"  [error] ツイート投稿失敗: {e}")
            page.screenshot(path="/tmp/x_tweet_error.png")

        browser.close()

    return success


def post_thread(posts: list[str], headless: bool = False) -> bool:
    """スレッド（連続ツイート）を投稿"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [error] pip install playwright && playwright install chromium")
        return False

    email, username, password = _get_credentials()
    if not password:
        print("  [error] X_PASSWORD が設定されていません")
        return False

    success = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        if Path(SESSION_PATH).exists():
            ctx = browser.new_context(storage_state=SESSION_PATH, locale="ja-JP")
        else:
            ctx = browser.new_context(locale="ja-JP")

        page = ctx.new_page()
        page.goto(f"{BASE}/home", timeout=30000)
        page.wait_for_timeout(2000)

        if "login" in page.url or not page.query_selector("[data-testid='tweetButtonInline']"):
            if not login(page, email, username, password):
                browser.close()
                return False
            ctx.storage_state(path=SESSION_PATH)

        try:
            for i, post_text in enumerate(posts):
                if i == 0:
                    # 最初のツイートボックス
                    tweet_box = page.wait_for_selector(
                        "[data-testid='tweetTextarea_0']", timeout=10000
                    )
                else:
                    # スレッドに追加ボタン
                    add_btn = page.query_selector("button[data-testid='addButton']") or \
                              page.query_selector("button:has-text('追加')")
                    if add_btn:
                        add_btn.click()
                        page.wait_for_timeout(500)
                    tweet_box = page.query_selector_all("[data-testid^='tweetTextarea_']")[-1]

                tweet_box.click()
                page.keyboard.type(post_text, delay=20)
                page.wait_for_timeout(300)

            # 全投稿ボタン
            send_btn = page.wait_for_selector(
                "button[data-testid='tweetButton']", timeout=5000
            )
            send_btn.click()
            page.wait_for_timeout(3000)
            success = True
            print(f"  ✓ スレッド {len(posts)} 投稿完了")

        except Exception as e:
            print(f"  [error] スレッド投稿失敗: {e}")
            page.screenshot(path="/tmp/x_thread_error.png")

        browser.close()

    return success


def publish_draft(draft_id: int, headless: bool = False) -> bool:
    """DB の draft_id から X ツイート/スレッドを投稿"""
    conn = get_conn()
    row = conn.execute(
        "SELECT platform, content_type, body FROM content_drafts WHERE id=?",
        (draft_id,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"  [error] draft_id={draft_id} が見つかりません")
        return False

    platform, ctype, body = row
    if platform != "x":
        print(f"  [error] このドラフトは {platform} 用です（x ではありません）")
        return False

    if ctype == "thread":
        # "---" 区切りのスレッドをパース
        posts = [p.strip() for p in body.split("---") if p.strip()]
        result = post_thread(posts, headless=headless)
    else:
        result = post_tweet(body, headless=headless)

    if result:
        conn = get_conn()
        conn.execute(
            "UPDATE content_drafts SET status='published', published_at=CURRENT_TIMESTAMP WHERE id=?",
            (draft_id,)
        )
        conn.execute(
            "INSERT INTO published_posts (draft_id, platform) VALUES (?, ?)",
            (draft_id, "x")
        )
        conn.commit()
        conn.close()

    return result
