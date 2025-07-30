import streamlit as st
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

# Load environment variables
load_dotenv()

# Azure keys
speech_key = st.secrets["AZURE_SPEECH_KEY"]
speech_region = st.secrets["AZURE_SPEECH_REGION"]
openai_key = st.secrets["AZURE_OPENAI_KEY"]
openai_endpoint = st.secrets["AZURE_OPENAI_ENDPOINT"]
deployment_name = st.secrets["AZURE_DEPLOYMENT_NAME"]

# OpenAI client
client = AzureOpenAI(
    api_key=openai_key,
    api_version="2025-01-01-preview",
    azure_endpoint=openai_endpoint
)

st.set_page_config(page_title="Voice AI for Business", layout="centered")
# Custom business-friendly header
st.markdown("""
    <div style='text-align: center; padding-bottom: 10px;'>
        <h1 style='color: #2c3e50;'>🧠 Business Voice AI</h1>
        <h4 style='color: #7f8c8d;'>Ask your question and get instant, voice-powered business insights.</h4>
    </div>
""", unsafe_allow_html=True)

# Hide Streamlit's default header/footer
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# Helpful example prompt
st.markdown("💼 Example: Try asking 'What product sold best last quarter?'")

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

# Streamlit layout: columns for voice and data
col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("🎤 Voice Input")
    
    # Option 1: Text input for testing
    st.markdown("**Option 1: Type your question**")
    text_input = st.text_input("Enter your business question:", placeholder="e.g., What product sold best last quarter?")
    
    # Option 2: Audio file upload
    st.markdown("**Option 2: Upload audio file**")
    uploaded_file = st.file_uploader("Upload an audio file (WAV, MP3)", type=['wav', 'mp3'])
    
    if text_input:
        # Process text input
        st.subheader("🔊 You said:")
        st.write(text_input)
        
        prompt = f"You are a smart voice assistant for small business owners. Here is your customer data: {df.to_markdown(index=False)}. Respond with a short voice-friendly answer first, then provide extra details after if needed. Here is the query: {text_input}"
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
            
            # Text-to-speech response
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
            response_text = response.choices[0].message.content
            # Remove markdown syntax (e.g. **bold**, *italic*)
            clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', response_text)
            synthesizer.speak_text_async(clean_text)
            
        except Exception as e:
            st.error(f"Error generating response: {e}")
    
    elif uploaded_file is not None:
        # Process uploaded audio file
        st.audio(uploaded_file, format="audio/wav")
        
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_audio_path = tmp_file.name
        
        try:
            # Azure Speech recognition from file
            audio_config = speechsdk.AudioConfig(filename=temp_audio_path)
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            
            with st.spinner("🟢 Processing your speech..."):
                result = recognizer.recognize_once()
            
            # Clean up temp file
            os.unlink(temp_audio_path)
            
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
                    
                    # Text-to-speech response
                    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
                    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
                    response_text = response.choices[0].message.content
                    # Remove markdown syntax (e.g. **bold**, *italic*)
                    clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', response_text)
                    synthesizer.speak_text_async(clean_text)
                    
                except Exception as e:
                    st.error(f"Error generating response: {e}")
            else:
                st.warning("Could not recognize speech. Please try again.")
                
        except Exception as e:
            st.error(f"Error processing audio: {e}")
            # Clean up temp file if it exists
            if 'temp_audio_path' in locals():
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass

with col2:
    st.subheader("📊 Sample Product Data")
    st.dataframe(df)