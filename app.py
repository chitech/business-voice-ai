import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase
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
import wave
import numpy as np

# Load environment variables
load_dotenv()

# Azure keys from Streamlit secrets
speech_key = st.secrets["AZURE_SPEECH_KEY"]
speech_region = st.secrets["AZURE_SPEECH_REGION"]
openai_key = st.secrets["AZURE_OPENAI_KEY"]
openai_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
deployment_name = st.secrets["AZURE_DEPLOYMENT_NAME"]

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

# Streamlit layout: columns for voice and data
col1, col2 = st.columns([1, 2])
with col1:
    if st.button("🎤 Click to Speak"):
        audio_config = speechsdk.AudioConfig(use_default_microphone=True)
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        with st.spinner("🟢 Listening..."):
            result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            st.subheader("🔊 You said:")
            st.write(result.text)

            prompt = f"You are a smart voice assistant for small business owners. Here is your customer data: {df.to_markdown(index=False)}. Respond with a short voice-friendly answer first, then provide extra details after if needed. Here is the query: {result.text}"
            try:
                response = client.chat.completions.create(
                    model=deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                st.markdown("### 🤖 AI Response:")
                st.markdown(f"""
                <div style='padding: 1em; background-color: #f9f9f9; border-left: 5px solid #4CAF50;'>
                    {response.choices[0].message.content}
                </div>
                """, unsafe_allow_html=True)
                speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
                response_text = response.choices[0].message.content
                # Remove markdown syntax (e.g. **bold**, *italic*)
                clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', response_text)
                synthesizer.speak_text_async(clean_text)
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
        else:
            st.warning("Didn't catch that. Please try again.")
with col2:
    st.subheader("📊 Sample Product Data")
    st.dataframe(df)