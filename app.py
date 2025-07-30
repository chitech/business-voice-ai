import streamlit as st
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re 
import json
import elevenlabs

load_dotenv()

# Set ElevenLabs API Key
elevenlabs.set_api_key(st.secrets["ELEVENLABS_API_KEY"])

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

# Google Sheets setup
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

User Question: {result.text}

Instructions:
1. If the user asks about sales, revenue, products, or business performance, analyze the data and provide specific insights
2. If the user asks about trends, compare the data points and identify patterns
3. If the user asks for recommendations, suggest improvements based on the data
4. If the question is not related to the business data, provide a helpful general business response
5. Keep your response conversational and voice-friendly (under 2 sentences for the main answer)
6. If using sample data (Widget A, B, C), mention that real business data would provide better insights

Please respond:"""
            
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
                
                # Synthesize with ElevenLabs
                try:
                    audio_stream = elevenlabs.generate(text=response.choices[0].message.content, voice="Rachel", model="eleven_multilingual_v1")
                    elevenlabs.play(audio_stream)
                except Exception as e:
                    st.error(f"❌ Voice generation failed: {str(e)}")
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
        else:
            st.warning("Didn't catch that. Please try again.")
with col2:
    st.subheader("📊 Sample Product Data")
    st.dataframe(df)