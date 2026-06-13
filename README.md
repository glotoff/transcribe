# Transcription & OCR Telegram Bot

This bot provides:
1. **Audio/Voice transcription** using OpenAI Whisper API and formatting with GPT-4o-mini.
2. **PDF OCR** using `ocrmypdf`.

Two execution options are available:
- **Option 1: Local / VPS Polling (using Docker Compose)**
- **Option 2: Azure Functions (Serverless Webhook + Queue Storage)**

---

## Option 1: Local / VPS Polling (Docker Compose)

This mode uses a continuous polling loop to fetch updates from Telegram.

### Build
```bash
docker buildx create --use --name cross-builder
docker buildx build --platform linux/amd64,linux/arm64 -t glotoff/transcribe-bot:latest --push .
```

### Run
```bash
docker-compose down && docker image prune -f && docker-compose pull && docker-compose up -d --build
```

---

## Option 2: Azure Functions (Serverless Webhook + Queue)

This mode deploys the bot to Azure Functions. It uses a **Webhook + Azure Queue Storage** pattern:
- **`telegram-webhook` (HTTP Trigger):** Receives the message payload from Telegram, writes it to a queue, and immediately returns a `200 OK` (takes < 1 second). This prevents Telegram from retrying the request due to timeouts.
- **`process-telegram-update` (Queue Trigger):** Reads the update payload from the queue and handles the transcription/OCR asynchronously in the background.

### Prerequisites
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- An Azure Storage Account (required for the Storage Queue)

### Local Development
1. Configure your local settings in `local.settings.json`:
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "FUNCTIONS_WORKER_RUNTIME": "python",
       "AzureWebJobsStorage": "<your-azure-storage-account-connection-string>",
       "TELEGRAM_BOT_TOKEN": "<your-telegram-bot-token>",
       "OPENAI_API_KEY": "<your-openai-api-key>"
     }
   }
   ```
2. Start the local functions host:
   ```bash
   func start
   ```

### Container Build (Azure Functions)
Because `ocrmypdf` depends on system binaries (`tesseract-ocr`, `ghostscript`), the Azure Function must be deployed as a custom container using `Dockerfile.azure`.

1. Build the container image:
   ```bash
   docker build -t glotoff/transcribe-azure-bot:latest -f Dockerfile.azure .
   ```
2. Push it to your Docker Hub registry:
   ```bash
   docker push glotoff/transcribe-azure-bot:latest
   ```

### Azure Setup & Deployment

#### 1. Create the Storage Account
Create a new Azure Storage Account to handle the function execution state and queues:
- **Performance:** **Standard** (General-purpose v2).
- **Redundancy:** **Locally-redundant storage (LRS)** (cheapest tier).
- **Preferred Storage Type:** **Queues** or **Any**.
- **Networking:** **Enable public network access** (Enable from all networks) so the serverless worker can reach it.
- **Recovery:** **Disable/Uncheck all soft delete options** (blob, container, file shares) to avoid paying for retained temporary run files and queue history.

#### 2. Create the Function App
Create a new Function App with the following hosting options:
- **Hosting Plan:** Select **Container Apps environment**.
  - *Why:* This is the only serverless (scale-to-zero) hosting option on Azure that supports custom Linux Docker containers (needed for `ocrmypdf`).
- **Deploy the container image** to this Function App once built and pushed.

#### 3. Configure App Settings
Go to the **Configuration** or **Environment variables** section of your Function App and add:
- `TELEGRAM_BOT_TOKEN`: Your bot's API token from BotFather.
- `OPENAI_API_KEY`: Your OpenAI API key.
- `AzureWebJobsStorage`: The Connection String of the Storage Account you created in Step 1.
  - *How to retrieve:* In the Azure Portal, navigate to your storage account, go to **Security + networking** -> **Access keys**, click **Show** next to the `key1` **Connection string**, and copy the entire string (starts with `DefaultEndpointsProtocol=https...`).

#### 4. Register the Webhook
Register your HTTP trigger endpoint as Telegram's webhook URL:
```bash
curl -F "url=https://<your-function-app-name>.azurewebsites.net/api/telegram-webhook" https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
```