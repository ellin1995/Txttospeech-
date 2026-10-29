import os
import telebot
from gtts import gTTS

# ضع التوكن الخاص بك هنا
TOKEN = '8846303152:AAGZfWwK5C9kFL_OlIbncp5_cZ96Lb8xYWQ'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(bot_instance, message):
    bot_instance.reply_to(message, "أهلاً بك! أرسل أي نص وسأقوم بتحويله إلى ملف صوتي بأي لغة.")

@bot.message_handler(func=lambda message: True)
def text_to_speech(message):
    text = message.text
    if not text.strip():
        return

    try:
        # رسالة توضيحية للمستخدم
        sent_msg = bot.reply_to(message, "جاري تحويل النص إلى صوت...")

        # توليد الملف الصوتي (افتراضياً باللغة العربية أو تلقائي، يمكن ضبط اللغة)
        # يمكنك استخدام gtts لتوليد الصوت
        tts = gTTS(text=text, lang='ar', slow=False)
        audio_path = f"voice_{message.chat.id}.mp3"
        tts.save(audio_path)

        # إرسال الملف الصوتي للمستخدم
        with open(audio_path, 'rb') as audio:
            bot.send_voice(message.chat.id, audio)

        bot.delete_message(message.chat.id, sent_msg.message_id)

        # حذف الملف المؤقت من الجهاز
        if os.path.exists(audio_path):
            os.remove(audio_path)

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء المعالجة: {str(e)}")

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
