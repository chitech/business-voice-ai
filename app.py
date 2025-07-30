import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase
import tempfile
from openai import AzureOpenAI
from elevenlabs import generate, play, set_api_key
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import json
import wave
import numpy as np

# Load environment variables
load_dotenv()

# Set ElevenLabs API Key
set_api_key(st.secrets["ELEVENLABS_API_KEY"])

# Azure OpenAI config
client = AzureOpenAI(
    api_key=st.secrets["AZURE_OPENAI_KEY"],
    api_version="2025-01-01-preview",
    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"]
)

deployment_name = st.secrets["AZURE_DEPLOYMENT_NAME"]

# UI Layout
st.set_page_config(page_title="Voice AI for Business", layout="centered")
st.title("🧠 Voice AI for Small Business")
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
    st.warning("⚠️ Google Sheets not configured. Using sample data.")
    # Sample data if Google Sheets is not available
    df = pd.DataFrame({
        'Product': ['Widget A', 'Widget B', 'Widget C'],
        'Sales': [100, 150, 200],
        'Revenue': [1000, 1500, 2000]
    })

# Audio Processor
class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.frames = []

    def recv(self, frame):
        self.frames.append(frame.to_ndarray().tobytes())
        return frame

# Stream audio
ctx = webrtc_streamer(key="speech", audio_processor_factory=AudioProcessor, media_stream_constraints={"audio": True, "video": False})

# Handle transcription & response
if ctx.state.playing:
    st.info("Recording... speak now")

if ctx.audio_processor and ctx.audio_processor.frames:
    st.success("Processing your voice...")
    audio_bytes = b"".join(ctx.audio_processor.frames)

    # Convert raw audio bytes to proper WAV format
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        # Create a proper WAV file
        with wave.open(f.name, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(16000)  # 16kHz sample rate
            wav_file.writeframes(audio_bytes)
        audio_path = f.name

    # Transcribe using Azure Speech
    speech_key = st.secrets["AZURE_SPEECH_KEY"]
    speech_region = st.secrets["AZURE_SPEECH_REGION"]

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = speech_recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        transcript = result.text
    else:
        transcript = "Sorry, I couldn't understand the audio."

    st.subheader("🔊 You said:")
    st.write(transcript)

    # Generate response using Azure OpenAI with business data
    prompt = f"You are a smart voice assistant for small business owners. Here is your customer data: {df.to_markdown(index=False)}. Respond with a short voice-friendly answer first, then provide extra details after if needed. Here is the query: {transcript}"
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    reply = response.choices[0].message.content
    st.subheader("🤖 AI Response:")
    st.write(reply)

    # Synthesize with ElevenLabs
    audio_stream = generate(text=reply, voice="Rachel", model="eleven_multilingual_v1")
    play(audio_stream)

    # Reset the frames
    ctx.audio_processor.frames.clear()

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)