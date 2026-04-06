"""
投稿スケジューラー
APScheduler で定期的に記事調査・生成・投稿を自動実行する

実行:
  python scheduler.py              # 常駐起動
  python scheduler.py --once       # 今すぐ1回だけ実行して終了
  python scheduler.py --status     # スケジュール確認
"""
import sys
import yaml
import json
import signal
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

CONFIG = yaml.safe_load(open(Path(__file__).parent / "config.yaml"))


# ── ジョブ定義 ─────────────────────────────────────────

def job_research():
    """トレンド調査（NOTE + X）"""
    log.info("=== [research] トレンド調査開始 ===")
    from research.note_scraper import scrape_and_store
    from research.x_scraper import scrape_x_trends

    topics = CONFIG["topics"]["primary"] + CONFIG["topics"]["secondary"]
    n = scrape_and_store(topics, pages=2)
    log.info(f"  NOTE: {n} 件収集")

    # X スクレイピングはネットワーク負荷が高いので一部のみ
    try:
        xn = scrape_x_trends(CONFIG["topics"]["primary"], max_per_topic=15)
        log.info(f"  X: {xn} 件収集")
    except Exception as e:
        log.warning(f"  X スクレイピングスキップ: {e}")


def job_strategy():
    """週次戦略更新（月曜朝）"""
    log.info("=== [strategy] 週次戦略立案 ===")
    from research.note_scraper import analyze_audience, analyze_top_articles
    from writer.strategy import build_weekly_strategy, save_strategy

    audience = analyze_audience(CONFIG["topics"]["primary"])
    top = analyze_top_articles(20)

    if not audience:
        log.warning("  調査データなし。research ジョブを先に実行してください")
        return

    strategy = build_weekly_strategy(audience, top)
    sid = save_strategy(strategy, CONFIG["topics"]["primary"])
    log.info(f"  戦略保存 (id={sid})")


def job_auto_tweet():
    """X ツイート自動生成 + 投稿（有効な場合）"""
    log.info("=== [tweet] X 自動ツイート ===")
    from writer.article_gen import generate_x_tweets, save_draft
    from writer.strategy import get_latest_strategy
    from publisher.x_publisher import publish_draft

    strategy = get_latest_strategy() or ""

    # 戦略から今日のトピックを抽出（簡易: primary topics からランダム選択）
    import random
    topic = random.choice(CONFIG["topics"]["primary"])
    style = random.choice(["知識共有", "事例紹介"])

    log.info(f"  テーマ: {topic} / スタイル: {style}")
    tweets = generate_x_tweets(topic, count=1, style=style)

    if not tweets:
        log.warning("  ツイート生成失敗")
        return

    draft_id = save_draft("x", "tweet", tweets[0], strategy_note=topic)
    log.info(f"  ドラフト保存 (id={draft_id})")

    # 自動投稿が有効な場合のみ実際に投稿
    if CONFIG.get("scheduler", {}).get("auto_post_x", False):
        result = publish_draft(draft_id, headless=True)
        log.info(f"  投稿結果: {'✓' if result else '✗'}")
    else:
        log.info("  auto_post_x=false のためドラフト保存のみ（main.py publish で手動投稿）")


def job_opportunity():
    """売れるテーマを自動検知 → スコア上位1位の下書きを自動生成"""
    log.info("=== [opportunity] 売れるテーマ自動検知 ===")
    from research.trend_detector import detect_opportunities, suggest_article_from_opportunity, save_opportunities
    from writer.article_gen import generate_note_article, save_draft

    topics = CONFIG["topics"]["primary"] + CONFIG["topics"]["secondary"]
    opportunities = detect_opportunities(topics, top_n=5)

    if not opportunities:
        log.warning("  オポチュニティ未検出")
        return

    for o in opportunities:
        log.info(f"  [{o['opportunity_score']:5.1f}] {o['keyword']} "
                 f"(trend={o['trend_score']:.0f}, comp={o['competitor_count']}{'🔥' if o['is_rising'] else ''})")

    save_opportunities(opportunities)

    # スコア1位のテーマで自動下書き生成
    best = opportunities[0]
    log.info(f"  → 「{best['keyword']}」で下書きを自動生成")

    suggestion = suggest_article_from_opportunity(best, CONFIG.get("author_profile", ""))

    lines = suggestion["suggestion"].split("\n")
    title = ""
    for line in lines:
        if line.strip().startswith("1.") or line.strip().startswith("1．"):
            title = line.strip().lstrip("1.").lstrip("1．").strip()
            break
    if not title:
        title = f"{best['keyword']}完全ガイド"

    outline = [best["keyword"], "実践手順", "注意点とコツ", "まとめ"]
    article = generate_note_article(title, outline, is_paid=True,
                                     extra_context=suggestion["suggestion"][:500])
    did = save_draft("note", "article", article, title=title,
                      strategy_note=f"opportunity: {best['keyword']} score={best['opportunity_score']}")
    log.info(f"  ✓ 下書き自動保存 (id={did}) タイトル: {title}")


