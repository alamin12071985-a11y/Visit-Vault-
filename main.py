import logging
import sqlite3
import datetime
import requests
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# --- FLASK KEEP-ALIVE SERVER (FOR RENDER) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render assigns a port via the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION ---
# We use os.environ.get to fetch the token from Render's settings securely
BOT_TOKEN = os.environ.get("8561330173:AAGOtGKX63tsy7-FyGyPoZSGuscQd8M3hlo") 
RAPID_API_KEY = "804a832d72msha80a359a7d29bdcp16d69cjsnbdab13b7f417"
RAPID_API_HOST = "instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com"
PREMIUM_PRICE = 100 
SUBSCRIPTION_DAYS = 30

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- DATABASE SETUP ---
# WARNING: On Render Free Tier, this file resets on every deploy/restart.
# For permanent storage, you need Render Disk (Paid) or PostgreSQL.
def init_db():
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users 
           (user_id INTEGER PRIMARY KEY, language TEXT, expiry_date TEXT)"""
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_language(user_id, lang):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, language, expiry_date) VALUES (?, ?, ?)", 
              (user_id, lang, None))
    c.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()

def update_subscription(user_id):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    new_expiry = (datetime.datetime.now() + datetime.timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
    c.execute("INSERT OR IGNORE INTO users (user_id, language, expiry_date) VALUES (?, ?, ?)", 
              (user_id, 'en', new_expiry))
    c.execute("UPDATE users SET expiry_date=? WHERE user_id=?", (new_expiry, user_id))
    conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user or not user[2]:
        return False
    expiry = datetime.datetime.fromisoformat(user[2])
    if datetime.datetime.now() < expiry:
        return True
    return False

# --- LANGUAGES & TEXTS ---
LANGUAGES = {
    "en": "🇺🇸 English", "bn": "🇧🇩 Bangla", "hi": "🇮🇳 Hindi", "es": "🇪🇸 Spanish", 
    "ar": "🇸🇦 Arabic", "ru": "🇷🇺 Russian", "fr": "🇫🇷 French", "de": "🇩🇪 German",
    "pt": "🇵🇹 Portuguese", "id": "🇮🇩 Indonesian", "tr": "🇹🇷 Turkish", "it": "🇮🇹 Italian",
    "ja": "🇯🇵 Japanese", "ko": "🇰🇷 Korean", "zh": "🇨🇳 Chinese", "vi": "🇻🇳 Vietnamese",
    "ur": "🇵🇰 Urdu", "fa": "🇮🇷 Persian", "pl": "🇵🇱 Polish", "th": "🇹🇭 Thai"
}

TEXTS = {
    "welcome": {"en": "Welcome!", "bn": "স্বাগতম!"},
    "set_lang": {"en": "Language set! Send link.", "bn": "ভাষা সেট করা হয়েছে! লিঙ্ক পাঠান।"},
    "pay_wall": {
        "en": "🔒 <b>Premium Required</b>\nPrice: 100 Stars / 1 Month.",
        "bn": "🔒 <b>প্রিমিয়াম প্রয়োজন</b>\nমূল্য: ১০০ স্টার / ১ মাস।"
    },
    "processing": {"en": "🔄 Processing...", "bn": "🔄 প্রক্রিয়া করা হচ্ছে..."},
    "success": {"en": "✅ Payment Successful!", "bn": "✅ পেমেন্ট সফল!"},
    "error": {"en": "❌ Failed.", "bn": "❌ ব্যর্থ হয়েছে।"}
}

def get_text(lang, key):
    lang_dict = TEXTS.get(key, {})
    return lang_dict.get(lang, lang_dict.get("en", "Text Error"))

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for code, name in LANGUAGES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 Select Language / ভাষা নির্বাচন করুন:", reply_markup=reply_markup)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_")[1]
    update_language(query.from_user.id, lang_code)
    await query.edit_message_text(text=get_text(lang_code, "set_lang"))

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    user_data = get_user(user_id)
    lang = user_data[1] if user_data else "en"

    if "instagram.com" not in message_text:
        return 
        
    if not check_premium(user_id):
        title = "Instagram Premium"
        description = get_text(lang, "pay_wall")
        payload = "Instagram-Premium-30Days"
        currency = "XTR"
        prices = [LabeledPrice("1 Month Sub", PREMIUM_PRICE)]
        await context.bot.send_invoice(
            chat_id=update.message.chat_id,
            title=title,
            description="Unlock downloads.",
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices,
        )
        return

    await update.message.reply_text(get_text(lang, "processing"))
    try:
        url = "https://instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com/"
        querystring = {"Userinfo": message_text} 
        headers = {"x-rapidapi-host": RAPID_API_HOST, "x-rapidapi-key": RAPID_API_KEY}
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        
        video_url = None
        if isinstance(data, list) and len(data) > 0:
             if 'url' in data[0]: video_url = data[0]['url']
        elif isinstance(data, dict):
             if 'url' in data: video_url = data['url']
        
        if video_url:
            await update.message.reply_video(video_url)
        else:
            await update.message.reply_text("Could not find video in link.")
    except Exception as e:
        logging.error(f"API Error: {e}")
        await update.message.reply_text(get_text(lang, "error"))

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    update_subscription(user_id)
    user_data = get_user(user_id)
    lang = user_data[1] if user_data else "en"
    await update.message.reply_text(get_text(lang, "success"))

def main():
    init_db()
    
    # Check for Token
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in environment variables.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start Bot
    print("Bot is polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
