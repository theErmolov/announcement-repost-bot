import os
import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
FORWARD_CHAT_ID = os.environ.get('FORWARD_CHAT_ID')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"Received /start command from user ID: {user_id}.")
    await update.message.reply_text('Hello! I will now forward all messages to the designated chat.')
    logger.info(f"Welcome message sent to user ID: {user_id}.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Entering handle_message for update ID: {update.update_id}")
    message = update.message
    user = update.effective_user

    if not message or not user:
        logger.warning("Received an update without a message or user.")
        return

    if not FORWARD_CHAT_ID:
        logger.error("FORWARD_CHAT_ID is not set. Cannot forward message.")
        return

    if str(message.chat_id) == str(FORWARD_CHAT_ID):
        logger.info(f"Message {message.message_id} from chat {message.chat_id} is from the forward chat. Not forwarding.")
        return

    try:
        logger.info(f"Forwarding message {message.message_id} from user {user.id} to chat {FORWARD_CHAT_ID}.")
        await context.bot.forward_message(chat_id=FORWARD_CHAT_ID, from_chat_id=message.chat_id, message_id=message.message_id)
        logger.info(f"Successfully forwarded message {message.message_id}.")
    except Exception as e:
        logger.error(f"Error forwarding message: {e}", exc_info=True)
        # Optionally, notify the original user of the failure
        # await message.reply_text(f"Sorry, there was an error forwarding your message: {e}")

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    if not FORWARD_CHAT_ID:
        logger.warning("FORWARD_CHAT_ID environment variable not set. Forwarding will fail.")

    logger.info("Starting bot...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == '__main__':
    main()
