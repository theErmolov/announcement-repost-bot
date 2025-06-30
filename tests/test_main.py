import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Set environment variables for testing BEFORE importing from main
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_pytest' # Use a distinct token for clarity
os.environ['AUTHORIZED_USER_IDS'] = '123,456'
os.environ['TARGET_CHANNEL_ID'] = '-100987654321'
# The KEYWORD is defined in main.py and will be imported.

import datetime # Import for datetime.timezone
from unittest.mock import call # Import for checking multiple calls if needed

# Now import from main
from main import handle_message, AUTHORIZED_USER_IDS as MAIN_AUTHORIZED_USER_IDS, \
                 TARGET_CHANNEL_ID as MAIN_TARGET_CHANNEL_ID, KEYWORDS as MAIN_KEYWORDS, \
                 MESSAGE_TEMPLATES, POLL_MESSAGE_IDENTIFIERS

# Verify that the imported constants from main.py reflect the os.environ settings
# This is a good sanity check.
assert MAIN_TARGET_CHANNEL_ID == '-100987654321'
assert 123 in MAIN_AUTHORIZED_USER_IDS
assert 456 in MAIN_AUTHORIZED_USER_IDS
assert "#анонс" in MAIN_KEYWORDS
assert "#опрос" in MAIN_KEYWORDS


@pytest.fixture
def mock_update_fixture():
    """Fixture to create a mock Update object."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.effective_user = MagicMock(spec=User)
    update.update_id = 12345
    update.message.text = None
    update.message.poll = None
    update.message.message_id = 789
    update.message.chat_id = 54321
    update.message.date = MagicMock() # Mock datetime object
    update.message.date.isoformat.return_value = "2023-01-01T12:00:00" # Example ISO string

    # Mock chat object and its attributes
    update.message.chat = MagicMock()
    update.message.chat.type = "private" # Default chat type
    update.message.chat.title = None # Default no title for private chats

    # Attributes for logging
    update.effective_user.full_name = "Test User Full Name"
    update.effective_user.is_bot = False
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.username = "testuser"


    update.message.reply_to_message = None
    update.message.forward_from = None
    update.message.forward_from_chat = None

    # Message content types, default to None
    update.message.photo = None
    update.message.video = None
    update.message.document = None
    update.message.audio = None
    update.message.voice = None
    update.message.sticker = None
    update.message.contact = None
    update.message.location = None
    update.message.venue = None


    # Ensure reply_text is an AsyncMock if it's awaited
    update.message.reply_text = AsyncMock()
    return update

@pytest.fixture
def mock_bot_message_fixture():
    """Fixture to create a mock Message object, e.g., for forwarded messages."""
    message = MagicMock(spec=Message)
    message.message_id = 1001  # Example ID for forwarded/bot messages
    message.date = datetime.datetime.now(datetime.timezone.utc) # Default to now
    message.text = "Forwarded content" # Default text
    message.caption = None
    # Add other fields if they are accessed in the code for these messages
    return message

@pytest.fixture
def mock_context_fixture(mock_bot_message_fixture):
    """Fixture to create a mock ContextTypes.DEFAULT_TYPE object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    # Mock methods that might be called on bot
    context.bot.get_chat = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    # Configure forward_message to return a message mock by default
    context.bot.forward_message = AsyncMock(return_value=mock_bot_message_fixture)
    # send_message can also return a message mock if its result is used
    context.bot.send_message = AsyncMock(return_value=mock_bot_message_fixture)

    # Default behavior for get_chat (can be overridden in tests)
    mock_chat_obj = MagicMock()
    mock_chat_obj.username = None # Default to no username
    context.bot.get_chat.return_value = mock_chat_obj
    return context

