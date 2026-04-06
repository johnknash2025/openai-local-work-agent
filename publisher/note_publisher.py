"""
NOTE 記事・投稿 Playwright 自動化
NOTE に公式 write API はないため、ブラウザ操作で投稿する

使用前に環境変数を設定:
  export NOTE_EMAIL=your@email.com
  export NOTE_PASSWORD=yourpassword

または config.yaml の note.email / note.password に記載
"""
import os
import sys
import time
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn

BASE = "https://note.com"


def _get_credentials() -> tuple[str, str]:
    import yaml
    config = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
    email    = os.environ.get("NOTE_EMAIL")    or config.get("note", {}).get("email", "")
    password = os.environ.get("NOTE_PASSWORD") or config.get("note", {}).get("password", "")
    return email, password


def login(page, email: str, password: str) -> bool:
    """NOTE に Google SSO でログイン（同一ページ遷移型）"""
    page.goto(f"{BASE}/login", timeout=30000)
    page.wait_for_timeout(3000)

    try:
        # Google ボタンが存在すればクリック、すでに Google ページにいる場合はスキップ
        if "accounts.google.com" not in page.url:
            google_btn = page.wait_for_selector("button[aria-label='Google']", timeout=8000)
            google_btn.click()
            page.wait_for_timeout(4000)

        # Google メール入力（すでに Google ページにいる場合も含む）
        email_input = page.wait_for_selector("input[type='email']", timeout=10000)
        email_input.click(click_count=3)  # 既存テキストを全選択してから上書き
        email_input.fill(email)
        page.wait_for_timeout(500)
        page.click("#identifierNext")
        page.wait_for_timeout(2500)

        # Google パスワード入力
        pw_input = page.wait_for_selector("input[type='password']", timeout=10000)
        pw_input.fill(password)
        page.wait_for_timeout(500)
        page.click("#passwordNext")
        page.wait_for_timeout(6000)

        # NOTE にリダイレクトされているか確認
        if "note.com" in page.url and "login" not in page.url:
            return True

        # 追加確認ステップがある場合（2段階認証など）
        page.screenshot(path="/tmp/note_login_state.png")
        print(f"  [warn] ログイン後 URL: {page.url}")
        print("  スクリーンショット: /tmp/note_login_state.png")
        return False

    except Exception as e:
        print(f"  [error] ログイン失敗: {e}")
        page.screenshot(path="/tmp/note_login_error.png")
        print("  スクリーンショット: /tmp/note_login_error.png")
        return False


