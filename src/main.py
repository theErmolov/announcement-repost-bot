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
from typing import Optional # Added for Python 3.9 compatibility

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

# Note: The duplicate definitions of BOT_POLL_PROMPT_STARTS and LAST_ANNOUNCEMENT_KEY
# that were here have been removed. Their primary definitions are at the top of the file.

async def find_bot_last_message_in_channel(bot: Bot, channel_id: str, max_age_hours: int = 1, search_limit: int = 20) -> Optional[dict]:
    """
    Tries to find the last message posted by the bot itself in the specified channel.

    Args:
        bot: The telegram.Bot instance.
        channel_id: The ID of the target channel.
        max_age_hours: Maximum age of the message in hours.
        search_limit: How many recent messages to search through.

    Returns:
        A dictionary with 'message_id' and 'text_content' if found, else None.
    """
    logger.info(f"Searching for bot's last message in channel {channel_id} (search limit: {search_limit} messages, max age: {max_age_hours}h).")
    bot_id = bot.id
    try:
        # IMPORTANT: bot.get_chat_messages is NOT a standard method in python-telegram-bot.
        # This is a conceptual placeholder for whatever method is used to fetch recent channel messages.
        # This might require the bot to be an admin and use a more complex search or specific library features
        # if available, or the user might have a specific way to do this.
        # A common approach for bots if not admin is to process 'channel_post' updates as they arrive,
        # but this function attempts an on-demand fetch as per user suggestion.
        #
        # If a direct method like this isn't available, this function would need significant changes
        # or rely on the bot having administrator privileges to search messages effectively.
        # For example, one might need to use a raw API call if the library doesn't wrap it.
        #
        # messages = await bot.get_chat_messages(chat_id=channel_id, limit=search_limit, offset_id=0, offset_date=0, etc...)
        # ^^^ THIS IS PSEUDOCODE for fetching messages ^^^

        # For the purpose of this exercise, and without a concrete API call that's guaranteed to work
        # for all bot permission levels, this function will currently return None.
        # The user will need to replace the message fetching part with a working solution
        # based on their bot's capabilities and the `python-telegram-bot` version/extensions they might use.

        logger.warning(f"Message fetching part of find_bot_last_message_in_channel is a placeholder. It needs a real implementation.")
        # Simulate fetching - replace this with actual API call
        # Example of what the loop would do if `channel_messages` was populated:
        # channel_messages = [] # Actual fetched messages would go here
        # for msg in reversed(channel_messages): # Assuming messages are newest first if limit applied, or sort them
        #    if msg.from_user and msg.from_user.id == bot_id:
        #        message_age = datetime.datetime.now(datetime.timezone.utc) - msg.date
        #        if message_age <= timedelta(hours=max_age_hours):
        #            logger.info(f"Found bot's message (ID: {msg.message_id}, Age: {message_age}) within {max_age_hours}h.")
        #            return {'message_id': msg.message_id, 'text_content': msg.text}
        #        else:
        #            logger.info(f"Found bot's message (ID: {msg.message_id}), but it's too old (Age: {message_age}).")
        #            return None # Found our message, but it's too old. Stop searching.
        #    elif msg.sender_chat and msg.sender_chat.id == int(channel_id): # For anonymous admin bot posts
        #        # This case is harder as sender_chat.id is the channel_id if bot posts as channel
        #        # We might need to check content or rely on it being the only recent message
        #        pass

        # Returning None as placeholder behavior
        return None

    except Exception as e:
        logger.error(f"Error trying to find bot's last message in channel {channel_id}: {e}", exc_info=True)
        return None


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
                # No longer storing announcement details in user_data for this flow
                # context.user_data[LAST_ANNOUNCEMENT_KEY] = announcement_details_to_store
                # logger.info(f"Stored announcement details in user_data for user {user.id}, key '{LAST_ANNOUNCEMENT_KEY}': {json.dumps(announcement_details_to_store, default=str)}")
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

        # New logic: Find the bot's last message in the target channel
        logger.info(f"Attempting to find bot's last message in channel {TARGET_CHANNEL_ID} to attach poll link.")

        last_bot_message_details = await find_bot_last_message_in_channel(
            bot=context.bot,
            channel_id=TARGET_CHANNEL_ID,
            max_age_hours=1  # As per user's requirement
        )

        if not last_bot_message_details:
            logger.warning(f"Could not find a recent message from the bot (or it was too old) in channel {TARGET_CHANNEL_ID}. Cannot attach poll link.")
            # Optionally, inform user: await message.reply_text("I couldn't find my last announcement to attach the poll to.")
            return

        logger.info(f"Found bot's last message: ID {last_bot_message_details['message_id']}, Text: \"{last_bot_message_details['text_content'][:50]}...\"")

        base_announcement_text = last_bot_message_details['text_content']
        target_message_id_to_edit = last_bot_message_details['message_id']

        # Determine Poll Prompt Text based on keywords in original poll's caption
        chosen_keyword_for_template = "#анонс" # Default
        if message.text: # Poll caption
            logger.info(f"Poll has caption: \"{message.text[:100]}...\"")
            for kw in KEYWORDS:
                if kw.lower() in message.text.lower():
                    chosen_keyword_for_template = kw
                    if kw == "#опрос": break
            logger.info(f"Using template for '{chosen_keyword_for_template}' based on poll caption for message {target_message_id_to_edit}.")
        else:
            logger.info(f"No caption in poll. Defaulting to '{chosen_keyword_for_template}' template for message {target_message_id_to_edit}.")

        # Prepare link to the original user's poll message
        link_to_original_poll = ""
        if message.chat.username:
            link_to_original_poll = f"https://t.me/{message.chat.username}/{message.message_id}"
        elif str(message.chat_id).startswith("-100"):
            numeric_chat_id = str(message.chat_id)[4:] # Strip -100 prefix
            link_to_original_poll = f"https://t.me/c/{numeric_chat_id}/{message.message_id}"
        else: # Attempt for other private/group chats if possible, log warning
            logger.warning(f"Poll is from chat ID {message.chat_id} (type: {message.chat.type}), username: {message.chat.username}. Public link generation might be unreliable.")
            if message.chat.type == "private":
                 logger.warning(f"Cannot create a public link for a poll from a private chat with user {user.id}.")
                 await message.reply_text("For polls from private chat, I can't make a public link. Please use a group/channel.")
                 # No user_data to pop here anymore
                 return
            elif str(message.chat_id).startswith("-"): # Non-supergroup, e.g. -12345
                 stripped_chat_id = str(message.chat_id).lstrip("-")
                 link_to_original_poll = f"https://t.me/c/{stripped_chat_id}/{message.message_id}"
                 logger.info(f"Attempting /c/ link for non-supergroup private chat: {link_to_original_poll}")
            else: # Other cases, like bot's own chat if it's not a group/channel
                 logger.error(f"Cannot determine a shareable link for poll from chat {message.chat_id} (type {message.chat.type}).")
                 await message.reply_text("Cannot create a shareable link for this poll's location.")
                 # context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None) # No longer using user_data for this
                 # logger.info(f"Popped '{LAST_ANNOUNCEMENT_KEY}' from user_data as poll link cannot be generated.") # No longer using user_data for this
                 return

        logger.info(f"Generated poll link: {link_to_original_poll}")

        if not link_to_original_poll: # Should be caught by earlier returns, but as a safeguard
             logger.error(f"Link generation failed unexpectedly for poll {message.message_id} from chat {message.chat_id}.")
             await message.reply_text("Sorry, I could not generate a link for your poll.")
             # context.user_data.pop(LAST_ANNOUNCEMENT_KEY, None) # No longer using user_data for this
             # logger.info(f"Popped '{LAST_ANNOUNCEMENT_KEY}' from user_data due to link generation failure.") # No longer using user_data for this
             return

        new_poll_prompt_segment = POLL_LINK_MESSAGE_TEMPLATES[chosen_keyword_for_template].format(link=link_to_original_poll)
        logger.info(f"New poll prompt segment: \"{new_poll_prompt_segment}\"")

        # Logic to remove old poll prompt and append new one
        text_to_edit = base_announcement_text
        cleaned_text = base_announcement_text
        # Try to find if an old prompt exists and remove it.
        # This simple search might need to be more robust if text structure varies.
        logger.info(f"Original text for edit (before cleaning old prompt): \"{text_to_edit[:150]}...\"")
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
                    logger.info(f"Removed old poll prompt part starting with '{prompt_start_identifier}' from message {target_message_id_to_edit}. Cleaned text: \"{cleaned_text[:100]}...\"")
                    break
                # Fallback for #опрос template which might start directly with <a href=
                elif text_to_edit.startswith(prompt_start_identifier) and chosen_keyword_for_template == "#опрос":
                    cleaned_text = "" # If the whole message was the #опрос prompt
                    logger.info(f"Message {target_message_id_to_edit} seems to be an old #опрос prompt. Replacing with new. Cleaned text is now empty.")
                    break

        if cleaned_text == base_announcement_text:
            logger.info("No existing poll prompt found to remove from base announcement text.")


        final_text = cleaned_text.strip() + "\n\n" + new_poll_prompt_segment
        logger.info(f"Final text for edit: \"{final_text[:200]}...\"")

        edit_params = {
            "chat_id": TARGET_CHANNEL_ID,
            "message_id": target_message_id_to_edit,
            "text": final_text,
            "parse_mode": 'HTML',
            "disable_web_page_preview": True
        }
        logger.info(f"Attempting to edit message with params: {json.dumps(edit_params, default=str)}")

        try:
            await context.bot.edit_message_text(**edit_params)
            logger.info(f"Successfully edited message {target_message_id_to_edit} in chat {TARGET_CHANNEL_ID} with new poll prompt.")
        except Exception as e:
            logger.error(f"Error editing message {target_message_id_to_edit} in chat {TARGET_CHANNEL_ID}: {e}", exc_info=True)
            await message.reply_text(f"Sorry, I could not update the announcement with the poll link: {e}")

        # No user_data to clear related to LAST_ANNOUNCEMENT_KEY anymore
        return

    logger.info(f"Message from user {user.id} (update ID: {update.update_id}) did not match keyword criteria or was not a poll. No action taken.")

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