# To use fixtures, pass their names as arguments to the test functions
@pytest.mark.asyncio
async def test_handle_message_unauthorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 999 # Unauthorized
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} Some announcement" # Use first keyword
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.forward_message.assert_not_called() # Changed: original send_message is now forward_message
    mock_context_fixture.bot.send_message.assert_not_called() # This is for the poll link message
    # Check if reply_text was called (it shouldn't be for unauthorized, based on current code)
    # If main.py is changed to reply to unauthorized users, this assertion needs to change.
    mock_update_fixture.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_no_keyword_no_poll(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123 # Authorized
    mock_update_fixture.message.text = "Just a regular message"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.edit_message_text.assert_not_called()


# This test is replaced by more specific ones below for the new keyword logic
# @pytest.mark.asyncio
# async def test_handle_message_with_keyword_authorized_user(mock_update_fixture, mock_context_fixture):
#     mock_update_fixture.effective_user.id = 123 # Authorized
#     test_text = f"{MAIN_KEYWORDS[0]} This is a text announcement"
#     mock_update_fixture.message.text = test_text
#     await handle_message(mock_update_fixture, mock_context_fixture)
#     # ... new assertions needed ...

@pytest.mark.asyncio
async def test_handle_message_direct_poll_from_authorized_user_no_keyword(mock_update_fixture, mock_context_fixture):
    """Tests forwarding a direct poll object when no keyword is in its caption/text."""
    mock_update_fixture.effective_user.id = 456 # Authorized
    mock_update_fixture.message.poll = MagicMock() # Simulate a poll object
    mock_update_fixture.message.text = None
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.forward_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        from_chat_id=mock_update_fixture.message.chat_id,
        message_id=mock_update_fixture.message.message_id
    )
    mock_context_fixture.bot.send_message.assert_not_called() # No keyword processing, so no poll link message
    mock_context_fixture.bot.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_keyword_in_poll_caption_takes_precedence(mock_update_fixture, mock_context_fixture, mock_bot_message_fixture):
    """Tests that if a poll has a keyword in its caption, keyword logic is used."""
    mock_update_fixture.effective_user.id = 123 # Authorized
    mock_update_fixture.message.poll = MagicMock() # It's a poll
    keyword_to_test = MAIN_KEYWORDS[0] # e.g. #анонс
    original_caption = f"{keyword_to_test} Event details in poll caption"
    mock_update_fixture.message.text = original_caption # Polls store caption in 'text' field for bot library if caption exists
                                                        # or it could be message.caption. For this test, .text is fine.

    # Setup forwarded message mock
    forwarded_message_id = 2002
    mock_bot_message_fixture.message_id = forwarded_message_id
    mock_bot_message_fixture.text = original_caption # Forwarded message will have the caption as its text
    mock_bot_message_fixture.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5) # Recent
    mock_context_fixture.bot.forward_message.return_value = mock_bot_message_fixture

    # Mock get_chat to return a chat without a username (for link format testing)
    mock_chat_obj = MagicMock()
    mock_chat_obj.username = None
    mock_context_fixture.bot.get_chat.return_value = mock_chat_obj

    # Expected link using channel ID (stripped)
    expected_channel_id_for_link = MAIN_TARGET_CHANNEL_ID[4:] # Remove "-100"
    expected_link = f"https://t.me/{expected_channel_id_for_link}/{forwarded_message_id}"
    expected_poll_text = MESSAGE_TEMPLATES[keyword_to_test].format(link=expected_link)

    await handle_message(mock_update_fixture, mock_context_fixture)

    # 1. Original message (poll with caption) should be forwarded
    mock_context_fixture.bot.forward_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        from_chat_id=mock_update_fixture.message.chat_id,
        message_id=mock_update_fixture.message.message_id
    )

    # 2. A new message with the poll link should be sent (Case 2.1)
    mock_context_fixture.bot.send_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        text=expected_poll_text,
        parse_mode='HTML',
        reply_to_message_id=forwarded_message_id,
        disable_web_page_preview=True
    )
    mock_context_fixture.bot.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_no_target_channel_id_for_keyword(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} test" # Use first keyword
    # Patch main.TARGET_CHANNEL_ID for this test
    with patch('main.TARGET_CHANNEL_ID', ''): # No target channel ID
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured." # Updated error message
    )
    mock_context_fixture.bot.forward_message.assert_not_called()
    mock_context_fixture.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_target_channel_id_for_direct_poll(mock_update_fixture, mock_context_fixture):
    """Test direct poll forwarding when TARGET_CHANNEL_ID is not set."""
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.poll = MagicMock()
    mock_update_fixture.message.text = None # Ensure no keyword processing
    with patch('main.TARGET_CHANNEL_ID', ''):
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured. Cannot repost poll."
    )
    mock_context_fixture.bot.forward_message.assert_not_called()

