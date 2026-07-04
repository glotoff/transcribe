# Transcription & OCR Telegram Bot

This bot provides:
1. **Audio/Voice transcription** using OpenAI Whisper API and formatting with GPT-4o-mini.
2. **PDF OCR** using `ocrmypdf`.

Three execution options are available:
- **Option 1: Local / VPS Polling (using Docker Compose)**
- **Option 2: Azure Functions (Serverless Webhook + Queue Storage)**
- **Option 3: Google Cloud Run (Serverless Webhook)**


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

> [!TIP]
> **Troubleshooting ARM64 Hosts (Windows ARM64 / macOS Apple Silicon):**
> Because the Azure Function base image is compiled for `linux/amd64`, building it on an ARM64 host may fail with `exec /bin/sh: exec format error`.
> To fix this, run this command in your terminal to register the AMD64 emulator in your Docker daemon:
> ```bash
> docker run --privileged --rm tonistiigi/binfmt --install all
> ```
> Once registered, retry the `docker build` command.

1. Build the container image:
   ```bash
   docker build --platform linux/amd64 -t glotoff/transcribe-azure-bot:latest -f Dockerfile.azure .
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
- **Enable Ingress (Public URL access):**
  1. Once created, open your Function App in the portal and go to **Networking** -> **Ingress** in the left-hand menu.
  2. Toggle **Ingress** to **Enabled**.
  3. Select **Accepting traffic from anywhere** (to allow Telegram to call it).
  4. Set **Target port** to **80** (default Azure Functions port).
  5. Click **Save**. This will generate your public **Application URL** on the app's **Overview** page.

#### 3. Configure App Settings
Go to the **Configuration** or **Environment variables** section of your Function App and add:
- `TELEGRAM_BOT_TOKEN`: Your bot's API token from BotFather.
- `OPENAI_API_KEY`: Your OpenAI API key.
- `TELEGRAM_WEBHOOK_SECRET`: (Optional, recommended) The secure random string you choose for webhook security verification.
- `AzureWebJobsStorage`: The Connection String of the Storage Account you created in Step 1.
  - *How to retrieve:* In the Azure Portal, navigate to your storage account, go to **Security + networking** -> **Access keys**, click **Show** next to the `key1` **Connection string**, and copy the entire string (starts with `DefaultEndpointsProtocol=https...`).

#### 4. Register the Webhook (Securely)
To secure your webhook endpoint, register it with a secure, random `secret_token`. This tells Telegram to send this secret in the headers so that your function app can verify the request comes from Telegram:

1. Generate a secure random string (e.g., a UUID or random character sequence).
2. Set the `TELEGRAM_WEBHOOK_SECRET` App Setting in your Function App to this random string.
3. Register the webhook with Telegram by passing the `secret_token` parameter:
   ```bash
   curl -F "url=https://<your-function-app-name>.azurewebsites.net/api/telegram-webhook" \
        -F "secret_token=<YOUR_SECURE_RANDOM_TOKEN>" \
        https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
   ```

#### 5. Removing the Webhook (Switching back to Option 1)
If you want to stop using Azure Functions and switch back to the local/VPS polling bot (Option 1), you must delete the webhook from Telegram's servers. Run this command:
```bash
curl https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook
```

---

## Option 3: Google Cloud Run (Serverless Webhook)

This mode deploys the bot to Google Cloud Run, a serverless platform that automatically scales containers to zero when they are idle.

### Prerequisites
- [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- A Google Cloud Project with billing enabled.

### Deployment

1. **First-time deployment** (deploys the service and registers a dummy webhook to pass startup health checks):
   ```bash
   gcloud run deploy transcribe-bot \
     --source . \
     --region <GCP_REGION> \
     --allow-unauthenticated \
     --set-env-vars TELEGRAM_BOT_TOKEN="<TELEGRAM_BOT_TOKEN>",OPENAI_API_KEY="<OPENAI_API_KEY>",WEBHOOK_URL="https://example.com"
   ```
   *(Note: If you receive an error about a missing default Compute service account, use the `--build-service-account` and `--service-account` flags to specify custom service accounts.)*

2. **Retrieve the Service URL** output by the command (e.g. `https://transcribe-bot-xxxxx.a.run.app`).

3. **Update WEBHOOK_URL** to set the real service URL. This will trigger a rolling update and register the webhook with Telegram:
   ```bash
   gcloud run services update transcribe-bot \
     --region <GCP_REGION> \
     --update-env-vars WEBHOOK_URL="https://transcribe-bot-xxxxx.a.run.app"
   ```

### How to Stop / Pause the Bot

Because Cloud Run charges only for active request processing, when the bot is idle, it consumes 0 resources and generates 0 cost. However, if you want to stop/pause the bot from processing messages entirely, use one of the following methods:

#### Method A: Disable Telegram's Webhook (Recommended)
This tells Telegram to stop forwarding new messages to your Cloud Run URL. The service will naturally scale down to 0 instances and stay inactive:
```bash
curl https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook
```
* **To Resume:** Redeploy or call Telegram's `setWebhook` endpoint to re-register the Cloud Run URL.

#### Method B: Turn off public Ingress
This blocks external traffic (including Telegram) from reaching your Cloud Run service:
```bash
gcloud run services update transcribe-bot \
  --ingress internal \
  --region <GCP_REGION>
```
* **To Resume:** Re-enable external traffic:
  ```bash
  gcloud run services update transcribe-bot --ingress all --region <GCP_REGION>
  ```

#### Method C: Set Maximum Instances to 0
This prevents Cloud Run from starting any container instances, returning a `503 Service Unavailable` error to incoming requests:
```bash
gcloud run services update transcribe-bot \
  --max-instances 0 \
  --region <GCP_REGION>
```
* **To Resume:** Reset the maximum instance limit (e.g., 10 or more):
  ```bash
  gcloud run services update transcribe-bot --max-instances 10 --region <GCP_REGION>
  ```

#### Method D: Delete the Service
If you want to permanently remove the deployment:
```bash
gcloud run services delete transcribe-bot \
  --region <GCP_REGION>
```