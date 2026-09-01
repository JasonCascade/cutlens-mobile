# CutLens — Mobile AI Meal Macro Estimator

CutLens is a mobile-first Streamlit web app for fat-loss meal tracking. It can use
the Codex CLI with a ChatGPT workspace entitlement, a local Ollama model, or the OpenAI API.

## What it does

1. Opens the phone camera from the webpage.
2. Lets you capture a main overhead photo and optional 45° / third-angle photos.
3. Uses a vision-capable Codex, Ollama, or OpenAI model to identify foods and estimate cooked portion weights.
4. Looks up nutrition using USDA FoodData Central.
5. Shows total Calories / Protein / Carbs / Fat.
6. Shows low/high visual weight ranges instead of pretending photo-based grams are exact.
7. Lets you manually correct grams or the USDA search query and recalculates nutrition.

## Best phone workflow

- Photo 1: directly overhead, entire plate visible.
- Photo 2: about 45° from the side so food thickness is visible.
- Enter plate/bowl diameter if known.
- Tell the app about oil, dressing, butter, sauce, or other hidden calories when known.

## No-API-credit Codex mode (Windows)

This mode calls the official Codex CLI signed in with ChatGPT, so it uses your
ChatGPT/Codex workspace entitlement instead of OpenAI Platform API credit. Images
are sent to OpenAI and follow the permissions and data policies of the signed-in
ChatGPT workspace. A temporary Cloudflare HTTPS tunnel lets Safari use the camera.

### First-time setup

Open PowerShell in this folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_local.ps1
```

The script installs the official Codex CLI and portable `cloudflared`, creates a
Python virtual environment, and checks that Codex is signed in with ChatGPT.

### Start CutLens

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start_local.ps1
```

The window prints:

- a temporary `https://...trycloudflare.com` phone URL
- a random six-digit access PIN

Open the HTTPS URL in Safari, enter the PIN, and take a photo. Keep the computer
awake and keep the PowerShell window open while using the app. Press `Ctrl+C` to
stop sharing. A new temporary URL and PIN are generated the next time you start it.

Each analysis counts against the signed-in workspace's Codex usage limits. The
temporary URL is protected by a random PIN and only exposes this fixed meal-analysis
workflow—not an arbitrary Codex prompt or shell. USDA nutrition lookup still uses
the public `DEMO_KEY` by default.

## Cloud deployment

### Option A — Streamlit Community Cloud (OpenAI API required)

1. Create a GitHub repository and upload this folder.
2. Go to Streamlit Community Cloud and create an app from `app.py`.
3. In App Settings → Secrets, add:

```toml
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
USDA_API_KEY = "YOUR_USDA_API_KEY"
OPENAI_VISION_MODEL = "gpt-5.6-terra"
CUTLENS_AI_BACKEND = "openai"
```

4. Streamlit gives you an HTTPS URL.
5. Open that URL on iPhone or Android. `st.camera_input` will invoke the phone camera.
6. Add the page to your Home Screen if you want it to feel more like an app.

HTTPS matters because mobile browsers generally require a secure context for camera access.

### Option B — Render (OpenAI API required)

This project includes `Dockerfile` and `render.yaml`.

1. Push this folder to GitHub.
2. Create a Render Blueprint/Web Service from the repository.
3. Set `OPENAI_API_KEY` and `USDA_API_KEY` as environment variables.
4. Open the Render HTTPS URL on your phone.

## Optional Ollama backend

For fully local inference, install Ollama and pull a vision model such as
`gemma3:4b`, then configure:

On your computer:

```bash
pip install -r requirements.txt
export CUTLENS_AI_BACKEND="ollama"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_VISION_MODEL="gemma3:4b"
export USDA_API_KEY="DEMO_KEY"
streamlit run app.py --server.address=0.0.0.0
```

Windows PowerShell:

```powershell
pip install -r requirements.txt
$env:CUTLENS_AI_BACKEND="ollama"
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:OLLAMA_VISION_MODEL="gemma3:4b"
$env:USDA_API_KEY="DEMO_KEY"
streamlit run app.py --server.address=0.0.0.0
```

Then find your computer's LAN IP, for example `192.168.1.20`, and on your phone open:

```text
http://192.168.1.20:8501
```

Note: some mobile browsers restrict direct camera capture on non-HTTPS LAN pages. If that happens, use the photo-library upload on LAN or deploy with HTTPS using Streamlit Cloud/Render.

## API keys

### OpenAI

Set `OPENAI_API_KEY` only on the server/deployment secrets. Never embed the key in browser-side JavaScript.
The key is optional when `CUTLENS_AI_BACKEND=codex` or `ollama`.

### USDA

FoodData Central requires a data.gov API key. `DEMO_KEY` can be used for testing but has much lower limits, so a normal free key is recommended.

## Accuracy

Photo-based portion estimation is not scale-equivalent. The biggest error sources are:

- hidden cooking oil
- sauces/dressings
- food thickness that is not visible
- overlapping food
- dense mixed dishes
- unknown plate dimensions

Two-angle photos plus plate diameter can materially improve consistency. For home meals, a kitchen scale remains the best method. CutLens is designed to make restaurant/takeout logging much more useful than a single-image calorie guess.
