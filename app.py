import streamlit as st
import streamlit.components.v1 as components
import tempfile
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import json
import base64
import io
import requests

# Load environment variables
load_dotenv()

# Azure keys from Streamlit secrets
speech_key = st.secrets["AZURE_SPEECH_KEY"]
speech_region = st.secrets["AZURE_SPEECH_REGION"]
openai_key = st.secrets["AZURE_OPENAI_KEY"]
openai_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
deployment_name = st.secrets["AZURE_DEPLOYMENT_NAME"]

# Optional ElevenLabs
eleven_api_key = st.secrets.get("ELEVENLABS_API_KEY")
eleven_voice_id = st.secrets.get("ELEVENLABS_VOICE_ID")

# Azure OpenAI config
client = AzureOpenAI(
    api_key=openai_key,
    api_version="2025-01-01-preview",
    azure_endpoint=openai_endpoint
)

# UI Layout
st.set_page_config(page_title="Voice AI for Business", layout="centered")
st.title("🧠 Unieros Digital Voice AI for Small Business")
st.info("Use your microphone to ask a question. We'll respond with a smart answer and a realistic voice.")

# Google Sheets setup (optional)
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(creds_dict), scope)
    client_gsheets = gspread.authorize(creds)
    
    # Data loading
    sheet = client_gsheets.open("BusinessProducts").get_worksheet(1)
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    st.success("✅ Connected to Google Sheets")
except Exception as e:
    st.warning(f"⚠️ Google Sheets not configured: {str(e)}. Using sample data.")
    # Sample data if Google Sheets is not available
    df = pd.DataFrame({
        'Product': ['Premium Widget', 'Standard Widget', 'Budget Widget'],
        'Sales': [150, 300, 200],
        'Revenue': [4500, 6000, 2000],
        'Profit_Margin': [0.25, 0.20, 0.10]
    })

###############################################################################
# Voice input (reliable): Streamlit mic + Azure Speech-to-Text
###############################################################################

st.subheader("🎤 Ask by voice")
# Support older Streamlit versions without st.audio_input
audio_bytes = None
if hasattr(st, "audio_input"):
    audio_rec = st.audio_input("Record your question and release to stop")
    if audio_rec is not None:
        audio_bytes = audio_rec.getvalue()
else:
    uploaded = st.file_uploader("Upload a short audio clip (wav/mp3/m4a)", type=["wav", "mp3", "m4a"]) 
    if uploaded is not None:
        audio_bytes = uploaded.getvalue()

###############################################################################
# Transcription with Azure Speech (if audio provided), or text input fallback
###############################################################################

# Text input as fallback
user_input = st.text_input("Or type your question here:", placeholder="e.g., What product sold best last quarter?")

# Determine transcript
transcript = None

if audio_bytes is not None:
    try:
        # Save recorded audio (WAV) to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf:
            tf.write(audio_bytes)
            wav_path = tf.name

        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        st.caption("Transcribing...")
        res = recognizer.recognize_once_async().get()
        if res.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript = res.text
        elif res.reason == speechsdk.ResultReason.NoMatch:
            st.warning("Didn't catch that. Please try again.")
        else:
            st.error(f"Speech recognition error: {res.reason}")
    except Exception as e:
        st.error(f"Audio transcription failed: {e}")
    finally:
        try:
            os.remove(wav_path)
        except Exception:
            pass
elif user_input:
    transcript = user_input

if transcript:
    st.subheader("🔊 You said:")
    st.write(transcript)
    
    # Generate response using Azure OpenAI with business data
    prompt = f"You are a smart voice assistant for small business owners. Here is your customer data: {df.to_markdown(index=False)}. Respond with a short voice-friendly answer first, then provide extra details after if needed. Here is the query: {transcript}"
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        reply = response.choices[0].message.content
        st.subheader("🤖 AI Response:")
        st.write(reply)

        # TTS provider choice
        st.markdown("**Voice provider**")
        tts_provider = st.radio(
            "Choose voice engine",
            options=["Azure", "ElevenLabs"],
            index=0,
            horizontal=True,
        )

        # Clean markdown for TTS
        clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', reply)

        if tts_provider == "ElevenLabs":
            if not (eleven_api_key and eleven_voice_id):
                st.warning("ElevenLabs not configured. Add ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to secrets.")
            else:
                try:
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}"
                    headers = {
                        "xi-api-key": eleven_api_key,
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "text": clean_text,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                    }
                    r = requests.post(url, headers=headers, json=payload, timeout=60)
                    if r.status_code == 200:
                        audio_bytes = bytes(r.content)
                        st.audio(audio_bytes, format="audio/mp3")
                    else:
                        st.error(f"ElevenLabs TTS error: {r.status_code} {r.text[:200]}")
                except Exception as e:
                    st.error(f"ElevenLabs TTS failed: {e}")
        else:
            # Azure Speech TTS and play in browser
            try:
                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
                speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
                )
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
                synth_res = synthesizer.speak_text_async(clean_text).get()
                if synth_res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    audio_bytes = bytes(synth_res.audio_data)
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.info("Text-to-speech couldn't play. Showing text response above.")
            except Exception:
                st.info("💡 Voice synthesis not available in this environment; showing text response above.")
            
    except Exception as e:
        st.error(f"Error generating response: {e}")

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)