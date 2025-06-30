import json
import asyncio
import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from main import handle_message, start

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_WEBHOOK_SECRET_TOKEN = os.environ.get('TELEGRAM_WEBHOOK_SECRET_TOKEN') # For verifying Telegram requests

application = None

async def initialize_bot():
    global application
    if application is None:
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")

        logger.info("Initializing bot application with custom httpx timeouts...")

        timeout_config = httpx.Timeout(connect=15.0, read=15.0, write=15.0, pool=15.0)
        custom_httpx_client = httpx.AsyncClient(timeout=timeout_config)

        builder = Application.builder().token(TELEGRAM_BOT_TOKEN)

        async def post_init_func(app: Application):
            app.bot._client = custom_httpx_client

        builder.post_init(post_init_func)
        application = builder.build()

        await application.initialize()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("Bot application initialized and handlers registered.")
    return application

async def actual_async_logic(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        if TELEGRAM_WEBHOOK_SECRET_TOKEN:
            header_secret_token = event.get('headers', {}).get('X-Telegram-Bot-Api-Secret-Token')
            if header_secret_token != TELEGRAM_WEBHOOK_SECRET_TOKEN:
                logger.warning("Invalid X-Telegram-Bot-Api-Secret-Token.")
                return {'statusCode': 403, 'body': json.dumps({'message': 'Forbidden - Invalid secret token'})}
            logger.info("X-Telegram-Bot-Api-Secret-Token verified.")
        else:
            logger.warning("TELEGRAM_WEBHOOK_SECRET_TOKEN is not set. Skipping header check (less secure).")


        app = await initialize_bot()

        if 'body' not in event:
            logger.error("Event does not contain a 'body'.")
            return {'statusCode': 400, 'body': json.dumps({'message': 'Missing body'})}

        try:
            update_data = json.loads(event['body'])
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from event body: {e}")
            return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid JSON format'})}

        update = Update.de_json(update_data, app.bot)
        logger.info(f"Processing update ID: {update.update_id}")

        await app.process_update(update)

        logger.info(f"Successfully processed update ID: {update.update_id}")
        return {'statusCode': 200, 'body': json.dumps({'message': 'Update processed'})}

    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        return {'statusCode': 500, 'body': json.dumps({'message': f"Configuration error: {ve}"})}
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps({'message': f"Internal server error: {str(e)}"})}

# New lambda_handler function
def lambda_handler(event, context):
    return asyncio.run(actual_async_logic(event, context))
