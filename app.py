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

# Voice recording interface
st.subheader("🎤 Voice Input")

# Option 1: Text input for testing
st.markdown("**Option 1: Type your question**")
text_input = st.text_input("Enter your business question:", placeholder="e.g., What product sold best last quarter?")

# Option 2: Audio recording with HTML5
st.markdown("**Option 2: Record audio directly in browser**")

# HTML5 audio recorder
audio_recorder_html = """
<div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin: 10px 0;">
    <h4>🎙️ Browser Audio Recorder</h4>
    <p>Click the button below to record your question:</p>
    <button id="recordButton" style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">🎤 Start Recording</button>
    <button id="stopButton" style="background-color: #f44336; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; display: none;">⏹️ Stop Recording</button>
    <div id="status" style="margin-top: 10px; font-weight: bold;"></div>
    <audio id="audioPlayback" controls style="margin-top: 10px; display: none;"></audio>
    <button id="uploadButton" style="background-color: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px; display: none;">📤 Process Audio</button>
</div>

<script>
let mediaRecorder;
let audioChunks = [];
let audioBlob;

document.getElementById('recordButton').addEventListener('click', async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = () => {
            audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            document.getElementById('audioPlayback').src = audioUrl;
            document.getElementById('audioPlayback').style.display = 'block';
            document.getElementById('uploadButton').style.display = 'inline-block';
        };
        
        mediaRecorder.start();
        document.getElementById('recordButton').style.display = 'none';
        document.getElementById('stopButton').style.display = 'inline-block';
        document.getElementById('status').textContent = '🔴 Recording... Speak now!';
        
    } catch (error) {
        document.getElementById('status').textContent = '❌ Error: ' + error.message;
    }
});

document.getElementById('stopButton').addEventListener('click', () => {
    mediaRecorder.stop();
    document.getElementById('recordButton').style.display = 'inline-block';
    document.getElementById('stopButton').style.display = 'none';
    document.getElementById('status').textContent = '✅ Recording complete!';
});

document.getElementById('uploadButton').addEventListener('click', () => {
    if (audioBlob) {
        // Convert blob to base64 for Streamlit
        const reader = new FileReader();
        reader.onload = function() {
            const base64Audio = reader.result.split(',')[1];
            // Send to Streamlit via session state
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                value: base64Audio
            }, '*');
        };
        reader.readAsDataURL(audioBlob);
        document.getElementById('status').textContent = '📤 Processing audio...';
    }
});
</script>
"""

st.components.v1.html(audio_recorder_html, height=300)

# Option 3: File upload as fallback
st.markdown("**Option 3: Upload audio file**")
uploaded_file = st.file_uploader("Upload an audio file (WAV, MP3):", type=['wav', 'mp3'])

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
