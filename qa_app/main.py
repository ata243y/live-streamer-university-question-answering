import logging
from flask import Flask, request, render_template, jsonify, Response
import signal
import sys
import queue
import threading
import time

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



app = Flask(__name__, template_folder='templates', static_folder='static')
import json
import os

# --- Load Filler Data (Global) ---
filler_data = []
filler_index = 0
try:
    filler_path = os.path.join(settings.RAW_DATA_DIR, "../filler_qa.json") # qa_app/data/filler_qa.json
    if os.path.exists(filler_path):
         with open(filler_path, "r", encoding="utf-8") as f:
             filler_data = json.load(f)
         logger.info(f"Loaded {len(filler_data)} filler Q&A items.")
    else:
        logger.warning(f"Filler data not found at {filler_path}")
except Exception as e:
    logger.error(f"Error loading filler data: {e}")


# --- Motorları ve Yönlendiriciyi Başlatma ---
logger.info("Sistem bileşenleri başlatılıyor...")
try:
    rag_engine = RAGEngine()
    tts_engine = TTSEngine() # YENİ
    avatar_controller = AvatarController() # YENİ: Avatar kontrolcüsünü başlat
    query_router = QueryRouter() # Yönlendiriciyi başlat
    
    # WEB SEARCH AGENT
    from qa_app.core.web_search_agent import WebSearchAgent
    web_search_agent = WebSearchAgent()

    # YOUTUBE ENTEGRASYONU
    from qa_app.core.youtube_client import YouTubeClient
    youtube_client = YouTubeClient()
    
    # AI CHITCHAT CLASSIFIER
    from qa_app.core.chitchat_classifier import ChitchatClassifier
    chitchat_classifier = ChitchatClassifier()
    
    # Rate Limiting Storage
    user_last_question_time = {} # {author_name: timestamp}

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
    import time
    import os

    try:
        logger.info(f"Soru İşleniyor: '{question}'")
        
        # KARAR AĞACI ADIM 0: Author Parsing (YouTube Entegrasyonu için)
        author = None
        cleaned_question = question
        if ": " in question:
            possible_author, possible_msg = question.split(": ", 1)
            # Basic heuristic: names are usually short, messages can be anything.
            if len(possible_author) < 50: 
                author = possible_author
                cleaned_question = possible_msg

        # KARAR AĞACI ADIM 0.5: Rate Limiting & Greeting Detection
        greetings = ["merhaba", "hello", "selam", "hi", "günaydın", "iyi akşamlar", "hey"]
        lower_q = cleaned_question.lower()
        is_greeting = any(g in lower_q for g in greetings)
        
        if author:
            # If IT IS a greeting: Allow it (don't check timer), and don't update timer.
            # If IT IS NOT a greeting: Check timer.
            if not is_greeting:
                last_time = user_last_question_time.get(author, 0)
                if time.time() - last_time < 30:
                    logger.warning(f"Rate Limit: {author} is asking too fast. Ignored.")
                    return None # Ignore spam
                else:
                    # Update timer for valid question
                    user_last_question_time[author] = time.time()

        # KARAR AĞACI ADIM 1: GÜVENLİK KONTROLÜ (Cleaned question üzerinden)
        if query_router.is_injection_attempt(cleaned_question):
            logger.warning(f"Potansiyel Prompt Injection: '{cleaned_question}'")
            return "Sorunuz güvenlik nedeniyle yanıtlanamadı."

        # Avatar kullanımı için bayrak (Default: Aktif)
        should_use_avatar = True
        skip_tts = False  # New flag for text-only updates

        # KARAR AĞACI ADIM 2: AI DESTEKLİ CHITCHAT KONTROLÜ
        # Önce yapay zeka ile "Is this chitchat?" diye soruyoruz
        is_chitchat = chitchat_classifier.is_chitchat(cleaned_question)
        answer = None
        
        if is_chitchat:
            logger.info(f"AI 'chitchat' tespiti yaptı: '{cleaned_question}'")
            
        if is_chitchat:
            logger.info(f"AI 'chitchat' tespiti yaptı: '{cleaned_question}'")
            
            # If chitchat detected + has author tag + IS GREETING -> Personalized Greeting
            if author and is_greeting:
                # "👋 Merhaba, hoşgeldin (username) sorunu sabırsızlıkla bekliyorum :)"
                answer = f"👋 Merhaba, hoşgeldin {author} sorunu sabırsızlıkla bekliyorum :)"
                skip_tts = True
            else:
                return None # Tamamen sessiz kal (Anonim chitchat veya Greeting olmayan)

        # KARAR AĞACI ADIM 3: Normal Chitchat Kontrolü (Router'da varsa)
        if not answer: # Check if answer already set by Step 2
            chitchat_answer_router = query_router.get_chitchat_response(cleaned_question)
            if chitchat_answer_router:
                 logger.info(f"Router 'chitchat' tespiti yaptı: '{cleaned_question}'")
                 
                 # Logic simplified since we detected is_greeting above
                 if author and is_greeting:
                     answer = f"👋 Merhaba, hoşgeldin {author} sorunu sabırsızlıkla bekliyorum :)"
                     skip_tts = True
                 else:
                     return None # Tamamen sessiz kal

        # KARAR AĞACI ADIM 4: BİLGİ SORGUSU (RAG)
        if not answer: # Only run RAG if no answer yet
            rag_response = ""
            for chunk in rag_engine.answer_query(cleaned_question):
                    rag_response += chunk
            
            # --- FALLBACK MECHANISM: WEB SEARCH ---
            if "NO_CONTEXT" in rag_response or not rag_response.strip():
                logger.info("RAG cevapsız kaldı (NO_CONTEXT). Web Search agent devreye giriyor...")
                
                # 1. Get raw info/context from Web Search
                web_context_text = web_search_agent.search_and_answer(cleaned_question)
                
                if web_context_text:
                    logger.info("Web Search context alındı. Main LLM ile işleniyor...")
                    
                    # 2. Format as context for RAG Engine's generator
                    web_context_structured = [{
                        "text": web_context_text,
                        "source": "Web Search (GPT-5)"
                    }]
                    
                    # 3. Generate final concise answer using Main LLM
                    final_answer_buf = ""
                    # rag_engine.generate returns a generator, so we join the chunks
                    for chunk in rag_engine.generate(cleaned_question, web_context_structured, is_web_search=True):
                         final_answer_buf += chunk
                    
                    answer = final_answer_buf
                    logger.info("Main LLM cevabı üretti.")

                    # 4. Save FINAL ANSWER to Vector DB & JSONL (Only if no error)
                    if "Web araması sırasında hata oluştu" not in web_context_text:
                        try:
                            import json
                            qa_entry = {
                                "question": question,
                                "answer": answer,
                                "raw_web_context": web_context_text,
                                "source": "web_search",
                                "timestamp": time.time()
                            }
                            
                            # Ensure directory exists
                            raw_data_dir = settings.RAW_DATA_DIR
                            if not os.path.exists(raw_data_dir):
                                os.makedirs(raw_data_dir)
                                
                            web_qa_path = os.path.join(raw_data_dir, "web_search_qa.jsonl")
                            with open(web_qa_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps(qa_entry, ensure_ascii=False) + "\n")
                            logger.info(f"QA saved to {web_qa_path}")
                        
                            # 5. Add to Vector DB (Dynamic Update)
                            # User Request: Save the Web Agent result (raw context), not the refined answer
                            rag_engine.add_knowledge(
                                f"SORU: {question}\nBİLGİ: {web_context_text}", 
                                source="web_search_fallback"
                            )
                            
                        except Exception as save_err:
                            logger.error(f"Error saving web search result: {save_err}")
                    else:
                        logger.warning("Web search returned an error, skipping save to knowledge base.")
                        logger.error(f"Error saving web search result: {save_err}")
                        
                else:
                    answer = "Üzgünüm, bu konuda bilgi bulamadım."
            else:
                answer = rag_response

        # --- Talking Head Entegrasyonu ---
        # Sadece cevap varsa buraya gelir
        import time
        import os
        
        # Determine behavior based on skip_tts flag
        if skip_tts:
             logger.info("Only displaying text (No TTS) for chitchat.")
             avatar_controller.add_qa_text(question, answer)
        else:
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
            # Put in queue instead of direct processing
            question_queue.put(f"{author}: {message}")
            
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
    # --- Processing Queue & Worker ---
    question_queue = queue.Queue()

    def process_queue_worker():
        global filler_index # Use global index to cycle through fillers
        logger.info("Question processing worker started.")
        while True:
            try:
                # Try to get a real question with a timeout
                # If timeout happens (queue empty), we inject a filler.
                try:
                    question_text = question_queue.get(timeout=5) # 5 seconds idle wait
                    
                    logger.info(f"Worker processing: {question_text}")
                    with app.app_context():
                        process_question(question_text)
                    
                    question_queue.task_done()
                    
                except queue.Empty:
                    # Queue is empty! Inject Filler if available.
                    if filler_data:
                        logger.info("Queue empty. Injecting Filler Q&A...")
                        
                        item = filler_data[filler_index]
                        
                        # Use pre-generated asset (NO LLM, NO NEW TTS)
                        # Construct full audio URL/Path as expected by Avatar Controller
                        # Note: avatar_controller.speak expects just the filename if it's in the assets folder
                        # OR a URL. The script saved them to talkingmodel/ folder which is usually served.
                        # Let's assume settings.TALKING_HEAD_URL matches where these files are served.
                        # Actually, save_fillers.py saved to TALKING_HEAD_PATH.
                        # The JS code plays relative to its root or absolute URL.
                        # We passed filename "filler_X.mp3" to speak().
                        
                        logger.info(f"Playing filler: {item['question']}")
                        
                        # Directly call speak (Bypass process_question)
                        # But wait! We need to ensure we don't overlap if user asked something just now? 
                        # No, queue.get(timeout=5) ensures we waited 5s and nothing came.
                        
                        # We also need to check if avatar is currently speaking (maybe previous filler is still going?)
                        # avatar_controller.speak handles blocking now? Yes, we added wait_for_audio_finish!
                        
                        avatar_controller.speak(item['question'], item['answer'], item['audio_file'])
                        
                        # Move to next filler
                        filler_index = (filler_index + 1) % len(filler_data)
                    else:
                        pass # No fillers available, just loop back to wait

            except Exception as e:
                logger.error(f"Worker error: {e}")

    # Start Worker Thread
    worker_thread = threading.Thread(target=process_queue_worker, daemon=True)
    worker_thread.start()

    # --- Auto-Start YouTube Listener if Configured ---
    if settings.YOUTUBE_VIDEO_ID:
        logger.info(f"Auto-starting YouTube listener for Video ID: {settings.YOUTUBE_VIDEO_ID}")
        
        def on_question_auto(author, message):
            logger.info(f"YouTube sorusu alındı ({author}): {message}")
            question_queue.put(f"{author}: {message}")

        # Start listening
        youtube_client.start_listening(settings.YOUTUBE_VIDEO_ID, on_question_auto)

    # --- Graceful Shutdown Handler ---
    def graceful_shutdown(signum, frame):
        logger.info("\nShutdown signal received (Ctrl+C). Cleaning up...")
        if youtube_client:
            logger.info("Stopping YouTube client...")
            youtube_client.stop_listening()
        if avatar_controller:
            logger.info("Closing Avatar controller...")
            avatar_controller.close()
        logger.info("Cleanup complete. Exiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)

    logger.info("Flask geliştirme sunucusu başlatılıyor...")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)