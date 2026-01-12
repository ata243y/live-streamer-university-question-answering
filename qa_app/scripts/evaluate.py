import sys
import os
from tqdm import tqdm
from datasets import Dataset
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qa_app.core.rag_engine import RAGEngine
from qa_app.evaluation_dataset import EVALUATION_QUESTIONS
from qa_app.config import settings

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)
from langchain_ollama.chat_models import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings

def main():
    print("="*50)
    print("RAG SİSTEMİ DEĞERLENDİRME SCRIPT'İ BAŞLATILDI")
    print("="*50)

    rag_engine = RAGEngine()

    print("\nTest veri seti üzerinde cevaplar ve context'ler toplanıyor...")
    results = []
    for item in tqdm(EVALUATION_QUESTIONS, desc="Sorular işleniyor"):
        question = item["question"]
        response = rag_engine.answer_query_with_context(question)
        results.append({
            "question": question,
            "answer": response["answer"],
            "contexts": response["contexts"],
            "ground_truth": item["ground_truth"]
        })

    dataset = Dataset.from_pandas(pd.DataFrame(results))

    print("\nRAGAS ile metrikler hesaplanıyor... (Bu işlem uzun sürebilir)")
    
    evaluation_llm = ChatOllama(model=settings.LLM_MODEL, request_timeout=600)
    evaluation_embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
    
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]
    
    score = evaluate(
        dataset=dataset, 
        metrics=metrics, 
        llm=evaluation_llm,
        embeddings=evaluation_embeddings
    )

    print("\n" + "="*50)
    print("DEĞERLENDİRME SONUÇLARI")
    print("="*50)
    print(score)
    print("\n(Puanlar 0-1 arasındadır, 1 en iyi skordur)")
    print("="*50)

if __name__ == "__main__":
    main()