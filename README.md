# 🧠 Voice AI for Small Business

A Streamlit web app that lets small business owners ask questions by voice and get AI-generated answers, along with optional spoken responses. It uses the browser’s Web Speech API for on-device speech recognition, Azure OpenAI for reasoning, Azure Speech for text-to-speech, and can optionally pull business data from Google Sheets.

## ✨ Features

- **Browser Speech Recognition (client-side)**: Uses the Web Speech API in the browser to capture voice and transcribe to text.
- **AI Responses via Azure OpenAI**: Sends the transcript plus business data context to Azure OpenAI Chat Completions.
- **Natural Speech Output (server-side)**: Uses Azure Cognitive Services Speech SDK to synthesize a voice reply when available.
- **Optional Google Sheets data**: Loads a worksheet from a Google Sheet to ground responses; falls back to sample data if not configured.
- **Simple UI**: Built entirely with Streamlit.

## 🚀 Quick Start

### Prerequisites

- Python 3.10.13 (see `runtime.txt`)
- A modern browser with microphone access (Web Speech API support is best in Chromium-based browsers)
- Azure credentials (OpenAI + Speech). Google service account is optional for Sheets.

### Install

1) Clone and enter the project
```bash
git clone <repository-url>
cd BusinessVoiceAI
```

2) Install dependencies
```bash
pip install -r requirements.txt
```

3) Configure Streamlit secrets

Create `.streamlit/secrets.toml` with your keys. Minimum required keys:
```toml
AZURE_OPENAI_KEY = "your_azure_openai_key"
AZURE_OPENAI_ENDPOINT = "https://your-openai-resource.openai.azure.com/"
AZURE_DEPLOYMENT_NAME = "your_model_deployment_name"
AZURE_SPEECH_KEY = "your_azure_speech_key"
AZURE_SPEECH_REGION = "your_azure_speech_region"

# Optional: Google Sheets service account (used by gspread)
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-sa%40your-project.iam.gserviceaccount.com"
```

Notes:
- The app reads secrets from `st.secrets`; `.env` is loaded but the Azure keys must be present in `secrets.toml` for Streamlit Cloud.
- If Google Sheets is not configured, the app will use built-in sample data.

### Run

```bash
streamlit run app.py
```

Then open `http://localhost:8501`, allow microphone access, click “Start Voice Recognition,” speak your question, and view/hear the response.

## 🔧 Services Setup

### Azure OpenAI
1. Create an Azure OpenAI resource.
2. Deploy a model (e.g., GPT-4o or the model you prefer) and note the deployment name.
3. Copy the resource endpoint and an API key into `secrets.toml`.

### Azure Speech Services
1. Create an Azure Speech resource.
2. Copy the key and region into `secrets.toml`.
3. The app uses voice `en-US-JennyNeural` by default; you can change it in `app.py`.

### Google Sheets (optional)
1. Create a Google Cloud service account and download its credentials JSON.
2. Paste values into the `[gcp_service_account]` section of `secrets.toml`.
3. Create a Google Sheet named `BusinessProducts` and ensure worksheet index 1 has your data (the app opens worksheet 1). Share the sheet with the service account email.

## 🗂️ Project Structure

```
BusinessVoiceAI/
├── app.py               # Streamlit app: UI, browser speech, Azure OpenAI + Speech, Google Sheets
├── requirements.txt     # Python dependencies
├── runtime.txt          # Python version
├── .streamlit/
│   └── secrets.toml     # Your secrets (not committed)
└── README.md            # This file
```

## 🛠️ Dependencies

From `requirements.txt`:
- streamlit==1.35.0
- gspread==6.0.1
- oauth2client==4.1.3
- python-dotenv==1.0.1
- openai==1.30.1
- azure-cognitiveservices-speech==1.34.1
- pandas==2.2.2
- tabulate

## 🧩 How it works

1. The custom `speech_recognition_component()` in `app.py` embeds HTML/JS that uses the browser’s Web Speech API to transcribe speech and post messages back to Streamlit.
2. The transcript (or manual text input) is combined with business data (from Google Sheets if configured, otherwise sample data) and sent to Azure OpenAI Chat Completions.
3. The AI reply is shown in the UI. If Azure Speech is available, the reply is cleaned of Markdown and synthesized to audio on the server.

## 🔒 Security

- Do not commit secrets. Use Streamlit Secrets locally and on Streamlit Community Cloud.
- Prefer service accounts for Google Sheets and share only the sheet that’s needed.

## 🚢 Deployment

- **Streamlit Community Cloud**: Add your repository, set the Python version via `runtime.txt`, configure all keys in the Secrets UI using the same names as above.
- **Other hosts (e.g., Azure App Service)**: Ensure environment provides the same secrets (e.g., via environment variables mapped into `st.secrets` or secrets files) and microphone access is allowed by the browser.

## 🧰 Troubleshooting

- **Web Speech not supported**: Use a Chromium-based browser. Safari may have limited support.
- **“Google Sheets not configured” warning**: Verify `[gcp_service_account]` is present and the sheet `BusinessProducts` worksheet index 1 exists and is shared with the service account.
- **Azure errors**: Check `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_DEPLOYMENT_NAME`, `AZURE_SPEECH_KEY`, and `AZURE_SPEECH_REGION` in `secrets.toml`.
- **No audio output**: Azure Speech might not be available in the environment; the app will still display the text response.
- **Microphone blocked**: Ensure site permissions allow mic access.

---

Built with ❤️ to help small businesses get answers faster.