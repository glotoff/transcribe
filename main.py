#python3 -m venv env
#source env/bin/activate
#sudo apt install ffmpeg
#pip install openai-whisper
#pip install pydub
#ffmpeg -i input.opus -ar 16000 -ac 1 output.wav

from pydub import AudioSegment
import whisper
import os
import jsonify
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def convert(input_file):

    # Convert Opus to WAV (16kHz mono for Whisper)
    audio = AudioSegment.from_file(input_file, format="ogg")
    audio = audio.set_frame_rate(16000).set_channels(1)  # Optimize for Whisper
    output_file ="output.wav" 
    audio.export(output_file, format="wav")
    return output_file
    #print("Conversion complete: output.wav")

def transcribe():
    model = whisper.load_model("base")
    result = model.transcribe("output.wav")
    print(result["text"])

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
        messages=[{"role": "system", "content": ""},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

#output_file = convert("input.opus")
#transcription = transcribe_online(output_file)

transcription = transcribe_online("input.ogg")

test = format_text_with_gpt(transcription)
print(test)
#test = format_text_with_gpt(" Salut Lilia, j'espère que tu vas bien. Écoute, nous on a reçu cette semaine le calendrier pour l'année prochaine à Mermoz. Je ne sais pas si vous, vous avez déjà aussi le calendrier. J'étais en train de me dire, la semaine d'octobre, les filles pourraient partir peut-être toutes les deux à Bakou pour une semaine pour faire un stage dans un laboratoire. Puisque tu sais, le frère d'Azad est chirurgien et donc je pense que pour lui ce serait facile de trouver")
