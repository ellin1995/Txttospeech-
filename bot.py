import os
import time
import telebot
from telebot import types
from flask import Flask
from gtts import gTTS

TOKEN = '9002637890:AAHzUTVGa116PF4v4bHf'
bot = telebot.TeleBot(TOKEN)

CHANNEL_USERNAME = '@txttospeechali'
user_subscriptions = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Error checking sub: {e}")
    return False

def verify_and_process(message):
    user_id = message.from_user.id
    current_time = time.time()
    
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        join_btn = types.InlineKeyboardButton("📢 اشترك في القناة أولاً", url=f"https://t.me/txttospeechali")
        check_btn = types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub")
        markup.add(join_btn)
        markup.add(check_btn)
        
        bot.reply_to(
            message, 
            "عذراً، يجب عليك الاشتراك في قناتنا أولاً لتتمكن من استخدام البوت مجاناً لمدة شهر!", 
            reply_markup=markup
        )
        return False

    ONE_MONTH_SECONDS = 30 * 24 * 60 * 60
    
    if user_id not in user_subscriptions:
        user_subscriptions[user_id] = current_time + ONE_MONTH_SECONDS
    
    if current_time > user_subscriptions[user_id]:
        markup = types.InlineKeyboardMarkup()
        buy_btn = types.InlineKeyboardButton("💳 شراء اشتراك جديد (تجديد شهر)", callback_data="buy_subscription")
        markup.add(buy_btn)
        
        bot.reply_to(
            message, 
            "⚠️ انتهت فترة تجربتك المجانية (الشهر الأول).\nللاستمرار في استخدام البوت، يرجى تجديد الاشتراك.", 
            reply_markup=markup
        )
        return False

    return True

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if verify_and_process(message):
        bot.reply_to(message, "أهلاً بك في بوت تحويل النصوص إلى صوت! 🎙️\nأرسل أي نص وسأقوم بتحويله لك فوراً.")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not verify_and_process(message):
        return

    user_id = message.from_user.id
    text = message.text
    bot.reply_to(message, "⏳ جاري تحويل النص إلى صوت...")
    
    try:
        tts = gTTS(text=text, lang='ar')
        audio_path = f"voice_{user_id}.mp3"
        tts.save(audio_path)
        
        with open(audio_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio)
        
        os.remove(audio_path)
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء التوليد: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if call.data == "check_sub":
        if check_subscription(user_id):
            bot.answer_callback_query(call.id, "تم التحقق بنجاح! يمكنك استخدام البوت الآن.")
            bot.send_message(call.id, "أهلاً بك مجدداً! أرسل أي نص لتحويله إلى صوت.")
        else:
            bot.answer_callback_query(call.id, "لم تقم بالاشتراك في القناة بعد!", show_alert=True)
            
    elif call.data == "buy_subscription":
        bot.answer_callback_query(call.id, "تواصل مع المطور لشراء الاشتراك.")
        bot.send_message(call.id, "لشراء الاشتراك وتجديد المدة، يرجى التواصل مع الإدارة.")

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()
    bot.infinity_polling()