def publish_note_article(
    draft_id: int,
    headless: bool = False,
    tags: list[str] | None = None,
) -> str | None:
    """
    DB の draft_id から記事を取得して NOTE に投稿する。
    headless=False で実際のブラウザを表示（確認用）
    戻り値: 投稿されたURL (成功時) | None
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [error] pip install playwright && playwright install chromium")
        return None

    conn = get_conn()
    row = conn.execute(
        "SELECT platform, content_type, title, body, tags FROM content_drafts WHERE id=?",
        (draft_id,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"  [error] draft_id={draft_id} が見つかりません")
        return None

    platform, ctype, title, body, tags_json = row
    if platform != "note":
        print(f"  [error] このドラフトは {platform} 用です（note ではありません）")
        return None

    draft_tags = json.loads(tags_json) if tags_json else []
    all_tags = list(set((tags or []) + draft_tags))

    email, password = _get_credentials()
    if not email or not password:
        print("  [error] NOTE_EMAIL / NOTE_PASSWORD が設定されていません")
        print("  config.yaml の note.email / note.password に記載するか")
        print("  export NOTE_EMAIL=xxx NOTE_PASSWORD=yyy を実行してください")
        return None

    post_url = None

    SESSION_PATH = "/tmp/note_session.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, channel="msedge",
            args=["--disable-blink-features=AutomationControlled"],
        )
        # 保存済みセッションがあれば使用（ログイン省略）
        if Path(SESSION_PATH).exists():
            ctx = browser.new_context(storage_state=SESSION_PATH, locale="ja-JP")
        else:
            ctx = browser.new_context(locale="ja-JP")
        page = ctx.new_page()

        # すでにログイン済みか確認
        page.goto(f"{BASE}/notes/new", timeout=30000)
        page.wait_for_timeout(2000)

        if "login" in page.url:
            # ログインが必要
            if not login(page, email, password):
                browser.close()
                return None
            page.goto(f"{BASE}/notes/new", timeout=30000)
            page.wait_for_timeout(2000)

        # ログイン後のセッションを保存
        ctx.storage_state(path=SESSION_PATH)

        print(f"  ✓ NOTE ログイン済み (URL: {page.url[:60]})")
        page.screenshot(path="/tmp/note_notes_new.png")
        print("  スクリーンショット: /tmp/note_notes_new.png")

        try:
            # タイトル入力
            title_el = page.query_selector("textarea[placeholder]") or \
                       page.query_selector("[data-placeholder='タイトル']") or \
                       page.query_selector(".o-editor__title")
            if title_el:
                title_el.click()
                title_el.fill(title or "")
                page.wait_for_timeout(500)

            # 本文入力 (ProseMirror エディタ)
            body_el = page.query_selector(".ProseMirror") or \
                      page.query_selector("[contenteditable='true']")
            if body_el:
                body_el.click()
                # markdown をそのままペースト（NOTE エディタは一部 markdown を解釈）
                page.keyboard.type(body, delay=10)
                page.wait_for_timeout(1000)

            # タグ追加
            for tag in all_tags[:5]:
                try:
                    tag_input = page.query_selector("input[placeholder*='タグ']") or \
                                page.query_selector(".m-tagInput input")
                    if tag_input:
                        tag_input.fill(tag)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(300)
                except Exception:
                    pass

            # 公開ボタンを押す
            publish_btn = page.query_selector("button:has-text('公開する')") or \
                          page.query_selector("button:has-text('投稿')") or \
                          page.query_selector("[data-name='publish']")
            if publish_btn:
                publish_btn.click()
                page.wait_for_timeout(2000)

                # 確認ダイアログ
                confirm_btn = page.query_selector("button:has-text('公開する')") or \
                              page.query_selector("button:has-text('完了')")
                if confirm_btn:
                    confirm_btn.click()
                    page.wait_for_timeout(3000)

            post_url = page.url
            if "/n/" in post_url:
                print(f"  ✓ 投稿完了: {post_url}")
                _mark_published(draft_id, "note", post_url)
            else:
                print(f"  [warn] 投稿後URLが想定外です: {post_url}")
                post_url = None

        except Exception as e:
            print(f"  [error] 投稿中にエラー: {e}")
            # スクリーンショットで状況確認
            page.screenshot(path="/tmp/note_publish_error.png")
            print("  スクリーンショット: /tmp/note_publish_error.png")

        browser.close()

    return post_url


def _mark_published(draft_id: int, platform: str, url: str):
    conn = get_conn()
    conn.execute(
        "UPDATE content_drafts SET status='published', published_at=CURRENT_TIMESTAMP WHERE id=?",
        (draft_id,)
    )
    conn.execute(
        "INSERT INTO published_posts (draft_id, platform, post_url) VALUES (?, ?, ?)",
        (draft_id, platform, url)
    )
    conn.commit()
    conn.close()


def save_session(ctx, path: str = "/tmp/note_session.json"):
    """ログイン済みセッションを保存（次回ログイン省略）"""
    ctx.storage_state(path=path)
    print(f"  セッション保存: {path}")


def load_session_context(p, path: str = "/tmp/note_session.json"):
    """保存済みセッションから Context を復元"""
    if Path(path).exists():
        return p.chromium.launch(headless=True).new_context(
            storage_state=path, locale="ja-JP"
        )
    return None
