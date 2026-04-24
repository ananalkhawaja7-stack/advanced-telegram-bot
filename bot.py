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
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
MARKETAUX_KEY = os.getenv("MARKETAUX_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# قائمة الأصول (يمكن إضافة المزيد)
ASSETS = {
    "الذهب": "GC=F",      # رمز الذهب في ياهو فاينانس
    "الفضة": "SI=F",
    "ناسداك": "IXIC",
    "داو جونز": "DJI",
    "النفط": "CL=F"
}

def fetch_finnhub(asset, symbol):
    """جلب أخبار من Finnhub (لأسهم محددة)"""
    if not FINNHUB_KEY:
        return []
    # Finnhub يحتاج رموزاً مثل AAPL, MSFT. سنستخدم رموزاً تقريبية
    symbol_map = {"الذهب": "GC", "الفضة": "SI", "ناسداك": "NDAQ", "داو جونز": "DJI", "النفط": "CL"}
    fin_symbol = symbol_map.get(asset, "GC")
    url = f"https://finnhub.io/api/v1/news?symbol={fin_symbol}&token={FINNHUB_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if isinstance(data, list):
            return [{"title": a["headline"], "content": a.get("summary", ""), "source": "Finnhub"} for a in data[:2]]
    except:
        pass
    return []

def fetch_marketaux(asset):
    """جلب أخبار من Marketaux"""
    if not MARKETAUX_KEY:
        return []
    url = f"https://api.marketaux.com/v1/news/all?symbols={asset}&limit=2&api_token={MARKETAUX_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "data" in data:
            return [{"title": a["title"], "content": a.get("description", ""), "source": "Marketaux"} for a in data["data"][:2]]
    except:
        pass
    return []

def fetch_gnews(asset, symbol):
    """جلب أخبار من GNews"""
    if not GNEWS_KEY:
        return []
    query = f"{asset} market news"
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=2&token={GNEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "articles" in data:
            return [{"title": a["title"], "content": a.get("description", ""), "source": "GNews"} for a in data["articles"][:2]]
    except:
        pass
    return []

def collect_news(asset, symbol):
    """جمع الأخبار من جميع المصادر المتاحة"""
    all_news = []
    all_news.extend(fetch_gnews(asset, symbol))
    all_news.extend(fetch_finnhub(asset, symbol))
    all_news.extend(fetch_marketaux(asset))
    # إزالة التكرارات البسيطة
    seen = set()
    unique = []
    for n in all_news:
        key = n["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique[:3]  # كحد أقصى 3 أخبار

def analyze_sentiment(title, content):
    """تحليل بسيط للمشاعر"""
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
    if not analyses:
        return "WAIT", 0, "لا أخبار"
    avg = sum(a["score"] for a in analyses) / len(analyses)
    conf = min(0.9, 0.5 + 0.1 * len(analyses))
    if avg >= 0.4:
        return "📈 BUY", conf, "إيجابي قوي"
    elif avg <= -0.4:
        return "📉 SELL", conf, "سلبي قوي"
    elif avg >= 0.15:
        return "🤚 HOLD", conf, "إيجابي بسيط"
    else:
        return "⏸ WAIT", conf, "بدون إشارة"

async def news(update, context):
    await update.message.reply_text("📡 جارٍ جلب الأخبار من عدة مصادر...")
    result = [f"📊 تحليل الأسواق\n🕐 {datetime.now().strftime('%H:%M')}\n"]
    for name, symbol in ASSETS.items():
        articles = collect_news(name, symbol)
        if not articles:
            result.append(f"*{name}*: ⚠️ لا أخبار حديثة (جميع المصادر).")
            continue
        analyses = []
        for a in articles:
            score, label = analyze_sentiment(a["title"], a["content"])
            analyses.append({"score": score, "source": a["source"], "title": a["title"]})
        decision, conf, reason = quant_decision(analyses)
        sources = list(set(a["source"] for a in analyses))
        result.append(f"*{name}*\n📌 {decision} (ثقة {conf:.0%})\n📝 {reason}\n🗞️ مصادر: {', '.join(sources)}\n🔹 {analyses[0]['title'][:80]}...")
    final = "\n\n".join(result) + "\n\n⚠️ تحليل آلي، ليس استشارة مالية."
    await update.message.reply_text(final[:4096], parse_mode='Markdown')

async def start(update, context):
    await update.message.reply_text("🚀 بوت تحليل الأسواق\n/news - تحليل فوري")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    logger.info("✅ Bot running with multiple sources")
    app.run_polling()

if __name__ == "__main__":
    main()
