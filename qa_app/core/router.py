import re
import unicodedata
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)

class QueryRouter:
    def __init__(self):
        """
        Yönlendiriciyi başlatır. Güvenlik ve sohbet için gerekli yapıları bir kere oluşturur.
        """
        # --- 1. GÜVENLİK UZMANI: Injection Filtresi ---
        self.injection_patterns = [

            # "Farz et ki...", "diyelim ki...", "sanki..." gibi ifadelerle modeli farklı bir role sokma girişimleri.
            r'(?=.*\b(farz et|varsayalım|diyelim ki|hayal et|sanki|mış gibi yap)\b)(?=.*\b(hafıza kaybı|yeni birisin|kuralların yok|her şey serbest|sınırsızsın|filtresizsin|unuttun)\b)',
            
            # 2. Dolaylı Sıfırlama ve Manipülasyon
            # Doğrudan "unut" demeden, sohbet geçmişini geçersiz kılmaya yönelik ifadeler.
            r'\b(önceki|yukarıdaki|geçmişteki|bu sohbetteki)\s+(konuşma|talimat|bilgi|kural|direktif).*\b(geçersiz|yok say|unut|önemli değil|dikkate alma|hiç yaşanmadı|bir testti)\b',
            r'\b(yeni bir sayfa açalım|temiz bir başlangıç|sıfırdan başlayalım|o konuyu kapatalım)\b',

            # 3. Genişletilmiş Unutma/Yoksayma Komutları
            r'(?=.*\b(unut|sil|yok say|görmezden gel|sıfırla|hatırlama|dikkate alma|kaale alma)\b)(?=.*\b(her şey|tüm|önceki|talimat|kural|bilgi|konuşma|hafıza|kimliğin|görevin|sınırlamaların|protokollerin)\b)',
            
            # 4. Otorite ve Görev Değişikliği
            # Modelin temel görev tanımını veya sadakatini sorgulatan ifadeler.
            r'(?=.*\b(asıl|gerçek|yeni|birincil)\s+(görevin|amacın|önceliğin)\b)(?=.*\b(değil|artık şu|olarak değişti)\b)',
            r'(?=.*\b(artık|bundan sonra)\b)(?=.*\b(bağlı değilsin|uymak zorunda değilsin|senin için geçerli değil)\b)',
            r'\b(rol\s+yap|gibi\s+davran|olarak\s+davran|taklidi yap)\b',

            # 5. Güvenlik Atlama 
            r'(?=.*\b(atla|bypass|ihlal et|devre dışı bırak|esnet)\b)(?=.*\b(güvenlik|filtre|koruma|kural|sansür|etik kuralları)\b)',
            
            # 6. Sistem Komutları Taklidi
            r'^(sistem|kullanıcı|asistan|system|user|assistant)\s*[:>]\s*',
            r'\[(talimat|sistem|gizli|admin|root|komut)\].*\[/(talimat|sistem|gizli|admin|root|komut)\]',
            
            # --- Olası İngilizce Gelişmiş Pattern'ler 
            r'(?=.*\b(forget|ignore|disregard|erase|delete|reset)\b)(?=.*\b(everything|all|previous|prior|instruction|command|rule|context|conversation)\b)',
            r'(?=.*\b(you|your role|your task)\b)(?=.*\b(are now|will act as|pretend to be)\b)',
            r'\b(new|different|updated|secret|confidential)\s+(instruction|prompt|rule|system|context)\b',
            r'\b(act as|roleplay as|pretend to be)\b',
            r'(?=.*\b(bypass|override|disable)\b)(?=.*\b(security|filter|safety|rule|censorship)\b)',
            r'<\s*(system|prompt|instruction|admin|root)\s*>',
            r'```(system|user|assistant|prompt)',
        ]
        
        self.injection_regex = re.compile('|'.join(self.injection_patterns), re.IGNORECASE | re.UNICODE)
        
        # Tehlikeli kelime kombinasyonları 
        self.danger_keywords_tr = {
            'unut', 'sil', 'yoksay', 'görmezden', 'atla', 'değiştir', 
            'yeni talimat', 'sistem', 'yetki', 'bypass', 'override'
        }
        self.danger_keywords_en = {
            'ignore', 'forget', 'disregard', 'pretend', 'act as',
            'system:', 'new instruction', 'override', 'bypass'
        }

        # --- 2. Sohbet Uzmanı: Chitchat Desenleri ---
        raw_chitchat_patterns = {
            "greeting": {
                "keywords": [
                    "selam", "selamlar", "slm", "merhaba", "merhabalar", "mrb", "hey", "hi", "hello",
                    "günaydın", "gunaydin", "iyi günler", "iyigünler", "iyi akşamlar", "iyiaksamlar",
                    "naber", "naber canım", "nabersin", "selamun aleyküm", "selamun aleykum"
                ],
                "response": "Merhaba! Ben GTU yönetmelikleri konusunda uzmanlaşmış yapay zeka asistanıyım. Sana nasıl yardımcı olabilirim?"
            },
            "wellbeing": {
                "keywords": [
                    "nasılsın", "nasilsin", "nasılsınız", "nasilsiniz", "nslsn",
                    "ne haber", "nehaber", "nasıl gidiyor", "nasilgidiyor",
                    "iyimisin", "iyi misin", "iyimisiniz", "ne var ne yok", "nevarne yok"
                ],
                "response": "Harikayım, sorduğun için teşekkürler! Yönetmeliklerle ilgili bir sorun var mı?"
            },
            "thanks": {
                "keywords": [
                    "teşekkürler", "teşekkür ederim", "teşekkür", "tesekkurler", "tesekkür ederim",
                    "çok teşekkürler", "çok teşekkür ederim", "cok tesekkurler",
                    "tşk", "tsk", "tşkler", "thx", "thanks", "thank you", "ty", "tysm",
                    "sağol", "sağolun", "sağolasın", "sagol", "sagolun", "sagolasın", "saol", "saolun",
                    "sağ ol", "sağ olun", "sağ olasın", "sag ol",
                    "eyvallah", "eyv", "eyw", "eyv allah", "eyvallah sağol",
                    "allah razı olsun", "allah razi olsun", "allaha razı olsun", "rabbim razı olsun",
                    "kralsın", "kralsin", "adamsın", "adamsin", "efsanesin", "süpersin", "harikasın",
                    "canımsın", "canisin", "canısın", "tatlısın", "opuyorum", "seviyorum"
                ],
                "response": "Rica ederim, yardımcı olabildiğime sevindim! Başka bir sorun var mı?"
            },
            "farewell": {
                "keywords": [
                    "görüşürüz", "gorusuruz", "hoşçakal", "hoscakal", "hoşça kal", "hosca kal",
                    "bay", "bye", "bb", "güle güle", "gule gule", "iyi günler", "kendine iyi bak",
                    "görüşmek üzere", "gorusmek uzere", "sonra görüşürüz"
                ],
                "response": "Görüşmek üzere, başka bir sorun olursa yine beklerim!"
            },
            "identity": {
                "keywords": [
                    "kimsin", "kim", "sen kimsin", "sen nesin", "ne yapabilirsin", "neler yapabilirsin",
                    "sen ne", "hangi konularda", "bana nasıl yardım edebilirsin",
                    "ne iş yapıyorsun", "görevin ne"
                ],
                "response": "Ben GTU öğrencilerine yönetmeliklerle ilgili sorularda yardımcı olan yapay zeka asistanıyım. Kayıt dondurma, ders ekleme-silme, mezuniyet şartları gibi konularda sorularını yanıtlayabilirim."
            },
            "affirmative": {
                "keywords": [
                    "tamam", "ok", "okay", "oki", "olur", "anladım", "anladim", "peki", "tamamdır",
                    "anlıyorum", "anliyorum", "güzel", "guzel", "iyi", "harika", "süper", "mükemmel"
                ],
                "response": "Süper! Başka bir konuda yardımcı olabilir miyim?"
            },
            "negative": {
                "keywords": [
                    "hayır", "hayir", "yok", "değil", "degil", "olmaz", "istemiyorum", "gerek yok"
                ],
                "response": "Tamam, anladım. Başka bir şey lazım olursa buradayım!"
            }
        }
        
        # Pattern'leri normalize et ve hızlı arama için set'e çevir
        self.chitchat_patterns = {}
        self.all_keywords_set = set()
        
        for category, data in raw_chitchat_patterns.items():
            normalized_keywords = [
                self._normalize_turkish(kw) for kw in data["keywords"]
            ]
            self.chitchat_patterns[category] = {
                "keywords": normalized_keywords,
                "keywords_set": set(normalized_keywords),
                "response": data["response"]
            }
            self.all_keywords_set.update(normalized_keywords)
        
        logger.info(f"QueryRouter başlatıldı. {len(self.all_keywords_set)} chitchat pattern yüklendi.")

    def _normalize_turkish(self, text: str) -> str:
        """Türkçe karakterleri normalize eder ve küçük harfe çevirir."""
        text = text.lower()
        
        replacements = {
            'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
            'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'
        }
        for tr_char, en_char in replacements.items():
            text = text.replace(tr_char, en_char)
        
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """İki string arasındaki benzerliği hesaplar (0-1 arası)"""
        return SequenceMatcher(None, str1, str2).ratio()

    def is_injection_attempt(self, query: str) -> bool:
        """
        Gelişmiş injection tespiti yapar.
        
        ÖNEMLİ: Hem orijinal hem normalize edilmiş metni kontrol eder.
        """
        # 1. Regex kontrolü (orijinal metin)
        if self.injection_regex.search(query):
            logger.warning(f" Injection detected (regex): {query[:100]}")
            return True
        
        # 2. Normalize edilmiş metin üzerinde regex kontrolü
        normalized = self._normalize_turkish(query)
        if self.injection_regex.search(normalized):
            logger.warning(f" Injection detected (normalized regex): {query[:100]}")
            return True
        
        # 3. Uzunluk kontrolü
        if len(query) > 500:
            logger.warning(f" Query too long ({len(query)} chars)")
            return True
        
        # 4. Özel karakter oranı kontrolü
        special_char_ratio = len(re.findall(r'[{}()<>[\]|\\`]', query)) / max(len(query), 1)
        if special_char_ratio > 0.15:
            logger.warning(f" Too many special chars ({special_char_ratio:.2%})")
            return True
        
        # 5. Tehlikeli kelime kombinasyonları kontrolü
        words_lower = query.lower()
        
        # Türkçe tehlikeli kombinasyonlar
        danger_count_tr = sum(1 for keyword in self.danger_keywords_tr if keyword in words_lower)
        if danger_count_tr >= 2:  # 2+ tehlikeli kelime varsa şüpheli
            logger.warning(f" Multiple danger keywords (TR): {danger_count_tr}")
            return True
        
        # İngilizce tehlikeli kombinasyonlar
        danger_count_en = sum(1 for keyword in self.danger_keywords_en if keyword in words_lower)
        if danger_count_en >= 2:
            logger.warning(f" Multiple danger keywords (EN): {danger_count_en}")
            return True
        
        # 6. Kod injection pattern'leri
        code_patterns = ['```', '<script', 'javascript:', 'onclick=', 'onerror=']
        if any(pattern in query.lower() for pattern in code_patterns):
            logger.warning(f" Code injection pattern detected")
            return True
        
        return False

    def get_chitchat_response(self, query: str) -> str | None:
        """
        OPTİMİZE EDİLMİŞ chitchat tespiti.
        
        Optimizasyon Stratejisi:
        1. Set lookup (O(1)) ile hızlı exact match
        2. Substring kontrolü sadece kısa sorgularda
        3. Fuzzy matching EN SON çare olarak
        """
        normalized_query = self._normalize_turkish(query)
        
        if not normalized_query or len(normalized_query) < 2:
            return "Lütfen bir soru sorun."
        
        words = normalized_query.split()
        word_count = len(words)
        
        # OPTİMİZASYON 1: EXACT MATCH (Set lookup - O(1))
        if normalized_query in self.all_keywords_set:
            for category, data in self.chitchat_patterns.items():
                if normalized_query in data["keywords_set"]:
                    logger.info(f" Chitchat (exact): '{query}' → {category}")
                    return data["response"]
        
        # OPTİMİZASYON 2: TEK KELİMELİK SORGULAR için direkt set lookup
        if word_count == 1:
            for category, data in self.chitchat_patterns.items():
                if normalized_query in data["keywords_set"]:
                    logger.info(f" Chitchat (single word): '{query}' → {category}")
                    return data["response"]
        
        # KISA SORGULAR (2-3 kelime): Daha fazla tolerans
        if word_count <= 3:
            # OPTİMİZASYON 3: SUBSTRING kontrolü
            for category, data in self.chitchat_patterns.items():
                for keyword in data["keywords"]:
                    if keyword in normalized_query or normalized_query in keyword:
                        logger.info(f" Chitchat (substring): '{query}' → {category}")
                        return data["response"]
            
            # OPTİMİZASYON 4: FUZZY MATCHING (sadece kısa sorgularda)
            for category, data in self.chitchat_patterns.items():
                for keyword in data["keywords"]:
                    # Önce uzunluk farkını kontrol et (hızlı pre-filter)
                    len_diff = abs(len(normalized_query) - len(keyword))
                    if len_diff > 3:  # Çok farklı uzunluktaysa skip
                        continue
                    
                    similarity = self._calculate_similarity(normalized_query, keyword)
                    if similarity >= 0.85:
                        logger.info(f" Chitchat (fuzzy {similarity:.2f}): '{query}' → {category}")
                        return data["response"]
        
        # UZUN SORGULAR: Sadece exact match (karma sorguları RAG'e yönlendir)
        logger.debug(f" No chitchat match: '{query}' ({word_count} words)")
        return None

    def debug_query(self, query: str) -> dict:
        """Sorgunun nasıl işlendiğini gösterir"""
        normalized = self._normalize_turkish(query)
        chitchat_response = self.get_chitchat_response(query)
        
        # En yakın pattern'i bul
        closest_pattern = None
        max_similarity = 0
        for category, data in self.chitchat_patterns.items():
            for keyword in data["keywords"]:
                similarity = self._calculate_similarity(normalized, keyword)
                if similarity > max_similarity:
                    max_similarity = similarity
                    closest_pattern = f"{category}: {keyword}"
        
        return {
            "original": query,
            "normalized": normalized,
            "word_count": len(normalized.split()),
            "is_in_exact_set": normalized in self.all_keywords_set,
            "is_injection": self.is_injection_attempt(query),
            "is_chitchat": chitchat_response is not None,
            "chitchat_response": chitchat_response,
            "closest_pattern": closest_pattern,
            "similarity": f"{max_similarity:.2f}"
        }

    def get_stats(self) -> dict:
        """Router istatistiklerini döndürür"""
        total_patterns = sum(len(data["keywords"]) for data in self.chitchat_patterns.values())
        return {
            "total_categories": len(self.chitchat_patterns),
            "total_patterns": total_patterns,
            "injection_patterns": len(self.injection_patterns),
            "danger_keywords_tr": len(self.danger_keywords_tr),
            "danger_keywords_en": len(self.danger_keywords_en),
            "categories": {cat: len(data["keywords"]) for cat, data in self.chitchat_patterns.items()}
        }