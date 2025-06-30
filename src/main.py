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

import datetime # For timedelta and timezone
from datetime import datetime as RealDatetimeClass # Alias for type checking
from datetime import timedelta

# Environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_IDS = [int(user_id) for user_id in os.environ.get('AUTHORIZED_USER_IDS', '').split(',') if user_id]
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID')
KEYWORDS = ["#анонс", "#опрос"]

# Templates for messages that link to forwarded polls
POLL_LINK_MESSAGE_TEMPLATES = {
    "#анонс": "Проголосуй <a href=\"{link}\">здесь</a>, если придёшь (ну или хотя бы рассматриваешь такую возможность)",
    "#опрос": "<a href=\"{link}\">Проголосуй тут</a>"
}
# Identifiers to check if a poll's caption (after forwarding) already contains a poll prompt
# This helps decide whether to edit the caption or send a new message.
POLL_CAPTION_IDENTIFIERS = [
    "Проголосуй <a href=", # From #анонс template
    "<a href=",             # From #опрос template (broader)
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

    if message.text:
        log_details["message"]["type"] = "text"
    elif message.poll:
        log_details["message"]["type"] = "poll"
    # ... (other message types can be added here if needed for logging)
    else:
        log_details["message"]["type"] = "other/unknown"
    logger.info(f"Received message: {json.dumps(log_details, ensure_ascii=False, indent=2)}")

    if user.id not in AUTHORIZED_USER_IDS:
        logger.warning(f"User {user.id} is not in AUTHORIZED_USER_IDS. Ignoring message.")
        return
    logger.info(f"User {user.id} is authorized.")

    # CASE 1: User sends a POLL OBJECT to the bot
    if message.poll:
        logger.info(f"Received a poll object from user {user.id}. Applying poll linking logic.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set. Cannot process poll.")
            await message.reply_text("Error: Target channel ID is not configured for polls.")
            return

        # Step A: Forward the user's poll to the target channel
        try:
            logger.info(f"Forwarding poll from user {user.id} (msg_id: {message.message_id}) to channel {TARGET_CHANNEL_ID}...")
            forwarded_poll_message = await context.bot.forward_message(
                chat_id=TARGET_CHANNEL_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"Poll successfully forwarded. New message ID in target channel: {forwarded_poll_message.message_id}")
        except Exception as e:
            logger.error(f"Error forwarding poll to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, there was an error forwarding your poll: {e}")
            return

        # Step B: Age Check for the forwarded poll message
        now = datetime.datetime.now(datetime.timezone.utc)
        forwarded_date = forwarded_poll_message.date
        if not isinstance(forwarded_date, RealDatetimeClass):
            logger.warning(f"Forwarded poll (ID: {forwarded_poll_message.message_id}) has no valid date ({type(forwarded_date)}). Skipping age check and further processing for linking.")
            return

        if (now - forwarded_date) > timedelta(hours=1):
            logger.info(f"Forwarded poll (ID: {forwarded_poll_message.message_id}) is older than 1 hour. No linking message will be added/edited.")
            return

        # Step C: Determine Poll Prompt Text (based on keywords in original poll's caption)
        # Default to "#анонс" style if no specific keyword found in caption
        chosen_keyword_for_template = "#анонс"
        if message.text: # Poll caption is in message.text for python-telegram-bot
            for kw in KEYWORDS: # Check #опрос first due to its specific template
                if kw.lower() in message.text.lower():
                    chosen_keyword_for_template = kw
                    if kw == "#опрос": # #опрос is more specific for template choice here
                        break
            logger.info(f"Using template for keyword '{chosen_keyword_for_template}' based on poll caption.")
        else:
            logger.info(f"No caption in the original poll. Defaulting to '{chosen_keyword_for_template}' template.")

        # Prepare link to the forwarded_poll_message
        target_chat_for_link = TARGET_CHANNEL_ID
        try:
            chat_obj = await context.bot.get_chat(chat_id=TARGET_CHANNEL_ID)
            if chat_obj.username:
                target_chat_for_link = chat_obj.username
            elif isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                target_chat_for_link = TARGET_CHANNEL_ID[4:]
            elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -1000000000000: # check for typical supergroup/channel ID range
                target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]
        except Exception as e:
            logger.warning(f"Could not fetch chat details for {TARGET_CHANNEL_ID} to optimize link: {e}. Using raw ID for link.")
            if isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                target_chat_for_link = TARGET_CHANNEL_ID[4:]
            elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -1000000000000:
                 target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]

        link_to_forwarded_poll = f"https://t.me/{target_chat_for_link}/{forwarded_poll_message.message_id}"
        poll_prompt_text = POLL_LINK_MESSAGE_TEMPLATES[chosen_keyword_for_template].format(link=link_to_forwarded_poll)

        # Step D: Check if forwarded poll's caption already contains a poll prompt
        edit_caption_of_forwarded_poll = False
        # The caption of the forwarded_poll_message is in its '.text' or '.caption' attribute
        # For polls from users, PTB puts question into poll.question, options into poll.options
        # If user sends /poll command, text is caption. If user forwards a poll, caption is kept.
        # Let's check forwarded_poll_message.text (more common for bot-seen captions)
        # and forwarded_poll_message.caption (more robust)
        caption_to_check = forwarded_poll_message.text or forwarded_poll_message.caption
        if caption_to_check:
            for identifier in POLL_CAPTION_IDENTIFIERS:
                if identifier in caption_to_check:
                    edit_caption_of_forwarded_poll = True
                    logger.info(f"Forwarded poll's caption (ID: {forwarded_poll_message.message_id}) contains identifier ('{identifier}'). Will attempt to edit this poll's caption.")
                    break

        if edit_caption_of_forwarded_poll:
            # Step D.1: Edit the caption of the forwarded poll
            try:
                logger.info(f"Attempting to edit caption of forwarded poll ID {forwarded_poll_message.message_id} in {TARGET_CHANNEL_ID}. New caption: {poll_prompt_text}")
                await context.bot.edit_message_caption(
                    chat_id=TARGET_CHANNEL_ID,
                    message_id=forwarded_poll_message.message_id,
                    caption=poll_prompt_text,
                    parse_mode='HTML'
                )
                logger.info(f"Successfully edited caption of poll {forwarded_poll_message.message_id}.")
            except Exception as e:
                logger.error(f"Error editing poll caption for {forwarded_poll_message.message_id}: {e}", exc_info=True)
                await message.reply_text(f"Forwarded your poll, but could not update its caption with the link: {e}")
        else:
            # Step E: Send a new message linking to the forwarded poll
            try:
                logger.info(f"Attempting to send new message linking to poll {forwarded_poll_message.message_id} in {TARGET_CHANNEL_ID}. Text: {poll_prompt_text}")
                await context.bot.send_message(
                    chat_id=TARGET_CHANNEL_ID,
                    text=poll_prompt_text,
                    parse_mode='HTML',
                    reply_to_message_id=forwarded_poll_message.message_id,
                    disable_web_page_preview=True
                )
                logger.info(f"Successfully sent message linking to poll {forwarded_poll_message.message_id}.")
            except Exception as e:
                logger.error(f"Error sending message linking to poll {forwarded_poll_message.message_id}: {e}", exc_info=True)
                await message.reply_text(f"Forwarded your poll, but could not send the linking message: {e}")
        return # Processed poll

    # CASE 2: User sends a TEXT MESSAGE with a keyword
    # This is for standard announcements as per original behavior.
    if message.text:
        found_keyword_in_text = None
        for kw in KEYWORDS:
            if kw.lower() in message.text.lower():
                found_keyword_in_text = kw
                break

        if found_keyword_in_text:
            logger.info(f"Keyword '{found_keyword_in_text}' found in text message from user {user.id}. Reposting text.")
            if not TARGET_CHANNEL_ID:
                logger.error("TARGET_CHANNEL_ID is not set. Cannot repost text announcement.")
                await message.reply_text("Error: Target channel ID is not configured for text announcements.")
                return

            # Determine text to send (e.g., strip keyword or send full)
            # For now, sending full text as per previous baseline.
            text_to_repost = message.text
            # Example: if you want to strip the keyword:
            # text_to_repost = message.text.lower().replace(found_keyword_in_text.lower(), "").strip()

            try:
                logger.info(f"Attempting to send text announcement to channel {TARGET_CHANNEL_ID}...")
                await context.bot.send_message(
                    chat_id=TARGET_CHANNEL_ID,
                    text=text_to_repost
                )
                logger.info(f"Text announcement successfully sent to channel {TARGET_CHANNEL_ID}.")
            except Exception as e:
                logger.error(f"Error sending text announcement to {TARGET_CHANNEL_ID}: {e}", exc_info=True)
                await message.reply_text(f"Sorry, there was an error trying to post the announcement text: {e}")
            return # Processed text keyword

    logger.info(f"Message from user {user.id} is not a poll and does not contain a recognized keyword in text. Ignoring.")

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
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    # Combined handler for text and polls, routing to handle_message
    application.add_handler(MessageHandler(filters.TEXT | filters.POLL & ~filters.COMMAND, handle_message))
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == '__main__':
    main()
