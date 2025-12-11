import logging
import sqlite3
import datetime
import requests
import json
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

# --- CONFIGURATION ---
BOT_TOKEN = "a8561330173:AAGOtGKX63tsy7-FyGyPoZSGuscQd8M3hlo"  # Replace with your Bot Token
RAPID_API_KEY = "804a832d72msha80a359a7d29bdcp16d69cjsnbdab13b7f417"
RAPID_API_HOST = "instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com"

# Subscription Cost in Telegram Stars (XTR)
PREMIUM_PRICE = 100  # 100 Stars
SUBSCRIPTION_DAYS = 30

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- DATABASE SETUP (SQLite) ---
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
    # Insert or ignore, then update
    c.execute("INSERT OR IGNORE INTO users (user_id, language, expiry_date) VALUES (?, ?, ?)", 
              (user_id, lang, None))
    c.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()

def update_subscription(user_id):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    
    # Calculate new expiry (Now + 30 days)
    new_expiry = (datetime.datetime.now() + datetime.timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
    
    c.execute("INSERT OR IGNORE INTO users (user_id, language, expiry_date) VALUES (?, ?, ?)", 
              (user_id, 'en', new_expiry))
    c.execute("UPDATE users SET expiry_date=? WHERE user_id=?", (new_expiry, user_id))
    conn.commit()
    conn.close()

def check_premium(user_id):
    user = get_user(user_id)
    if not user or not user[2]: # user[2] is expiry_date
        return False
    
    expiry = datetime.datetime.fromisoformat(user[2])
    if datetime.datetime.now() < expiry:
        return True
    return False

# --- LOCALIZATION / LANGUAGES ---
LANGUAGES = {
    "en": "🇺🇸 English", "bn": "🇧🇩 Bangla", "hi": "🇮🇳 Hindi", "es": "🇪🇸 Spanish", 
    "ar": "🇸🇦 Arabic", "ru": "🇷🇺 Russian", "fr": "🇫🇷 French", "de": "🇩🇪 German",
    "pt": "🇵🇹 Portuguese", "id": "🇮🇩 Indonesian", "tr": "🇹🇷 Turkish", "it": "🇮🇹 Italian",
    "ja": "🇯🇵 Japanese", "ko": "🇰🇷 Korean", "zh": "🇨🇳 Chinese", "vi": "🇻🇳 Vietnamese",
    "ur": "🇵🇰 Urdu", "fa": "🇮🇷 Persian", "pl": "🇵🇱 Polish", "th": "🇹🇭 Thai"
}

# Simple translation dictionary
TEXTS = {
    "welcome": {
        "en": "Welcome! Please select your language:",
        "bn": "স্বাগতম! আপনার ভাষা নির্বাচন করুন:",
        "hi": "स्वागत हे! कृपया अपनी भाषा चुनें:",
        "es": "¡Bienvenido! Por favor seleccione su idioma:",
        # Add others as needed, defaulting to English for missing ones
    },
    "set_lang": {
        "en": "Language set to English! Send me an Instagram link to download.",
        "bn": "ভাষা বাংলায় সেট করা হয়েছে! ডাউনলোড করতে আমাকে একটি ইনস্টাগ্রাম লিঙ্ক পাঠান।",
        "es": "¡Idioma configurado en español! Envíame un enlace de Instagram.",
    },
    "pay_wall": {
        "en": "🔒 <b>Premium Required</b>\n\nYou need to subscribe to download videos.\nPrice: 100 Stars / 1 Month.",
        "bn": "🔒 <b>প্রিমিয়াম প্রয়োজন</b>\n\nভিডিও ডাউনলোড করতে আপনাকে সাবস্ক্রাইব করতে হবে।\nমূল্য: ১০০ স্টার / ১ মাস।",
        "es": "🔒 <b>Premium Requerido</b>\n\nNecesitas suscribirte para descargar videos.",
    },
    "pay_btn": {
        "en": "Buy Premium (30 Days)",
        "bn": "প্রিমিয়াম কিনুন (৩০ দিন)",
        "es": "Comprar Premium",
    },
    "processing": {
        "en": "🔄 Processing video...",
        "bn": "🔄 ভিডিও প্রক্রিয়া করা হচ্ছে...",
    },
    "success": {
        "en": "✅ Payment Successful! You can now download videos for 30 days.",
        "bn": "✅ পেমেন্ট সফল! আপনি এখন ৩০ দিনের জন্য ভিডিও ডাউনলোড করতে পারবেন।",
    },
    "error": {
        "en": "❌ Failed to download. Make sure the link is public and valid.",
        "bn": "❌ ডাউনলোড ব্যর্থ হয়েছে। লিঙ্কটি সঠিক কিনা চেক করুন।",
    }
}

def get_text(lang, key):
    # Fallback to English if lang or key missing
    lang_dict = TEXTS.get(key, {})
    return lang_dict.get(lang, lang_dict.get("en", "Text Error"))

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Build a 2-column keyboard for 20 languages
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
    user_id = query.from_user.id
    
    # Save Language to DB
    update_language(user_id, lang_code)
    
    # Get translated text
    welcome_msg = get_text(lang_code, "set_lang")
    
    # Edit message to confirm
    await query.edit_message_text(text=welcome_msg)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # 1. Get User Language
    user_data = get_user(user_id)
    lang = user_data[1] if user_data else "en"
    
    # 2. Check if text looks like a URL
    if "instagram.com" not in message_text:
        return # Ignore non-links
        
    # 3. Check Subscription
    is_premium = check_premium(user_id)
    
    if not is_premium:
        # Send Invoice for Stars
        title = "Instagram Downloader Premium"
        description = get_text(lang, "pay_wall")
        payload = "Instagram-Premium-30Days"
        currency = "XTR" # Telegram Stars
        price = PREMIUM_PRICE
        prices = [LabeledPrice("1 Month Sub", price)]

        await context.bot.send_invoice(
            chat_id=update.message.chat_id,
            title=title,
            description="Unlock unlimited downloads for 30 days.",
            payload=payload,
            provider_token="", # Empty for Telegram Stars
            currency=currency,
            prices=prices,
        )
        await update.message.reply_html(get_text(lang, "pay_wall"))
        return

    # 4. If Premium, Download Video
    await update.message.reply_text(get_text(lang, "processing"))
    
    # CALL RAPID API
    try:
        # Note: The user provided URL is mapped to the 'Userinfo' param based on the prompt.
        # Usually, this param is encoded.
        url = "https://instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com/"
        querystring = {"Userinfo": message_text} 

        headers = {
            "x-rapidapi-host": RAPID_API_HOST,
            "x-rapidapi-key": RAPID_API_KEY
        }

        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        
        # Logic to extract video URL from response. 
        # Note: Depending on the specific API response structure, this part might need adjustment.
        # I am assuming a generic 'url' or 'media' key field often found in these APIs.
        
        video_url = None
        
        # Simplistic parsing logic (adjust based on actual JSON response of this specific API)
        if isinstance(data, list) and len(data) > 0:
             if 'url' in data[0]: video_url = data[0]['url']
        elif isinstance(data, dict):
             if 'url' in data: video_url = data['url']
             # Sometimes rapidapis return nested lists for posts
        
        if video_url:
            await update.message.reply_video(video_url, caption="Downloaded via Premium Bot 🌟")
        else:
            # Fallback if API response is strictly user info (as indicated by parameter name)
            # but usually these APIs return media list for profile links too.
            await update.message.reply_text(f"API Response received but could not parse video. Raw: {str(data)[:100]}")
            
    except Exception as e:
        logging.error(f"API Error: {e}")
        await update.message.reply_text(get_text(lang, "error"))

# --- PAYMENT HANDLERS ---

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    # Check the payload, is this for our bot?
    if query.invoice_payload != "Instagram-Premium-30Days":
        await query.answer(ok=False, error_message="Something went wrong.")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Update DB
    update_subscription(user_id)
    
    # Get Lang
    user_data = get_user(user_id)
    lang = user_data[1] if user_data else "en"
    
    await update.message.reply_text(get_text(lang, "success"))

# --- MAIN ---

def main():
    # Initialize DB
    init_db()
    
    # Build App
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    
    # Payment Handlers
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Message Handler (Must be last to catch texts)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Run
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
