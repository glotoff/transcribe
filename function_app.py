import os
import json
import logging
import azure.functions as func
from telegram import Update
from bot import create_app

# Initialize the Azure Function App
app = func.FunctionApp()

# ──────────────────────────────────────────────────────────────────────────────
# 1. Telegram Webhook Endpoint (HTTP POST Trigger)
# ──────────────────────────────────────────────────────────────────────────────
# Receives the update from Telegram, puts it in the Azure Storage Queue, and
# returns HTTP 200 immediately to acknowledge receipt and prevent Telegram from retrying.
@app.route(route="telegram-webhook", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
@app.queue_output(arg_name="msg", queue_name="telegram-updates", connection="AzureWebJobsStorage")
def telegram_webhook(req: func.HttpRequest, msg: func.Out[str]) -> func.HttpResponse:
    logging.info("Telegram Webhook received a request.")
    try:
        body = req.get_json()
        if not body:
            logging.warning("Received empty request body.")
            return func.HttpResponse("Empty body", status_code=400)
        
        # Write update to queue for asynchronous processing
        msg.set(json.dumps(body))
        return func.HttpResponse("Accepted", status_code=200)
    except Exception as e:
        logging.error(f"Error in telegram_webhook: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)

# ──────────────────────────────────────────────────────────────────────────────
# 2. Telegram Update Processor (Queue Trigger)
# ──────────────────────────────────────────────────────────────────────────────
# Triggered by new items in the queue, processes the updates in the background.
@app.queue_trigger(arg_name="msg", queue_name="telegram-updates", connection="AzureWebJobsStorage")
async def process_telegram_update(msg: func.QueueMessage):
    logging.info("Processing Telegram update from queue.")
    try:
        body_str = msg.get_body().decode("utf-8")
        update_data = json.loads(body_str)
        
        # Create a fresh application instance for isolated execution of this update
        tg_app = create_app()
        
        # De-serialize the update using the bot client
        update = Update.de_json(update_data, tg_app.bot)
        
        # Execute the update inside the application lifecycle
        async with tg_app:
            await tg_app.process_update(update)
            
        logging.info("Successfully processed Telegram update.")
    except Exception as e:
        logging.exception(f"Failed to process queued Telegram update: {e}")
