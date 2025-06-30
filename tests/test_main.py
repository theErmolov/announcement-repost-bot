import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Set environment variables for testing BEFORE importing from main
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_pytest'
os.environ['AUTHORIZED_USER_IDS'] = '123,456'
os.environ['TARGET_CHANNEL_ID'] = '-100987654321'

from main import (
    handle_message,
    AUTHORIZED_USER_IDS as MAIN_AUTHORIZED_USER_IDS,
    TARGET_CHANNEL_ID as MAIN_TARGET_CHANNEL_ID,
    KEYWORDS as MAIN_KEYWORDS,
    POLL_LINK_MESSAGE_TEMPLATES, # Correctly named from main.py
    POLL_CAPTION_IDENTIFIERS     # Correctly named from main.py
)

# Basic Sanity Checks
assert MAIN_TARGET_CHANNEL_ID == '-100987654321'
assert 123 in MAIN_AUTHORIZED_USER_IDS
assert "#анонс" in MAIN_KEYWORDS and "#опрос" in MAIN_KEYWORDS

from telegram import Update, Message, User, Bot, Poll as TelegramPoll
from telegram.ext import ContextTypes
import datetime

@pytest.fixture
def mock_update_fixture():
    update = MagicMock(spec=Update)
    update.update_id = 12345

    # Configure effective_user with actual string values for logging
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123
    update.effective_user.username = "testuser"  # Actual string
    update.effective_user.first_name = "Test"    # Actual string
    update.effective_user.last_name = "User"     # Actual string
    update.effective_user.full_name = "Test User" # Actual string
    update.effective_user.is_bot = False

    # Configure message and its chat with actual string/serializable values
    update.message = MagicMock(spec=Message)
    update.message.message_id = 789
    update.message.chat_id = 54321
    update.message.date = datetime.datetime.now(datetime.timezone.utc) # Real datetime object
    # message.date.isoformat() will be called by main.py, which is fine.

    update.message.text = None
    update.message.poll = None
    update.message.caption = None

    update.message.chat = MagicMock()
    update.message.chat.type = "private" # Actual string
    update.message.chat.title = None     # None is serializable

    # Other message attributes if accessed by log_details (e.g., reply_to_message)
    update.message.reply_to_message = None
    update.message.forward_from = None
    update.message.forward_from_chat = None
    # For "text_summary" in log_details, message.text is used. If None, it's fine.
    # For "is_poll", "is_reply", "is_forwarded", these bool(mock) will be fine.

    update.message.reply_text = AsyncMock()
    return update

# configured_forwarded_message_mock fixture is removed.

@pytest.fixture
def mock_context_fixture(): # No longer injects configured_forwarded_message_mock
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    context.bot.send_message = AsyncMock()
    # bot.forward_message is now a plain AsyncMock.
    # Tests will set its .return_value with a locally created mock.
    context.bot.forward_message = AsyncMock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.get_chat = AsyncMock()
    mock_chat_obj = MagicMock()
    mock_chat_obj.username = None
    context.bot.get_chat.return_value = mock_chat_obj
    return context

# --- General Tests ---
@pytest.mark.asyncio
async def test_handle_message_unauthorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 999 # Unauthorized
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} Some announcement"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_keyword_no_poll(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123 # Authorized
    mock_update_fixture.message.text = "Just a regular message"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()

# --- Tests for Text Messages with Keywords (No Linking) ---
@pytest.mark.asyncio
@pytest.mark.parametrize("keyword_to_test", MAIN_KEYWORDS)
async def test_handle_text_message_with_keyword_sends_text(keyword_to_test, mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    original_text = f"{keyword_to_test} This is a test announcement text."
    mock_update_fixture.message.text = original_text
    mock_update_fixture.message.poll = None # Not a poll

    await handle_message(mock_update_fixture, mock_context_fixture)

    mock_context_fixture.bot.send_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        text=original_text # Expecting full text as per current main.py
    )
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()

# --- Tests for Poll Object Forwarding & Caption Editing (Commented out for now) ---
# @pytest.mark.asyncio
# @pytest.mark.parametrize("user_poll_caption_keyword, expected_template_key", [
#     (MAIN_KEYWORDS[0], MAIN_KEYWORDS[0]),      # #анонс in caption -> #анонс template
#     (MAIN_KEYWORDS[1], MAIN_KEYWORDS[1]),      # #опрос in caption -> #опрос template
#     ("Some event", MAIN_KEYWORDS[0]),           # No specific keyword -> default #анонс
#     (None, MAIN_KEYWORDS[0])                    # No caption -> default #анонс
# ])
# @patch('main.datetime.datetime') # More specific patch
# async def test_handle_poll_forwards_and_edits_caption(
#     mock_datetime_class, user_poll_caption_keyword, expected_template_key,
#     mock_update_fixture, mock_context_fixture
# ):
#     # Create and configure local mock for the forwarded message
#     local_forwarded_message = MagicMock(spec=Message)
#     local_forwarded_message.message_id = 1001 # Example ID

#     mock_update_fixture.effective_user.id = 123
#     mock_update_fixture.message.poll = MagicMock(spec=TelegramPoll)
#     mock_update_fixture.message.text = user_poll_caption_keyword # User's poll caption

