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

# HTML5 Audio Recorder Component
def audio_recorder():
    components.html("""
    <div style="text-align: center; padding: 20px;">
        <button id="recordButton" style="background-color: #4CAF50; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin: 10px;">🎤 Start Recording</button>
        <button id="stopButton" style="background-color: #f44336; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin: 10px;" disabled>⏹️ Stop Recording</button>
        <div id="status" style="margin: 10px; font-weight: bold; color: #666;"></div>
        <audio id="audioPlayback" controls style="margin: 10px; width: 100%; max-width: 400px;"></audio>
    </div>
    <script>
        let mediaRecorder;
        let audioChunks = [];
        
        document.getElementById('recordButton').onclick = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, {type: 'audio/wav'});
                    const audioUrl = URL.createObjectURL(audioBlob);
                    document.getElementById('audioPlayback').src = audioUrl;
                    
                    // Send to Streamlit
                    const reader = new FileReader();
                    reader.onload = () => {
                        const base64Audio = reader.result.split(',')[1];
                        window.parent.postMessage({
                            type: 'audio_data',
                            data: base64Audio
                        }, '*');
                    };
                    reader.readAsDataURL(audioBlob);
                };
                
                mediaRecorder.start();
                document.getElementById('recordButton').disabled = true;
                document.getElementById('stopButton').disabled = false;
                document.getElementById('status').textContent = '🎤 Recording... Speak now!';
                document.getElementById('status').style.color = '#4CAF50';
            } catch (error) {
                document.getElementById('status').textContent = '❌ Error: ' + error.message;
                document.getElementById('status').style.color = '#f44336';
            }
        };
        
        document.getElementById('stopButton').onclick = () => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                document.getElementById('recordButton').disabled = false;
                document.getElementById('stopButton').disabled = true;
                document.getElementById('status').textContent = '✅ Recording stopped. Processing...';
                document.getElementById('status').style.color = '#2196F3';
            }
        };
    </script>
    """, height=200)

# Display the audio recorder
audio_recorder()

# Handle audio data from JavaScript
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = None

# Listen for audio data from JavaScript
try:
    # This would normally be handled by Streamlit's component communication
    # For now, we'll use a file uploader as a fallback
    uploaded_audio = st.file_uploader("Or upload an audio file (WAV, MP3)", type=['wav', 'mp3'])
    
    if uploaded_audio is not None:
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(uploaded_audio.getvalue())
            audio_path = tmp_file.name
        
        # Transcribe using Azure Speech
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
        
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        result = speech_recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript = result.text
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
            
            # Synthesize with Azure Speech TTS
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
            # Remove markdown syntax (e.g. **bold**, *italic*)
            clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', reply)
            synthesizer.speak_text_async(clean_text)
            
        else:
            st.warning("Could not understand the audio. Please try again.")
        
        # Clean up temp file
        try:
            os.unlink(audio_path)
        except:
            pass

except Exception as e:
    st.error(f"Error processing audio: {e}")

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)