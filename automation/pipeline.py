"""
収益化サイクル自動実行

1. NOTE/X の調査
2. 週次戦略の生成
3. 売れるテーマの検出
4. NOTE 有料記事ドラフト生成
5. X 集客ツイート / スレッド生成
6. レポート保存
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import yaml

from research.note_scraper import analyze_audience, analyze_top_articles, scrape_and_store
from research.trend_detector import (
    detect_opportunities,
    save_opportunities,
    suggest_article_from_opportunity,
)
from research.x_scraper import scrape_x_trends
from writer.article_gen import (
    generate_note_article,
    generate_x_thread,
    generate_x_tweets,
    save_draft,
)
from writer.strategy import build_weekly_strategy, save_strategy

CONFIG = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
REPORT_DIR = Path(__file__).parent.parent / "reports"


def _slugify(value: str) -> str:
    ascii_value = re.sub(r"\s+", "-", value.strip().lower())
    ascii_value = re.sub(r"[^a-z0-9\-_]+", "-", ascii_value)
    ascii_value = re.sub(r"-{2,}", "-", ascii_value).strip("-")
    return ascii_value or "report"


def _extract_title(suggestion: str, fallback_keyword: str) -> str:
    for line in suggestion.splitlines():
        text = line.strip()
        if re.match(r"^1[\.．]\s*", text):
            title = re.sub(r"^1[\.．]\s*", "", text).strip()
            if title:
                return title
    return f"{fallback_keyword}完全ガイド"


def _extract_outline(keyword: str, suggestion: str) -> list[str]:
    outline = []
    in_outline = False
    for raw_line in suggestion.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "構成メモ" in line:
            in_outline = True
            continue
        if in_outline and line.startswith("### "):
            break
        if in_outline and line.startswith("-"):
            outline.append(line.lstrip("-").strip())
    if outline:
        return outline[:5]
    return [keyword, "導入背景", "実践手順", "収益化ポイント", "まとめ"]


def _build_report_markdown(
    run_id: str,
    strategy: str,
    opportunities: list[dict],
    generated_assets: list[dict],
) -> str:
    lines = [
        f"# Monetization Run Report {run_id}",
        "",
        "## Top Opportunities",
        "",
    ]
    for idx, opp in enumerate(opportunities, 1):
        lines.append(
            f"{idx}. {opp['keyword']} "
            f"(score={opp['opportunity_score']}, trend={opp['trend_score']}, competitors={opp['competitor_count']})"
        )
    lines.extend([
        "",
        "## Generated Assets",
        "",
    ])
    for asset in generated_assets:
        lines.append(
            f"- {asset['keyword']}: note_draft={asset['note_draft_id']}, "
            f"x_tweets={asset['x_draft_ids']}, thread={asset['thread_draft_id']}, title={asset['title']}"
        )
    lines.extend([
        "",
        "## Weekly Strategy",
        "",
        strategy.strip(),
        "",
    ])
    return "\n".join(lines)


def run_monetization_cycle(
    top_n: int = 3,
    note_pages: int = 2,
    x_posts_per_topic: int = 10,
) -> dict:
    topics = CONFIG["topics"]["primary"] + CONFIG["topics"]["secondary"]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    REPORT_DIR.mkdir(exist_ok=True)

    note_count = scrape_and_store(topics, pages=note_pages)
    try:
        x_count = scrape_x_trends(CONFIG["topics"]["primary"], max_per_topic=x_posts_per_topic)
    except Exception as exc:
        x_count = 0
        x_error = str(exc)
    else:
        x_error = ""

    audience = analyze_audience(CONFIG["topics"]["primary"])
    top_articles = analyze_top_articles(20)

    strategy = ""
    strategy_id = None
    if audience:
        strategy = build_weekly_strategy(audience, top_articles)
        strategy_id = save_strategy(strategy, CONFIG["topics"]["primary"])

    opportunities = detect_opportunities(topics, top_n=top_n)
    save_opportunities(opportunities)

    generated_assets = []
    for opportunity in opportunities:
        suggestion = suggest_article_from_opportunity(opportunity, CONFIG.get("author_profile", ""))
        title = _extract_title(suggestion["suggestion"], opportunity["keyword"])
        outline = _extract_outline(opportunity["keyword"], suggestion["suggestion"])

        article = generate_note_article(
            title=title,
            outline=outline,
            is_paid=True,
            extra_context=suggestion["suggestion"][:1200],
        )
        note_draft_id = save_draft(
            "note",
            "article",
            article,
            title=title,
            tags=[opportunity["keyword"]],
            strategy_note=(
                f"opportunity={opportunity['keyword']} "
                f"score={opportunity['opportunity_score']} "
                f"trend={opportunity['trend_score']} "
                f"competitors={opportunity['competitor_count']}"
            ),
        )

        tweets = generate_x_tweets(opportunity["keyword"], count=3, style="事例紹介")
        x_draft_ids = [
            save_draft("x", "tweet", tweet, strategy_note=f"lead-in for note:{title}")
            for tweet in tweets
        ]

        thread_posts = generate_x_thread(opportunity["keyword"], num_posts=5)
        thread_body = "\n---\n".join(thread_posts)
        thread_draft_id = save_draft(
            "x",
            "thread",
            thread_body,
            title=f"{opportunity['keyword']} thread",
            strategy_note=f"thread funnel for note:{title}",
        )

        generated_assets.append({
            "keyword": opportunity["keyword"],
            "title": title,
            "note_draft_id": note_draft_id,
            "x_draft_ids": x_draft_ids,
            "thread_draft_id": thread_draft_id,
        })

    markdown_report = _build_report_markdown(run_id, strategy, opportunities, generated_assets)
    markdown_path = REPORT_DIR / f"monetization-run-{run_id}.md"
    json_path = REPORT_DIR / f"monetization-run-{run_id}.json"
    markdown_path.write_text(markdown_report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "note_count": note_count,
                "x_count": x_count,
                "x_error": x_error,
                "strategy_id": strategy_id,
                "opportunities": opportunities,
                "generated_assets": generated_assets,
                "report_markdown": str(markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "run_id": run_id,
        "note_count": note_count,
        "x_count": x_count,
        "x_error": x_error,
        "strategy_id": strategy_id,
        "opportunities": opportunities,
        "generated_assets": generated_assets,
        "markdown_report": str(markdown_path),
        "json_report": str(json_path),
    }
