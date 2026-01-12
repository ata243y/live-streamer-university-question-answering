from openai import OpenAI
from qa_app.config import settings
import logging

logger = logging.getLogger(__name__)

class WebSearchAgent:
    def __init__(self):
        self.client = None
        if settings.OPENAI_API_KEY:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OPENAI_API_KEY not found. Web search will not work.")

    def search_and_answer(self, query: str) -> str:
        """
        Uses OpenAI with web_search tool to answer the query.
        """
        if not self.client:
            return "Web search is not available (Missing API Key)."

        try:
            logger.info(f"Initiating Web Search for: '{query}'")
            
            # Using the new model which supports search (e.g. gpt-5-search-api)
            # We rely on the model name to trigger the search capability natively.
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_SEARCH_MODEL,
                messages=[
                    {"role": "user", "content": query}
                ]
            )

            return response.choices[0].message.content



        except Exception as e:
            logger.error(f"Web Search Error: {e}")
            return f"Web araması sırasında hata oluştu: {str(e)}"
