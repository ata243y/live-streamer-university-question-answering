from venv import logger
import torch, json, unicodedata, hashlib
import pandas as pd
import requests, re, os
import numpy as np
import openai
from collections import OrderedDict
from sentence_transformers import SentenceTransformer, util
from urllib.parse import urljoin
from qa_app.config import settings

class RAGEngine:
    def __init__(self, enable_cache: bool = True, cache_size: int = 100, semantic_cache_threshold: float = 0.95):
        """
        RAG motorunu başlatır. Modelleri ve vektör veritabanını belleğe yükler.
        
        Args:
            enable_cache: Cache mekanizmasını aktif eder (default: True)
            cache_size: Maksimum cache boyutu (default: 100 sorgu)
            semantic_cache_threshold: Semantic cache için minimum benzerlik skoru (default: 0.95)
        """
        print("RAG Motoru başlatılıyor...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Kullanılan cihaz: {self.device}")

        # Cache ayarları
        self.enable_cache = enable_cache
        self.cache_size = cache_size
        self._query_cache = OrderedDict()  # LRU cache için OrderedDict (exact match)
        
        # Semantic cache
        self.semantic_cache_threshold = semantic_cache_threshold
        self._semantic_cache = []  # [(query_embedding, results), ...]
        self._semantic_cache_queries = []  # Orijinal query metinleri (debug için)
        
        print(f"Cache: {'Aktif' if enable_cache else 'Kapalı'} (max {cache_size} sorgu, semantic threshold: {semantic_cache_threshold})")

        self.embedding_model = self._load_embedding_model()
        self.text_chunks, self.sources, self.embeddings = self._load_vector_db()

        # OpenAI Client Init
        self.openai_client = None
        if settings.LLM_PROVIDER == "openai":
            if not settings.OPENAI_API_KEY:
                print("UYARI: OpenAI seçildi ama OPENAI_API_KEY bulunamadı!")
            else:
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                print(f"OpenAI Client başlatıldı (Model: {settings.OPENAI_MODEL_NAME})")

        print("RAG Motoru başarıyla başlatıldı ve kullanıma hazır.")

    def _load_embedding_model(self):
        """Embedding modelini yükler."""
        print(f"Embedding modeli yükleniyor: {settings.EMBEDDING_MODEL}")
        return SentenceTransformer(settings.EMBEDDING_MODEL, device=self.device)

    def _load_vector_db(self):
        """İşlenmiş Parquet dosyasını okur ve embedding'leri bir Torch tensor'üne dönüştürür."""
        print(f"Vektör veritabanı yükleniyor: {settings.PROCESSED_DATA_PATH}")
        try:
            df = pd.read_parquet(settings.PROCESSED_DATA_PATH)
            text_chunks = df['text_chunk'].tolist()
            sources = df['source_document'].tolist()
            embeddings_list = df['embedding'].tolist()
            embeddings = torch.tensor(np.array(embeddings_list), dtype=torch.float32).to(self.device)
            print(f"Vektör veritabanı başarıyla yüklendi. Toplam {len(text_chunks)} chunk.")
            return text_chunks, sources, embeddings
        except FileNotFoundError:
            print(f"HATA: Embedding dosyası bulunamadı! Lütfen önce 'scripts/ingest.py' script'ini çalıştırın.")
            raise

    def add_knowledge(self, text: str, source: str):
        """
        Dynamically adds new knowledge to the vector database (memory + disk).
        """
        try:
            print(f"Adding new knowledge from source: {source}")
            
            # 1. Compute embedding
            with torch.no_grad():
                new_embedding = self.embedding_model.encode(
                    text,
                    convert_to_tensor=True,
                    device=self.device,
                    show_progress_bar=False
                )
            
            # 2. Update In-Memory Data
            self.text_chunks.append(text)
            self.sources.append(source)
            self.embeddings = torch.cat((self.embeddings, new_embedding.unsqueeze(0)), dim=0)
            
            # 3. Update Disk (Parquet)
            # Load existing DF to append safely
            try:
                df = pd.read_parquet(settings.PROCESSED_DATA_PATH)
                new_row = pd.DataFrame([{
                    "text_chunk": text,
                    "source_document": source,
                    "embedding": new_embedding.cpu().numpy()
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_parquet(settings.PROCESSED_DATA_PATH)
                print("Knowledge successfully saved to Parquet.")
                
                # 4. Invalidate Cache
                # This ensures the next query (likely the same one) doesn't hit the stale cache
                self.clear_cache()
                
            except Exception as e:
                print(f"Error saving to parquet: {e}")

        except Exception as e:
            print(f"Error adding knowledge: {e}")

    # ==================== CACHE METHODS ====================
    def _get_cache_key(self, query: str, top_k: int) -> str:
        """Sorgu için unique cache key üretir"""
        key_str = f"{query.lower().strip()}_{top_k}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str):
        """Cache'den sonuç getirir (LRU - en son kullanılanı güncelle)"""
        if cache_key in self._query_cache:
            # LRU: En son kullanılanı en sona taşı
            self._query_cache.move_to_end(cache_key)
            return self._query_cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, results: list):
        """Sonucu cache'e kaydeder (LRU mantığı)"""
        if len(self._query_cache) >= self.cache_size:
            # En eski elemanı sil (FIFO - OrderedDict'in ilk elemanı)
            self._query_cache.popitem(last=False)
        self._query_cache[cache_key] = results

    def clear_cache(self):
        """Cache'i temizler"""
        self._query_cache.clear()
        self._semantic_cache.clear()
        self._semantic_cache_queries.clear()
        print("✅ Cache temizlendi")

    def get_cache_stats(self) -> dict:
        """Cache istatistiklerini döndürür"""
        return {
            "enabled": self.enable_cache,
            "exact_cache_size": len(self._query_cache),
            "semantic_cache_size": len(self._semantic_cache),
            "max_size": self.cache_size,
            "semantic_threshold": self.semantic_cache_threshold
        }
    
    def _find_semantic_match(self, query_embedding):
        """Semantik olarak benzer cached sorgu var mı?"""
        if not self._semantic_cache:
            return None
        
        # Tüm cache embeddingler ile karşılaştır
        cached_embeddings = torch.stack([item[0] for item in self._semantic_cache])
        similarities = util.cos_sim(query_embedding, cached_embeddings)[0]
        
        max_idx = similarities.argmax()
        max_sim = similarities[max_idx].item()
        
        if max_sim >= self.semantic_cache_threshold:
            print(f"💡 Semantic cache hit! (benzerlik: {max_sim:.2%})")
            print(f"   Orijinal sorgu: '{self._semantic_cache_queries[max_idx]}'")
            return self._semantic_cache[max_idx][1]  # Cached results
        
        return None
    
    def _save_to_semantic_cache(self, query_embedding, query_text, results):
        """Semantic cache'e kaydet"""
        if len(self._semantic_cache) >= self.cache_size:
            self._semantic_cache.pop(0)
            self._semantic_cache_queries.pop(0)
        
        self._semantic_cache.append((query_embedding.cpu(), results))
        self._semantic_cache_queries.append(query_text)
    # ======================================================

    def retrieve(self, query: str, top_k: int = 5, similarity_threshold: float = 0.3, use_cache: bool = None) -> list[dict]:
        """
        Anlamsal arama yapar ve metin parçalarını kaynak bilgileriyle birlikte döndürür.
        
        Args:
            query: Kullanıcı sorgusu
            top_k: En benzer kaç sonuç döndürülecek
            similarity_threshold: Minimum benzerlik skoru
            use_cache: Cache kullanımı (None ise self.enable_cache kullanılır)
        """
        # Cache kontrolü
        if use_cache is None:
            use_cache = self.enable_cache
        
        if use_cache:
            cache_key = self._get_cache_key(query, top_k)
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                print("💾 Cache hit!")
                return cached

        # Query expansion (GELİŞTİRİLMİŞ - v3.0)
        search_query = query
        query_lower = query.lower()
        
        # 1. ÇAP başvuru koşulları (pozitif + negatif sorular)
        if ("çift anadal" in query_lower or "çap" in query_lower) and \
           ("koşul" in query_lower or "şart" in query_lower or "nasıl" in query_lower or 
            "kimler" in query_lower or "başvuramaz" in query_lower or "yapamaz" in query_lower):
            print("--- INFO: 'ÇAP Koşulları' sorgu genişletmesi (v3.0) ---")
            search_query = f"{query} ÇAP başvuru koşulları AGNO GANO genel not ortalaması en az kaç olmalı anadal başarı sırası şartı kabul"
        
        # 2. ÇAP başarısızlık/ara sınıf durumları
        elif ("çap" in query_lower or "çift anadal" in query_lower) and \
             ("kalırsa" in query_lower or "başarısız" in query_lower or "ara sınıf" in query_lower or 
              "düşürse" in query_lower or "etkilemez" in query_lower):
            print("--- INFO: 'ÇAP Başarısızlık' sorgu genişletmesi ---")
            search_query = f"{query} ÇAP başarısızlık mezuniyet etkilemez ana dal transkript ayrı program"

        # Embedding oluştur (optimized - no gradient)
        with torch.no_grad():
            query_embedding = self.embedding_model.encode(
                search_query,
                convert_to_tensor=True,
                device=self.device,
                show_progress_bar=False
            )
        
        # Similarity search
        scores = util.dot_score(query_embedding, self.embeddings)[0]
        top_results = torch.topk(scores, k=min(top_k, len(self.embeddings)))

        # Sonuçları filtrele
        results = []
        for score, idx in zip(top_results.values, top_results.indices):
            if score > similarity_threshold:
                results.append({
                    "text": self.text_chunks[idx],
                    "source": self.sources[idx]
                })
        
        # Cache'e kaydet
        if use_cache:
            self._save_to_cache(cache_key, results)
        
        return results
    
    def _clean_llm_output(self, text: str) -> str:
        """LLM çıktısındaki istenmeyen tüm etiketleri ve formatlamayı temizler."""
        text = unicodedata.normalize('NFKC', text).strip()
        
        label_pattern = r'.*?\b(CEVAP|YANIT|ANSWER|ÖZET|SONUÇ|NOT)\s*[:*\-–—]\s*\*{0,2}\s*'
        match = re.search(label_pattern, text, flags=re.IGNORECASE | re.DOTALL)
        
        if match:
            text = text[match.end():].strip()
            logger.debug(f"Label found and removed. Remaining text: '{text[:50]}...'")
        
        unwanted_prefixes = [
            r'^\s*\*{0,2}\s*(cevap|yanıt|yanit|answer|not|özet)\s*[:\.]*\s*\*{0,2}\s*',
            r'^\s*[-–—]\s*',
        ]
        for pattern in unwanted_prefixes:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        text = re.sub(r'\*{2,}', '', text)
        text = text.replace('*', '')
        text = re.sub(r'\s+', ' ', text)
        text = text.strip(' .:*-–—')
        
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text

    def generate(self, query: str, context: list[dict], is_web_search: bool = False) -> str:
        """Verilen sorgu ve zenginleştirilmiş bağlam (context) ile cevap üretir."""
        context_str = ""
        for item in context:
            context_str += f"Kaynak: {item['source']}\nMetin: {item['text']}\n\n"

        # --- DEBUG LOGGING ---
        print("\n" + "="*40)
        mode = "WEB SEARCH" if is_web_search else "RAG"
        print(f"🔍 {mode} CONTEXT (Query: {query})")
        print("="*40)
        print(context_str.strip())
        print("="*40 + "\n")
        # ---------------------

        if is_web_search:
            # --- WEB SEARCH PROMPT (ESNEK) ---
            prompt = f"""
Sen bir yardımcı asistansın. Web arama sonuçlarından elde edilen aşağıdaki Context bilgisini kullanarak soruya cevap ver.

Context:
{context_str}

Soru: {query}

KURALLAR:
1. Webden gelen bilgiyi kullanarak kullanıcıya en iyi cevabı ver.
2. Context içindeki bilgiyi sentezle ve özetle.
3. "NO_CONTEXT" DEME. Elindeki bilgiyle yardımcı olmaya çalış.
4. EĞER aranan bölüm/konu metinde yoksa ama "şu fakülte altında", "şu isimle geçiyor" gibi bir açıklama varsa, BU BİLGİYİ KULLANARAK CEVAP VER. (Örn: Matematik -> Mühendislik ve Doğa Bilimleri altındadır gibi).
5. Tek paragraf, Türkçe, net ve anlaşılır özetle.
6. Cevabı DOĞRUDAN başlat.
            """
        else:
            # --- RAG PROMPT (GÜVENLİ/KATI) ---
            prompt = f"""
Sen bir üniversite yönetmelik uzmanısın. SADECE aşağıdaki Context bilgisini kullanarak soruya cevap ver.

Context:
{context_str}

Soru: {query}

ÖNEMLİ KURALLAR:
1. SADECE Context içinde verilen bilgiyi kullan. Kendinden bilgi ekleme.
2. Eğer Context içinde sorunun cevabı KESİN OLARAK yoksa, SADECE "NO_CONTEXT" yaz. Başka hiçbir şey yazma.
3. Bağlam (Context) soruyla tamamen alakasızsa, "NO_CONTEXT" yaz.
4. "Bu metinde bilgi yok" veya "Bilmiyorum" deme, sadece "NO_CONTEXT" çıktısı ver.
5. Cevabı DOĞRUDAN başlat - "Cevap:", "Yanıt:" gibi başlık KULLANMA.
6. Tek paragraf, Türkçe, net ve kısa cevap ver.
            """

        payload = {
            "model": settings.LLM_MODEL,
            "prompt": prompt,
            "stream": True
        }
        
        # --- OPENAI ENTEGRASYONU ---
        if settings.LLM_PROVIDER == "openai" and self.openai_client:
            try:
                stream = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "Sen bir üniversite yönetmelik uzmanısın."},
                        {"role": "user", "content": prompt}
                    ],
                    stream=True,
                )

                buffer = ""
                is_start_cleaned = False
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        text_chunk = chunk.choices[0].delta.content
                        
                        if not is_start_cleaned:
                            buffer += text_chunk
                            if len(buffer) >= 50: # OpenAI daha temiz dönüyor, buffer'ı kısa tutabiliriz
                                cleaned_buffer = self._clean_llm_output(buffer)
                                yield cleaned_buffer
                                is_start_cleaned = True
                                buffer = ""
                        else:
                            yield text_chunk
                
                if buffer and not is_start_cleaned:
                    cleaned_buffer = self._clean_llm_output(buffer)
                    yield cleaned_buffer
                    
                return # OpenAI bitti, fonksiyondan çık
                
            except Exception as e:
                logger.error(f"OpenAI Hatası: {e}")
                yield f"OpenAI API ile iletişimde hata oluştu: {str(e)}"
                return

        # --- OLLAMA (ESKİ YÖNTEM) ---
        try:
            api_url = urljoin(settings.OLLAMA_URL, "/api/generate")
            response = requests.post(api_url, json=payload, stream=True, timeout=300)
            response.raise_for_status()
            
            buffer = ""
            is_start_cleaned = False
            
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    text_chunk = chunk['response']
                    
                    if not is_start_cleaned:
                        buffer += text_chunk
                        if len(buffer) >= 100:
                            cleaned_buffer = self._clean_llm_output(buffer)
                            yield cleaned_buffer
                            is_start_cleaned = True
                            buffer = ""
                    else:
                        yield text_chunk
            
            if buffer and not is_start_cleaned:
                cleaned_buffer = self._clean_llm_output(buffer)
                yield cleaned_buffer
                        
        except requests.exceptions.RequestException as e:
            print(f"Ollama API'sine bağlanırken hata oluştu: {e}")
            yield "Üzgünüm, yapay zeka sunucusuna bağlanırken bir sorun oluştu."

    def answer_query(self, query: str) -> str:
        """Tüm RAG sürecini yönetir: retrieval ve generation."""
        relevant_context = self.retrieve(query, top_k=3)
        answer = self.generate(query, relevant_context)
        return answer
    
    def answer_query_with_context(self, query: str) -> dict:
        """Değerlendirme için hem cevabı hem de kullanılan context'i döndürür."""
        relevant_context_dicts = self.retrieve(query, top_k=3)
        context_texts = [item['text'] for item in relevant_context_dicts]
        answer = self.generate(query, relevant_context_dicts)
        
        return {
            "answer": answer,
            "contexts": context_texts
        }