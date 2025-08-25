#python3 -m venv env
#source env/bin/activate
#sudo apt install ffmpeg
#pip install python-telegram-bot openai ocrmypdf
#(optionnel pour voix locales) pip install pydub openai-whisper
#ffmpeg -i input.opus -ar 16000 -ac 1 output.wav

import os
import tempfile
import logging
from pathlib import Path
from urllib.parse import urlparse
from io import BytesIO

import ocrmypdf

from openai import OpenAI

from telegram import Update, InputFile
from telegram.constants import MessageLimit
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ──────────────────────────────────────────────────────────────────────────────
# Config & clients
# ──────────────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN manquant dans l'environnement.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY manquant dans l'environnement.")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def split_text(text: str, limit: int = MessageLimit.MAX_TEXT_LENGTH - 50) -> list[str]:
    """
    Coupe le texte proprement pour respecter la limite Telegram.
    Privilégie coupures sur \n\n, puis \n, puis espace.
    """
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts

async def send_text_safely(update: Update, text: str):
    """
    Envoie 'text' en plusieurs messages si nécessaire.
    Si c'est très long (beaucoup de fragments), bascule en fichier .txt.
    """
    chunks = split_text(text)
    # S'il y a > 6 morceaux, on préfère envoyer en fichier pour éviter le spam.
    if len(chunks) > 6:
        buf = BytesIO(text.encode("utf-8"))
        buf.name = "transcription.txt"
        await update.message.reply_document(
            document=buf,
            caption="📝 Transcription complète en pièce jointe"
        )
        return

    if len(chunks) == 1:
        await update.message.reply_text(chunks[0])
        return

    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        header = f"📝 Transcription (partie {i}/{total})\n"
        # S'assurer que l'entête + chunk ne dépasse pas la limite :
        remaining = MessageLimit.MAX_TEXT_LENGTH - len(header)
        if len(chunk) > remaining:
            subparts = split_text(chunk, limit=remaining)
            for j, sp in enumerate(subparts, 1):
                prefix = header if j == 1 else ""
                await update.message.reply_text(prefix + sp)
        else:
            await update.message.reply_text(header + chunk)

# ──────────────────────────────────────────────────────────────────────────────
# OpenAI calls
# ──────────────────────────────────────────────────────────────────────────────
def transcribe_online(file_path: str) -> str:
    """
    Envoie le fichier audio à l'API OpenAI (Whisper).
    """
    with open(file_path, "rb") as audio_file:
        resp = client.audio.transcriptions.create(
            model="whisper-1",  # ou "gpt-4o-transcribe" si activé sur votre compte
            file=audio_file
        )
        return resp.text

def format_text_with_gpt(transcription: str) -> str:
    """
    Formate le texte (ponctuation, paragraphes). Ne traduit pas.
    """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # plus rapide/économique; remplacez par "gpt-4" si souhaité
        messages=[
            {"role": "system", "content": "You are a professional text formatter. Format text only, do not translate."},
            {"role": "user", "content": transcription},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content

# ──────────────────────────────────────────────────────────────────────────────
# Bot handlers
# ──────────────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Envoyez-moi un message vocal et je vous le transcris 🙂")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Télécharge l'audio, transcrit, formate, et renvoie en respectant la limite Telegram.
    """
    voice_or_audio = update.message.voice or update.message.audio
    if not voice_or_audio:
        await update.message.reply_text("❌ Je n'ai pas trouvé de voix/audio dans ce message.")
        return

    file = await context.bot.get_file(voice_or_audio.file_id)
    filename = os.path.basename(urlparse(file.file_path).path)
    ext = Path(filename).suffix or ".ogg"  # fallback

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        temp_in_path = tmp.name
    try:
        await file.download_to_drive(temp_in_path)
        await update.message.reply_text("⏳ Transcription en cours...")
        transcription = transcribe_online(temp_in_path)

        await update.message.reply_text("🛠️ Mise en forme du texte...")
        formatted_text = format_text_with_gpt(transcription)

        # Envoi sécurisé (chunking ou pièce jointe)
        await send_text_safely(update, f"📝 Transcription :\n{formatted_text}")

    finally:
        try:
            if os.path.exists(temp_in_path):
                os.remove(temp_in_path)
        except Exception:
            logger.warning("Impossible de supprimer le fichier temporaire: %s", temp_in_path)

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    OCR pour PDF et renvoi du PDF OCRisé.
    """
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ Aucun document reçu.")
        return
    # Vérif extension
    if not doc.mime_type or "pdf" not in doc.mime_type.lower():
        await update.message.reply_text("❌ Seuls les fichiers PDF sont supportés pour l'OCR.")
        return

    file = await context.bot.get_file(doc.file_id)
    filename = os.path.basename(urlparse(file.file_path).path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_in:
        temp_pdf_path = temp_in.name
    await file.download_to_drive(temp_pdf_path)

    orig_name = doc.file_name if getattr(doc, "file_name", None) else filename
    ocr_name = (orig_name[:-4] + " (ocr).pdf") if orig_name.lower().endswith(".pdf") else (orig_name + " (ocr).pdf")
    temp_out_pdf_path = os.path.join(os.path.dirname(temp_pdf_path), ocr_name)

    try:
        await update.message.reply_text("⏳ OCR en cours...")
        try:
            # Vous pouvez ajouter des options (lang=...) si besoin :
            # ocrmypdf.ocr(temp_pdf_path, temp_out_pdf_path, language="fra")
            ocrmypdf.ocr(temp_pdf_path, temp_out_pdf_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Échec de l'OCR : {e}")
            return

        with open(temp_out_pdf_path, "rb") as out_pdf:
            await update.message.reply_document(document=InputFile(out_pdf, filename=ocr_name))
    finally:
        for p in (temp_pdf_path, temp_out_pdf_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                logger.warning("Impossible de supprimer le fichier temporaire: %s", p)

# ──────────────────────────────────────────────────────────────────────────────
# Error handler (évite les plantages et informe l’utilisateur)
# ──────────────────────────────────────────────────────────────────────────────
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    logger.exception("Unhandled exception: %s", err)
    try:
        if hasattr(update, "effective_message") and update.effective_message:
            if isinstance(err, BadRequest) and "Message is too long" in str(err):
                await update.effective_message.reply_text(
                    "⚠️ Le message était trop long : j’envoie en plusieurs parties / en fichier."
                )
            else:
                await update.effective_message.reply_text("⚠️ Une erreur s’est produite. J’essaie de continuer.")
    except Exception:
        # Éviter de boucler si l’erreur vient aussi de reply_text
        pass

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_error_handler(on_error)

    app.run_polling()

if __name__ == "__main__":
    main()
