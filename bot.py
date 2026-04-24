import os
import requests
import logging
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")

if not BOT_TOKEN or not GNEWS_KEY:
    raise ValueError("Missing API Keys")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartHybridBot")

# ========= FLASK (حل مشكلة Render) =========
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# ========= SESSION =========
session = requests.Session()
retry = Retry(total=3, backoff_factor=1,
              status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))

# ========= ASSETS =========
ASSETS = {
    "الذهب": "gold price market",
    "الفضة": "silver price market",
    "ناسداك": "Nasdaq stock market",
    "داو جونز": "Dow Jones index",
    "النفط": "crude oil market"
}

# ========= KEYWORDS =========
KEYWORDS = ["market", "stock", "price", "oil", "gold", "nasdaq", "dow", "inflation", "fed"]

def is_relevant(text):
    return any(word in text.lower() for word in KEYWORDS)

# ========= FETCH =========
def fetch_news(query):
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=5&token={GNEWS_KEY}"
    try:
        res = session.get(url, timeout=10)
        data = res.json()
        articles = data.get("articles", [])
        return [
            {
                "title": a["title"],
                "desc": a.get("description", ""),
            }
            for a in articles
            if is_relevant(a["title"] + (a.get("description") or ""))
        ]
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return []

# ========= SENTIMENT =========
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

# ========= DECISION =========
def make_decision(scores):
    if not scores:
        return "WAIT ⏸", 0

    avg = sum(scores) / len(scores)
    strong_signal = max(scores, key=abs)

    if abs(strong_signal) > 2:
        avg = strong_signal

    if avg > 1.5:
        return "BUY 📈", avg
    elif avg < -1.5:
        return "SELL 📉", avg
    elif -0.5 <= avg <= 0.5:
        return "WAIT ⏸", avg
    else:
        return "HOLD 🤚", avg

# ========= CONFIDENCE =========
def confidence_model(scores):
    if not scores:
        return 55

    variance = max(scores) - min(scores)
    avg = abs(sum(scores) / len(scores))

    conf = 60 + (len(scores) * 5) + (avg * 5) - (variance * 4)
    return max(50, min(95, int(conf)))

# ========= NEUTRAL =========
def neutral_message(asset):
    return (
        f"*{asset}*\n"
        f"📊 حالة السوق: هدوء إخباري\n"
        f"📌 WAIT ⏸ | 🎯 ثقة 55%"
    )

# ========= COMMAND =========
async def news(update: Update, context):
    await update.message.reply_text("📡 Smart Hybrid Engine يعمل...")

    report = [f"📊 Smart Hybrid Analysis - {datetime.now().strftime('%H:%M')}\n"]

    for asset, query in ASSETS.items():
        articles = fetch_news(query)

        if not articles:
            report.append(neutral_message(asset))
            continue

        scores = []
        headlines = []

        for a in articles:
            text = a["title"] + " " + a["desc"]
            score = sentiment_score(text)
            scores.append(score)

            icon = "🟢" if score > 0 else "🔴" if score < 0 else "🟡"
            headlines.append(f"{icon} {a['title'][:70]}")

        decision, _ = make_decision(scores)
        confidence = confidence_model(scores)

        report.append(
            f"*{asset}*\n"
            f"📌 {decision} | 🎯 ثقة {confidence}%\n"
            f"🔹 {headlines[0]}"
        )

    final = "\n\n".join(report)
    final += "\n\n⚠️ تحليل ذكي يعتمد على الأخبار + نماذج تقدير."

    await update.message.reply_text(final[:4000], parse_mode='Markdown')

# ========= START =========
async def start(update: Update, context):
    await update.message.reply_text("🚀 البوت شغال\n/news للتحليل")

# ========= MAIN =========
def main():
    # تشغيل Flask (لحل مشكلة Render)
    threading.Thread(target=run_web).start()

    # تشغيل البوت
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))

    logger.info("🔥 Bot + Web Running...")
    app.run_polling()

# ========= RUN =========
if __name__ == "__main__":
    main()
