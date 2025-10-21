import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Set up environment variables for the tests
FORWARD_CHAT_ID_VALUE = '-100987654321'
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_pytest'
os.environ['FORWARD_CHAT_ID'] = FORWARD_CHAT_ID_VALUE

from main import handle_message
from telegram import Update, Message, User, Bot
from telegram.ext import ContextTypes

@pytest.fixture
def mock_update():
    """Creates a mock Telegram Update object."""
    update = MagicMock(spec=Update)
    update.update_id = 12345

    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 123
    update.effective_user.username = "testuser"

    update.message = MagicMock(spec=Message)
    update.message.message_id = 789
    update.message.chat_id = 54321
    update.message.text = "Hello, world!"

    return update

@pytest.fixture
def mock_context():
    """Creates a mock Telegram Context object with a mocked bot."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock(spec=Bot)
    context.bot.forward_message = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_handle_message_forwards_message_successfully(mock_update, mock_context):
    """
    Tests that a message is correctly forwarded when FORWARD_CHAT_ID is set.
    """
    await handle_message(mock_update, mock_context)

    # Assert that the forward_message method was called once with the correct parameters
    mock_context.bot.forward_message.assert_called_once_with(
        chat_id=FORWARD_CHAT_ID_VALUE,
        from_chat_id=mock_update.message.chat_id,
        message_id=mock_update.message.message_id
    )

@pytest.mark.asyncio
async def test_handle_message_no_forward_chat_id(mock_update, mock_context):
    """
    Tests that no message is forwarded if the FORWARD_CHAT_ID environment variable is not set.
    """
    with patch('main.FORWARD_CHAT_ID', None):
        await handle_message(mock_update, mock_context)

    # Assert that forward_message was not called
    mock_context.bot.forward_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_no_message_or_user(mock_context):
    """
    Tests that the function exits gracefully if the update contains no message or user.
    """
    # Test with no message
    no_message_update = MagicMock(spec=Update)
    no_message_update.message = None
    no_message_update.effective_user = MagicMock(spec=User)

    await handle_message(no_message_update, mock_context)
    mock_context.bot.forward_message.assert_not_called()

    # Test with no user
    no_user_update = MagicMock(spec=Update)
    no_user_update.message = MagicMock(spec=Message)
    no_user_update.effective_user = None

    await handle_message(no_user_update, mock_context)
    mock_context.bot.forward_message.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_from_forward_chat_id(mock_update, mock_context):
    """
    Tests that a message originating from the FORWARD_CHAT_ID is not forwarded.
    """
    # Set the message's chat_id to be the same as the FORWARD_CHAT_ID
    mock_update.message.chat_id = int(FORWARD_CHAT_ID_VALUE)

    await handle_message(mock_update, mock_context)

    # Assert that forward_message was not called
    mock_context.bot.forward_message.assert_not_called()
