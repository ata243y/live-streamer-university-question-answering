# 3D Talking Head Model

This project is a web-based 3D avatar that can lip-sync to audio and display chat messages. It is designed to be controlled by a Python backend for AI streaming.

## 1. How to Run

You need to serve these files using a local web server.

1.  Open your terminal/command prompt in this folder.
2.  Run the Python HTTP server:
    ```bash
    python3 -m http.server 8000
    ```
3.  Open your browser to: `http://localhost:8000`

---

## 2. Python Integration (API)

You can control the avatar from Python using **Selenium** (web driver). This allows your AI script to "push" audio and text to the browser.

### The Javascript API
We have exposed two main functions in `window` object:

1.  **`window.playTalkingHeadAudio(urlOrFile)`**:
    -   Takes a URL string (relative or absolute) pointing to an audio file (mp3/wav).
    -   *Note:* The audio file must be accessible to the browser (e.g., saved in the same folder as `index.html`).

2.  **`window.addQA(question, answer)`**:
    -   Adds a chat bubble with the user's question and the AI's answer.
    -   Automatically removes old messages to keep the screen clean.

### Python Example (using Selenium)

```python
import time
import os
from selenium import webdriver

# 1. Setup Chrome Driver
options = webdriver.ChromeOptions()
# options.add_argument("--headless") # Uncomment if you don't want to see the browser window
driver = webdriver.Chrome(options=options)

# 2. Open the page
driver.get("http://localhost:8000")

# Wait for avatar to load
time.sleep(5) 

# --- SCENARIO: AI Responding ---

# Step A: Your AI generates audio to a file accessible by the server
audio_filename = "response.mp3"
# (Save your AI's TTS output to /Users/h.atay./Desktop/talkingmodel/response.mp3)

# Step B: Tell the browser to play it
driver.execute_script(f'window.playTalkingHeadAudio("{audio_filename}")')

# Step C: Update the Chat UI
question_text = "What is the capital of France?"
answer_text = "The capital of France is Paris."
driver.execute_script(f'window.addQA("{question_text}", "{answer_text}")')

# Keep running...
input("Press Enter to close...")
driver.quit()
```

---

## 3. Streaming to YouTube with OBS

To stream this avatar to YouTube:

1.  **Install OBS Studio** if you haven't already.
2.  **Add a Source**:
    -   Click the `+` icon in the **Sources** dock.
    -   Select **Browser**.
    -   Name it "AI Avatar".
3.  **Configure Source**:
    -   **URL**: `http://localhost:8000`
    -   **Width**: `1920` (or your stream width)
    -   **Height**: `1080` (or your stream height)
    -   Check "Control audio via OBS" if you want to mix the audio in OBS.
4.  **Setup YouTube**:
    -   Go to **Settings** -> **Stream**.
    -   Service: **YouTube - RTMPS**.
    -   Click "Connect Account" or use your Stream Key.
5.  **Go Live**:
    -   Click **Start Streaming**.

**Tip**: Since the background is a solid color, you can even use a **Color Key** filter in OBS to make it transparent if you want to overlay the avatar on top of a game or desktop capture!
