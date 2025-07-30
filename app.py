import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase
import tempfile
from openai import AzureOpenAI
import elevenlabs
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
elevenlabs.set_api_key(st.secrets["ELEVENLABS_API_KEY"])

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
    st.warning(f"⚠️ Google Sheets not configured: {str(e)}. Using sample data.")
    # Sample data if Google Sheets is not available
    df = pd.DataFrame({
        'Product': ['Premium Widget', 'Standard Widget', 'Budget Widget'],
        'Sales': [150, 300, 200],
        'Revenue': [4500, 6000, 2000],
        'Profit_Margin': [0.25, 0.20, 0.10]
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

# Handle transcription & response - simplified like the working version
if ctx.audio_processor and ctx.audio_processor.frames:
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
    
    # Show what data is being analyzed
    st.subheader("📊 Data being analyzed:")
    st.write(f"Using {'Google Sheets' if 'gcp_service_account' in st.secrets else 'sample'} data")
    st.dataframe(df)
    
    # Generate response using Azure OpenAI with business data
    try:
        data_summary = df.to_markdown(index=False)
    except ImportError:
        # Fallback if tabulate is not available
        data_summary = df.to_string(index=False)
    
    # Create a more specific prompt for business analysis
    prompt = f"""You are a smart business analyst assistant. Analyze the following business data and provide insights:

Business Data:
{data_summary}

User Question: {transcript}

Instructions:
1. If the user asks about sales, revenue, products, or business performance, analyze the data and provide specific insights
2. If the user asks about trends, compare the data points and identify patterns
3. If the user asks for recommendations, suggest improvements based on the data
4. If the question is not related to the business data, provide a helpful general business response
5. Keep your response conversational and voice-friendly (under 2 sentences for the main answer)
6. If using sample data (Widget A, B, C), mention that real business data would provide better insights

Please respond:"""
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    reply = response.choices[0].message.content
    st.subheader("🤖 AI Response:")
    st.write(reply)

    # Synthesize with ElevenLabs
    try:
        audio_stream = elevenlabs.generate(text=reply, voice="Rachel", model="eleven_multilingual_v1")
        elevenlabs.play(audio_stream)
    except Exception as e:
        st.error(f"❌ Voice generation failed: {str(e)}")

    # Reset the frames
    ctx.audio_processor.frames.clear()

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)