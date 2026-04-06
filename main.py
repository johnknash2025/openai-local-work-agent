#!/usr/bin/env python3
"""
OpenAI Local Work Agent - CLI
OpenAI 系エージェントが主担当のローカル仕事エージェント基盤。

主な使い方:
  python main.py models                    # Ollama の利用可能モデル表示
  python main.py workers                   # 利用可能 worker 一覧
  python main.py task path/to/task.json    # 汎用タスクを実行
  python main.py task-init                 # サンプル task 一覧

互換用コンテンツ機能:
  python main.py research
  python main.py strategy
  python main.py write note
  python main.py write x
  python main.py write thread
  python main.py auto
  python main.py publish note ID
  python main.py publish x ID
  python main.py analyze
  python main.py drafts
  python main.py opportunity
"""
import sys
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint

from agent_runtime.config import REPO_ROOT, load_config
from agent_runtime.llm import get_model_profile, list_models
from agent_runtime.runner import execute_task
from agent_runtime.tasks import load_task

console = Console()
CONFIG = load_config()

# DB 初期化
from db.schema import init_db
init_db()


def cmd_models():
    console.print(Panel("[bold blue]🧠 Local Models[/bold blue]"))
    profile = get_model_profile()
    models = list_models()
    console.print(f"  fast: {profile.fast}")
    console.print(f"  quality: {profile.quality}")
    if not models:
        console.print("  [yellow]Ollama model list unavailable[/yellow]")
        return
    for model in models:
        console.print(f"  - {model}")


def cmd_workers():
    console.print(Panel("[bold blue]🛠 Available Workers[/bold blue]"))
    table = Table("worker", "purpose", "default model")
    table.add_row("research", "リサーチメモ、比較、検証計画", "quality")
    table.add_row("writing", "記事草案、仕様書、提案書", "quality")
    table.add_row("ops", "runbook、手順書、運用チェックリスト", "quality")
    table.add_row("idea", "売れるテーマ、企画、ネタ出し", "quality")
    table.add_row("offer", "有料商品、価格仮説、販売導線", "quality")
    table.add_row("repurpose", "1つの結果を複数媒体へ転用", "fast")
    table.add_row("character", "AI VTuber、AI creator、人格設計", "quality")
    console.print(table)


