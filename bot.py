# ============================================================
# بوت تليجرام بسيط لاختبار التوكن والاتصال
# يمكنك لاحقاً إضافة ميزات تحليل الأخبار المالية هنا
# ============================================================

import os
from telegram import Update
from telegram.ext import Application, CommandHandler

# قراءة التوكن من متغيرات البيئة (يجب أن يكون موجوداً في Render)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# التأكد من وجود التوكن (رسالة خطأ واضحة)
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود! تأكد من إضافته في Environment Variables على Render.")

# أمر /start - رسالة ترحيبية تعلم المستخدم أن البوت يعمل
async def start(update: Update, context):
    await update.message.reply_text(
        "✅ البوت يعمل بنجاح!\n\n"
        "📌 الأوامر المتاحة حالياً:\n"
        "/start - عرض هذه الرسالة\n"
        "/news - (قيد التطوير) سيتم إضافة تحليل الأسواق المالية قريباً.\n\n"
        "🤖 تم إنشاء هذا البوت باستخدام Render + GitHub + Python."
    )

# أمر /news - رسالة مؤقتة لحين إضافة التحليل المتقدم
async def news(update: Update, context):
    await update.message.reply_text(
        "📈 تحليل الأسواق المالية قيد التطوير.\n"
        "سيتم إضافة: الذهب، الفضة، ناسداك، داو جونز، النفط، وشركات التكنولوجيا.\n"
        "باستخدام GNews API + Gemini AI (قريباً)."
    )

# الوظيفة الرئيسية لتشغيل البوت
def main():
    # إنشاء تطبيق البوت باستخدام التوكن
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ربط الأوامر مع الوظائف
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    
    # طباعة رسالة في سجل Render تؤكد بدء التشغيل
    print("✅ Bot is running... (انتظر رسالة 'Live' ثم اختبر /start على تليجرام)")
    
    # بدء الاستماع للطلبات (تشغيل البوت)
    app.run_polling()

# نقطة الدخول - تشغيل main() فقط إذا تم تنفيذ الملف مباشرة (وليس استيراده)
if __name__ == "__main__":
    main()

# ============================================================
# نهاية الكود
# ملاحظة: إذا أردت إضافة تحليل متقدم، ضع الكود الجديد تحت هذا السطر
# مع تحديث دالة news() ودالة التحليل.
# ============================================================
