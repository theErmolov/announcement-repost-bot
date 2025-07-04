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
TELEGRAM_WEBHOOK_SECRET_TOKEN = os.environ.get('TELEGRAM_WEBHOOK_SECRET_TOKEN')

application = None

async def initialize_bot():
    global application
    logger.info("Starting initialize_bot()...")
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
        application.add_handler(MessageHandler(filters.POLL, handle_message))
        logger.info("Bot application initialized and handlers registered for text and poll messages.")
    logger.info("Finished initialize_bot().")
    return application

async def actual_async_logic(event, context):
    global application
    logger.info(f"actual_async_logic started. AWS Request ID: {context.aws_request_id if context else 'N/A'}")
    try:
        event_summary = {k: v for k, v in event.items() if k != 'body'}
        if 'body' in event and isinstance(event['body'], str) and len(event['body']) > 512:
            event_summary['body_summary'] = event['body'][:512] + "... (truncated)"
        else:
            event_summary['body_summary'] = event.get('body')
        logger.info(f"Received event summary: {json.dumps(event_summary)}")


        if TELEGRAM_WEBHOOK_SECRET_TOKEN:
            header_secret_token = event.get('headers', {}).get('X-Telegram-Bot-Api-Secret-Token')
            if header_secret_token != TELEGRAM_WEBHOOK_SECRET_TOKEN:
                logger.warning("Invalid X-Telegram-Bot-Api-Secret-Token. Request denied.")
                return {'statusCode': 403, 'body': json.dumps({'message': 'Forbidden - Invalid secret token'})}
            logger.info("X-Telegram-Bot-Api-Secret-Token successfully verified.")
        else:
            logger.info("TELEGRAM_WEBHOOK_SECRET_TOKEN is not set. Proceeding without webhook secret token verification (less secure).")

        logger.info("Initializing bot application for this invocation...")
        app = await initialize_bot()
        logger.info(f"Bot application {'newly initialized' if app and not hasattr(app, '_already_initialized_marker') else 'reused or re-initialized'}. Proceeding with update processing.")
        if app and not hasattr(app, '_already_initialized_marker'):
            app._already_initialized_marker = True


        if 'body' not in event:
            logger.error("Event does not contain a 'body'.")
            return {'statusCode': 400, 'body': json.dumps({'message': 'Missing body'})}

        try:
            update_data = json.loads(event['body'])
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from event body: {e}")
            return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid JSON format'})}

        update = Update.de_json(update_data, app.bot)
        logger.info(f"Update object created successfully for update ID: {update.update_id}. Type: {update.effective_chat.type if update.effective_chat else 'N/A'}")
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
    finally:
        if application and hasattr(application, 'bot') and hasattr(application.bot, '_client') and application.bot._client:
            try:
                logger.info("Attempting to close httpx client before Lambda execution ends.")
                await application.bot._client.aclose()
                logger.info("httpx client closed successfully.")
            except Exception as e_close:
                logger.error(f"Error trying to close httpx client: {e_close}", exc_info=True)

        if application is not None:
            application = None
            logger.info("Global application object set to None to force re-initialization on next invocation.")

def lambda_handler(event, context):
    aws_request_id = "N/A"
    if context and hasattr(context, 'aws_request_id'):
        aws_request_id = context.aws_request_id
    logger.info(f"lambda_handler invoked. AWS Request ID: {aws_request_id}. Event keys: {list(event.keys()) if isinstance(event, dict) else 'Non-dict event'}")
    return asyncio.run(actual_async_logic(event, context))
