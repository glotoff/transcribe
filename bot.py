#python3 -m venv env
#source env/bin/activate
#sudo apt install ffmpeg
#pip install openai-whisper
#pip install pydub
#ffmpeg -i input.opus -ar 16000 -ac 1 output.wav

import os
import tempfile
import logging
from openai import OpenAI
from pydub import AudioSegment
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters  # ✅ Fixed imports

# Load API Keys from Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def transcribe_online(file_path):
    # Send to OpenAI Whisper API
    client = OpenAI(api_key=OPENAI_API_KEY)

    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        #print(f"tr: {response.text}")
        return response.text
        
def format_text_with_gpt(transcription):
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"Format the text, correct errors: {transcription}"

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a professional text formatter."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
    
async def start(update: Update, context):
    """Handles /start command"""
    await update.message.reply_text("Send me a voice message, and I'll transcribe it for you!")

async def handle_voice(update: Update, context):
    """Handles voice messages, transcribes, and formats text"""
    bot = context.bot
    voice = update.message.voice or update.message.audio
    file_id = voice.file_id

    await update.message.reply_text("⏳ Processing your voice message...")

    # Download file from Telegram
    file = await bot.get_file(file_id)
    temp_opus_path = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg").name
    await file.download_to_drive(temp_opus_path)

    # Convert Opus to WAV
    temp_wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    audio = AudioSegment.from_file(temp_opus_path, format="ogg")
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(temp_wav_path, format="wav")

    
    transcription = transcribe_online(temp_wav_path)

    formatted_text = format_text_with_gpt(transcription)
    # Send response
    await update.message.reply_text(f"📝 Transcription:\n{formatted_text}")

def main():
    """Starts the Telegram bot using async API"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))  # ✅ Uses new async filters

    app.run_polling()

if __name__ == "__main__":
    main()
