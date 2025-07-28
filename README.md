# 🧠 Voice AI for Small Business

A real-time voice AI assistant designed specifically for small business owners. This application allows users to speak into their microphone and receive intelligent responses with realistic voice synthesis.

## ✨ Features

- **Real-time Speech Recognition**: Uses Azure Speech Services for accurate speech-to-text conversion
- **AI-Powered Responses**: Leverages Azure OpenAI for intelligent, business-focused responses
- **Natural Voice Synthesis**: ElevenLabs integration for realistic text-to-speech
- **Web-based Interface**: Built with Streamlit for easy access and deployment
- **Real-time Audio Streaming**: WebRTC integration for seamless audio processing

## 🚀 Quick Start

### Prerequisites

- Python 3.10.13 (as specified in runtime.txt)
- Microphone access
- Required API keys (see Setup section)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd BusinessVoiceAI
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the project root with the following variables:
   ```env
   AZURE_OPENAI_KEY=your_azure_openai_key
   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   AZURE_DEPLOYMENT_NAME=your_deployment_name
   AZURE_SPEECH_KEY=your_azure_speech_key
   AZURE_SPEECH_REGION=your_azure_speech_region
   ```

4. **Configure Streamlit secrets**
   
   Create a `.streamlit/secrets.toml` file:
   ```toml
   ELEVENLABS_API_KEY = "your_elevenlabs_api_key"
   ELEVENLABS_VOICE_ID = "your_elevenlabs_voice_id"
   ```

### Running the Application

1. **Start the Streamlit app**
   ```bash
   streamlit run app.py
   ```

2. **Open your browser**
   - Navigate to `http://localhost:8501`
   - Allow microphone access when prompted

3. **Start using the Voice AI**
   - Click the "Start" button to begin recording
   - Speak your business question
   - Listen to the AI's response with natural voice synthesis

## 🔧 API Setup

### Azure OpenAI
1. Create an Azure OpenAI resource
2. Deploy a model (e.g., GPT-4)
3. Get your API key and endpoint from Azure Portal

### Azure Speech Services
1. Create a Speech resource in Azure
2. Get your subscription key and region
3. Configure speech recognition settings

### ElevenLabs
1. Sign up at [ElevenLabs](https://elevenlabs.io)
2. Get your API key
3. Choose or create a voice ID for synthesis

## 📁 Project Structure

```
BusinessVoiceAI/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── runtime.txt        # Python version specification
└── README.md         # This file
```

## 🛠️ Dependencies

- **streamlit**: Web application framework
- **openai>=1.0.0**: Azure OpenAI client
- **azure-cognitiveservices-speech**: Azure Speech Services
- **pandas**: Data manipulation
- **gspread**: Google Sheets integration (optional)
- **oauth2client**: Google authentication
- **python-dotenv**: Environment variable management

## 🎯 Use Cases

This Voice AI assistant is perfect for small business owners who need:
- Quick answers to business questions
- Voice-based interaction for hands-free operation
- Professional AI responses tailored to business needs
- Natural voice synthesis for better user experience

## 🔒 Security Notes

- Never commit API keys to version control
- Use environment variables for sensitive data
- Keep your `.env` and `.streamlit/secrets.toml` files secure

## 🚀 Deployment

This application can be deployed to:
- **Streamlit Cloud**: Connect your GitHub repository
- **Heroku**: Use the provided runtime.txt
- **Azure App Service**: Configure with Python runtime
- **Local server**: For internal business use

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter any issues:
1. Check that all API keys are correctly configured
2. Ensure microphone permissions are granted
3. Verify all dependencies are installed
4. Check the browser console for any errors

---

**Built with ❤️ for small business owners** 