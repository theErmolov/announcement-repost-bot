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

# Now import from main
from main import handle_message, AUTHORIZED_USER_IDS as MAIN_AUTHORIZED_USER_IDS, \
                 TARGET_CHANNEL_ID as MAIN_TARGET_CHANNEL_ID, KEYWORD as MAIN_KEYWORD

# Verify that the imported constants from main.py reflect the os.environ settings
# This is a good sanity check.
assert MAIN_TARGET_CHANNEL_ID == '-100987654321'
assert 123 in MAIN_AUTHORIZED_USER_IDS
assert 456 in MAIN_AUTHORIZED_USER_IDS
# KEYWORD is '#анонс' by default in main.py, not set by env var in the provided code.
# If KEYWORD could be set by an env var, we'd test that too.
# For now, we assume it's the hardcoded value.

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
def mock_context_fixture():
    """Fixture to create a mock ContextTypes.DEFAULT_TYPE object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    return context

# To use fixtures, pass their names as arguments to the test functions
@pytest.mark.asyncio
async def test_handle_message_unauthorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 999 # Unauthorized
    mock_update_fixture.message.text = f"{MAIN_KEYWORD} Some announcement"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()
    # Check if reply_text was called (it shouldn't be for unauthorized, based on current code)
    # If main.py is changed to reply to unauthorized users, this assertion needs to change.
    mock_update_fixture.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_no_keyword_no_poll(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123 # Authorized
    mock_update_fixture.message.text = "Just a regular message"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_not_called()
    mock_context_fixture.bot.forward_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_with_keyword_authorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123 # Authorized
    test_text = f"{MAIN_KEYWORD} This is a text announcement"
    mock_update_fixture.message.text = test_text
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.send_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID, # Use imported constant
        text=test_text
    )
    mock_context_fixture.bot.forward_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_poll_from_authorized_user(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 456 # Authorized
    mock_update_fixture.message.poll = MagicMock() # Simulate a poll object
    mock_update_fixture.message.text = None
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.forward_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID, # Use imported constant
        from_chat_id=mock_update_fixture.message.chat_id,
        message_id=mock_update_fixture.message.message_id
    )
    mock_context_fixture.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_poll_with_keyword_text_ignored(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123 # Authorized
    mock_update_fixture.message.poll = MagicMock()
    mock_update_fixture.message.text = f"{MAIN_KEYWORD} This text should be ignored"
    await handle_message(mock_update_fixture, mock_context_fixture)
    mock_context_fixture.bot.forward_message.assert_called_once_with(
        chat_id=MAIN_TARGET_CHANNEL_ID, # Use imported constant
        from_chat_id=mock_update_fixture.message.chat_id,
        message_id=mock_update_fixture.message.message_id
    )
    mock_context_fixture.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_target_channel_id_for_text(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.text = f"{MAIN_KEYWORD} test"
    # Patch main.TARGET_CHANNEL_ID for this test
    with patch('main.TARGET_CHANNEL_ID', ''):
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured. Cannot repost text announcement."
    )
    mock_context_fixture.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_target_channel_id_for_poll(mock_update_fixture, mock_context_fixture):
    mock_update_fixture.effective_user.id = 123
    mock_update_fixture.message.poll = MagicMock()
    with patch('main.TARGET_CHANNEL_ID', ''):
        await handle_message(mock_update_fixture, mock_context_fixture)
    mock_update_fixture.message.reply_text.assert_called_once_with(
        "Error: Target channel ID is not configured. Cannot repost poll."
    )
    mock_context_fixture.bot.forward_message.assert_not_called()

# Need to import these for spec
from telegram import Update, Message, User, Bot
from telegram.ext import ContextTypes
