import openai
from qa_app.config import settings

class TTSEngine:
    def __init__(self):
        self.openai_client = None
        if settings.TTS_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                print(f"TTS Motoru başlatılıyor (Model: {settings.TTS_MODEL}, Ses: {settings.TTS_VOICE})")
            except Exception as e:
                print(f"TTS Client başlatma hatası: {e}")

    def generate_audio_stream(self, text: str):
        """
        OpenAI API kullanarak metni ses akışına (stream) dönüştürür.
        """
        if not self.openai_client:
            print("HATA: TTS Engine başlatılamadı veya API Key eksik.")
            return None

        try:
            response = self.openai_client.audio.speech.create(
                model=settings.TTS_MODEL,
                voice=settings.TTS_VOICE,
                input=text
            )
            # Stream the raw bytes directly
            return response.iter_bytes()
        except Exception as e:
            print(f"Ses üretme hatası: {e}")
            return None

    def save_to_file(self, text: str, file_path: str):
        """
        Metinden ses üretir ve belirtilen dosyaya kaydeder.
        """
        if not self.openai_client:
            return False

        try:
            response = self.openai_client.audio.speech.create(
                model=settings.TTS_MODEL,
                voice=settings.TTS_VOICE,
                input=text
            )
            response.stream_to_file(file_path)
            return True
        except Exception as e:
            print(f"Ses kaydetme hatası: {e}")
            return False
