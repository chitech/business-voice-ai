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

# Simple audio recording with HTML
st.subheader("🎤 Voice Input")

# Option 1: Text input for testing
st.markdown("**Option 1: Type your question**")
text_input = st.text_input("Enter your business question:", placeholder="e.g., What product sold best last quarter?")

# Option 2: Audio file upload
st.markdown("**Option 2: Record and upload audio**")
st.markdown("""
<div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin: 10px 0;'>
    <h4>📱 How to record audio:</h4>
    <ol>
        <li>Use your phone's voice memo app</li>
        <li>Record your question clearly</li>
        <li>Save as MP3 or WAV file</li>
        <li>Upload below</li>
    </ol>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload your audio file:", type=['wav', 'mp3'])

if text_input:
    # Process text input
    st.subheader("🔊 You said:")
    st.write(text_input)
    
    # Generate response using Azure OpenAI with business data
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
        
        # Synthesize with Azure Speech TTS
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
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = speechsdk.audio.AudioConfig(filename=temp_audio_path)
        
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        with st.spinner("🟢 Processing your speech..."):
            result = speech_recognizer.recognize_once()
        
        # Clean up temp file
        os.unlink(temp_audio_path)
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            st.subheader("🔊 You said:")
            st.write(result.text)
            
            # Generate response using Azure OpenAI with business data
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
                
                # Synthesize with Azure Speech TTS
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

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)
