import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_pytest'
os.environ['AUTHORIZED_USER_IDS'] = '123,456'
os.environ['TARGET_CHANNEL_ID'] = '-100987654321'

from main import (
    handle_message,
    AUTHORIZED_USER_IDS as MAIN_AUTHORIZED_USER_IDS,
    TARGET_CHANNEL_ID as MAIN_TARGET_CHANNEL_ID,
    KEYWORDS as MAIN_KEYWORDS,
    POLL_LINK_MESSAGE_TEMPLATES,
    POLL_CAPTION_IDENTIFIERS
)

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

    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.full_name = "Test User"
    update.effective_user.is_bot = False

    update.message = MagicMock(spec=Message)
    update.message.message_id = 789
    update.message.chat_id = 54321
    update.message.date = datetime.datetime.now(datetime.timezone.utc)

    update.message.text = None
    update.message.poll = None
    update.message.caption = None

    update.message.chat = MagicMock()
    update.message.chat.type = "private"
    update.message.chat.title = None

    update.message.reply_to_message = None
    update.message.forward_from = None
    update.message.forward_from_chat = None

    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_context_fixture():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    context.bot.send_message = AsyncMock()
    context.bot.forward_message = AsyncMock()
    context.bot.edit_message_caption = AsyncMock()
    context.bot.get_chat = AsyncMock()
    mock_chat_obj = MagicMock()
    mock_chat_obj.username = None
    context.bot.get_chat.return_value = mock_chat_obj
    return context

@pytest.mark.asyncio
async def test_handle_message_unauthorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 999
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} Some announcement"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_keyword_no_poll(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = "Just a regular message"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()

# @pytest.mark.asyncio
# @pytest.mark.parametrize("keyword_to_test", MAIN_KEYWORDS)
# @patch('main.datetime.datetime')
# async def test_handle_text_message_with_keyword_sends_text_and_reply(
#     mock_datetime_class, keyword_to_test, mock_update_fixture, mock_context_fixture
# ):
#     mock_update_fixture.effective_user.id = 123
#     original_text = f"{keyword_to_test} This is a test announcement text."
#     mock_update_fixture.message.text = original_text
#     mock_update_fixture.message.poll = None

#     current_time = datetime.datetime(2023, 10, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)
#     mock_datetime_class.now.return_value = current_time

#     message_mock = MagicMock(spec=Message)
#     message_mock.message_id = mock_update_fixture.message.message_id
#     message_mock.chat_id = mock_update_fixture.message.chat_id
#     message_mock.reply_text = mock_update_fixture.message.reply_text
#     message_mock.chat = mock_update_fixture.message.chat

#     message_mock.text = original_text
#     message_mock.poll = None

#     recent_message_date = current_time - datetime.timedelta(minutes=5)
#     message_mock.date = recent_message_date

#     mock_update_fixture.message = message_mock

#     bot_announcement_message_mock = MagicMock(spec=Message)
#     bot_announcement_message_mock.message_id = 2002

#     expected_channel_id_for_link = MAIN_TARGET_CHANNEL_ID[4:]

#     mock_context_fixture.bot.send_message.side_effect = [
#         bot_announcement_message_mock,
#         MagicMock(spec=Message)
#     ]

#     await handle_message(mock_update_fixture, mock_context_fixture)

#     link_to_bot_announcement = f"https://t.me/{expected_channel_id_for_link}/{bot_announcement_message_mock.message_id}"

#     prompt_template = POLL_LINK_MESSAGE_TEMPLATES.get(keyword_to_test, POLL_LINK_MESSAGE_TEMPLATES["#анонс"])
#     expected_reply_text = prompt_template.format(link=link_to_bot_announcement)

#     calls = [
#         call(chat_id=MAIN_TARGET_CHANNEL_ID, text=original_text),
#         call(chat_id=MAIN_TARGET_CHANNEL_ID,
#              text=expected_reply_text,
#              parse_mode='HTML',
#              reply_to_message_id=bot_announcement_message_mock.message_id,
#              disable_web_page_preview=True)
#     ]
#     mock_context_fixture.bot.send_message.assert_has_calls(calls, any_order=False)
#     assert mock_context_fixture.bot.send_message.call_count == 2

#     mock_context_fixture.bot.get_chat.assert_called_once_with(chat_id=MAIN_TARGET_CHANNEL_ID)
#     mock_context_fixture.bot.forward_message.assert_not_called()
#     mock_context_fixture.bot.edit_message_caption.assert_not_called()

# @pytest.mark.asyncio
# @pytest.mark.parametrize("user_poll_caption_keyword, expected_template_key", [
#     (MAIN_KEYWORDS[0], MAIN_KEYWORDS[0]),
#     (MAIN_KEYWORDS[1], MAIN_KEYWORDS[1]),
#     ("Some event", MAIN_KEYWORDS[0]),
#     (None, MAIN_KEYWORDS[0])
# ])
# @patch('main.datetime.datetime')
# async def test_handle_poll_forwards_and_edits_caption(
#     mock_datetime_class, user_poll_caption_keyword, expected_template_key,
#     mock_update_fixture, mock_context_fixture
# ):
#     local_forwarded_message = MagicMock(spec=Message)
#     local_forwarded_message.message_id = 1001

#     mock_update_fixture.effective_user.id = 123
#     mock_update_fixture.message.poll = MagicMock(spec=TelegramPoll)
#     mock_update_fixture.message.text = user_poll_caption_keyword

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
        "Error: Target channel ID is not configured for polls."
    )
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.edit_message_caption.assert_not_called()
