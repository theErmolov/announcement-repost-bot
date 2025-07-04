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
import re # For potential string manipulation
import json # For logging structured data

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
POLL_CAPTION_IDENTIFIERS = [ # Not currently used, BOT_POLL_PROMPT_STARTS is used instead
    "Проголосуй <a href=",
    "<a href=",
]

# Helper strings for identifying bot's own poll prompts
BOT_POLL_PROMPT_STARTS = [
    "Проголосуй <a href=",
    "<a href=" # For the #опрос template specifically
]

# For simplicity with user_data, let's define a key
LAST_ANNOUNCEMENT_KEY = 'last_announcement_details'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user_id = update.effective_user.id
    logger.info(f"Received /start command from user ID: {user_id}.")
    await update.message.reply_text('Hello! I am ready to monitor messages.')
    logger.info(f"Welcome message sent to user ID: {user_id}.")

# Helper strings for identifying bot's own poll prompts
BOT_POLL_PROMPT_STARTS = [
    "Проголосуй <a href=",
    "<a href=" # For the #опрос template specifically
]
# More specific identifiers for the start of the link part of templates
# This helps in reliably finding and replacing only the bot's link prompt part
# Example: "Проголосуй <a href=\"{link}\">здесь</a>" -> look for "\n\nПроголосуй <a href="
# Example: "<a href=\"{link}\">Проголосуй тут</a>" -> look for "\n\n<a href="
# We will simplify: if the message text contains any known prompt start, we replace the whole message.
# A more robust way is to store the base announcement text separately from the poll prompt.

# For simplicity with user_data, let's define a key
LAST_ANNOUNCEMENT_KEY = 'last_announcement_details'

