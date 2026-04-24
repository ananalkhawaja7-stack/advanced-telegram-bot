import os
import requests
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ... (كود الدوال الأخرى: fetch_gnews, collect_news, analyze_sentiment, quant_decision يبقى كما هو دون تغيير) ...

# قائمة لتخزين معرفات المستخدمين النشطين
active_users = set()

async def start(update: Update, context):
    """تسجيل المستخدم وإرسال رسالة ترحيب."""
    user_id = update.effective_chat.id
    active_users.add(user_id) # 🔴 إضافة المستخدم إلى القائمة
    await update.message.reply_text(
        "🚀 بوت تحليل الأسواق\n"
        "/news - تحليل فوري\n"
        "📢 ستصلك تحديثات تلقائية عن الأسواق كل 30 دقيقة."
    )

async def send_auto_update(context):
    """هذه الدالة تُستدعى تلقائياً كل 30 دقيقة وترسل التحليل لجميع المستخدمين."""
    if not active_users:
        return

    # 1. إنشاء نص التحليل
    result = [f"📊 تحديث تلقائي للأسواق\n🕐 {datetime.now().strftime('%H:%M')}\n"]
    for name, symbol in ASSETS.items():
        articles = collect_news(name, symbol)
        if not articles:
            result.append(f"*{name}*: ⚠️ لا أخبار حديثة.")
            continue
        # ... (نفس منطق التحليل في دالة news) ...
        analyses = []
        for a in articles:
            score, label = analyze_sentiment(a["title"], a["content"])
            analyses.append({"score": score, "source": a["source"], "title": a["title"]})
        decision, conf, reason = quant_decision(analyses)
        sources = list(set(a["source"] for a in analyses))
        result.append(f"*{name}*\n📌 {decision} (ثقة {conf:.0%})\n📝 {reason}\n🗞️ مصادر: {', '.join(sources)}\n🔹 {analyses[0]['title'][:80]}...")
    final = "\n\n".join(result)

    # 2. إرسال التحليل لجميع المستخدمين المسجلين
    for user_id in active_users:
        try:
            await context.bot.send_message(chat_id=user_id, text=final[:4096], parse_mode='Markdown')
        except Exception as e:
            logger.error(f"فشل الإرسال للمستخدم {user_id}: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # إضافة المعالج للأمر /start
    app.add_handler(CommandHandler("start", start))
    # ... (أضف معالج /news هنا أيضاً)

    # 🔴 إعداد المجدول لإرسال التحديثات كل 30 دقيقة
    scheduler = AsyncIOScheduler()
    trigger = IntervalTrigger(minutes=30)
    scheduler.add_job(send_auto_update, trigger, args=[app])
    scheduler.start()

    logger.info("✅ البوت يعمل مع تحديث تلقائي كل 30 دقيقة")
    app.run_polling()

if __name__ == "__main__":
    main()
