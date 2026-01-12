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

---

## 🚀 How to Run

Running the system involves starting two separate components: the 3D Avatar Server and the Backend Application.

### 1. Start the 3D Avatar Server

Open a terminal and navigate to the project directory. Run the HTTP server to serve the 3D model files:

```bash
cd talkingmodel
python3 -m http.server 8000
```

*(Keep this terminal running)*

### 2. Start the Backend Application

Open a **new** terminal window, activate the environment, and start the main application:

```bash
source venv/bin/activate
python -m qa_app.main
```

- Information API will be available at: `http://localhost:5001`
- Open the **Avatar Interface** in your browser: `http://localhost:8000`

---

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for University Students**