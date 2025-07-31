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

# Browser-based Speech Recognition Component
def speech_recognition_component():
    components.html("""
    <div style="text-align: center; padding: 20px;">
        <button id="startBtn" style="background-color: #4CAF50; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin: 10px;">🎤 Start Voice Recognition</button>
        <button id="stopBtn" style="background-color: #f44336; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin: 10px;" disabled>⏹️ Stop</button>
        <div id="status" style="margin: 10px; font-weight: bold; color: #666;">Click Start to begin voice recognition</div>
        <div id="transcript" style="margin: 10px; padding: 10px; background-color: #f0f0f0; border-radius: 5px; min-height: 50px;"></div>
    </div>
    <script>
        let recognition;
        let isListening = false;
        
        // Check if browser supports speech recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';
            
            recognition.onstart = () => {
                isListening = true;
                document.getElementById('status').textContent = '🎤 Listening... Speak now!';
                document.getElementById('status').style.color = '#4CAF50';
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
            };
            
            recognition.onresult = (event) => {
                let finalTranscript = '';
                let interimTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }
                
                document.getElementById('transcript').innerHTML = 
                    '<strong>Final:</strong> ' + finalTranscript + '<br>' +
                    '<em>Interim:</em> ' + interimTranscript;
                
                // Send final transcript to Streamlit
                if (finalTranscript) {
                    window.parent.postMessage({
                        type: 'speech_result',
                        data: finalTranscript
                    }, '*');
                }
            };
            
            recognition.onerror = (event) => {
                document.getElementById('status').textContent = '❌ Error: ' + event.error;
                document.getElementById('status').style.color = '#f44336';
                isListening = false;
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
            };
            
            recognition.onend = () => {
                isListening = false;
                document.getElementById('status').textContent = '✅ Recognition stopped';
                document.getElementById('status').style.color = '#2196F3';
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
            };
            
            document.getElementById('startBtn').onclick = () => {
                if (!isListening) {
                    recognition.start();
                }
            };
            
            document.getElementById('stopBtn').onclick = () => {
                if (isListening) {
                    recognition.stop();
                }
            };
        } else {
            document.getElementById('status').textContent = '❌ Speech recognition not supported in this browser';
            document.getElementById('status').style.color = '#f44336';
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = true;
        }
    </script>
    """, height=300)

# Display the speech recognition component
speech_recognition_component()

# Handle speech results
if 'speech_result' not in st.session_state:
    st.session_state.speech_result = None

# Text input as fallback
user_input = st.text_input("Or type your question here:", placeholder="e.g., What product sold best last quarter?")

# Process speech or text input
transcript = None
if st.session_state.speech_result:
    transcript = st.session_state.speech_result
    st.session_state.speech_result = None
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
        
        # Synthesize with Azure Speech TTS (if available)
        try:
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
            # Remove markdown syntax (e.g. **bold**, *italic*)
            clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', reply)
            synthesizer.speak_text_async(clean_text)
        except Exception as e:
            st.info("💡 Voice synthesis not available in this environment, but you can read the response above.")
            
    except Exception as e:
        st.error(f"Error generating response: {e}")

# Display business data
st.subheader("📊 Sample Product Data")
st.dataframe(df)