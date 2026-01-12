import logging
from flask import Flask, request, render_template, jsonify, Response

# DEĞİŞİKLİK BURADA ⬇️: Tam adresi veriyoruz
from qa_app.core.router import QueryRouter
from qa_app.core.rag_engine import RAGEngine
from qa_app.core.audio_engine import TTSEngine # YENİ
from qa_app.core.avatar_controller import AvatarController # YENİ
from qa_app.config import settings # Bu zaten doğru yerde olduğu için değişmiyor

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Flask'in template ve static klasörlerini doğru bulması için düzeltme
# 'qa_app' içinden çalıştığı için bir üst klasöre çıkması gerekiyor
app = Flask(__name__, template_folder='templates', static_folder='static')

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')



# --- Motorları ve Yönlendiriciyi Başlatma ---
logger.info("Sistem bileşenleri başlatılıyor...")
try:
    rag_engine = RAGEngine()
    tts_engine = TTSEngine() # YENİ
    avatar_controller = AvatarController() # YENİ: Avatar kontrolcüsünü başlat
    query_router = QueryRouter() # Yönlendiriciyi başlat
    
    # YOUTUBE ENTEGRASYONU
    from qa_app.core.youtube_client import YouTubeClient
    youtube_client = YouTubeClient()
    
    # AI CHITCHAT CLASSIFIER
    from qa_app.core.chitchat_classifier import ChitchatClassifier
    chitchat_classifier = ChitchatClassifier()

    logger.info("Tüm bileşenler başarıyla yüklendi ve hazır.")
except Exception as e:
    logger.error(f"Başlangıç sırasında KRİTİK HATA oluştu: {e}")
    raise

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        
        if not text:
            return jsonify({"error": "No text provided"}), 400
            
        audio_stream = tts_engine.generate_audio_stream(text)
        
        if not audio_stream:
            return jsonify({"error": "TTS engine failed"}), 500
            
        return Response(audio_stream, mimetype="audio/mpeg")
        
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return jsonify({"error": str(e)}), 500

def process_question(question: str):
    """
    RAG + TTS + Avatar akışını çalıştıran yardımcı fonksiyon.
    """
    try:
        logger.info(f"Soru İşleniyor: '{question}'")
        
        # KARAR AĞACI ADIM 1: GÜVENLİK KONTROLÜ
        if query_router.is_injection_attempt(question):
            logger.warning(f"Potansiyel Prompt Injection: '{question}'")
            return "Sorunuz güvenlik nedeniyle yanıtlanamadı."

        # Avatar kullanımı için bayrak (Default: Aktif)
        should_use_avatar = True

        # KARAR AĞACI ADIM 2: AI DESTEKLİ CHITCHAT KONTROLÜ
        # Önce yapay zeka ile "Is this chitchat?" diye soruyoruz
        is_chitchat = chitchat_classifier.is_chitchat(question)
        answer = None
        
        if is_chitchat:
            logger.info(f"AI 'chitchat' tespiti yaptı. Yanıt VERİLMEYECEK: '{question}'")
            return None # Tamamen sessiz kal

        # KARAR AĞACI ADIM 3: Normal Chitchat Kontrolü (Router'da varsa)
        chitchat_answer_router = query_router.get_chitchat_response(question)
        if chitchat_answer_router:
             logger.info(f"Router 'chitchat' tespiti yaptı. Yanıt VERİLMEYECEK: '{question}'")
             return None # Tamamen sessiz kal

        # KARAR AĞACI ADIM 4: BİLGİ SORGUSU
        rag_response = ""
        for chunk in rag_engine.answer_query(question):
                rag_response += chunk
        answer = rag_response

        # --- Talking Head Entegrasyonu ---
        # Sadece RAG cevabı varsa buraya gelir
        import time
        import os
        
        # 1. Dosya adı oluştur
        audio_filename = f"response_{int(time.time())}.mp3"
        full_audio_path = os.path.join(settings.TALKING_HEAD_PATH, audio_filename)
        
        # 2. Sesi kaydet
        if tts_engine.save_to_file(answer, full_audio_path):
            logger.info(f"Ses dosyası kaydedildi: {full_audio_path}")
            # 3. Avatarı konuştur
            avatar_controller.speak(question, answer, audio_filename)
        else:
            logger.warning("Ses oluşturulamadı.")
             
        return answer

    except Exception as e:
        logger.error(f"Soru işleme hatası: {e}")
        return "Bir hata oluştu."


@app.route("/api/start_youtube", methods=["POST"])
def start_youtube():
    try:
        data = request.get_json()
        video_id = data.get("video_id", "").strip()
        
        if not video_id:
            return jsonify({"error": "Video ID is required"}), 400
            
        def on_question(author, message):
            logger.info(f"YouTube sorusu alındı ({author}): {message}")
            process_question(message)
            
        youtube_client.start_listening(video_id, on_question)
        
        return jsonify({"status": "Started listening", "video_id": video_id})
        
    except Exception as e:
        logger.error(f"YouTube start error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/stop_youtube", methods=["POST"])
def stop_youtube():
    youtube_client.stop_listening()
    return jsonify({"status": "Stopped listening"})

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return Response("Lütfen bir soru sorun.", mimetype='text/plain'), 400

        # Mevcut mantığı process_question fonksiyonuna taşıdık
        answer = process_question(question)
        
        if answer is None:
            # Chitchat durumunda sessiz kal (204 No Content)
            return Response("", status=204, mimetype='text/plain')
            
        # Cevabı düz metin olarak dön
        return Response(answer, mimetype='text/plain')

    except Exception as e:
        logger.error(f"Tahmin sırasında bir hata oluştu: {e}", exc_info=True)
        return Response("Cevap üretilirken bir sorun oluştu. Lütfen tekrar deneyin.", mimetype='text/plain'), 500
    
if __name__ == "__main__":
    logger.info("Flask geliştirme sunucusu başlatılıyor...")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)