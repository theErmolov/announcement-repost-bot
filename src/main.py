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

        # Polls are no longer forwarded. Bot posts a new message linking to the original user's poll.

        # Age Check for the original user's poll message
        now = datetime.datetime.now(datetime.timezone.utc)
        original_poll_date = message.date
        if not isinstance(original_poll_date, RealDatetimeClass):
            logger.warning(f"Original poll (ID: {message.message_id}, from chat: {message.chat_id}) has no valid date ({type(original_poll_date)}). Cannot process for linking.")
            return
        if (now - original_poll_date) > timedelta(hours=1):
            logger.info(f"Original poll (ID: {message.message_id}, from chat: {message.chat_id}) is older than 1 hour. No linking message will be sent.")
            return

        # Determine Poll Prompt Text (based on keywords in original poll's caption)
        chosen_keyword_for_template = "#анонс" # Default
        if message.text: # Poll caption is in message.text
            for kw in KEYWORDS:
                if kw.lower() in message.text.lower():
                    chosen_keyword_for_template = kw
                    if kw == "#опрос": # Prioritize #опрос for its specific template
                        break
            logger.info(f"Using template for keyword '{chosen_keyword_for_template}' based on poll caption: '{message.text[:50]}...'")
        else:
            logger.info(f"No caption in the original poll. Defaulting to '{chosen_keyword_for_template}' template.")

        # Prepare link to the original user's poll message.
        link_to_original_poll = ""
        if message.chat.username: # Public group/channel with username
            link_to_original_poll = f"https://t.me/{message.chat.username}/{message.message_id}"
        elif str(message.chat_id).startswith("-100"): # Public supergroup/channel by ID
            numeric_chat_id = str(message.chat_id)[4:]
            link_to_original_poll = f"https://t.me/c/{numeric_chat_id}/{message.message_id}"
        else: # Private chat with bot, or private group. Direct linking is not reliably public.
              # The bot will inform the user if a public link cannot be made.
            logger.warning(f"Cannot form a reliable public link for poll in chat {message.chat_id} (type: {message.chat.type}). This link may only work for the sender or bot.")
            # For private chats (positive chat_id) or non-supergroups (negative but not -100xxxx)
            # a universally accessible t.me/c/... link isn't possible.
            # We can attempt a more general link for groups, but it's not guaranteed.
            # A simple message.link could be used if available and appropriate, but it's often for the user who received it.
            # Given the constraint, if a public link cannot be formed, we should notify the user.
            if message.chat.type == "private":
                 await message.reply_text("Sorry, I can't create a public link for polls from a private chat. Please send the poll in a group or channel where I am present.")
                 return # Stop processing for this poll
            else: # It's some other kind of group. Try to make a /c/ link if chat_id is negative.
                if str(message.chat_id).startswith("-"):
                    # This is a guess; non-supergroups might not work with /c/
                    stripped_chat_id = str(message.chat_id).lstrip("-")
                    link_to_original_poll = f"https://t.me/c/{stripped_chat_id}/{message.message_id}"
                    logger.info(f"Attempting /c/ link for non-supergroup: {link_to_original_poll}")
                else: # Should not happen for groups, but as a fallback.
                    await message.reply_text("Sorry, I was unable to create a shareable link for your poll from this group.")
                    return


        if not link_to_original_poll: # Should be caught by earlier returns if link is impossible
             logger.error(f"Failed to generate a link for poll message {message.message_id} in chat {message.chat_id}")
             await message.reply_text("Sorry, I could not generate a link for your poll.")
             return

        poll_prompt_text = POLL_LINK_MESSAGE_TEMPLATES[chosen_keyword_for_template].format(link=link_to_original_poll)

        # Always send a new message to TARGET_CHANNEL_ID
        try:
            logger.info(f"Attempting to send new message to channel {TARGET_CHANNEL_ID} linking to original poll (User's msg_id: {message.message_id} in chat {message.chat_id}). Text: {poll_prompt_text}")
            await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=poll_prompt_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"Successfully sent message to {TARGET_CHANNEL_ID} linking to original poll.")
        except Exception as e:
            logger.error(f"Error sending message linking to original poll to channel {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, I could not send the linking message: {e}")
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
            logger.info(f"Keyword '{found_keyword_in_text}' found in text message (ID: {message.message_id}) from user {user.id}.")
            if not TARGET_CHANNEL_ID:
                logger.error("TARGET_CHANNEL_ID is not set. Cannot process text keyword message.")
                await message.reply_text("Error: Target channel ID is not configured for text announcements.")
                return

            # Age Check for the original user's text message
            now = datetime.datetime.now(datetime.timezone.utc)
            original_text_date = message.date
            if not isinstance(original_text_date, RealDatetimeClass):
                logger.warning(f"Original text message (ID: {message.message_id}) has no valid date ({type(original_text_date)}). Cannot process.")
                return
            if (now - original_text_date) > timedelta(hours=1):
                logger.info(f"Original text message (ID: {message.message_id}) is older than 1 hour. Skipping.")
                return

            text_to_repost = message.text # Using full text for now

            try:
                logger.info(f"Attempting to send base text announcement to channel {TARGET_CHANNEL_ID}...")
                bot_announcement_message = await context.bot.send_message(
                    chat_id=TARGET_CHANNEL_ID,
                    text=text_to_repost
                )
                logger.info(f"Base text announcement successfully sent. Bot message ID: {bot_announcement_message.message_id}.")

                # Now, prepare and send the "Проголосуй..." message as a reply
                # Link to the bot_announcement_message
                target_chat_for_link = TARGET_CHANNEL_ID
                try:
                    chat_obj = await context.bot.get_chat(chat_id=TARGET_CHANNEL_ID)
                    if chat_obj.username:
                        target_chat_for_link = chat_obj.username
                    elif isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                        target_chat_for_link = TARGET_CHANNEL_ID[4:]
                    elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -1000000000000:
                        target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]
                except Exception as e:
                    logger.warning(f"Could not fetch chat details for {TARGET_CHANNEL_ID} to optimize link for text announcement reply: {e}. Using raw ID.")
                    if isinstance(TARGET_CHANNEL_ID, str) and TARGET_CHANNEL_ID.startswith("-100"):
                        target_chat_for_link = TARGET_CHANNEL_ID[4:]
                    elif isinstance(TARGET_CHANNEL_ID, int) and TARGET_CHANNEL_ID < -1000000000000:
                        target_chat_for_link = str(TARGET_CHANNEL_ID)[4:]

                link_to_bot_announcement = f"https://t.me/{target_chat_for_link}/{bot_announcement_message.message_id}"

                # Determine prompt based on the original keyword found
                prompt_text_template = POLL_LINK_MESSAGE_TEMPLATES.get(found_keyword_in_text, POLL_LINK_MESSAGE_TEMPLATES["#анонс"]) # Default to #анонс if somehow not found
                reply_prompt_text = prompt_text_template.format(link=link_to_bot_announcement)

                logger.info(f"Attempting to send poll prompt reply to {bot_announcement_message.message_id} in channel {TARGET_CHANNEL_ID}. Text: {reply_prompt_text}")
                await context.bot.send_message(
                    chat_id=TARGET_CHANNEL_ID,
                    text=reply_prompt_text,
                    parse_mode='HTML',
                    reply_to_message_id=bot_announcement_message.message_id,
                    disable_web_page_preview=True
                )
                logger.info(f"Successfully sent poll prompt reply for text announcement.")

            except Exception as e:
                logger.error(f"Error processing text announcement for keyword '{found_keyword_in_text}': {e}", exc_info=True)
                await message.reply_text(f"Sorry, there was an error trying to post your announcement: {e}")
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
