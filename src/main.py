import os
import logging
import json
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
logger = logging.getLogger(__name__)

import datetime
from datetime import datetime as RealDatetimeClass
from datetime import timedelta
import re
import json
from typing import Optional

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_IDS = [int(user_id) for user_id in os.environ.get('AUTHORIZED_USER_IDS', '').split(',') if user_id]
TARGET_CHANNEL_ID = os.environ.get('TARGET_CHANNEL_ID')
KEYWORDS = ["#анонс", "#опрос"]

POLL_LINK_MESSAGE_TEMPLATES = {
    "#анонс": "Проголосуй <a href=\"{link}\">здесь</a>, если придёшь (ну или хотя бы рассматриваешь такую возможность)",
    "#опрос": "<a href=\"{link}\">Проголосуй тут</a>"
}
POLL_CAPTION_IDENTIFIERS = [
    "Проголосуй <a href=",
    "<a href=",
]

BOT_POLL_PROMPT_STARTS = [
    "Проголосуй <a href=",
    "<a href="
]

LAST_ANNOUNCEMENT_KEY = 'last_announcement_details'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"Received /start command from user ID: {user_id}.")
    await update.message.reply_text('Hello! I am ready to monitor messages.')
    logger.info(f"Welcome message sent to user ID: {user_id}.")

async def find_bot_last_message_in_channel(bot: Bot, channel_id: str, max_age_hours: int = 1, search_limit: int = 20) -> Optional[dict]:
    logger.info(f"Searching for bot's last message in channel {channel_id} (search limit: {search_limit} messages, max age: {max_age_hours}h).")
    bot_id = bot.id
    try:
        logger.warning(f"Message fetching part of find_bot_last_message_in_channel is a placeholder. It needs a real implementation.")
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
            except Exception as e:
                logger.error(f"Error posting text announcement for keyword '{found_keyword_in_text}': {e}", exc_info=True)
                await message.reply_text(f"Sorry, error posting your announcement: {e}")
            return

    elif message.poll:
        logger.info(f"Received a poll object (msg_id: {message.message_id}) from user {user.id}. Attempting to edit last announcement.")
        if not TARGET_CHANNEL_ID:
            logger.error("TARGET_CHANNEL_ID is not set for poll prompts.")
            await message.reply_text("Error: Target channel ID is not configured for polls.")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        original_poll_date = message.date
        if not isinstance(original_poll_date, RealDatetimeClass):
            logger.warning(f"Original poll (ID: {message.message_id}) has no valid date ({type(original_poll_date)}). Skipping poll prompt.")
            return
        if (now - original_poll_date) > timedelta(hours=1):
            logger.info(f"Original poll (ID: {message.message_id}) is older than 1 hour. Skipping poll prompt.")
            return

        logger.info(f"Attempting to find bot's last message in channel {TARGET_CHANNEL_ID} to attach poll link.")

        last_bot_message_details = await find_bot_last_message_in_channel(
            bot=context.bot,
            channel_id=TARGET_CHANNEL_ID,
            max_age_hours=1
        )

        if not last_bot_message_details:
            logger.warning(f"Could not find a recent message from the bot (or it was too old) in channel {TARGET_CHANNEL_ID}. Cannot attach poll link.")
            return

        logger.info(f"Found bot's last message: ID {last_bot_message_details['message_id']}, Text: \"{last_bot_message_details['text_content'][:50]}...\"")

        base_announcement_text = last_bot_message_details['text_content']
        target_message_id_to_edit = last_bot_message_details['message_id']

        chosen_keyword_for_template = "#анонс"
        if message.text:
            logger.info(f"Poll has caption: \"{message.text[:100]}...\"")
            for kw in KEYWORDS:
                if kw.lower() in message.text.lower():
                    chosen_keyword_for_template = kw
                    if kw == "#опрос": break
            logger.info(f"Using template for '{chosen_keyword_for_template}' based on poll caption for message {target_message_id_to_edit}.")
        else:
            logger.info(f"No caption in poll. Defaulting to '{chosen_keyword_for_template}' template for message {target_message_id_to_edit}.")

        link_to_original_poll = ""
        if message.chat.username:
            link_to_original_poll = f"https://t.me/{message.chat.username}/{message.message_id}"
        elif str(message.chat_id).startswith("-100"):
            numeric_chat_id = str(message.chat_id)[4:]
            link_to_original_poll = f"https://t.me/c/{numeric_chat_id}/{message.message_id}"
        else:
            logger.warning(f"Poll is from chat ID {message.chat_id} (type: {message.chat.type}), username: {message.chat.username}. Public link generation might be unreliable.")
            if message.chat.type == "private":
                 logger.warning(f"Cannot create a public link for a poll from a private chat with user {user.id}.")
                 await message.reply_text("For polls from private chat, I can't make a public link. Please use a group/channel.")
                 return
            elif str(message.chat_id).startswith("-"):
                 stripped_chat_id = str(message.chat_id).lstrip("-")
                 link_to_original_poll = f"https://t.me/c/{stripped_chat_id}/{message.message_id}"
                 logger.info(f"Attempting /c/ link for non-supergroup private chat: {link_to_original_poll}")
            else:
                 logger.error(f"Cannot determine a shareable link for poll from chat {message.chat_id} (type {message.chat.type}).")
                 await message.reply_text("Cannot create a shareable link for this poll's location.")
                 return

        logger.info(f"Generated poll link: {link_to_original_poll}")

        if not link_to_original_poll:
             logger.error(f"Link generation failed unexpectedly for poll {message.message_id} from chat {message.chat_id}.")
             await message.reply_text("Sorry, I could not generate a link for your poll.")
             return

        new_poll_prompt_segment = POLL_LINK_MESSAGE_TEMPLATES[chosen_keyword_for_template].format(link=link_to_original_poll)
        logger.info(f"New poll prompt segment: \"{new_poll_prompt_segment}\"")

        text_to_edit = base_announcement_text
        cleaned_text = base_announcement_text
        logger.info(f"Original text for edit (before cleaning old prompt): \"{text_to_edit[:150]}...\"")
        for prompt_start_identifier in BOT_POLL_PROMPT_STARTS:
            if prompt_start_identifier in text_to_edit:
                parts = text_to_edit.split("\n\n" + prompt_start_identifier)
                if len(parts) > 1:
                    cleaned_text = parts[0]
                    logger.info(f"Removed old poll prompt part starting with '{prompt_start_identifier}' from message {target_message_id_to_edit}. Cleaned text: \"{cleaned_text[:100]}...\"")
                    break
                elif text_to_edit.startswith(prompt_start_identifier) and chosen_keyword_for_template == "#опрос":
                    cleaned_text = ""
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

        return

    logger.info(f"Message from user {user.id} (update ID: {update.update_id}) did not match keyword criteria or was not a poll. No action taken.")

def main() -> None:
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
    application.add_handler(MessageHandler(filters.TEXT | filters.POLL & ~filters.COMMAND, handle_message))
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == '__main__':
    main()
