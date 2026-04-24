import os
from telegram import Update
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Set it in Environment Variables.")

async def start(update: Update, context):
    await update.message.reply_text("✅ البوت يعمل بنجاح! الآن يمكنك إضافة ميزات التحليل المالي.")

async def news(update: Update, context):
    await update.message.reply_text("📈 ميزة التحليل المالي قيد التطوير. اشكر صبرك!")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
