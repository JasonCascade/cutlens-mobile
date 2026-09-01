# CutLens — Mobile AI Meal Macro Estimator

CutLens is a mobile-first Streamlit web app for fat-loss meal tracking.

## What it does

1. Opens the phone camera from the webpage.
2. Lets you capture a main overhead photo and optional 45° / third-angle photos.
3. Uses an OpenAI vision-capable model to identify foods and estimate cooked portion weights.
4. Looks up nutrition using USDA FoodData Central.
5. Shows total Calories / Protein / Carbs / Fat.
6. Shows low/high visual weight ranges instead of pretending photo-based grams are exact.
7. Lets you manually correct grams or the USDA search query and recalculates nutrition.

## Best phone workflow

- Photo 1: directly overhead, entire plate visible.
- Photo 2: about 45° from the side so food thickness is visible.
- Enter plate/bowl diameter if known.
- Tell the app about oil, dressing, butter, sauce, or other hidden calories when known.

## Fastest way to use it on your phone

### Option A — Streamlit Community Cloud

1. Create a GitHub repository and upload this folder.
2. Go to Streamlit Community Cloud and create an app from `app.py`.
3. In App Settings → Secrets, add:

```toml
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
USDA_API_KEY = "YOUR_USDA_API_KEY"
OPENAI_VISION_MODEL = "gpt-5.6-terra"
```

4. Streamlit gives you an HTTPS URL.
5. Open that URL on iPhone or Android. `st.camera_input` will invoke the phone camera.
6. Add the page to your Home Screen if you want it to feel more like an app.

HTTPS matters because mobile browsers generally require a secure context for camera access.

### Option B — Render

This project includes `Dockerfile` and `render.yaml`.

1. Push this folder to GitHub.
2. Create a Render Blueprint/Web Service from the repository.
3. Set `OPENAI_API_KEY` and `USDA_API_KEY` as environment variables.
4. Open the Render HTTPS URL on your phone.

## Use immediately on the same Wi-Fi

On your computer:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="..."
export USDA_API_KEY="..."
streamlit run app.py --server.address=0.0.0.0
```

Windows PowerShell:

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY="..."
$env:USDA_API_KEY="..."
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

