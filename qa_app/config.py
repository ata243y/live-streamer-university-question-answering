import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Model ve API Ayarları
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-mpnet-base-v2")
    LLM_MODEL = os.getenv("LLM_MODEL_NAME", "llama3")
    OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # OpenAI Ayarları
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai") # ollama or openai
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

    # AI Chitchat Check Ayarları
    CHITCHAT_CHECK_PROVIDER = os.getenv("CHITCHAT_CHECK_PROVIDER", "openai") # openai or ollama
    CHITCHAT_CHECK_MODEL = os.getenv("CHITCHAT_CHECK_MODEL", "gpt-4o-mini")

    # Audio/TTS Ayarları
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")
    TTS_MODEL = os.getenv("TTS_MODEL", "tts-1") # tts-1 or tts-1-hd
    TTS_VOICE = os.getenv("TTS_VOICE", "nova") # alloy, echo, fable, onyx, nova, shimmer

    # Talking Head Entegrasyonu
    TALKING_HEAD_PATH = os.getenv("TALKING_HEAD_PATH", os.path.abspath("talkingmodel"))
    TALKING_HEAD_URL = os.getenv("TALKING_HEAD_URL", "http://localhost:8000")

    # Dosya Yolları
    RAW_DATA_DIR = os.getenv("RAW_DATA_DIR", "qa_app/data/raw/")
    PROCESSED_DATA_PATH = os.getenv("PROCESSED_DATA_PATH", "qa_app/data/processed/embeddings.parquet")

    # Loglama
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()