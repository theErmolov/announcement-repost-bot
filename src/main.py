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

import datetime
from datetime import timedelta

# Environment variables (placeholders - these will be set in Lambda)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_IDS = [int(user_id) for user_id in os.environ.get('AUTHORIZED_USER_IDS', '').split(',') if user_id]
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID')
KEYWORDS = ["#анонс", "#опрос"]

MESSAGE_TEMPLATES = {
    "#анонс": "Проголосуй <a href=\"{link}\">здесь</a>, если придёшь (ну или хотя бы рассматриваешь такую возможность)",
    "#опрос": "<a href=\"{link}\">Проголосуй тут</a>"
}
# Identifiers to check if a message in the target channel already looks like one of our poll prompts.
POLL_MESSAGE_IDENTIFIERS = [
    "Проголосуй <a href=", # Corresponds to #анонс template
    "<a href=", # Corresponds to #опрос template, broader match
]


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

    # Check if message is from an authorized user (already done at the top of the function)

    # New logic for keyword-based poll announcements
    found_keyword = None
    if message.text:
        for kw in KEYWORDS:
            if kw.lower() in message.text.lower():
                found_keyword = kw
                break

    if found_keyword:
        logger.info(f"Keyword '{found_keyword}' found in text message (ID: {message.message_id}) from user {user.id}.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot process keyword message.")
            await message.reply_text("Error: Target channel ID is not configured.")
            return

        # Step 1: Forward the user's original message (which contains the keyword) to the target channel.
        # This forwarded message in the target channel is what we will link to or edit.
        try:
            logger.info(f"Forwarding user's message (ID: {message.message_id} from chat {message.chat_id}) to target channel {TARGET_CHANNEL_ID} due to keyword '{found_keyword}'.")
            forwarded_message = await context.bot.forward_message(
                chat_id=TARGET_CHANNEL_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"Original message successfully forwarded to target channel. New message ID in target channel: {forwarded_message.message_id}")
        except Exception as e:
            logger.error(f"Error forwarding original message for keyword '{found_keyword}' to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error forwarding your message: {e}")
            return

        # Step 2: Prepare the link to the forwarded message.
        # Try to use channel username for cleaner links, otherwise use channel ID.
        target_chat_for_link = TARGET_CHANNEL_ID # Fallback
        try:
            chat_obj = await context.bot.get_chat(chat_id=TARGET_CHANNEL_ID)
            if chat_obj.username:
                target_chat_for_link = chat_obj.username
            elif isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                 target_chat_for_link = TARGET_CHANNEL_ID[4:] # Strip "-100" for t.me/c/ format
            elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -100000000000: # For supergroup IDs
                 target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]
        except Exception as e:
            logger.warning(f"Could not fetch chat details for {TARGET_CHANNEL_ID} to optimize link format (using raw ID): {e}")
            # Apply stripping logic even in fallback if applicable
            if isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                 target_chat_for_link = TARGET_CHANNEL_ID[4:]
            elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -100000000000:
                 target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]

        poll_message_link = f"https://t.me/{target_chat_for_link}/{forwarded_message.message_id}"
        text_for_poll_prompt = MESSAGE_TEMPLATES[found_keyword].format(link=poll_message_link)

        # Step 3: Check age of the forwarded message in the target channel.
        # Do nothing further if it's older than 1 hour.
        now = datetime.datetime.now(datetime.timezone.utc)
        message_date = forwarded_message.date
        if not isinstance(message_date, datetime.datetime):
            logger.warning(f"forwarded_message.date (ID: {forwarded_message.message_id}) is not a datetime object: {type(message_date)}. Cannot perform age check reliably.")
        elif (now - message_date) > timedelta(hours=1):
            logger.info(f"The forwarded message (ID: {forwarded_message.message_id} in target channel) is older than 1 hour. No poll prompt will be sent/edited.")
            return

        # Step 4: Determine if we need to edit the forwarded message or send a new one.
        # This is based on whether the forwarded message's text *already* contains poll-like identifiers.
        edit_forwarded_message_instead_of_sending_new = False
        if forwarded_message.text:
            for identifier in POLL_MESSAGE_IDENTIFIERS:
                if identifier in forwarded_message.text:
                    edit_forwarded_message_instead_of_sending_new = True
                    logger.info(f"Forwarded message (ID: {forwarded_message.message_id}) text contains poll identifier ('{identifier}'). Will attempt to edit this message.")
                    break

        if edit_forwarded_message_instead_of_sending_new:
            # Case 2.2: Edit the existing forwarded message in the target channel.
            # The text_for_poll_prompt is already formatted with the correct link to the forwarded_message itself.
            try:
                logger.info(f"Attempting to edit forwarded message ID {forwarded_message.message_id} in channel {TARGET_CHANNEL_ID}. New text: {text_for_poll_prompt}")
                await context.bot.edit_message_text(
                    chat_id=TARGET_CHANNEL_ID,
                    message_id=forwarded_message.message_id,
                    text=text_for_poll_prompt,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info(f"Successfully edited message {forwarded_message.message_id} in channel {TARGET_CHANNEL_ID}.")
            except Exception as e:
                logger.error(f"Error editing message {forwarded_message.message_id} in channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
                await message.reply_text(f"Forwarded your message, but could not edit it to update the poll link: {e}")
        else:
            # Case 2.1: Send a new message to the target channel, replying to the forwarded message.
            try:
                logger.info(f"Attempting to send new poll prompt to channel {TARGET_CHANNEL_ID}, replying to forwarded message {forwarded_message.message_id}. Text: {text_for_poll_prompt}")
                await context.bot.send_message(
                    chat_id=TARGET_CHANNEL_ID,
                    text=text_for_poll_prompt,
                    parse_mode='HTML',
                    reply_to_message_id=forwarded_message.message_id,
                    disable_web_page_preview=True
                )
                logger.info(f"Successfully sent new poll prompt message to channel {TARGET_CHANNEL_ID}.")
            except Exception as e:
                logger.error(f"Error sending new poll prompt message to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
                await message.reply_text(f"Forwarded your message, but could not send the poll link message: {e}")
        return

    # Fallback: If not a keyword message, check if it's a direct poll object from an authorized user.
    if message.poll:
        logger.info(f"Received a direct poll object (no keyword detected in caption/text) from user {user.id}. Forwarding as is.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot forward direct poll.")
            await message.reply_text("Error: Target channel ID is not configured. Cannot repost poll.")
            return
        try:
            await context.bot.forward_message(
                chat_id=TARGET_CHANNEL_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"Direct poll from user {user.id} successfully forwarded to channel {TARGET_CHANNEL_ID}.")
        except Exception as e:
            logger.error(f"Error forwarding direct poll from user {user.id} to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error trying to repost the poll: {e}")
        return

    logger.info(f"No relevant keyword found and not a direct poll. Update ID {update.update_id} from user {user.id} ignored.")


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
