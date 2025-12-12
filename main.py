import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = "8561330173:AAGOtGKX63tsy7-FyGyPoZSGuscQd8M3hlo"
GROQ_API_KEY = "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"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.message.chat_id

    await update.message.reply_chat_action("typing")

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {"role": "user", "content": user_text}
                ]
            }
        )

        ai_msg = response.json()["choices"][0]["message"]["content"]
        await update.message.reply_text(ai_msg)

    except:
        await update.message.reply_text("❌ Error: AI could not reply.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot Running...")
    app.run_polling()
