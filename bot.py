import os
import sqlite3
import asyncio
import logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import edge_tts

# ==========================================
# ⚙️ إعدادات البوت والروابط:
# (يمكنك تعديلها هنا مباشرة أو إدخالها كـ Environment Variables على منصة الاستضافة)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
NETLIFY_URL = os.getenv("NETLIFY_URL", "https://YOUR_SUBDOMAIN.netlify.app")

DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "ar-SA-HamedNeural")
REWARD_CREDITS = int(os.getenv("REWARD_CREDITS", "3"))
INITIAL_FREE_CREDITS = int(os.getenv("INITIAL_FREE_CREDITS", "2"))
PORT = int(os.getenv("PORT", "8080"))
# ==========================================

# إعداد السجلات (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# 🗄️ قاعدة بيانات SQLite لتتبع الرصيد
# ==========================================
DB_FILE = "bot_users.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_user_credits(user_id: int) -> int:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row is not None:
            return row[0]
        cursor.execute(
            "INSERT INTO users (user_id, credits) VALUES (?, ?)",
            (user_id, INITIAL_FREE_CREDITS)
        )
        conn.commit()
        return INITIAL_FREE_CREDITS

def add_user_credits(user_id: int, amount: int) -> int:
    current = get_user_credits(user_id)
    new_credits = current + amount
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET credits = ? WHERE user_id = ?", (new_credits, user_id))
        conn.commit()
    return new_credits

def deduct_user_credit(user_id: int) -> bool:
    current = get_user_credits(user_id)
    if current <= 0:
        return False
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    return True

# ==========================================
# 🤖 أوامر البوت
# ==========================================

def get_ad_keyboard():
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان لتفعيل/شحن الرصيد", url=NETLIFY_URL)]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "صديقي"

    args = context.args or []
    if args and "reward" in args:
        total_credits = add_user_credits(user_id, REWARD_CREDITS)
        await update.message.reply_text(
            f"🎉 **مبروك يا {first_name}!**\n\n"
            f"✅ تم تأكيد مشاهدة الإعلان بنجاح وإضافة **+{REWARD_CREDITS} محاولات** إلى رصيدك.\n"
            f"💳 رصيدك الحالي: **{total_credits} محاولات**.\n\n"
            f"✍️ أرسل لي الآن أي نص وسأقوم بتحويله فوراً إلى تسجيل صوتي بجودة عالية!",
            parse_mode="Markdown"
        )
        return

    credits = get_user_credits(user_id)
    msg = (
        f"مرحباً بك يا **{first_name}** في بوت تحويل النصوص إلى صوت 🎙️\n\n"
        f"🔊 نقوم بتحويل نصوصك إلى صوت احترافي وطبيعي باللغة العربية عبر الذكاء الاصطناعي.\n\n"
        f"💳 رصيدك المتاح حالياً: **{credits} محاولات**.\n\n"
        f"📌 **طريقة الاستخدام:**\n"
        f"فقط اكتب أي نص باللغة العربية وأرسله هنا مباشرة.\n\n"
        f"إذا نفد رصيدك، يمكنك مشاهدة إعلان مجاني سريع للحصول على محاولات إضافية في أي وقت!"
    )

    if credits <= 0:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_ad_keyboard())
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")

async def text_to_speech_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    current_credits = get_user_credits(user_id)
    if current_credits <= 0:
        await update.message.reply_text(
            "⚠️ **عذراً، لقد نفد رصيدك من المحاولات المجانية!**\n\n"
            "اضغط على الزر أدناه لمشاهدة إعلان سريع والحصول على محاولات إضافية فوراً 🎁",
            parse_mode="Markdown",
            reply_markup=get_ad_keyboard()
        )
        return

    status_msg = await update.message.reply_text("⏳ جاري توليد الصوت الاحترافي، يرجى الانتظار...")
    temp_audio_file = f"tts_{user_id}_{update.message.message_id}.mp3"

    try:
        communicate = edge_tts.Communicate(text=text, voice=DEFAULT_VOICE)
        await communicate.save(temp_audio_file)

        deduct_user_credit(user_id)
        remaining = get_user_credits(user_id)

        caption = (
            f"✅ تم توليد الصوت بنجاح!\n"
            f"💳 الرصيد المتبقي: {remaining} محاولات."
        )

        with open(temp_audio_file, "rb") as audio:
            await update.message.reply_voice(voice=audio, caption=caption)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"خطأ أثناء توليد الصوت: {e}")
        await status_msg.edit_text("❌ حدث خطأ أثناء معالجة النص، يرجى التأكد من صحة النص والمحاولة مرة أخرى.")

    finally:
        if os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
            except Exception:
                pass

# ==========================================
# 🌐 سيرفر ويب خفيف لإبقاء البوت حياً على الاستضافات السحابية
# ==========================================
async def health_check(request):
    return web.Response(text="Bot is running online 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 خادم الويب السحابي يعمل على المنفذ {PORT}")

# ==========================================
# 🚀 نقطة التشغيل الرئيسية
# ==========================================
async def run_bot():
    init_db()

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ خطأ: يرجى وضع التوكن الخاص ببوتك في متغير BOT_TOKEN!")
        return

    # تشغيل خادم الويب في الخلفية للاستضافات مثل Render
    await start_web_server()

    # تشغيل البوت
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_to_speech_handler))

    logger.info("🚀 جاري بدء تشغيل البوت بنمط Polling...")
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    # الإبقاء على العملية تعمل باستمرار
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم إيقاف البوت.")
