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
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # اختياري

if not BOT_TOKEN or not GNEWS_KEY:
    raise ValueError("Missing API Keys")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartHybridBot")

# ========= FLASK =========
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Running ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# ========= SESSION =========
session = requests.Session()
retry = Retry(total=3, backoff_factor=1,
              status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))

# ========= ASSETS =========
ASSETS = {
    "الذهب": "gold inflation FED interest rate",
    "الفضة": "silver inflation economy",
    "ناسداك": "US tech stocks Apple Microsoft earnings Nasdaq",
    "داو جونز": "US economy inflation interest rates Dow Jones",
    "النفط": "crude oil OPEC supply demand geopolitics"
}

KEYWORDS = [
    "market","stock","price","oil","gold",
    "nasdaq","dow","inflation","fed",
    "interest","economy","earnings","recession"
]

# ========= FILTER =========
def is_relevant(text):
    return any(k in text.lower() for k in KEYWORDS)

# ========= FETCH MULTI SOURCE =========
def fetch_news(query):
    results = []

    # --- GNews ---
    try:
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=5&token={GNEWS_KEY}"
        data = session.get(url).json()
        for a in data.get("articles", []):
            results.append({
                "title": a["title"],
                "desc": a.get("description", ""),
                "source": "GNews"
            })
    except:
        pass

    # --- NewsAPI (اختياري) ---
    if NEWSAPI_KEY:
        try:
            url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=5&apiKey={NEWSAPI_KEY}"
            data = session.get(url).json()
            for a in data.get("articles", []):
                results.append({
                    "title": a["title"],
                    "desc": a.get("description", ""),
                    "source": "NewsAPI"
                })
        except:
            pass

    # فلترة + إزالة تكرار
    seen = set()
    filtered = []

    for r in results:
        key = r["title"][:60]
        if key in seen:
            continue
        if not is_relevant(r["title"] + r["desc"]):
            continue
        seen.add(key)
        filtered.append(r)

    return filtered[:4]

# ========= SENTIMENT =========
POS = {"surge":2,"rally":2,"gain":1.5,"growth":1.5,"bullish":2}
NEG = {"drop":-2,"fall":-2,"loss":-1.5,"crash":-3,"bearish":-2}

def sentiment(text):
    score = 0
    text = text.lower()
    for w,v in POS.items():
        if w in text: score += v
    for w,v in NEG.items():
        if w in text: score += v
    return score

# ========= DECISION =========
def decision(scores):
    if not scores:
        return "WAIT ⏸", 0

    avg = sum(scores)/len(scores)
    strong = max(scores, key=abs)

    if abs(strong) > 2:
        avg = strong

    if avg > 1.5:
        return "BUY 📈", avg
    elif avg < -1.5:
        return "SELL 📉", avg
    elif -0.5 <= avg <= 0.5:
        return "WAIT ⏸", avg
    else:
        return "HOLD 🤚", avg

# ========= CONFIDENCE =========
def confidence(scores):
    if not scores:
        return 55

    variance = max(scores) - min(scores)
    avg = abs(sum(scores)/len(scores))
    conf = 60 + len(scores)*5 + avg*5 - variance*4
    return max(50, min(95, int(conf)))

# ========= COMMAND =========
async def news(update: Update, context):
    await update.message.reply_text("📡 تحليل احترافي جاري...")

    report = [f"📊 Smart Hybrid Analysis - {datetime.now().strftime('%H:%M')}\n"]

    for asset, query in ASSETS.items():
        articles = fetch_news(query)

        if len(articles) < 2:
            report.append(
                f"*{asset}*\n📊 هدوء إخباري\n📌 WAIT ⏸ | 🎯 55%"
            )
            continue

        scores = []
        texts = []

        for a in articles:
            text = a["title"] + " " + a["desc"]
            s = sentiment(text)
            scores.append(s)

            icon = "🟢" if s>0 else "🔴" if s<0 else "🟡"
            texts.append(f"{icon} {a['title'][:70]}")

        dec, _ = decision(scores)
        conf = confidence(scores)

        report.append(
            f"*{asset}*\n"
            f"📌 {dec} | 🎯 {conf}%\n"
            f"🔹 {texts[0]}\n"
            f"🔹 {texts[1]}"
        )

    final = "\n\n".join(report)
    final += "\n\n⚠️ تحليل ذكي متعدد المصادر"

    await update.message.reply_text(final[:4000], parse_mode='Markdown')

# ========= START =========
async def start(update: Update, context):
    await update.message.reply_text("🚀 البوت الاحترافي جاهز\n/news")

# ========= MAIN =========
def main():
    threading.Thread(target=run_web).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))

    logger.info("🔥 Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
# أضف هذا المعالج الجديد (بدلاً من معالج start وحده)
async def auto_welcome(update: Update, context):
    """يرسل ترحيباً تلقائياً لأي رسالة نصية (بدون أوامر)"""
    await update.message.reply_text(
        "🚀 *مرحباً بك في بوت تحليل الأسواق المالية*\n\n"
        "الأوامر المتاحة:\n"
        "/news - تحليل فوري للذهب، الفضة، ناسداك، داو جونز، النفط\n"
        "/start - عرض هذه الرسالة مرة أخرى\n\n"
        "_تمتع بتحليلات دقيقة!_",
        parse_mode='Markdown'
    )

# ثم في دالة main()، أضف:
def main():
    threading.Thread(target=run_web).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # معالج الأوامر
    app.add_handler(CommandHandler("start", auto_welcome))
    app.add_handler(CommandHandler("news", news))
    
    # معالج النصوص العادية (لأي رسالة يكتبها المستخدم)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_welcome))
    
    logger.info("🔥 Running...")
    app.run_polling()
