"""
NOTE / X ログインセッション保存ツール
一回だけ実行してログインセッションを保存しておけば、
以降の自動投稿でログイン操作が不要になります。

実行:
  python publisher/auth_setup.py note   # NOTE のセッションを保存
  python publisher/auth_setup.py x      # X のセッションを保存
"""
import sys
import time
from pathlib import Path

NOTE_SESSION = "/tmp/note_session.json"
X_SESSION    = "/tmp/x_session.json"


def setup_note():
    from playwright.sync_api import sync_playwright

    print("=== NOTE ログインセットアップ ===")
    print("ブラウザが開きます。手動でログインしてください。")
    print("ログイン完了後、Enter キーを押してセッションを保存します。\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100, channel="msedge")
        ctx = browser.new_context(locale="ja-JP")
        page = ctx.new_page()
        page.goto("https://note.com/login")

        input("ブラウザでログイン後、ここで Enter を押してください > ")

        # ログイン済み確認
        page.reload()
        time.sleep(2)
        if "login" in page.url:
            print("  [warn] まだログインされていないようです")
        else:
            ctx.storage_state(path=NOTE_SESSION)
            print(f"  ✓ セッション保存完了: {NOTE_SESSION}")

        browser.close()


def setup_x():
    from playwright.sync_api import sync_playwright

    print("=== X ログインセットアップ ===")
    print("ブラウザが開きます。手動でログインしてください。")
    print("ログイン完了後、Enter キーを押してセッションを保存します。\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100, channel="msedge")
        ctx = browser.new_context(locale="ja-JP")
        page = ctx.new_page()
        page.goto("https://x.com/login")

        input("ブラウザでログイン後、ここで Enter を押してください > ")

        page.reload()
        time.sleep(2)
        if "login" in page.url:
            print("  [warn] まだログインされていないようです")
        else:
            ctx.storage_state(path=X_SESSION)
            print(f"  ✓ セッション保存完了: {X_SESSION}")

        browser.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target == "note":
        setup_note()
    elif target == "x":
        setup_x()
    else:
        print("使い方:")
        print("  python publisher/auth_setup.py note   # NOTE セッション保存")
        print("  python publisher/auth_setup.py x      # X セッション保存")
        print()
        print(f"  NOTE セッション: {NOTE_SESSION} (存在: {Path(NOTE_SESSION).exists()})")
        print(f"  X セッション:    {X_SESSION} (存在: {Path(X_SESSION).exists()})")
