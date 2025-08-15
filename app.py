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
from html import escape

# Helper: convert local PNGs to data URIs (so they render inside HTML components)
def _to_data_uri(png_path: str) -> str:
    try:
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""

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
    api_version="2024-10-21",
    azure_endpoint=openai_endpoint
)

# UI Layout
st.set_page_config(page_title="Business AI Voice", layout="centered", page_icon="unieros_digital_logo.png")
# Minimal header (centered title like mock)
st.markdown("<div style='text-align:center'>", unsafe_allow_html=True)
st.markdown("<h1 style='margin: 8px 0 14px 0; color:#ffffff;'>Business AI Voice</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Friendly styles
st.markdown(
    """
    <style>
    /* Global tweaks */
    .block-container {max-width: 900px !important;}
    body {background: #0b0b12; color: #e5e7eb;}
    h1, h2, h3, h4, h5, h6 { color: #ffffff; }
    
    /* Cards */
    .uc-card {
      background: #1a1b23;
      border: 1px solid #242634;
      border-radius: 14px;
      padding: 18px 18px 12px 18px;
      box-shadow: 0 2px 14px rgba(0,0,0,0.35);
      margin-top: 10px;
      margin-bottom: 8px;
      color: #e5e7eb;
    }
    .uc-card a { color: #93c5fd; }
    .uc-card p, .uc-card div, .uc-card span, .uc-card li { color: #e5e7eb; }
    .uc-section-title{font-weight:600; font-size: 1.05rem; margin-bottom: 8px;}
    
    /* Buttons & radio pills */
    .stButton>button { background: linear-gradient(135deg,#4f46e5,#06b6d4); color:#fff; border:0; border-radius:10px; padding:10px 16px; }
    .stButton>button:hover {filter: brightness(1.05);}    
    [data-testid="stRadio"] label { 
      border:1px solid #475569; border-radius:999px; padding:6px 12px; margin-right:6px; cursor:pointer; color:#e5e7eb;
    }
    [data-testid="stRadio"] input:checked + div { color:#0ea5e9; }
    
    /* Audio */
    audio { width: 100%; outline: none; }

    /* Icon row styling */
    .icon-row{ display:flex; align-items:center; justify-content:center; gap:40px; margin: 8px 0 14px 0; }
    .icon-row img{ height: 44px; width: 44px; }
    .wave-svg path{ stroke:#38bdf8; }

    /* Large circular mic visual */
    .big-mic{ display:flex; align-items:center; justify-content:center; margin: 18px auto 6px auto; }
    .big-mic .ring{ height: 96px; width: 96px; border-radius: 999px; background: radial-gradient(circle at 30% 30%, rgba(56,189,248,0.35), rgba(56,189,248,0.06)); border: 2px solid #38bdf8; display:flex; align-items:center; justify-content:center; }
    .big-mic img{ height: 44px; width: 44px; }
    
    /* Subheaders spacing */
    .stMarkdown h3, .stMarkdown h2 { margin-top: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Simple icon row under title (mic, waveform, audio) using embedded data URIs
mic_uri = _to_data_uri("microphone.png")
audio_uri = _to_data_uri("audio.png")
icon_container = f"""
<div class='icon-row'>
  {f"<img src='{mic_uri}' alt='mic' />" if mic_uri else ''}
  <svg class='wave-svg' width='48' height='44' viewBox='0 0 120 44' fill='none' xmlns='http://www.w3.org/2000/svg'>
    <path d='M2 22 C10 22, 10 10, 18 10 S26 34, 34 34 S42 10, 50 10 S58 34, 66 34 S74 10, 82 10 S90 34, 98 34 S106 22, 114 22' stroke-width='4' stroke-linecap='round'/>
  </svg>
  {f"<img src='{audio_uri}' alt='audio' />" if audio_uri else ''}
 </div>
"""
components.html(icon_container, height=70)

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
    st.success("Connected to Google Sheets")
except Exception as e:
    st.warning(f"Google Sheets not configured: {str(e)}. Using sample data.")
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

st.markdown('<div class="uc-card">', unsafe_allow_html=True)
# Support older Streamlit versions without st.audio_input
audio_bytes = None
if hasattr(st, "audio_input"):
    # Large circular mic visual above the recorder (decorative)
    mic_uri2 = mic_uri or _to_data_uri("microphone.png")
    st.markdown("<div class='big-mic'><div class='ring'>" +
                (f"<img src='{mic_uri2}' alt='mic'/>" if mic_uri2 else "") +
                "</div></div>", unsafe_allow_html=True)
    # Recorder control (label kept minimal)
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
st.markdown('</div>', unsafe_allow_html=True)

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

if transcript and transcript.strip():
    # Centered large question like mock
    st.markdown("<div style='text-align:center; margin: 10px 0 6px 0;'><div style='font-size:1.25rem; color:#ffffff;'>" +
                escape(transcript) + "</div></div>", unsafe_allow_html=True)
    
    # Generate response using Azure OpenAI with business data
    prompt = f"You are a smart voice assistant for small business owners. Here is your customer data: {df.to_markdown(index=False)}. Respond with a short voice-friendly answer first, then provide extra details after if needed. Here is the query: {transcript}"
    
    try:
        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model=deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
        if not response or not response.choices:
            st.error("No response from Azure OpenAI. Check your deployment name and keys in secrets.")
            st.stop()
        reply = response.choices[0].message.content or ""
        if not reply.strip():
            st.error("Empty reply from model. Verify your Azure OpenAI deployment and quota.")
            st.stop()
        st.markdown('<div class="uc-card">', unsafe_allow_html=True)
        st.write(reply)

        # TTS provider choice with custom audio icon header
        header_col_icon, header_col_text = st.columns([0.08, 0.92])
        with header_col_icon:
            try:
                audio_uri2 = audio_uri or _to_data_uri("audio.png")
                if audio_uri2:
                    st.markdown(f"<img src='{audio_uri2}' width='24' />", unsafe_allow_html=True)
            except Exception:
                pass
        with header_col_text:
            st.markdown("**Listen to response**")

        tts_provider = st.radio(
            "",
            options=["Default", "UnierosVoice"],
            index=0,
            horizontal=True,
        )

        # Clean markdown for TTS
        clean_text = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', reply)

        if tts_provider == "UnierosVoice":
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
                st.info("Voice synthesis not available in this environment; showing text response above.")
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error("Error generating response from Azure OpenAI.")
        st.exception(e)

# Display business data
st.markdown('<div class="uc-card"><div class="uc-section-title">Sample Product Data</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Transparency & Privacy note
st.markdown('<div class="uc-card"><div class="uc-section-title">Transparency & Privacy</div>', unsafe_allow_html=True)
st.markdown(
    "This demo processes your voice in-session to transcribe and synthesize a response. "
    "No voice recordings or personal information are stored by the app."
)
st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.caption("Built for small business owners by Unieros Digital — ask by voice, get answers fast.")