# ... (async def start is unchanged) ...

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    else:
        log_details["message"]["type"] = "other/unknown"
    logger.info(f"Received message: {json.dumps(log_details, ensure_ascii=False, indent=2)}")

    if user.id not in AUTHORIZED_USER_IDS:
        logger.warning(f"User {user.id} is not in AUTHORIZED_USER_IDS. Ignoring message.")
        return
    logger.info(f"User {user.id} is authorized.")

    # CASE 1: User sends a TEXT MESSAGE with a keyword (and it's not a poll)
    if message.text and not message.poll:
        found_keyword_in_text = None
        for kw in KEYWORDS:
            if kw.lower() in message.text.lower():
                found_keyword_in_text = kw
                break

        if found_keyword_in_text:
            logger.info(f"Keyword '{found_keyword_in_text}' found in text message (ID: {message.message_id}) from user {user.id}.")
            if not TARGET_CHANNEL_ID:
                logger.error("TARGET_CHANNEL_ID is not set for text announcements.")
                await message.reply_text("Error: Target channel ID is not configured.")
                return

            text_to_repost = message.text
            try:
                logger.info(f"Posting text announcement to {TARGET_CHANNEL_ID}: \"{text_to_repost[:100]}...\"")
                posted_announcement = await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=text_to_repost)
                logger.info(f"Successfully posted text announcement with ID {posted_announcement.message_id}.")
                # Store details of this announcement for potential poll attachment
                context.user_data[LAST_ANNOUNCEMENT_KEY] = {
                    'message_id': posted_announcement.message_id,
                    'text_content': posted_announcement.text, # Store the actual text posted
                    'timestamp': datetime.datetime.now(datetime.timezone.utc)
                }
                logger.info(f"Stored announcement details for user {user.id}, message ID {posted_announcement.message_id}")
            except Exception as e:
                logger.error(f"Error posting text announcement for keyword '{found_keyword_in_text}': {e}", exc_info=True)
                await message.reply_text(f"Sorry, error posting your announcement: {e}")
            return

    # CASE 2: User sends a POLL OBJECT to the bot
    elif message.poll:
        logger.info(f"Received a poll object (msg_id: {message.message_id}) from user {user.id}. Attempting to edit last announcement.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set for poll prompts.")
            await message.reply_text("Error: Target channel ID is not configured for polls.")
            return

        # Age Check for the original user's poll message
        now = datetime.datetime.now(datetime.timezone.utc)
        original_poll_date = message.date
        if not isinstance(original_poll_date, RealDatetimeClass):
            logger.warning(f"Original poll (ID: {message.message_id}) has no valid date ({type(original_poll_date)}). Skipping poll prompt.")
            return
        if (now - original_poll_date) > timedelta(hours=1):
            logger.info(f"Original poll (ID: {message.message_id}) is older than 1 hour. Skipping poll prompt.")
            return

        # Retrieve last announcement details from user_data
        last_announcement = context.user_data.get(LAST_ANNOUNCEMENT_KEY)

        if not last_announcement:
            logger.info(f"No last announcement found in user_data for user {user.id} to attach poll link to.")
            # As per "shouldn't post a new message", we do nothing if no base message.
            # Optionally, inform user: await message.reply_text("Please send a text announcement first to attach a poll to.")
            return

        # Check recency of the stored announcement (e.g., within last 10 minutes to be considered "active")
        # Also check if the announcement message itself in the channel is not too old (e.g. < 1 hour from its post time)
        # For simplicity, we'll use the timestamp of when we stored it.
        time_since_announcement_stored = now - last_announcement['timestamp']
        if time_since_announcement_stored > timedelta(minutes=10): # Configurable: how long is an announcement "active" for poll attachment?
            logger.info(f"Last announcement (ID: {last_announcement['message_id']}) was stored more than 10 minutes ago. Not attaching poll link.")
            # Also clear it so it's not used next time for an even older poll.
            context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None)
            return

        # Check if the actual announcement message in channel is too old (requires fetching it - complex)
        # For now, we rely on the recency of user_data storage. A more robust check would be needed
        # if the bot could have been restarted or if user_data is not perfectly reliable for message age.
        # The problem description also said "keep this link actual within an hour" referring to the user's poll.

        base_announcement_text = last_announcement.get('text_content', "")
        target_message_id_to_edit = last_announcement['message_id']

        # Determine Poll Prompt Text based on keywords in original poll's caption
        chosen_keyword_for_template = "#анонс" # Default
        if message.text: # Poll caption
            for kw in KEYWORDS:
                if kw.lower() in message.text.lower():
                    chosen_keyword_for_template = kw
                    if kw == "#опрос": break
            logger.info(f"Using template for '{chosen_keyword_for_template}' based on poll caption for message {target_message_id_to_edit}.")
        else:
            logger.info(f"No caption in poll. Defaulting to '{chosen_keyword_for_template}' template for message {target_message_id_to_edit}.")

        # Prepare link to the original user's poll message
        link_to_original_poll = ""
        # (Link generation logic as before - ensuring it's robust)
        if message.chat.username:
            link_to_original_poll = f"https://t.me/{message.chat.username}/{message.message_id}"
        elif str(message.chat_id).startswith("-100"):
            numeric_chat_id = str(message.chat_id)[4:]
            link_to_original_poll = f"https://t.me/c/{numeric_chat_id}/{message.message_id}"
        else:
            logger.warning(f"Poll from chat {message.chat_id} (type: {message.chat.type}). Public link may not be reliable.")
            if message.chat.type == "private":
                 await message.reply_text("For polls from private chat, I can't make a public link. Please use a group/channel.")
                 context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None) # Clear context as it can't be used
                 return
            elif str(message.chat_id).startswith("-"):
                 stripped_chat_id = str(message.chat_id).lstrip("-")
                 link_to_original_poll = f"https://t.me/c/{stripped_chat_id}/{message.message_id}"
                 logger.info(f"Attempting /c/ link for non-supergroup: {link_to_original_poll}")
            else:
                 await message.reply_text("Cannot create a shareable link for this poll's location.")
                 context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None)
                 return

        if not link_to_original_poll:
             logger.error(f"Link generation failed for poll {message.message_id} from chat {message.chat_id}.")
             await message.reply_text("Sorry, I could not generate a link for your poll.")
             context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None)
             return

        new_poll_prompt_segment = POLL_LINK_MESSAGE_TEMPLATES[chosen_keyword_for_template].format(link=link_to_original_poll)

        # Logic to remove old poll prompt and append new one
        text_to_edit = base_announcement_text
        # Try to find if an old prompt exists and remove it.
        # This simple search might need to be more robust if text structure varies.
        cleaned_text = base_announcement_text
        for prompt_start_identifier in BOT_POLL_PROMPT_STARTS:
            if prompt_start_identifier in text_to_edit:
                # Find the start of "\n\n" before the prompt start
                # This is a heuristic to remove the previous prompt section
                # A more robust way would be specific regex for each template or clear delimiters.
                # For now, look for common patterns of how it might have been appended.
                # This assumes the poll prompt was always appended with "\n\n".
                parts = text_to_edit.split("\n\n" + prompt_start_identifier)
                if len(parts) > 1: # Found and successfully split
                    cleaned_text = parts[0] # Take text before the old prompt
                    logger.info(f"Removed old poll prompt part starting with '{prompt_start_identifier}' from message {target_message_id_to_edit}.")
                    break
                # Fallback for #опрос template which might start directly with <a href=
                elif text_to_edit.startswith(prompt_start_identifier) and chosen_keyword_for_template == "#опрос":
                    cleaned_text = "" # If the whole message was the #опрос prompt
                    logger.info(f"Message {target_message_id_to_edit} seems to be an old #опрос prompt. Replacing.")
                    break


        final_text = cleaned_text.strip() + "\n\n" + new_poll_prompt_segment

        try:
            logger.info(f"Attempting to edit message {target_message_id_to_edit} in {TARGET_CHANNEL_ID}. New text: {final_text[:150]}...")
            await context.bot.edit_message_text(
                chat_id=TARGET_CHANNEL_ID,
                message_id=target_message_id_to_edit,
                text=final_text,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"Successfully edited message {target_message_id_to_edit} with new poll prompt.")
        except Exception as e:
            logger.error(f"Error editing message {target_message_id_to_edit} in {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, I could not update the announcement with the poll link: {e}")

        # Clear the last announcement from context after using it
        context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None)
        return

    logger.info(f"Message from user {user.id} did not match keyword criteria or was not a poll. Ignoring.")

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