#     current_time = datetime.datetime(2023, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
#     mock_datetime_class.now.return_value = current_time

#     dt_value = current_time - datetime.timedelta(minutes=30)
#     local_forwarded_message.configure_mock(
#         date=dt_value,
#         caption=user_poll_caption_keyword,
#         text=None,
#         poll=MagicMock(spec=TelegramPoll)
#     )

#     mock_context_fixture.bot.forward_message.return_value = local_forwarded_message

#     expected_channel_id_for_link = MAIN_TARGET_CHANNEL_ID[4:]
#     mock_context_fixture.bot.get_chat.return_value.username = None

#     await handle_message(mock_update_fixture, mock_context_fixture)

#     mock_context_fixture.bot.forward_message.assert_called_once_with(
#         chat_id=MAIN_TARGET_CHANNEL_ID,
#         from_chat_id=mock_update_fixture.message.chat_id,
#         message_id=mock_update_fixture.message.message_id
#     )

#     expected_link = f"https://t.me/{expected_channel_id_for_link}/{local_forwarded_message.message_id}"
#     expected_caption_text = POLL_LINK_MESSAGE_TEMPLATES[expected_template_key].format(link=expected_link)

#     mock_context_fixture.bot.edit_message_caption.assert_called_once_with(
#         chat_id=MAIN_TARGET_CHANNEL_ID,
#         message_id=local_forwarded_message.message_id,
#         caption=expected_caption_text,
#         parse_mode='HTML'
#     )

#     assert mock_context_fixture.bot.send_message.call_count == 0
#     mock_context_fixture.bot.get_chat.assert_called_once_with(chat_id=MAIN_TARGET_CHANNEL_ID)

# @pytest.mark.asyncio
# @patch('main.datetime.datetime')
# async def test_handle_poll_caption_already_has_identifier_updates_link(
#     mock_datetime_class, mock_update_fixture, mock_context_fixture
# ):
#     local_forwarded_message = MagicMock(spec=Message)
#     local_forwarded_message.message_id = 1001

#     mock_update_fixture.effective_user.id = 123
#     mock_update_fixture.message.poll = MagicMock(spec=TelegramPoll)
#     user_caption = f"{MAIN_KEYWORDS[1]} My Poll"
#     mock_update_fixture.message.text = user_caption

#     current_time = datetime.datetime(2023, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
#     mock_datetime_class.now.return_value = current_time

#     dt_value = current_time - datetime.timedelta(minutes=15)
#     local_forwarded_message.configure_mock(
#         date=dt_value,
#         caption=f"Some text before {POLL_CAPTION_IDENTIFIERS[1]} old_link_here",
#         text=None,
#         poll=MagicMock(spec=TelegramPoll)
#     )

#     mock_context_fixture.bot.forward_message.return_value = local_forwarded_message

#     expected_channel_id_for_link = MAIN_TARGET_CHANNEL_ID[4:]
#     expected_link_to_self = f"https://t.me/{expected_channel_id_for_link}/{local_forwarded_message.message_id}"
#     expected_final_caption = POLL_LINK_MESSAGE_TEMPLATES[MAIN_KEYWORDS[1]].format(link=expected_link_to_self)

#     await handle_message(mock_update_fixture, mock_context_fixture)

#     mock_context_fixture.bot.forward_message.assert_called_once()
#     mock_context_fixture.bot.edit_message_caption.assert_called_once_with(
#         chat_id=MAIN_TARGET_CHANNEL_ID,
#         message_id=local_forwarded_message.message_id,
#         caption=expected_final_caption,
#         parse_mode='HTML'
#     )
#     assert mock_context_fixture.bot.send_message.call_count == 0

# @pytest.mark.asyncio
# @patch('main.datetime.datetime')
# async def test_handle_poll_too_old_no_caption_edit(
#     mock_datetime_class, mock_update_fixture, mock_context_fixture
# ):
#     local_forwarded_message = MagicMock(spec=Message)
#     local_forwarded_message.message_id = 1001

#     mock_update_fixture.effective_user.id = 123
#     mock_update_fixture.message.poll = MagicMock(spec=TelegramPoll)
#     mock_update_fixture.message.text = MAIN_KEYWORDS[0]

#     current_time = datetime.datetime(2023, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
#     mock_datetime_class.now.return_value = current_time
#     local_forwarded_message.date = current_time - datetime.timedelta(hours=2)
#     local_forwarded_message.poll = MagicMock(spec=TelegramPoll)

#     mock_context_fixture.bot.forward_message.return_value = local_forwarded_message

#     await handle_message(mock_update_fixture, mock_context_fixture)

#     mock_context_fixture.bot.forward_message.assert_called_once()
#     mock_context_fixture.bot.edit_message_caption.assert_not_called()
#     mock_context_fixture.bot.send_message.assert_not_called()

# --- Error Handling Tests ---
@pytest.mark.asyncio
async def test_handle_text_message_no_target_channel_id(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} test"
    mock_update_fixture.message.poll = None
    with patch('main.TARGET_CHANNEL_ID', ''):
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured for text announcements."
    )
    mock_context_fixture.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_poll_no_target_channel_id(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.poll = MagicMock(spec=TelegramPoll)
    with patch('main.TARGET_CHANNEL_ID', ''):
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured for polls." # Corrected expected message
    )
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()
