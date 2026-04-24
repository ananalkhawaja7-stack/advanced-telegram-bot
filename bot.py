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
if not GNEWS_KEY:
    raise ValueError("GNEWS_KEY missing")

# رموز البحث الصحيحة لكل أصل (عبارات بحث دقيقة)
ASSETS = {
    "الذهب": "gold price",
    "الفضة": "silver price",
    "ناسداك": "Nasdaq index",
    "داو جونز": "Dow Jones",
    "النفط": "crude oil price"
}

def fetch_news(asset, query):
    """جلب أخبار ذات صلة بالأسواق المالية فقط"""
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=2&token={GNEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        articles = data.get("articles", [])
        results = []
        for art in articles:
            title = art.get("title", "")
            desc = art.get("description", "")
            # تجاهل الأخبار غير المالية
            if any(word in title.lower() for word in ["stock", "price", "market", "oil", "gold", "nasdaq", "dow"]):
                results.append({"title": title, "content": desc, "source": art.get("source", {}).get("name", "GNews")})
        return results[:2]
    except Exception as e:
        logger.error(f"Error fetching {asset}: {e}")
        return []

def sentiment_score(text):
    """تحليل بسيط للمشاعر"""
    pos = sum(1 for w in ["surge", "rally", "gain", "up", "high", "growth"] if w in text.lower())
    neg = sum(1 for w in ["drop", "fall", "decline", "down", "low", "loss"] if w in text.lower())
    total = pos + neg
    if total == 0:
        return 0, "🟡"
    score = (pos - neg) / total
    if score >= 0.3:
        return score, "🟢"
    elif score <= -0.3:
        return score, "🔴"
    else:
        return score, "🟡"

def make_decision(score):
    """توصية بسيطة بناءً على المشاعر"""
    if score >= 0.4:
        return "BUY 📈"
    elif score <= -0.4:
        return "SELL 📉"
    elif score >= 0.15:
        return "HOLD 🤚"
    else:
        return "WAIT ⏸"

async def news(update, context):
    await update.message.reply_text("📡 جلب وتحليل الأخبار المالية...")
    result = [f"📊 تحليل الأسواق - {datetime.now().strftime('%H:%M')}\n"]
    for asset, query in ASSETS.items():
        articles = fetch_news(asset, query)
        if not articles:
            result.append(f"*{asset}*: ⚠️ لا أخبار حديثة")
            continue
        total_score = 0
        titles = []
        for a in articles:
            score, icon = sentiment_score(a["title"] + " " + a["content"])
            total_score += score
            titles.append(f"{icon} {a['title'][:60]}")
        avg_score = total_score / len(articles)
        decision = make_decision(avg_score)
        confidence = min(90, 50 + len(articles) * 20)
        result.append(f"*{asset}*\n📌 {decision} (ثقة {confidence}%)\n🔹 {titles[0]}\n")
    final = "\n".join(result) + "\n⚠️ تحليل آلي، ليس استشارة مالية."
    await update.message.reply_text(final[:4000], parse_mode='Markdown')

async def start(update, context):
    await update.message.reply_text("🚀 بوت تحليل الأسواق\n/news - تحليل فوري")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    logger.info("✅ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
