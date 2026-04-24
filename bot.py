import os
import requests
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")

if not BOT_TOKEN or not GNEWS_KEY:
    raise ValueError("Missing API Keys")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartMarketBot")

# ================= SESSION WITH RETRY =================
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))

# ================= ASSETS =================
ASSETS = {
    "الذهب": "gold price market",
    "الفضة": "silver price market",
    "ناسداك": "Nasdaq stock market",
    "داو جونز": "Dow Jones index",
    "النفط": "crude oil market"
}

# ================= SMART FILTER =================
KEYWORDS = ["market", "stock", "price", "oil", "gold", "nasdaq", "dow", "inflation", "fed"]

def is_relevant(text):
    return any(word in text.lower() for word in KEYWORDS)

# ================= FETCH NEWS =================
def fetch_news(query):
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=5&token={GNEWS_KEY}"
    try:
        res = session.get(url, timeout=10)
        data = res.json()
        articles = data.get("articles", [])
        return [
            {
                "title": a["title"],
                "desc": a["description"] or "",
                "source": a["source"]["name"]
            }
            for a in articles if is_relevant(a["title"] + a["description"])
        ]
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return []

# ================= ADVANCED SENTIMENT =================
POSITIVE = {
    "surge": 2, "rally": 2, "gain": 1.5, "growth": 1.5, "bullish": 2
}
NEGATIVE = {
    "drop": -2, "fall": -2, "loss": -1.5, "crash": -3, "bearish": -2
}

def sentiment_score(text):
    score = 0
    text = text.lower()

    for word, weight in POSITIVE.items():
        if word in text:
            score += weight

    for word, weight in NEGATIVE.items():
        if word in text:
            score += weight

    return score

# ================= DECISION ENGINE =================
def make_decision(score):
    if score > 2:
        return "BUY 📈"
    elif score < -2:
        return "SELL 📉"
    elif -1 <= score <= 1:
        return "WAIT ⏸"
    else:
        return "HOLD 🤚"

# ================= CONFIDENCE MODEL =================
def confidence_model(scores):
    if not scores:
        return 0
    variance = max(scores) - min(scores)
    base = sum(scores) / len(scores)

    conf = 60 + (len(scores) * 5) - (variance * 5)
    return max(30, min(95, int(conf)))

# ================= MAIN COMMAND =================
async def news(update: Update, context):
    await update.message.reply_text("📡 تحليل الأسواق قيد التنفيذ...")

    report = [f"📊 Smart Hybrid Analysis - {datetime.now().strftime('%H:%M')}\n"]

    for asset, query in ASSETS.items():
        articles = fetch_news(query)

        if not articles:
            report.append(f"*{asset}*: ⚠️ لا بيانات")
            continue

        scores = []
        headlines = []

        for a in articles:
            text = a["title"] + " " + a["desc"]
            score = sentiment_score(text)
            scores.append(score)

            icon = "🟢" if score > 0 else "🔴" if score < 0 else "🟡"
            headlines.append(f"{icon} {a['title'][:70]}")

        avg_score = sum(scores) / len(scores)
        decision = make_decision(avg_score)
        confidence = confidence_model(scores)

        report.append(
            f"*{asset}*\n"
            f"📌 {decision} | 🎯 ثقة {confidence}%\n"
            f"🔹 {headlines[0]}"
        )

    final = "\n\n".join(report)
    final += "\n\n⚠️ النظام يعتمد على تحليل الأخبار + خوارزميات تقدير."

    await update.message.reply_text(final[:4000], parse_mode='Markdown')

# ================= START =================
async def start(update: Update, context):
    await update.message.reply_text("🚀 Smart Hybrid Bot جاهز\nاستخدم /news")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))

    logger.info("🔥 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