# Helper for generating parametrized test cases for keyword logic
def generate_keyword_test_case(keyword, message_template, channel_id_calc_func, has_username):
    original_message_text = f"{keyword} Test event details"
    mock_chat_obj = MagicMock()
    mock_chat_obj.username = "testchannelname" if has_username else None
    forwarded_message_id = 3003

    link_target = "testchannelname" if has_username else channel_id_calc_func(MAIN_TARGET_CHANNEL_ID)
    expected_link = f"https://t.me/{link_target}/{forwarded_message_id}"
    expected_reply_text = message_template.format(link=expected_link)

    return (keyword, original_message_text, mock_chat_obj, forwarded_message_id, expected_reply_text)

channel_id_stripped_func = lambda cid: cid[4:] if cid.startswith("-100") else cid

# Test cases for the "append poll prompt" logic (Case 2.1)
test_cases_append_logic = [
    generate_keyword_test_case(MAIN_KEYWORDS[0], MESSAGE_TEMPLATES[MAIN_KEYWORDS[0]], channel_id_stripped_func, True),
    generate_keyword_test_case(MAIN_KEYWORDS[0], MESSAGE_TEMPLATES[MAIN_KEYWORDS[0]], channel_id_stripped_func, False),
    generate_keyword_test_case(MAIN_KEYWORDS[1], MESSAGE_TEMPLATES[MAIN_KEYWORDS[1]], channel_id_stripped_func, True),
    generate_keyword_test_case(MAIN_KEYWORDS[1], MESSAGE_TEMPLATES[MAIN_KEYWORDS[1]], channel_id_stripped_func, False),
]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keyword, original_text, mock_chat_response, fwd_msg_id, expected_text",
    test_cases_append_logic
)
@patch('main.datetime')
async def test_handle_message_keyword_append_logic_parametrized(
    mock_dt, keyword, original_text, mock_chat_response, fwd_msg_id, expected_text,
    mock_update_fixture, mock_context_fixture, mock_bot_message_fixture
):
    """Tests Case 2.1: Bot forwards user's message and appends a new message with a poll link."""
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = original_text

    current_time = datetime.datetime(2023, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mock_dt.datetime.now.return_value = current_time

    mock_bot_message_fixture.message_id = fwd_msg_id
    mock_bot_message_fixture.date = current_time - datetime.timedelta(minutes=30) # Recent
    mock_bot_message_fixture.text = original_text
    mock_context_fixture.bot.forward_message.return_value = mock_bot_message_fixture
    mock_context_fixture.bot.get_chat.return_value = mock_chat_response

    await handle_message(mock_update_fixture, mock_context_fixture)

    mock_context_fixture.bot.forward_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        from_chat_id=mock_update_fixture.message.chat_id,
        message_id=mock_update_fixture.message.message_id
    )
    mock_context_fixture.bot.send_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        text=expected_text,
        parse_mode='HTML',
        reply_to_message_id=fwd_msg_id,
        disable_web_page_preview=True
    )
    mock_context_fixture.bot.edit_message_text.assert_not_called()
    mock_context_fixture.bot.get_chat.assert_called_once_with(chat_id=MAIN_TARGET_CHANNEL_ID)

