# General University Guidance Assistant

Empowering students and candidates with instant, accurate, and natural-language answers based on official university regulations.

---

## Overview

This project implements a sophisticated **Retrieval-Augmented Generation (RAG)** system designed to serve as an autonomous AI assistant for **Gebze Technical University (GTU)** and **Koç University**.

What sets this project apart is its **3D Talking Head Integration**: the system doesn't just display text; it speaks the answers using a realistic 3D avatar with synchronized lip movements.

---

## Features

* **Advanced Answer Generation:** Provides accurate answers from university regulations and data.
* **3D Avatar Integration:** Speaks answers with a realistic 3D avatar and synchronized lip movements.
* **Dual-Mode AI Core:** Supports both **OpenAI (GPT-4o)** for high accuracy and **Ollama** for local models.
* **Smart Interaction:** Distinguishes between chitchat (which is ignored) and actual knowledge queries.

---

## Getting Started

### Prerequisites

* **Python 3.11+**
* **Ollama (optional):** For local model support.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/emretechno/Natural-Language-Process.git
    cd Natural-Language-Process
    ```

2.  **Set up the Python virtual environment:**
    ```bash
    python3.11 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    *   Create a `.env` file (copy from example if available, or just create it).
    *   Add your `OPENAI_API_KEY=...` to `.env`.
    *   Add your YouTube Live Video ID to `qa_app/config.py`:
        ```python
        YOUTUBE_VIDEO_ID = "YOUR_VIDEO_ID"
        ```

---

## 🎥 Streaming Setup Guide

Follow this text step-by-step to start a live stream session:

### 1. Start Streaming
Start your stream on YouTube via **OBS**. Once live, copy the **Video ID** from the YouTube URL.

### 2. Configure Video ID
Paste the Video ID into `qa_app/config.py`:
```python
YOUTUBE_VIDEO_ID = "3iDf6s..." # Your ID here
```

### 3. Start the Avatar Server
Open a terminal and run the customized HTTP server for the 3D Avatar:
```bash
cd talkingmodel
python3 -m http.server 8000
```

### 4. Start the AI Backend
Open a **new** terminal and run the main application:
```bash
python -m qa_app.main
```
*This will auto-connect to the YouTube chat and begin processing.*

### 5. OBS Setup
- In OBS, create a **Browser Source** or **Window Capture**.
- Target the opened Chrome window running the Avatar (controlled by the app).
- **Done!** The Avatar will now respond to chat questions live.

> **Note on Filler Queue**: If the chat is quiet (empty queue), the system will automatically loop through a list of **common educational questions** (Filler Q&A) to keep the stream engaging.

---

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for University Students**