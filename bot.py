# أضف هذه الاستيرادات في الأعلى
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from textblob import TextBlob
import sqlite3
from datetime import datetime, timedelta

# ========= 1. قاعدة بيانات بسيطة (SQLite) =========
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS recommendations
                 (id INTEGER PRIMARY KEY, asset TEXT, title TEXT, 
                  decision TEXT, score REAL, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_feedback
                 (user_id INTEGER, recommendation_id INTEGER, feedback INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def save_recommendation(asset, title, decision, score):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO recommendations (asset, title, decision, score, timestamp) VALUES (?, ?, ?, ?, ?)",
              (asset, title, decision, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ========= 2. تحليل متقدم للمشاعر (TextBlob) =========
def advanced_sentiment(text):
    """تحليل المشاعر مع دعم أفضل للغة الإنجليزية"""
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity  # -1 إلى +1
    subjectivity = blob.sentiment.subjectivity  # 0 إلى 1
    
    if polarity > 0.3:
        sentiment = "🟢 إيجابي قوي"
        action = "BUY 📈"
    elif polarity > 0.05:
        sentiment = "🟡 إيجابي ضعيف"
        action = "HOLD 🤚"
    elif polarity < -0.3:
        sentiment = "🔴 سلبي قوي"
        action = "SELL 📉"
    elif polarity < -0.05:
        sentiment = "🟠 سلبي ضعيف"
        action = "WAIT ⏸"
    else:
        sentiment = "⚪ محايد"
        action = "WAIT ⏸"
    
    return polarity, sentiment, action, subjectivity

# ========= 3. تحديث تلقائي (Scheduler) =========
scheduler = AsyncIOScheduler()

async def auto_analysis(context):
    """إرسال تحليل تلقائي للمستخدمين النشطين"""
    # ستحتاج إلى تخزين chat_ids للمستخدمين الذين اشتركوا
    # هذا مثال مبسط
    logger.info("🔄 تحديث تلقائي للتحليل...")

# جدولة التحليل كل ساعة
scheduler.add_job(auto_analysis, 'interval', hours=1)

# ========= 4. نظام تقييم المستخدمين (أزرار) =========
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def news_with_feedback(update: Update, context):
    await update.message.reply_text("📡 جاري التحليل...")
    
    # ... كود التحليل ...
    
    # إضافة أزرار التقييم
    keyboard = [[
        InlineKeyboardButton("👍 مفيد", callback_data="feedback_up"),
        InlineKeyboardButton("👎 غير مفيد", callback_data="feedback_down")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(final, parse_mode='Markdown', reply_markup=reply_markup)

async def feedback_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "feedback_up":
        await query.edit_message_text("شكراً لتقييمك! 🙏")
    else:
        await query.edit_message_text("تم تسجيل تقييمك، سنحسن الأداء 📈")
