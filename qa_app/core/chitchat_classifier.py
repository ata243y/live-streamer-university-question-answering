
import logging
import requests
import json
from qa_app.config import settings

logger = logging.getLogger(__name__)

class ChitchatClassifier:
    def __init__(self):
        self.provider = settings.CHITCHAT_CHECK_PROVIDER
        self.model = settings.CHITCHAT_CHECK_MODEL
        
        # Eğer provider openai ise ve client yoksa, burada başlatılabilir
        # Ancak basitlik için requests ile veya main'deki gibi openai kütüphanesiyle devam edebiliriz.
        # Burada openai kütüphanesini kullanacağız.
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        logger.info(f"ChitchatClassifier initialized with provider: {self.provider}, model: {self.model}")

    def is_chitchat(self, text: str) -> bool:
        """
        Determines if the given text is chitchat (small talk, greetings, etc.) 
        or a specific knowledge query (requiring RAG).
        
        Returns:
            True if chitchat
            False if knowledge query
        """
        try:
            prompt = f"""
            You are a classifier. Determine if the following user input is "Chitchat" (greetings, small talk, compliments, general conversation) or a "Knowledge Query" (questions about regulations, facts, specific information).
            
            Input: "{text}"
            
            Reply ONLY with "YES" if it is chitchat, or "NO" if it is a knowledge query. Do not add any punctuation.
            """
            
            if self.provider == "openai":
                return self._check_openai(prompt)
            elif self.provider == "ollama":
                return self._check_ollama(prompt)
            else:
                logger.warning(f"Unknown provider '{self.provider}', defaulting to False (Knowledge Query)")
                return False
                
        except Exception as e:
            logger.error(f"Error in chitchat classification: {e}")
            # Fail-safe: Assume it's a query not chitchat so we don't miss important questions
            return False

    def _check_openai(self, prompt: str) -> bool:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=5
            )
            answer = response.choices[0].message.content.strip().upper()
            logger.debug(f"OpenAI Chitchat Check: {answer}")
            return "YES" in answer
        except Exception as e:
            logger.error(f"OpenAI check failed: {e}")
            return False

    def _check_ollama(self, prompt: str) -> bool:
        try:
            url = f"{settings.OLLAMA_URL}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data.get("response", "").strip().upper()
            logger.debug(f"Ollama Chitchat Check: {answer}")
            return "YES" in answer
        except Exception as e:
            logger.error(f"Ollama check failed: {e}")
            return False