@patch('main.datetime')
async def test_handle_message_keyword_append_logic_too_old(
    mock_dt, mock_update_fixture, mock_context_fixture, mock_bot_message_fixture
):
    """Tests that if the forwarded message is too old, no poll link message is sent (append logic)."""
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = f"{MAIN_KEYWORDS[0]} Some old event"

    current_time = datetime.datetime(2023, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mock_dt.datetime.now.return_value = current_time

    mock_bot_message_fixture.message_id = 4004
    mock_bot_message_fixture.date = current_time - datetime.timedelta(hours=2) # Older than 1 hour
    mock_context_fixture.bot.forward_message.return_value = mock_bot_message_fixture

    await handle_message(mock_update_fixture, mock_context_fixture)

    mock_context_fixture.bot.forward_message.assert_called_once()
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.edit_message_text.assert_not_called()

# Test cases for the "edit existing poll prompt" logic (Case 2.2)
# Structure: (keyword, user_text_with_poll_elements, template_for_final_text, use_username_for_link)
test_cases_edit_logic = [
    (MAIN_KEYWORDS[0], f"{MAIN_KEYWORDS[0]} text {POLL_MESSAGE_IDENTIFIERS[0]} link", MESSAGE_TEMPLATES[MAIN_KEYWORDS[0]], True),
    (MAIN_KEYWORDS[0], f"{MAIN_KEYWORDS[0]} {POLL_MESSAGE_IDENTIFIERS[0]} other", MESSAGE_TEMPLATES[MAIN_KEYWORDS[0]], False),
    (MAIN_KEYWORDS[1], f"{MAIN_KEYWORDS[1]} {POLL_MESSAGE_IDENTIFIERS[1]} etc", MESSAGE_TEMPLATES[MAIN_KEYWORDS[1]], True),
    (MAIN_KEYWORDS[1], f"{MAIN_KEYWORDS[1]} text {POLL_MESSAGE_IDENTIFIERS[1]} here", MESSAGE_TEMPLATES[MAIN_KEYWORDS[1]], False),
]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keyword, user_text, final_text_template, has_username",
    test_cases_edit_logic
)
@patch('main.datetime')
async def test_handle_message_keyword_edit_logic_parametrized(
    mock_dt, keyword, user_text, final_text_template, has_username,
    mock_update_fixture, mock_context_fixture, mock_bot_message_fixture
):
    """Tests Case 2.2: Bot forwards user's message and EDITS it because it contains poll identifiers."""
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = user_text

    current_time = datetime.datetime(2023, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mock_dt.datetime.now.return_value = current_time

    forwarded_message_id = 5005
    mock_bot_message_fixture.message_id = forwarded_message_id
    mock_bot_message_fixture.date = current_time - datetime.timedelta(minutes=15) # Recent
    mock_bot_message_fixture.text = user_text # Forwarded message text is the user's original text
    mock_context_fixture.bot.forward_message.return_value = mock_bot_message_fixture

    mock_chat_obj_for_link = MagicMock()
    mock_chat_obj_for_link.username = "testchannelusername" if has_username else None
    mock_context_fixture.bot.get_chat.return_value = mock_chat_obj_for_link

    link_target = "testchannelusername" if has_username else MAIN_TARGET_CHANNEL_ID[4:]
    expected_link_to_self = f"https://t.me/{link_target}/{forwarded_message_id}"
    expected_final_text = final_text_template.format(link=expected_link_to_self)

    await handle_message(mock_update_fixture, mock_context_fixture)

    mock_context_fixture.bot.forward_message.assert_called_once()
    mock_context_fixture.bot.edit_message_text.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID,
        message_id=forwarded_message_id,
        text=expected_final_text,
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    mock_context_fixture.bot.send_message.assert_not_called()

# Need to import these for spec
from telegram import Update, Message, User, Bot
from telegram.ext import ContextTypes
