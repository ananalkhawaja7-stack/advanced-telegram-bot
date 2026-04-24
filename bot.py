import os
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Tuple
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")
if not GNEWS_KEY:
    raise ValueError("GNEWS_KEY missing")

ASSETS = {
    "الذهب": "XAU/USD",
    "الفضة": "XAG/USD",
    "ناسداك": "IXIC",
    "داو جونز": "DJI",
    "النفط": "WTI"
}

REC_FILE = "recommendations.json"

def load_recommendations():
    if not os.path.exists(REC_FILE):
        return {}
    with open(REC_FILE, 'r') as f:
        return json.load(f)

def save_recommendations(data):
    with open(REC_FILE, 'w') as f:
        json.dump(data, f)

def is_recommended(asset, title):
    recs = load_recommendations()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    return key in recs.get(asset, {})

def mark_recommended(asset, title, decision):
    recs = load_recommendations()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    if asset not in recs:
        recs[asset] = {}
    recs[asset][key] = {"title": title, "decision": decision, "time": datetime.now().isoformat()}
    save_recommendations(recs)

def fetch_gnews(asset, symbol):
    query = f"{asset} {symbol} stock market"
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=2&token={GNEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        articles = data.get("articles", [])
        results = []
        for art in articles[:2]:
            results.append({
                "title": art.get("title", ""),
                "content": art.get("description", art.get("content", "")),
                "source": art.get("source", {}).get("name", "GNews"),
                "published": art.get("publishedAt", "")
            })
        return results
    except Exception as e:
        logger.error(f"GNews error {asset}: {e}")
        return []

def analyze_sentiment(title, content):
    text = (title + " " + content).lower()
    pos_words = ["surge","rally","gain","bullish","positive","record","high","growth","profit","up"]
    neg_words = ["drop","fall","decline","bearish","negative","crash","low","loss","down"]
    pos = sum(1 for w in pos_words if w in text)
    neg = sum(1 for w in neg_words if w in text)
    total = pos + neg
    if total == 0:
        return 0.0, "⚖️ محايد"
    raw = (pos - neg) / total
    if raw >= 0.4:
        return raw, "🟢 إيجابي"
    elif raw <= -0.4:
        return raw, "🔴 سلبي"
    else:
        return raw, "🟡 محايد"

def quant_decision(analyses):
    if not analyses:
        return "⏸ WAIT", 0.0, "لا أخبار كافية"
    scores = [a["sentiment_score"] for a in analyses]
    avg = sum(scores) / len(scores)
    conf = min(0.95, 0.5 + 0.15 * len(analyses))
    if avg >= 0.4:
        return "📈 BUY", conf, "إيجابي قوي"
    elif avg <= -0.4:
        return "📉 SELL", conf, "سلبي قوي"
    elif avg >= 0.15:
        return "🤚 HOLD", conf, "إيجابي بسيط"
    elif avg <= -0.15:
        return "⏸ WAIT", conf, "سلبي بسيط"
    else:
        return "⏸ WAIT", conf, "بدون إشارة"

async def news(update, context):
    await update.message.reply_text("📡 جارٍ جلب الأخبار وتحليلها... (15-20 ثانية)")
    result = [f"📊 *تحليل الأسواق*\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for name, sym in ASSETS.items():
        articles = fetch_gnews(name, sym)
        if not articles:
            result.append(f"*{name} ({sym})* : ⚠️ لا أخبار حديثة.")
            continue
        analyses = []
        for art in articles:
            score, label = analyze_sentiment(art["title"], art["content"])
            analyses.append({"sentiment_score": score, "source": art["source"], "title": art["title"]})
        unique = [a for a in analyses if not is_recommended(name, a["title"])]
        if not unique:
            result.append(f"*{name} ({sym})* : ♻️ مكررة (سبق إرسالها).")
            continue
        decision, conf, reason = quant_decision(unique)
        for a in unique:
            mark_recommended(name, a["title"], decision)
        sources = list(set(a["source"] for a in unique))
        result.append(f"*{name} ({sym})*\n📌 {decision} (ثقة {conf:.0%})\n📝 {reason}\n🗞️ مصادر: {', '.join(sources)}\n🔹 {unique[0]['title'][:80]}...")
    final = "\n\n".join(result) + "\n\n⚠️ تحليل آلي، ليس استشارة مالية."
    await update.message.reply_text(final[:4096], parse_mode='Markdown')

async def start(update, context):
    await update.message.reply_text("🚀 بوت تحليل الأسواق\n/news - تحليل فوري")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    logger.info("✅ Bot running with full features")
    app.run_polling()

if __name__ == "__main__":
    main()
