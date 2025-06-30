import os
import logging
import json
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
    # logger.info(f"Received message from user ID: {user.id}, username: {user.username}, text: {message.text}")

    log_details = {
        "update_id": update.update_id,
        "user": {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "is_bot": user.is_bot,
        },
        "message": {
            "id": message.message_id,
            "date": message.date.isoformat() if message.date else None,
            "chat_id": message.chat_id,
            "chat_type": message.chat.type if message.chat else None,
            "chat_title": message.chat.title if message.chat and message.chat.title else None,
            "text_summary": (message.text[:75] + '...' if message.text and len(message.text) > 75 else message.text) if message.text else None,
            "is_poll": bool(message.poll),
            "is_reply": bool(message.reply_to_message),
            "is_forwarded": bool(message.forward_from or message.forward_from_chat),
        }
    }

    # Determine message type
    if message.text:
        log_details["message"]["type"] = "text"
    elif message.poll:
        log_details["message"]["type"] = "poll"
    elif message.photo:
        log_details["message"]["type"] = "photo"
    elif message.video:
        log_details["message"]["type"] = "video"
    elif message.document:
        log_details["message"]["type"] = "document"
    elif message.audio:
        log_details["message"]["type"] = "audio"
    elif message.voice:
        log_details["message"]["type"] = "voice"
    elif message.sticker:
        log_details["message"]["type"] = "sticker"
    elif message.contact:
        log_details["message"]["type"] = "contact"
    elif message.location:
        log_details["message"]["type"] = "location"
    elif message.venue:
        log_details["message"]["type"] = "venue"
    else:
        log_details["message"]["type"] = "other/unknown"

    logger.info(f"Received message: {json.dumps(log_details, ensure_ascii=False, indent=2)}")

    # Check if message is from an authorized user
    if user.id not in AUTHORIZED_USER_IDS:
        logger.warning(f"User {user.id} is not in AUTHORIZED_USER_IDS. Ignoring message.")
        return
    logger.info(f"User {user.id} is authorized.")

    # Check if the message is a poll from an authorized user
    if message.poll:
        logger.info(f"Received a poll from user {user.id}.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot repost poll.")
            await message.reply_text("Error: Target channel ID is not configured. Cannot repost poll.")
            return
        logger.info(f"Target channel ID {TARGET_CHANNEL_ID} is configured for poll repost.")
        try:
            logger.info(f"Attempting to forward poll from user {user.id} to channel {TARGET_CHANNEL_ID}...")
            # Forward the poll as is
            await context.bot.forward_message(
                chat_id=TARGET_CHANNEL_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"Poll from user {user.id} successfully forwarded to channel {TARGET_CHANNEL_ID}.")
            # await message.reply_text("Poll reposted!") # Optional confirmation
        except Exception as e:
            logger.error(f"Error forwarding poll from user {user.id} to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error trying to repost the poll: {e}")
        return # Stop further processing if it's a poll from an authorized user

    # Check if the message text contains the keyword for text announcements
    if message.text and KEYWORD.lower() in message.text.lower():
        logger.info(f"Keyword '{KEYWORD}' found in text message from user {user.id}.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot repost text announcement.")
            await message.reply_text("Error: Target channel ID is not configured. Cannot repost text announcement.")
            return
        logger.info(f"Target channel ID {TARGET_CHANNEL_ID} is configured for text announcement.")

        try:
            logger.info(f"Attempting to send text announcement from user {user.id} to channel {TARGET_CHANNEL_ID}...")
            # Send the message text as a new message from the bot
            await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=message.text  # Use the text from the original message
            )
            logger.info(f"Text announcement from user {user.id} successfully sent to channel {TARGET_CHANNEL_ID}.")
            # await message.reply_text("Announcement text posted!") # Optional confirmation
        except Exception as e:
            logger.error(f"Error sending text announcement from user {user.id} to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error trying to post the announcement text: {e}")
    else:
        logger.info(f"Neither a poll from authorized user nor keyword '{KEYWORD}' found in message from user {user.id}. Or message text is empty. Ignoring.")


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
