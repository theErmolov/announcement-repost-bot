import os
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging for when running main.py directly
# Lambda will have its own logging configuration.
if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
logger = logging.getLogger(__name__)

# Environment variables (placeholders - these will be set in Lambda)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_IDS = [int(user_id) for user_id in os.environ.get('AUTHORIZED_USER_IDS', '').split(',') if user_id]
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID')
KEYWORD = "#анонс"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user_id = update.effective_user.id
    logger.info(f"Received /start command from user ID: {user_id}.")
    await update.message.reply_text('Hello! I am ready to monitor messages.')
    logger.info(f"Welcome message sent to user ID: {user_id}.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, checks for keyword and authorized user, then reposts."""
    logger.info(f"Entering handle_message for update ID: {update.update_id}")
    message = update.message
    user = update.effective_user

    if not message or not user:
        logger.warning("Received an update without a message or user.")
        return

    # Log basic message info
    logger.info(f"Received message from user ID: {user.id}, username: {user.username}, text: {message.text}")

    # Check if message is from an authorized user
    if user.id not in AUTHORIZED_USER_IDS:
        logger.warning(f"User {user.id} is not in AUTHORIZED_USER_IDS. Ignoring message.")
        return
    logger.info(f"User {user.id} is authorized.")

    # Check if the message text contains the keyword
    if message.text and KEYWORD.lower() in message.text.lower():
        logger.info(f"Keyword '{KEYWORD}' found in message from user {user.id}.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot repost.")
            await message.reply_text("Error: Target channel ID is not configured. Cannot repost.")
            return
        logger.info(f"Target channel ID {TARGET_CHANNEL_ID} is configured.")

        try:
            logger.info(f"Attempting to send message text from user {user.id} to channel {TARGET_CHANNEL_ID}...")
            # Send the message text as a new message from the bot
            await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=message.text  # Use the text from the original message
            )
            logger.info(f"Message text from user {user.id} successfully sent to channel {TARGET_CHANNEL_ID}.")
            # Optionally, send a confirmation to the user (can be noisy)
            # await message.reply_text("Announcement text posted!")
        except Exception as e:
            logger.error(f"Error sending message text from user {user.id} to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error trying to post the announcement text: {e}")
    else:
        logger.info(f"Keyword '{KEYWORD}' not found in message from user {user.id} or message text is empty. Ignoring.")


def main() -> None:
    """Starts the bot (for local testing - Lambda will use a different entry point)."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    if not AUTHORIZED_USER_IDS:
        logger.warning("AUTHORIZED_USER_IDS environment variable not set or empty. No messages will be processed based on user.")
    if not TARGET_CHANNEL_ID:
        logger.warning("TARGET_CHANNEL_ID environment variable not set. Reposting will fail.")

    logger.info("Starting bot...")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == '__main__':
    main()
