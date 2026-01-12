# GTU RAG Assistant: An Advanced Conversational AI

Empowering students and candidates with instant, accurate, and natural-language answers based on official university regulations.

---

## Overview
 
This project implements a sophisticated **Retrieval-Augmented Generation (RAG)** system designed to serve as an autonomous AI assistant for **Gebze Technical University (GTU)** and **Koç University**.
 
What sets this project apart is its **3D Talking Head Integration**: the system doesn't just display text; it speaks the answers using a realistic 3D avatar with synchronized lip movements.
 
---
 
## 🎯 Core Features
 
* **State-of-the-Art RAG Pipeline:** Uses `RecursiveCharacterTextSplitter` and advanced embedding retrieval to provide accurate answers from university regulations and data.
 
* **3D Avatar Integration:**
    *   **Text-to-Speech (TTS):** Generates high-quality audio responses using OpenAI TTS.
    *   **Lip-Sync:** The 3D model (Viseme-based) animates in real-time to match the audio.
    *   **Chitchat Suppression:** The avatar remains silent for small talk ("Merhaba", "Nasılsın") to focus on conveying information.
 
* **Dual-Mode AI Core:**
    *   **OpenAI Integration:** Configured to use **GPT-4o** for high-accuracy reasoning and generation.
    *   **Ollama Support:** Can optionally use local models (like Mistral) for privacy/offline capability.
 
* **🧠 Intelligent Query Router:**
    *   **Intent Classification:** Distinguishes between chitchat and knowledge queries.
    *   **Security:** Prompt Injection filtering to prevent misuse.
 
* **Data Retrieval:**
    *   Optimized for "Koç University" and "GTU" specific data.
    *   **Semantic Boosting:** Uses advanced chunking strategies (e.g., entity repetition) to ensure high retrieval accuracy for university names.

* ** Quantitative Evaluation & Testing:**
    * Includes a comprehensive test suite with **Pytest** to ensure the core logic is robust.
    * Integrates the **RAGAS** framework to scientifically measure the quality of the RAG pipeline with metrics like `faithfulness`, `answer_relevancy`, and `context_recall`.

* **Production-Ready Architecture:** The entire application is containerized with **Docker** and designed to be served with **Gunicorn**, making it scalable and easy to deploy on any cloud server.

---

## 🛠️ Technology Stack

* **Backend:** Python 3.11+, Flask, Gunicorn
* **AI Core:** PyTorch, Sentence Transformers, LangChain
* **LLM Serving:** Ollama
* **Vector Database:** Pandas & PyArrow (for `Parquet` file storage)
* **Security & Routing:** `pyahocorasick`
* **Testing & Evaluation:** Pytest, RAGAS
* **Deployment:** Docker

---

## Getting Started

### Prerequisites

Make sure you have the following installed on your machine:

* **Python 3.11+**
* **Ollama:** Download and install from [ollama.com](https://ollama.com)
* **Docker:** (Optional for local development, required for deployment)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/emretechno/Natural-Language-Process.git
   cd Natural-Language-Process
   ```

2. **Set up the Python virtual environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**


## Usage
 
Running the system is a two-step process involved starting the Avatar server and the Backend application.

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
 
The application API will be available at `http://localhost:5001`.
Open the Avatar interface in your browser (usually `http://localhost:8000`) to interact with the system.

---

## Testing & Evaluation

### Run Unit Tests

To ensure the core components like `RAGEngine` are working correctly, run the test suite using Pytest. From the root directory:

```bash
pytest
```

### Evaluate RAG Quality

To quantitatively measure the performance of your RAG pipeline, run the evaluation script. This will use the RAGAS framework to calculate key metrics.

```bash
python -m qa_app.scripts.evaluate
```

**Sample Output:**

```
==================================================
DEĞERLENDİRME SONUÇLARI
==================================================
{
    'faithfulness': 0.95,
    'answer_relevancy': 0.92,
    'context_precision': 0.88,
    'context_recall': 0.90
}
```

---

## 🚀 Deployment

### Using Docker

1. **Build the Docker image:**
   ```bash
   docker build -t gtu-rag-assistant .
   ```

2. **Run the container:**
   ```bash
   docker run -p 5001:5001 gtu-rag-assistant
   ```

### Production Deployment

For production environments, the application is configured to run with **Gunicorn**:

```bash
gunicorn -w 4 -b 0.0.0.0:5001 qa_app.main:app
```

---

## 📊 Performance Metrics

* **Response Time (TTFT):** < 3 seconds
* **Faithfulness:** 0.95
* **Answer Relevancy:** 0.92
* **Context Precision:** 0.88
* **Context Recall:** 0.90

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 📧 Contact

For questions or support, please open an issue on GitHub.

---


**Built with ❤️ for Gebze Technical University**