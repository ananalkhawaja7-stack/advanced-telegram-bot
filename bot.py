import os
import requests
import logging
import threading
import json
import hashlib
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

if not BOT_TOKEN or not GNEWS_KEY:
    raise ValueError("Missing API Keys")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartHybridBot")

# ========= ملف منع التكرار =========
RECOMMENDATIONS_FILE = "recommendations.json"

def load_recs():
    try:
        with open(RECOMMENDATIONS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_recs(data):
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def is_already_sent(asset, title):
    """التحقق من عدم إرسال نفس التوصية خلال 24 ساعة"""
    recs = load_recs()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    if key in recs:
        last_time = datetime.fromisoformat(recs[key]['time'])
        if datetime.now() - last_time < timedelta(hours=24):
            return True
    return False

def mark_sent(asset, title, decision):
    """تسجيل التوصية لمنع التكرار"""
    recs = load_recs()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    recs[key] = {
        'asset': asset,
        'title': title[:100],
        'decision': decision,
        'time': datetime.now().isoformat()
    }
    # تنظيف التوصيات القديمة (أكثر من 7 أيام)
    recs = {k: v for k, v in recs.items() 
            if datetime.now() - datetime.fromisoformat(v['time']) < timedelta(days=7)}
    save_recs(recs)

# ========= FLASK =========
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Running ✅"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# ========= SESSION =========
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5,  # أسرع
              status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))

# ========= ASSETS =========
ASSETS = {
    "الذهب": "gold market news",
    "الفضة": "silver market news",
    "ناسداك": "Nasdaq stock news",
    "داو جونز": "Dow Jones news",
    "النفط": "crude oil news"
}

# ========= FETCH (محسّن) =========
def fetch_news(query):
    results = []
    
    # GNews
    try:
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=3&token={GNEWS_KEY}"
        data = session.get(url, timeout=8).json()
        for a in data.get("articles", [])[:2]:
            results.append({
                "title": a["title"],
                "desc": a.get("description", "")[:300],
                "source": "📰 GNews"
            })
    except Exception as e:
        logger.warning(f"GNews error: {e}")

    # NewsAPI
    if NEWSAPI_KEY:
        try:
            url = f"https://newsapi.org/v2/everything?q={query}&language=en&pageSize=2&apiKey={NEWSAPI_KEY}"
            data = session.get(url, timeout=8).json()
            for a in data.get("articles", [])[:1]:
                results.append({
                    "title": a["title"],
                    "desc": a.get("description", "")[:300],
                    "source": "📰 NewsAPI"
                })
        except:
            pass

    return results[:3]

# ========= SENTIMENT (محسّن) =========
def sentiment_score(text):
    text = text.lower()
    pos_count = sum(1 for w in ['surge','rally','gain','bullish','positive','up','growth'] if w in text)
    neg_count = sum(1 for w in ['drop','fall','decline','bearish','negative','down','loss'] if w in text)
    total = pos_count + neg_count
    if total == 0:
        return 0, "⚖️"
    raw = (pos_count - neg_count) / total
    icon = "🟢" if raw > 0.2 else "🔴" if raw < -0.2 else "🟡"
    return raw, icon

# ========= DECISION =========
def get_decision(score):
    if score > 0.4:
        return "📈 BUY"
    elif score < -0.4:
        return "📉 SELL"
    elif -0.15 <= score <= 0.15:
        return "⏸ WAIT"
    else:
        return "🤚 HOLD"

# ========= COMMAND /news =========
async def news(update: Update, context):
    await update.message.reply_text("📡 تحليل الأسواق... لحظة")

    result_lines = [f"📊 *تحليل الأسواق* - {datetime.now().strftime('%H:%M')}\n"]

    for asset, query in ASSETS.items():
        articles = fetch_news(query)
        
        if not articles:
            result_lines.append(f"*{asset}*\n⚠️ لا أخبار حديثة\n")
            continue

        scores = []
        headlines = []
        
        for a in articles[:2]:
            score, icon = sentiment_score(a['title'] + " " + a['desc'])
            
            # منع التكرار
            if is_already_sent(asset, a['title']):
                continue
                
            scores.append(score)
            headlines.append(f"{icon} {a['title'][:65]}")
            mark_sent(asset, a['title'], get_decision(score))
        
        if not scores:
            result_lines.append(f"*{asset}*\n🔄 تم تحليله مسبقاً\n")
            continue
            
        avg_score = sum(scores) / len(scores)
        decision = get_decision(avg_score)
        confidence = min(90, 50 + len(articles) * 15)
        
        result_lines.append(
            f"*{asset}*\n"
            f"📌 {decision} | 🎯 {confidence}%\n"
            f"🔹 {headlines[0]}\n"
        )

    final = "\n".join(result_lines)
    final += "\n\n⚠️ *تحليل آلي - ليس استشارة مالية*"
    await update.message.reply_text(final[:4000], parse_mode='Markdown')

# ========= START & WELCOME =========
async def start(update: Update, context):
    await update.message.reply_text(
        "🚀 *بوت تحليل الأسواق*\n"
        "/news - تحليل فوري\n\n"
        "_ذهب | فضة | ناسداك | داو جونز | نفط_",
        parse_mode='Markdown'
    )

async def auto_welcome(update: Update, context):
    await update.message.reply_text(
        "🚀 *مرحباً بك*\n"
        "📊 /news لتحليل الأسواق",
        parse_mode='Markdown'
    )

# ========= MAIN =========
def main():
    # تشغيل Flask
    threading.Thread(target=run_web, daemon=True).start()
    
    # تشغيل البوت
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_welcome))
    
    logger.info("✅ Smart Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