def cmd_task(task_path: str):
    path = Path(task_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        console.print(f"[red]task file not found: {path}[/red]")
        return

    task = load_task(path)
    console.print(Panel(f"[bold green]▶ Task Run[/bold green]\n{task.title} ({task.task_type})"))
    result = execute_task(task)
    console.print(f"  worker: {result['worker']}")
    console.print(f"  artifact: [link]{result['artifact_path']}[/link]")
    console.print(f"  run_id: {result['run_id']}")


def cmd_task_init():
    examples_dir = REPO_ROOT / "examples" / "tasks"
    console.print(Panel("[bold blue]📁 Example Tasks[/bold blue]"))
    for path in sorted(examples_dir.glob("*.json")):
        console.print(f"  - [link]{path}[/link]")

# ── コマンド: research ─────────────────────────────────
def cmd_research():
    console.print(Panel("[bold green]📊 NOTE / X トレンド調査開始[/bold green]"))
    from research.note_scraper import scrape_and_store, analyze_audience, analyze_top_articles
    from research.x_scraper import scrape_x_trends, analyze_x_trends

    topics = CONFIG["topics"]["primary"] + CONFIG["topics"]["secondary"]
    console.print(f"  調査トピック: {', '.join(topics)}")

    with console.status("NOTE 記事を収集中..."):
        total = scrape_and_store(topics, pages=2)
    console.print(f"  ✓ NOTE: {total} 件の記事を収集")

    with console.status("X ツイートを収集中..."):
        try:
            xtotal = scrape_x_trends(CONFIG["topics"]["primary"], max_per_topic=15)
            console.print(f"  ✓ X: {xtotal} 件のツイートを収集")
        except Exception as e:
            console.print(f"  [yellow]X スクレイピングスキップ: {e}[/yellow]")

    with console.status("読者層を分析中..."):
        audience = analyze_audience(CONFIG["topics"]["primary"])
        top      = analyze_top_articles(20)

    console.print("\n[bold]── トピック別エンゲージメント ──[/bold]")
    t = Table("トピック", "平均いいね", "平均エンゲージメント率", "収集件数")
    for topic, d in audience.items():
        t.add_row(
            topic,
            str(d["avg_likes"]),
            f"{d['avg_engagement']}%",
            str(d["total_articles"]),
        )
    console.print(t)

    console.print("\n[bold]── 人気記事 TOP10 ──[/bold]")
    for i, a in enumerate(top[:10], 1):
        console.print(f"  {i:2}. ❤{a['likes']:4}  {a['title'][:50]}")

    return audience, top

# ── コマンド: strategy ────────────────────────────────
def cmd_strategy():
    console.print(Panel("[bold blue]🎯 週次戦略立案[/bold blue]"))
    from research.note_scraper import analyze_audience, analyze_top_articles
    from writer.strategy import build_weekly_strategy, save_strategy

    with console.status("データ読み込み中..."):
        audience = analyze_audience(CONFIG["topics"]["primary"])
        top = analyze_top_articles(20)

    if not audience:
        console.print("[yellow]⚠ 調査データなし。先に `python main.py research` を実行してください[/yellow]")
        return

    console.print("  LLM で戦略を生成中... (数分かかります)")
    strategy = build_weekly_strategy(audience, top)
    sid = save_strategy(strategy, CONFIG["topics"]["primary"])
    console.print(f"  ✓ 戦略を保存 (id={sid})")
    console.print()
    console.print(Markdown(strategy))

# ── コマンド: write ───────────────────────────────────
def cmd_write(target: str):
    from writer.article_gen import (
        generate_note_article, generate_x_tweets,
        generate_x_thread, save_draft
    )
    from writer.strategy import get_latest_strategy

    strategy = get_latest_strategy() or ""

    if target == "note":
        console.print(Panel("[bold magenta]✍️  NOTE記事生成[/bold magenta]"))
        title   = console.input("[bold]タイトル: [/bold]").strip()
        outline_raw = console.input("[bold]構成メモ（カンマ区切り）: [/bold]").strip()
        outline = [o.strip() for o in outline_raw.split(",")]
        paid_ans = console.input("[bold]有料記事にしますか？ (y/N): [/bold]").strip().lower()
        is_paid = paid_ans == "y"

        console.print("\n  生成中... (1〜3分)")
        article = generate_note_article(title, outline, is_paid, strategy[:300])
        did = save_draft("note", "article", article, title, strategy_note=strategy[:200])
        console.print(f"\n  ✓ 下書き保存 (id={did})")
        console.print()
        console.print(Markdown(article))

    elif target in ("x", "tweet"):
        console.print(Panel("[bold cyan]🐦 Xツイート生成[/bold cyan]"))
        topic = console.input("[bold]テーマ: [/bold]").strip()
        styles = ["知識共有", "問い掛け", "事例紹介", "実況"]
        console.print(f"スタイル: " + " / ".join(f"{i+1}.{s}" for i,s in enumerate(styles)))
        idx = int(console.input("番号を選択 (1-4, default=1): ").strip() or "1") - 1
        style = styles[max(0, min(3, idx))]

        console.print(f"\n  [{style}] ツイートを生成中...")
        tweets = generate_x_tweets(topic, count=3, style=style)
        for i, tw in enumerate(tweets, 1):
            body = f"[Tweet {i}]\n" + tw
            did = save_draft("x", "tweet", tw, strategy_note=topic)
            console.print(f"\n  ✓ 下書き保存 (id={did})")
            console.print(Panel(tw, title=f"Tweet {i}", border_style="cyan"))

    elif target == "thread":
        console.print(Panel("[bold cyan]🧵 Xスレッド生成[/bold cyan]"))
        topic = console.input("[bold]テーマ: [/bold]").strip()
        n = int(console.input("投稿数 (default=5): ").strip() or "5")

        console.print(f"\n  {n}投稿のスレッドを生成中...")
        thread = generate_x_thread(topic, n)
        for i, post in enumerate(thread, 1):
            did = save_draft("x", "thread", post, strategy_note=topic)
            console.print(Panel(post, title=f"[{i}/{len(thread)}]", border_style="cyan"))
        console.print(f"\n  ✓ {len(thread)} 投稿を下書き保存")

# ── コマンド: analyze ─────────────────────────────────
def cmd_analyze():
    console.print(Panel("[bold yellow]📈 反応データ分析[/bold yellow]"))
    from analytics.collector import collect_note_stats, analyze_with_llm
    from writer.strategy import get_latest_strategy

    username = CONFIG["note"].get("username", "")
    if not username:
        username = console.input("[bold]NOTEユーザー名を入力: [/bold]").strip()
        if not username:
            console.print("[red]ユーザー名が必要です[/red]")
            return

    with console.status("NOTE記事データを収集中..."):
        stats = collect_note_stats(username)

    if not stats:
        console.print("[yellow]⚠ データを取得できませんでした[/yellow]")
        return

    console.print(f"  ✓ {len(stats)} 件の記事データを取得")
    t = Table("タイトル", "❤ いいね", "👁 ビュー", "💬 コメント")
    for s in sorted(stats, key=lambda x: x["likes"], reverse=True)[:10]:
        t.add_row(
            s["title"][:40], str(s["likes"]),
            str(s.get("views", "-")), str(s["comments"])
        )
    console.print(t)

    strategy = get_latest_strategy() or ""
    console.print("\n  LLM で分析中...")
    insight = analyze_with_llm(stats, strategy)
    console.print()
    console.print(Panel(Markdown(insight), title="📊 インサイト", border_style="yellow"))

# ── コマンド: opportunity ─────────────────────────────
def cmd_opportunity():
    console.print(Panel("[bold yellow]🎯 売れるテーマ自動検知[/bold yellow]"))
    from research.trend_detector import detect_opportunities, suggest_article_from_opportunity, save_opportunities
    from writer.article_gen import generate_note_article, save_draft

    topics = CONFIG["topics"]["primary"] + CONFIG["topics"]["secondary"]

    with console.status("トレンド分析中... (1〜2分かかります)"):
        opportunities = detect_opportunities(topics, top_n=5)

    if not opportunities:
        console.print("[yellow]オポチュニティが検出されませんでした[/yellow]")
        return

    # 結果テーブル表示
    console.print("\n[bold]── 今書くべきテーマ TOP5 ──[/bold]")
    t = Table("スコア", "キーワード", "トレンド", "競合数", "急上昇")
    for o in opportunities:
        rising = "🔥" if o["is_rising"] else ""
        t.add_row(
            f"{o['opportunity_score']:.0f}",
            o["keyword"],
            f"{o['trend_score']:.0f}",
            str(o["competitor_count"]),
            rising,
        )
    console.print(t)

    save_opportunities(opportunities)

    # 1位のテーマで記事案を生成
    best = opportunities[0]
    console.print(f"\n  [bold]「{best['keyword']}」で記事案を生成中...[/bold]")
    suggestion = suggest_article_from_opportunity(best, CONFIG.get("author_profile", ""))

    console.print()
    console.print(Panel(
        Markdown(suggestion["suggestion"]),
        title=f"📝 記事提案: {best['keyword']}",
        border_style="yellow",
    ))

    # そのまま下書きを生成するか確認
    ans = console.input("\n[bold]この提案で下書きを自動生成しますか？ (y/N): [/bold]").strip().lower()
    if ans == "y":
        # タイトルと構成をLLMから抽出して生成
        lines = suggestion["suggestion"].split("\n")
        title = ""
        for line in lines:
            if line.strip().startswith("1.") or line.strip().startswith("1．"):
                title = line.strip().lstrip("1.").lstrip("1．").strip()
                break
        if not title:
            title = f"{best['keyword']}完全ガイド"

        outline = [best["keyword"], "実践手順", "注意点とコツ", "まとめ"]

        console.print(f"  生成中: 「{title}」")
        article = generate_note_article(title, outline, is_paid=True,
                                         extra_context=suggestion["suggestion"][:500])
        did = save_draft("note", "article", article, title=title,
                          strategy_note=f"opportunity: {best['keyword']} score={best['opportunity_score']}")
        console.print(f"  ✓ 下書き保存 (id={did})")
        console.print()
        console.print(Markdown(article[:2000] + "\n...(以下省略)"))


# ── コマンド: publish ─────────────────────────────────
def cmd_publish(target: str, draft_id: int):
    if target == "note":
        console.print(Panel(f"[bold magenta]🚀 NOTE 投稿 (draft_id={draft_id})[/bold magenta]"))
        from publisher.note_publisher import publish_note_article
        # headless=False でブラウザを表示して確認できる
        url = publish_note_article(draft_id, headless=False)
        if url:
            console.print(f"  ✓ 投稿完了: [link]{url}[/link]")
        else:
            console.print("  [red]投稿失敗。config.yaml の note.email/password を確認してください[/red]")

    elif target == "x":
        console.print(Panel(f"[bold cyan]🚀 X 投稿 (draft_id={draft_id})[/bold cyan]"))
        from publisher.x_publisher import publish_draft
        result = publish_draft(draft_id, headless=False)
        if result:
            console.print("  ✓ 投稿完了")
        else:
            console.print("  [red]投稿失敗。config.yaml の x.email/username/password を確認してください[/red]")

    else:
        console.print(f"[red]不明なターゲット: {target} (note または x)[/red]")


# ── コマンド: drafts ──────────────────────────────────
def cmd_drafts():
    from writer.article_gen import list_drafts
    console.print(Panel("[bold]📝 下書き一覧[/bold]"))
    for platform in ["note", "x"]:
        drafts = list_drafts(platform)
        if drafts:
            t = Table("ID", "種別", "タイトル/テーマ", "作成日")
            for d in drafts:
                t.add_row(
                    str(d["id"]), d["type"],
                    (d["title"] or "（タイトルなし）")[:40],
                    d["created"][:16]
                )
            console.print(f"\n[bold]{platform.upper()}[/bold]")
            console.print(t)


def cmd_auto():
    console.print(Panel("[bold green]🤖 自動収益化サイクル実行[/bold green]"))
    from automation.pipeline import run_monetization_cycle

    with console.status("調査・戦略・ドラフト生成を実行中..."):
        result = run_monetization_cycle()

    console.print(f"  ✓ NOTE収集: {result['note_count']} 件")
    if result["x_error"]:
        console.print(f"  [yellow]X収集は一部失敗: {result['x_error']}[/yellow]")
    else:
        console.print(f"  ✓ X収集: {result['x_count']} 件")

    table = Table("キーワード", "NOTE", "Xツイート", "スレッド")
    for asset in result["generated_assets"]:
        table.add_row(
            asset["keyword"],
            str(asset["note_draft_id"]),
            ", ".join(str(v) for v in asset["x_draft_ids"]),
            str(asset["thread_draft_id"]),
        )
    console.print()
    console.print(table)
    console.print()
    console.print(f"  レポート(MD): [link]{result['markdown_report']}[/link]")
    console.print(f"  レポート(JSON): [link]{result['json_report']}[/link]")

# ── エントリポイント ──────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args:
        console.print(__doc__)
        return

    cmd = args[0]
    if cmd == "models":
        cmd_models()
    elif cmd == "workers":
        cmd_workers()
    elif cmd == "task":
        if len(args) < 2:
            console.print("[red]使い方: python main.py task path/to/task.json[/red]")
        else:
            cmd_task(args[1])
    elif cmd == "task-init":
        cmd_task_init()
    elif cmd == "research":
        cmd_research()
    elif cmd == "strategy":
        cmd_strategy()
    elif cmd == "write":
        target = args[1] if len(args) > 1 else "note"
        cmd_write(target)
    elif cmd == "analyze":
        cmd_analyze()
    elif cmd == "opportunity":
        cmd_opportunity()
    elif cmd == "publish":
        target = args[1] if len(args) > 1 else ""
        if not target or len(args) < 3:
            console.print("[red]使い方: python main.py publish note|x <draft_id>[/red]")
        else:
            try:
                did = int(args[2])
                cmd_publish(target, did)
            except ValueError:
                console.print(f"[red]draft_id は整数で指定してください: {args[2]}[/red]")
    elif cmd == "drafts":
        cmd_drafts()
    elif cmd == "auto":
        cmd_auto()
    else:
        console.print(f"[red]不明なコマンド: {cmd}[/red]")
        console.print(__doc__)

if __name__ == "__main__":
    main()
