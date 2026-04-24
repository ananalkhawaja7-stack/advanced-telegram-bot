"""
بوت تحليل الأسواق المالية المتقدم
يدعم: 3 مصادر أخبار، منع تكرار، ذاكرة مستخدمين، تشفير، ناقل قرار كمي، تقييم مجتمعي
يعمل على Render مجاناً
"""
import requests
import json
import hashlib
import os
import logging
from datetime import datetime
from cryptography.fernet import Fernet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# ================== إعدادات أساسية ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات البيئة (تضبطها في Render)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")
MARKETAUX_KEY = os.getenv("MARKETAUX_KEY")   # اختياري
FINNHUB_KEY = os.getenv("FINNHUB_KEY")       # اختياري
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY") # اختياري، للتشفير
if ENCRYPTION_KEY:
    cipher = Fernet(ENCRYPTION_KEY.encode())
else:
    cipher = None

# ================== ملفات الذاكرة ==================
RECOMMENDATIONS_FILE = "recommendations.json"  # منع التكرار
USER_MEMORY_FILE = "user_memory.json"          # تفضيلات المستخدمين

def load_json(file):
    try:
        with open(file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# ================== منع التكرار ==================
def get_hash(title, asset):
    return hashlib.md5(f"{asset}:{title}".encode()).hexdigest()

def already_recommended(asset, title):
    recs = load_json(RECOMMENDATIONS_FILE)
    h = get_hash(title, asset)
    return h in recs.get(asset, {})

def mark_recommended(asset, title, decision):
    recs = load_json(RECOMMENDATIONS_FILE)
    if asset not in recs:
        recs[asset] = {}
    h = get_hash(title, asset)
    recs[asset][h] = {
        'title': title[:150],
        'decision': decision,
        'timestamp': datetime.now().isoformat()
    }
    save_json(RECOMMENDATIONS_FILE, recs)

# ================== جلب الأخبار من 3 مصادر ==================
def fetch_gnews(asset, symbol):
    if not GNEWS_KEY:
        return []
    url = f"https://gnews.io/api/v4/search?q={asset}+{symbol}&lang=en&max=2&token={GNEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "articles" in data:
            return [{
                'title': a['title'],
                'content': a.get('description', ''),
                'source': 'GNews',
                'time': a['publishedAt']
            } for a in data['articles'][:2]]
    except Exception as e:
        logger.warning(f"GNews error: {e}")
    return []

def fetch_marketaux(asset):
    if not MARKETAUX_KEY:
        return []
    url = f"https://api.marketaux.com/v1/news/all?symbols={asset}&limit=2&api_token={MARKETAUX_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "data" in data:
            return [{
                'title': a['title'],
                'content': a.get('description', ''),
                'source': 'Marketaux',
                'time': a.get('published_at', '')
            } for a in data['data'][:2]]
    except:
        pass
    return []

def fetch_finnhub(asset):
    if not FINNHUB_KEY:
        return []
    url = f"https://finnhub.io/api/v1/news?category={asset.lower()}&token={FINNHUB_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if isinstance(data, list):
            return [{
                'title': a['headline'],
                'content': a.get('summary', ''),
                'source': 'Finnhub',
                'time': datetime.fromtimestamp(a['datetime']).isoformat()
            } for a in data[:2]]
    except:
        pass
    return []

def collect_all_news(asset, symbol):
    """جمع من 3 مصادر وتوحيد النتائج"""
    all_news = []
    all_news.extend(fetch_gnews(asset, symbol))
    all_news.extend(fetch_marketaux(asset))
    all_news.extend(fetch_finnhub(asset))
    
    # إزالة التكرارات البسيطة حسب العنوان
    unique = {}
    for n in all_news:
        key = n['title'][:50].lower()
        if key not in unique:
            unique[key] = n
    return list(unique.values())[:4]  # كحد أقصى 4 أخبار

# ================== تحليل المشاعر والثقة ==================
def analyze_sentiment(title, content):
    text = (title + " " + content).lower()
    pos = sum(1 for w in ['surge','rally','gain','bullish','positive','record','growth'] if w in text)
    neg = sum(1 for w in ['drop','fall','decline','bearish','negative','crash','loss'] if w in text)
    total = pos + neg
    if total == 0:
        return 0.0, "محايد"
    score = (pos - neg) / total
    sentiment = "🟢 إيجابي" if score > 0.3 else "🔴 سلبي" if score < -0.3 else "🟡 محايد"
    return score, sentiment

def compute_confidence(analyses):
    """حساب درجة الثقة بناءً على عدد المصادر وتطابقها"""
    if not analyses:
        return 0.0
    # كلما زاد عدد المصادر وزاد تطابق الإشارات زادت الثقة
    scores = [a['sentiment'] for a in analyses]
    if len(set(scores)) == 1 and len(analyses) >= 3:
        return 0.9
    elif len(analyses) >= 2 and max(scores) - min(scores) < 0.3:
        return 0.7
    elif len(analyses) >= 2:
        return 0.5
    else:
        return 0.3

# ================== ناقل القرار الكمي المبسط ==================
def quantitative_decision(analyses):
    if not analyses:
        return "WAIT", 0.0, "لا توجد أخبار كافية"
    
    weighted = sum(a['sentiment'] * (0.5 if a['source']=='GNews' else 0.3) for a in analyses)
    total = sum((0.5 if a['source']=='GNews' else 0.3) for a in analyses)
    final_score = weighted / total if total else 0
    
    if final_score > 0.4:
        return "BUY 📈", min(0.99, final_score), "إشارة شراء قوية"
    elif final_score < -0.4:
        return "SELL 📉", min(0.99, abs(final_score)), "إشارة بيع"
    elif final_score > 0.15:
        return "HOLD 🤚", final_score, "اتجاه إيجابي ضعيف"
    else:
        return "WAIT ⏸", abs(final_score), "لا إشارة واضحة"

# ================== أوامر البوت ==================
async def start(update, context):
    await update.message.reply_text(
        "🤖 *بوت تحليل الأسواق المتقدم*\n\n"
        "✅ 3 مصادر أخبار (GNews, Marketaux, Finnhub)\n"
        "✅ منع تكرار التوصيات\n"
        "✅ ذاكرة مستخدمين\n"
        "✅ ناقل قرار كمي (BUY/SELL/HOLD/WAIT)\n"
        "✅ تشفير اختياري\n\n"
        "/news - تحليل فوري\n"
        "/feedback - تقييم التوصيات\n"
        "/stats - إحصائياتك",
        parse_mode='Markdown'
    )

async def news(update, context):
    await update.message.reply_text("📊 جاري التحليل من 3 مصادر... (10-15 ثانية)")
    
    assets = {
        "الذهب": "XAU/USD",
        "الفضة": "XAG/USD",
        "ناسداك": "IXIC",
        "داو جونز": "DJI",
        "النفط": "WTI"
    }
    user_id = str(update.effective_user.id)
    result = f"📈 *تحليل السوق*\n🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
    
    for name, symbol in assets.items():
        news_items = collect_all_news(name, symbol)
        if not news_items:
            result += f"*{name}*: ⚠️ لا أخبار جديدة\n\n"
            continue
        
        analyses = []
        for item in news_items:
            if already_recommended(name, item['title']):
                continue
            sentiment_score, sentiment_label = analyze_sentiment(item['title'], item['content'])
            analyses.append({
                'title': item['title'][:80],
                'sentiment': sentiment_score,
                'source': item['source'],
                'label': sentiment_label
            })
        
        if not analyses:
            result += f"*{name}*: تكررت التوصيات\n\n"
            continue
        
        decision, confidence, reason = quantitative_decision(analyses)
        # تسجيل التوصية لمنع التكرار
        for a in analyses:
            mark_recommended(name, a['title'], decision)
        
        result += f"*{name}* ({symbol})\n"
        result += f"📌 {decision} (ثقة {confidence:.0%})\n"
        result += f"📝 {reason}\n"
        result += f"🗂️ مصادر: {', '.join(set(a['source'] for a in analyses))}\n\n"
    
    # تشفير النتيجة إذا تم تفعيله
    final_text = result[:4000]  # حد تلغرام
    if cipher and len(final_text) > 100:
        encrypted = cipher.encrypt(final_text.encode()).decode()
        final_text = f"🔒 *رسالة مشفرة*\n`{encrypted[:200]}...`"
    
    await update.message.reply_text(final_text, parse_mode='Markdown')
    
    # تحديث ذاكرة المستخدم
    mem = load_json(USER_MEMORY_FILE)
    if user_id not in mem:
        mem[user_id] = {'count': 0, 'feedback': []}
    mem[user_id]['count'] += 1
    mem[user_id]['last'] = datetime.now().isoformat()
    save_json(USER_MEMORY_FILE, mem)

async def feedback(update, context):
    keyboard = [[
        InlineKeyboardButton("✅ مفيد", callback_data="up"),
        InlineKeyboardButton("❌ غير مفيد", callback_data="down")
    ]]
    await update.message.reply_text("هل كانت التوصيات مفيدة؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    mem = load_json(USER_MEMORY_FILE)
    if user_id not in mem:
        mem[user_id] = {'feedback': []}
    mem[user_id]['feedback'].append({'type': query.data, 'time': datetime.now().isoformat()})
    save_json(USER_MEMORY_FILE, mem)
    await query.edit_message_text("شكراً لتقييمك! 🙏")

async def stats(update, context):
    user_id = str(update.effective_user.id)
    mem = load_json(USER_MEMORY_FILE)
    data = mem.get(user_id, {})
    msg = f"📊 *إحصائياتك*\n"
    msg += f"طلبات التحليل: {data.get('count', 0)}\n"
    msg += f"آخر تحديث: {data.get('last', 'لايوجد')[:16]}\n"
    feedbacks = data.get('feedback', [])
    if feedbacks:
        ups = sum(1 for f in feedbacks if f['type'] == 'up')
        msg += f"تقييمات إيجابية: {ups}/{len(feedbacks)}"
    else:
        msg += "لم تقيّم بعد"
    await update.message.reply_text(msg, parse_mode='Markdown')

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("✅ Bot is running... Advanced features enabled.")
    app.run_polling()

if __name__ == "__main__":
    main()