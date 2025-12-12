import logging
import os
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from groq import Groq
from flask import Flask

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# Load keys from Environment Variables (Set these in Render Dashboard later)
TELEGRAM_BOT_TOKEN = os.getenv("8561330173:AAGOtGKX63tsy7-FyGyPoZSGuscQd8M3hlo")
GROQ_API_KEY = os.getenv("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")
GROQ_MODEL = "llama3-8b-8192"

# -----------------------------------------------------------------------------
# FLASK SERVER (To keep Render happy)
# -----------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!"

def run_flask():
    # Render sets the PORT environment variable. Default to 10000 if not found.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# -----------------------------------------------------------------------------
# BOT LOGIC
# -----------------------------------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Check if keys are present
if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("Missing API Keys. Please set TELEGRAM_BOT_TOKEN and GROQ_API_KEY in environment variables.")

groq_client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am an AI chatbot on Render. Send me a message!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_text}
            ],
            model=GROQ_MODEL,
        )
        ai_response = chat_completion.choices[0].message.content
        await update.message.reply_text(ai_response)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("Sorry, I encountered an error.")

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    # 1. Start the Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # 2. Start the Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

    application.add_handler(start_handler)
    application.add_handler(message_handler)

    print("Bot is polling...")
    application.run_polling()
