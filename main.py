import os
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def transcribe_online(file_path):
    # Send to Google Gemini 3.5 Transcribe
    client = genai.Client(api_key=GEMINI_API_KEY)

    uploaded_file = client.files.upload(
        file=file_path,
        config=types.UploadFileConfig(mime_type="audio/ogg"),
    )
    try:
        interaction = client.interactions.create(
            model="gemini-3.5-transcribe",
            input=[
                {
                    "type": "file_data",
                    "file_uri": uploaded_file.uri,
                    "mime_type": "audio/ogg",
                }
            ],
        )
        text = getattr(interaction, "text", None) or getattr(interaction, "output_text", None)
        if not text and hasattr(interaction, "outputs"):
            text = "".join([str(o) for o in interaction.outputs])
        return str(text).strip() if text else ""
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

if __name__ == "__main__":
    audio_path = "input.ogg"
    if os.path.exists(audio_path):
        transcription = transcribe_online(audio_path)
        print("Transcription:")
        print(transcription)
    else:
        print(f"File {audio_path} not found. Please provide an audio file to test.")
