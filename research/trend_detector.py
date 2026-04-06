"""
需要トレンド自動検知モジュール
「検索量が増えているのに記事が少ないキーワード」= 売れるタイミング を検出する

スコア式:
  opportunity_score = 検索トレンド上昇率 × (1 / 競合記事数) × 鮮度係数
"""
import json
import time
import httpx
from pathlib import Path
from datetime import datetime, timedelta
import sys
sys.path.append(str(Path(__file__).parent.parent))
from db.schema import get_conn


# ── Google Trends ────────────────────────────────────────

def get_google_trends(keywords: list[str], timeframe: str = "now 7-d") -> dict[str, float]:
    """
    キーワードのGoogleトレンドスコアを取得
    戻り値: {keyword: 上昇率} (0〜100+, 100以上なら急上昇)
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))

        result = {}
        # pytrends は一度に5キーワードまで
        for i in range(0, len(keywords), 5):
            chunk = keywords[i:i+5]
            try:
                pytrends.build_payload(chunk, timeframe=timeframe, geo="JP")
                df = pytrends.interest_over_time()
                if df.empty:
                    for kw in chunk:
                        result[kw] = 0.0
                    continue

                for kw in chunk:
                    if kw in df.columns:
                        vals = df[kw].tolist()
                        if len(vals) >= 2:
                            # 直近3点の平均 vs 前半の平均で上昇率を計算
                            recent = sum(vals[-3:]) / 3
                            earlier = sum(vals[:max(1, len(vals)//2)]) / max(1, len(vals)//2)
                            result[kw] = round(recent / max(earlier, 1) * 100, 1)
                        else:
                            result[kw] = float(vals[0]) if vals else 0.0
                    else:
                        result[kw] = 0.0
                time.sleep(1.5)
            except Exception as e:
                print(f"  [warn] trends chunk error: {e}")
                for kw in chunk:
                    result[kw] = 0.0

        return result
    except ImportError:
        print("  [warn] pytrends 未インストール: pip install pytrends")
        return {kw: 50.0 for kw in keywords}


def get_related_rising_queries(seed_keywords: list[str]) -> list[str]:
    """Google Trends の「急上昇キーワード」関連語を取得"""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
        rising = []

        for kw in seed_keywords[:3]:  # 負荷軽減のため最大3件
            try:
                pytrends.build_payload([kw], timeframe="now 7-d", geo="JP")
                related = pytrends.related_queries()
                if kw in related and related[kw]["rising"] is not None:
                    df = related[kw]["rising"]
                    rising.extend(df["query"].tolist()[:5])
                time.sleep(1.5)
            except Exception:
                pass

        return list(set(rising))
    except Exception:
        return []


# ── 競合記事数（NOTE内） ────────────────────────────────

def count_note_articles(keyword: str) -> int:
    """NOTE の検索結果件数（競合の多さ）"""
    import urllib.parse
    q = urllib.parse.quote(keyword)
    url = f"https://note.com/api/v3/searches?context=note&q={q}&page=1&sort=like"
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        total = r.json().get("data", {}).get("notes", {}).get("total_count", 0)
        return total
    except Exception:
        return 999


# ── オポチュニティスコア計算 ────────────────────────────

def calc_opportunity_score(
    trend_score: float,
    competitor_count: int,
    days_since_last_post: int = 0,
) -> float:
    """
    売れるタイミングスコア (0〜100)
    - trend_score: 検索量スコア (高いほど需要あり)
    - competitor_count: 競合記事数 (少ないほど差別化しやすい)
    - days_since_last_post: 最後に自分が書いた日数
    """
    # トレンド: 0〜100に正規化（元データが0のときは平均的な50として扱う）
    effective_trend = trend_score if trend_score > 0 else 30.0
    trend_factor = min(effective_trend / 100, 2.0)

    # 競合: 対数スケールで計算（1万件でも0にしない）
    import math
    competition_factor = max(0.1, 1 - math.log10(max(competitor_count, 1)) / 5)

    # 鮮度: 一度も書いていない or 30日以上経過で最大
    freshness_factor = min(days_since_last_post / 30, 1.0) * 0.5 + 0.5

    score = trend_factor * competition_factor * freshness_factor * 100
    return round(min(score, 100), 1)


# ── メイン検知ロジック ──────────────────────────────────

def detect_opportunities(topics: list[str], top_n: int = 5) -> list[dict]:
    """
    トレンド × 競合 × 鮮度でオポチュニティを検出
    戻り値: スコア上位 top_n 件
    """
    print("  Google Trends を取得中...")
    trends = get_google_trends(topics)

    print("  関連急上昇キーワードを取得中...")
    rising_queries = get_related_rising_queries(topics[:3])
    # 急上昇キーワードも候補に追加
    all_keywords = list(set(topics + rising_queries[:10]))

    if rising_queries:
        extra_trends = get_google_trends(rising_queries[:10])
        trends.update(extra_trends)

    print("  NOTE 競合記事数を確認中...")
    conn = get_conn()

    results = []
    for kw in all_keywords:
        trend = trends.get(kw, 50.0)
        competitors = count_note_articles(kw)

        # 自分が最後にこのキーワードで書いた日を確認
        row = conn.execute("""
            SELECT MAX(created_at) FROM content_drafts
            WHERE body LIKE ? OR title LIKE ? OR strategy_note LIKE ?
        """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchone()

        last_written = row[0] if row and row[0] else None
        if last_written:
            try:
                dt = datetime.fromisoformat(last_written)
                days_since = (datetime.now() - dt).days
            except Exception:
                days_since = 30
        else:
            days_since = 30  # 一度も書いていない → 書き時

        score = calc_opportunity_score(trend, competitors, days_since)

        results.append({
            "keyword": kw,
            "trend_score": trend,
            "competitor_count": competitors,
            "days_since_last": days_since,
            "opportunity_score": score,
            "is_rising": kw in rising_queries,
        })
        time.sleep(0.3)

    conn.close()

    # スコア降順でソート
    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return results[:top_n]


def save_opportunities(opportunities: list[dict]):
    """検出したオポチュニティをDBに保存（audience_profiles テーブルを流用）"""
    conn = get_conn()
    for opp in opportunities:
        conn.execute("""
            INSERT INTO audience_profiles
            (platform, topic, engagement_rate, note)
            VALUES ('trend', ?, ?, ?)
        """, (
            opp["keyword"],
            opp["opportunity_score"],
            json.dumps(opp, ensure_ascii=False),
        ))
    conn.commit()
    conn.close()


# ── LLM による記事テーマ提案 ────────────────────────────

def suggest_article_from_opportunity(opportunity: dict, author_profile: str = "") -> dict:
    """
    オポチュニティから具体的な記事テーマ・構成・投稿タイミングをLLMで提案
    """
    import yaml
    config = yaml.safe_load(open(Path(__file__).parent.parent / "config.yaml"))
    from writer.ollama_client import chat

    model = config["ollama"]["model_fast"]
    kw = opportunity["keyword"]
    trend = opportunity["trend_score"]
    comp = opportunity["competitor_count"]
    score = opportunity["opportunity_score"]

    prompt = f"""
## 今注目のキーワード
「{kw}」
- Googleトレンドスコア: {trend} (100=通常、200=2倍急上昇)
- NOTE競合記事数: {comp}件
- オポチュニティスコア: {score}/100

## 発信者プロフィール
{author_profile}

## タスク
このキーワードで今すぐ書くべきNOTE記事を提案してください。

以下の形式で出力：

### 推奨タイトル案（3つ）
1.
2.
3.

### ターゲット読者
（具体的に）

### 無料 or 有料
（理由も1行で）

### 構成メモ（3〜5点）
-

### 投稿推奨タイミング
（なぜ今なのか）

### 一言コメント
（このテーマで書く価値）
"""
    response = chat(prompt, model, "あなたはコンテンツマーケティングの専門家です。")
    return {
        "keyword": kw,
        "opportunity": opportunity,
        "suggestion": response,
    }
