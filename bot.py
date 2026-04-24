# -*- coding: utf-8 -*-
"""
بوت تليجرام متخصص في تحليل الأسواق المالية
- مصادر: GNews API (يمكن إضافة المزيد لاحقاً)
- تحليل المشاعر: بسيط باستخدام كلمات مفتاحية (يجنب الاعتماد على AI مدفوع)
- منع تكرار التوصيات عبر تخزين بصمات الأخبار (ملف recommendations.json)
- قرارات: BUY, SELL, HOLD, WAIT مع درجة ثقة
- يعمل على Render (Python 3) مع متغيرات البيئة: BOT_TOKEN, GNEWS_KEY
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Tuple

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler

# ======================== إعدادات السجلات ========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== التحقق من المتغيرات المطلوبة ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GNEWS_KEY = os.getenv("GNEWS_KEY")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود. أضفه في Environment Variables على Render.")
if not GNEWS_KEY:
    raise ValueError("❌ GNEWS_KEY غير موجود. سجل مجاناً في gnews.io ثم أضف المفتاح.")

# ======================== الأصول المالية والرموز ========================
ASSETS = {
    "الذهب": "XAU/USD",
    "الفضة": "XAG/USD",
    "ناسداك": "IXIC",
    "داو جونز": "DJI",
    "النفط": "WTI"
}

# ======================== ملف لتجنب إعادة التوصيات ========================
REC_FILE = "recommendations.json"

def load_recommendations() -> Dict:
    """تحميل سجل التوصيات السابقة"""
    if not os.path.exists(REC_FILE):
        return {}
    with open(REC_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_recommendations(data: Dict):
    """حفظ سجل التوصيات"""
    with open(REC_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_already_recommended(asset: str, title: str) -> bool:
    """التحقق مما إذا كان هذا الخبر قد أوصي به من قبل"""
    recs = load_recommendations()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    return key in recs.get(asset, {})

def mark_recommended(asset: str, title: str, decision: str):
    """تسجيل التوصية لمنع إعادة الإرسال"""
    recs = load_recommendations()
    key = hashlib.md5(f"{asset}|{title}".encode()).hexdigest()
    if asset not in recs:
        recs[asset] = {}
    recs[asset][key] = {
        "title": title,
        "decision": decision,
        "time": datetime.now().isoformat()
    }
    save_recommendations(recs)

# ======================== جلب الأخبار من GNews ========================
def fetch_gnews(asset: str, symbol: str) -> List[Dict]:
    """إرجاع قائمة بالأخبار (العنوان، المحتوى، المصدر، الوقت)"""
    query = f"{asset} {symbol} stock market"
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=3&token={GNEWS_KEY}"
    try:
        resp = requests.get(url, timeout=12)
        data = resp.json()
        articles = data.get("articles", [])
        results = []
        for art in articles[:3]:
            results.append({
                "title": art.get("title", "بدون عنوان"),
                "content": art.get("description", art.get("content", "")),
                "source": art.get("source", {}).get("name", "GNews"),
                "published": art.get("publishedAt", ""),
            })
        return results
    except Exception as e:
        logger.error(f"GNews error for {asset}: {e}")
        return []

# ======================== تحليل المشاعر (بسيط، بدون AI) ========================
def analyze_sentiment(title: str, content: str) -> Tuple[float, str]:
    """إرجاع (المعامل، النص) معامل من -1 إلى +1، والمشاعر"""
    text = (title + " " + content).lower()
    pos_keywords = ["surge", "rally", "gain", "bullish", "positive", "record", "high", "growth", "profit", "up", "soar"]
    neg_keywords = ["drop", "fall", "decline", "bearish", "negative", "crash", "low", "loss", "down", "slump", "crisis"]
    pos = sum(1 for w in pos_keywords if w in text)
    neg = sum(1 for w in neg_keywords if w in text)
    total = pos + neg
    if total == 0:
        return 0.0, "⚖️ محايد"
    raw = (pos - neg) / total  # من -1 إلى +1
    # تقريب وتفسير
    if raw >= 0.4:
        return raw, "🟢 إيجابي 🔼"
    elif raw <= -0.4:
        return raw, "🔴 سلبي 🔽"
    else:
        return raw, "🟡 محايد (انتظار)"

# ======================== ناقل القرار الكمي المبسط ========================
def quant_decision(analyses: List[Dict]) -> Tuple[str, float, str]:
    """
    analyses: قائمة تحتوي على كل خبر (sentiment_score, source, title)
    """
    if not analyses:
        return "⏸ WAIT", 0.0, "لا توجد أخبار كافية"
    # متوسط مرجح (كل مصدر له نفس الوزن حالياً)
    scores = [a["sentiment_score"] for a in analyses]
    avg = sum(scores) / len(scores)
    confidence = min(0.95, 0.5 + 0.15 * len(analyses))  # ثقة أكبر كلما زادت المصادر
    if avg >= 0.4:
        return "📈 BUY (شراء)", confidence, "إشارة إيجابية قوية"
    elif avg <= -0.4:
        return "📉 SELL (بيع)", confidence, "إشارة سلبية قوية"
    elif avg >= 0.15:
        return "🤚 HOLD (احتفاظ)", confidence, "اتجاه إيجابي بسيط"
    elif avg <= -0.15:
        return "⏸ WAIT (انتظار)", confidence, "اتجاه سلبي بسيط"
    else:
        return "⏸ WAIT (انتظار)", confidence, "لا إشارة واضحة"

# ======================== أمر /news ========================
async def news(update: Update, context):
    """الرد على /news: جلب وتحليل جميع الأصول"""
    await update.message.reply_text("📡 جارٍ جلب آخر أخبار الأسواق وتحليلها...\nقد يستغرق 15-20 ثانية.")
    result_lines = []
    for asset_name, symbol in ASSETS.items():
        articles = fetch_gnews(asset_name, symbol)
        if not articles:
            result_lines.append(f"*{asset_name} ({symbol})* : ⚠️ لا أخبار حديثة.")
            continue
        analyses = []
        for art in articles:
            sent_score, sent_label = analyze_sentiment(art["title"], art["content"])
            analyses.append({
                "sentiment_score": sent_score,
                "source": art["source"],
                "title": art["title"],
                "content": art["content"]
            })
        # إزالة التوصيات المكررة (حسب العنوان)
        unique_analyses = []
        for a in analyses:
            if not is_already_recommended(asset_name, a["title"]):
                unique_analyses.append(a)
        if not unique_analyses:
            result_lines.append(f"*{asset_name} ({symbol})* : ♻️ لا توجد توصيات جديدة (تم عرضها سابقاً).")
            continue
        # اتخاذ القرار الكمي
        decision, confidence, reason = quant_decision(unique_analyses)
        # تسجيل التوصيات لمنع التكرار مستقبلاً
        for a in unique_analyses:
            mark_recommended(asset_name, a["title"], decision)
        sources_list = list(set([a["source"] for a in unique_analyses]))
        result_lines.append(
            f"*{asset_name} ({symbol})*\n"
            f"📌 *القرار*: {decision}\n"
            f"🎯 *الثقة*: {confidence:.0%}\n"
            f"📝 *السبب*: {reason}\n"
            f"🗞️ *المصادر*: {', '.join(sources_list)}\n"
            f"🔹 *أبرز عنوان*: {unique_analyses[0]['title'][:100]}...\n"
        )
    # تجميع النتيجة
    final_msg = "📊 *تحليل الأسواق المالية*\n" + f"⏱️ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    final_msg += "\n\n".join(result_lines)
    final_msg += "\n\n🤖 *ملاحظة*: التحليل آلي باستخدام أخبار GNews. يُنصح بعدم الاعتماد عليه كاستشارة مالية وحيدة."
    # تجزئة الرسالة إذا تجاوزت الطول
    if len(final_msg) > 4096:
        for i in range(0, len(final_msg), 4000):
            await update.message.reply_text(final_msg[i:i+4000], parse_mode='Markdown')
    else:
        await update.message.reply_text(final_msg, parse_mode='Markdown')

async def start(update: Update, context):
    """رسالة الترحيب"""
    await update.message.reply_text(
        "🚀 *بوت تحليل الأسواق المالية*\n\n"
        "الأوامر المتاحة:\n"
        "/news – تحليل فوري للذهب، الفضة، ناسداك، داو جونز، النفط.\n\n"
        "🔧 *ملاحظات*:\n"
        "- يستخدم GNews API (مجاني).\n"
        "- لا تُعاد نفس التوصية مرتين.\n"
        "- القرارات: BUY, SELL, HOLD, WAIT مع درجة ثقة.\n\n"
        "_يتمنى لك البوت تداولاً موفقاً_",
        parse_mode='Markdown'
    )

def main():
    """تشغيل البوت"""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    logger.info("✅ البوت شغال الآن على Render... استخدم /news")
    app.run_polling()

if __name__ == "__main__":
    main()
