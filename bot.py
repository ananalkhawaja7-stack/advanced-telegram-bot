import os
import requests
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# الأصول المالية
ASSETS = {
    "الذهب": "gold",
    "الفضة": "silver",
    "ناسداك": "Nasdaq",
    "داو جونز": "Dow Jones",
    "النفط": "oil"
}

def fetch_news(asset):
    """جلب أخبار من GNews API"""
    if not GNEWS_KEY:
        return []
    url = f"https://gnews.io/api/v4/search?q={asset}&lang=en&max=2&token={GNEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "articles" in data:
            return [{"title": a["title"], "content": a.get("description", ""), "source": "GNews"} for a in data["articles"][:2]]
    except Exception as e:
        logger.error(f"Error fetching {asset}: {e}")
    return []

def analyze_sentiment(title, content):
    """تحليل المشاعر"""
    text = (title + " " + content).lower()
    pos = sum(1 for w in ["surge","rally","gain","bullish","positive","up","growth"] if w in text)
    neg = sum(1 for w in ["drop","fall","decline","bearish","negative","down","loss"] if w in text)
    total = pos + neg
    if total == 0:
        return 0, "🟡 محايد"
    score = (pos - neg) / total
    if score >= 0.3:
        return score, "🟢 إيجابي"
    elif score <= -0.3:
        return score, "🔴 سلبي"
    else:
        return score, "🟡 محايد"

def quant_decision(analyses):
    """اتخاذ القرار"""
    if not analyses:
        return "WAIT", 0, "لا أخبار"
    avg = sum(a["score"] for a in analyses) / len(analyses)
    conf = min(0.9, 0.5 + 0.1 * len(analyses))
    if avg >= 0.4:
        return "📈 BUY", conf, "إيجابي قوي"
    elif avg <= -0.4:
        return "📉 SELL", conf, "سلبي قوي"
    else:
        return "⏸ WAIT", conf, "بدون إشارة"

async def news(update, context):
    """الأمر /news"""
    await update.message.reply_text("📡 جارٍ جلب الأخبار وتحليلها...")
    result = [f"📊 تحليل الأسواق\n🕐 {datetime.now().strftime('%H:%M')}\n"]
    
    for name, keyword in ASSETS.items():
        articles = fetch_news(keyword)
        if not articles:
            result.append(f"*{name}*: ⚠️ لا أخبار حديثة")
            continue
        
        analyses = []
        for a in articles:
            score, label = analyze_sentiment(a["title"], a["content"])
            analyses.append({"score": score, "source": a["source"], "title": a["title"]})
        
        decision, conf, reason = quant_decision(analyses)
        sources = list(set(a["source"] for a in analyses))
        result.append(f"*{name}*\n📌 {decision} (ثقة {conf:.0%})\n📝 {reason}\n🗞️ {', '.join(sources)}\n🔹 {analyses[0]['title'][:80]}...")
    
    final = "\n\n".join(result) + "\n\n⚠️ تحليل آلي، ليس استشارة مالية."
    await update.message.reply_text(final[:4096], parse_mode='Markdown')

async def start(update, context):
    await update.message.reply_text("🚀 بوت تحليل الأسواق\n/news - تحليل فوري")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    logger.info("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