def job_analytics():
    """自分の記事の反応データ収集・分析"""
    log.info("=== [analytics] 反応データ収集 ===")
    username = CONFIG.get("note", {}).get("username", "")
    if not username:
        log.warning("  config.yaml の note.username を設定してください")
        return

    from analytics.collector import collect_note_stats
    stats = collect_note_stats(username)
    if stats:
        log.info(f"  {len(stats)} 件の記事データを収集")
        # DB に保存（analytics テーブルへ）
        from db.schema import get_conn
        conn = get_conn()
        for s in stats:
            # published_posts に対応するレコードがあれば analytics に記録
            row = conn.execute(
                "SELECT id FROM published_posts WHERE post_url=?", (s["url"],)
            ).fetchone()
            if row:
                conn.execute("""
                    INSERT INTO analytics (post_id, platform, likes, views, comments)
                    VALUES (?, 'note', ?, ?, ?)
                """, (row[0], s["likes"], s.get("views", 0), s["comments"]))
        conn.commit()
        conn.close()
    else:
        log.warning("  データ取得失敗")


# ── スケジューラー起動 ─────────────────────────────────

def build_scheduler():
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("APScheduler が未インストールです: pip install apscheduler")
        sys.exit(1)

    sched = BlockingScheduler(timezone="Asia/Tokyo")
    sc = CONFIG.get("scheduler", {})

    # トレンド調査: 毎日 6:00
    sched.add_job(
        job_research,
        CronTrigger(hour=sc.get("research_hour", 6), minute=0),
        id="research", replace_existing=True,
    )

    # 週次戦略: 月曜 7:00
    sched.add_job(
        job_strategy,
        CronTrigger(day_of_week="mon", hour=sc.get("strategy_hour", 7), minute=0),
        id="strategy", replace_existing=True,
    )

    # X 自動ツイート: 月・水・金 12:00 (エンゲージメント高い時間帯)
    sched.add_job(
        job_auto_tweet,
        CronTrigger(day_of_week="mon,wed,fri", hour=sc.get("tweet_hour", 12), minute=0),
        id="tweet", replace_existing=True,
    )

    # アナリティクス収集: 毎日 22:00
    sched.add_job(
        job_analytics,
        CronTrigger(hour=sc.get("analytics_hour", 22), minute=0),
        id="analytics", replace_existing=True,
    )

    # オポチュニティ検知 + 下書き自動生成: 火・木 8:00
    sched.add_job(
        job_opportunity,
        CronTrigger(day_of_week="tue,thu", hour=8, minute=0),
        id="opportunity", replace_existing=True,
    )

    return sched


def run_once():
    """今すぐ全ジョブを順番に実行"""
    log.info("=== ワンショット実行 ===")
    job_research()
    job_strategy()
    job_opportunity()


def show_status(sched):
    print("\n── スケジュール一覧 ──")
    for job in sched.get_jobs():
        print(f"  [{job.id:12s}] 次回実行: {job.next_run_time}")
    print()


def main():
    args = sys.argv[1:]

    if "--once" in args:
        run_once()
        return

    sched = build_scheduler()

    if "--status" in args:
        # ステータス表示のみ（BackgroundScheduler で非ブロッキング起動）
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            print("APScheduler が未インストールです: pip install apscheduler")
            sys.exit(1)

        sc = CONFIG.get("scheduler", {})
        bg = BackgroundScheduler(timezone="Asia/Tokyo")
        bg.add_job(job_research,  CronTrigger(hour=sc.get("research_hour", 6), minute=0), id="research")
        bg.add_job(job_strategy,  CronTrigger(day_of_week="mon", hour=sc.get("strategy_hour", 7), minute=0), id="strategy")
        bg.add_job(job_auto_tweet,CronTrigger(day_of_week="mon,wed,fri", hour=sc.get("tweet_hour", 12), minute=0), id="tweet")
        bg.add_job(job_analytics, CronTrigger(hour=sc.get("analytics_hour", 22), minute=0), id="analytics")
        bg.start()
        show_status(bg)
        bg.shutdown(wait=False)
        return

    log.info("スケジューラー起動 (Ctrl+C で停止)")
    show_status(sched)

    def _shutdown(sig, frame):
        log.info("シャットダウン中...")
        sched.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    sched.start()


if __name__ == "__main__":
    main()
