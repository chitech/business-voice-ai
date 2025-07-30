import streamlit as st
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase
import tempfile
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

# Load environment variables
load_dotenv()

# Set ElevenLabs API Key
voice_id = st.secrets["ELEVENLABS_VOICE_ID"]

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

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
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

    # Generate response using Azure OpenAI
    prompt = f"You are a helpful assistant for small business owners. Respond briefly and clearly. Question: {transcript}"
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    reply = response.choices[0].message.content
    st.subheader("🤖 AI Response:")
    st.write(reply)

    # Synthesize with ElevenLabs
    elevenlabs_client = ElevenLabs(api_key=st.secrets["ELEVENLABS_API_KEY"])
    audio_stream = elevenlabs_client.generate(
        text=reply,
        voice=st.secrets["ELEVENLABS_VOICE_ID"],
        model="eleven_multilingual_v1",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8)
    )
    audio_bytes = b"".join(audio_stream)
    st.audio(audio_bytes, format="audio/mp3")

    # Reset the frames
    ctx.audio_processor.frames.clear()
