import pandas as pd
import torch
import sys
import os
import re
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from tqdm import tqdm
    from qa_app.config import settings
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"Hata: Gerekli kütüphaneler yüklenmemiş. Lütfen 'pip install -r requirements.txt' komutunu çalıştırın.")
    sys.exit(1)

tqdm.pandas()

def clean_text(text: str) -> str:
    """Metindeki gereksiz başlıkları, sayfa numaralarını ve fazla boşlukları temizler."""
    # Headers
    # Headers - GTU spesifik kaldırıldı, daha genel temizlik
    text = re.sub(r'T\.C\..*?ÜNİVERSİTESİ.*?\n', '', text, flags=re.IGNORECASE)
    # text = re.sub(r'GEBZE TEKNİK ÜNİVERSİTESİ.*?\n', '', text, flags=re.IGNORECASE) # Removed hardcoded GTU
    
    # Page numbers
    text = re.sub(r'\d+\s*\|\s*.*', '', text)
    text = re.sub(r'\d+\s*/\s*\d+', '', text)
    
    # Document codes
    text = re.sub(r'\b0356\b', '', text)
    
    # Garip bölünmüş kelimeleri düzelt
    text = re.sub(r'ÜN\s+İVERS\s+İTES\s+İ', 'ÜNİVERSİTESİ', text, flags=re.IGNORECASE)
    text = re.sub(r'([A-ZİÖÜÇŞĞ])\s+([a-zıöüçşğ])', r'\1\2', text)
    
    # Normalize whitespace while keeping structure
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' \n ', '\n', text)
    
    return text.strip()

def normalize_source_title(title: str) -> str:
    """Kaynak başlıklarını normalize et"""
    # Döküman kodlarını temizle
    title = re.sub(r'\b0356\b', '', title)
    title = re.sub(r'YÖ-\d+', '', title)
    
    # PDF uzantısını kaldır
    title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE)
    
    # Revision numaralarını kaldır (R1, R2 gibi)
    title = re.sub(r'\s+R\d+', '', title, flags=re.IGNORECASE)
    
    # T.C. standardize et - ÖNEMLİ: Tüm varyasyonları yakala
    title = re.sub(r'T\.\s*C\.', 'T.C.', title, flags=re.IGNORECASE)
    title = re.sub(r'^T\s*\.\s*C\s*\.?\s*$', 'T.C.', title, flags=re.IGNORECASE)
    title = re.sub(r'^T\s*C\s*$', 'T.C.', title, flags=re.IGNORECASE)
    
    # Garip bölünmüş üniversite kelimelerini düzelt
    title = re.sub(r'ÜN\s+İVERS\s+İTES\s+İ', 'ÜNİVERSİTESİ', title, flags=re.IGNORECASE)
    
    # Tarihleri temizle
    title = re.sub(r'\s*Tarihi\s+\d{2}\.\d{2}\.\d{4}.*$', '', title, flags=re.IGNORECASE)
    
    # Fazla boşlukları temizle
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Boş veya çok kısa başlıkları "GENEL" yap
    if not title or len(title) < 3:
        title = "GENEL YÖNERGE"
    
    return title

def load_and_split_documents(data_dir: str) -> list[dict]:
    """
    Veri klasöründeki tüm .txt dosyalarını okur ve "===" ayıracına göre ayrı yönergelere böler.
    """
    print(f"Veri klasörü taranıyor: {data_dir}")
    if not os.path.exists(data_dir):
        print(f"HATA: Belirtilen klasör bulunamadı -> {data_dir}")
        return []

    documents = []
    
    # Iterate over all files in directory
    for filename in os.listdir(data_dir):
        if not filename.endswith(".txt"):
            continue
            
        file_path = os.path.join(data_dir, filename)
        print(f"Dosya işleniyor: {filename}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
            
            doc_splits = re.split(r'={40,}', full_text)
            
            for split in doc_splits:
                if not split.strip():
                    continue
                
                lines = split.strip().split('\n')
                raw_title = lines[0].strip()
                # If first line is empty or separator, use filename as fallback title base
                if not raw_title: 
                     raw_title = os.path.splitext(filename)[0]

                title = normalize_source_title(raw_title)
                content = "\n".join(lines[1:])
                
                if content.strip():  # Only add if has content
                    documents.append({'source': title, 'content': content})
                    
        except Exception as e:
            print(f"HATA: {filename} dosyası okunurken hata: {e}")
            continue
        
    print(f"Toplam {len(documents)} adet yönerge/bölüm yüklendi.")
    return documents

def extract_metadata(text: str) -> dict:
    """Extract metadata from text chunk"""
    metadata = {}
    
    # Extract article number
    madde_match = re.search(r'Madde\s+(\d+)', text, flags=re.IGNORECASE)
    metadata['madde_no'] = madde_match.group(1) if madde_match else None
    
    # Extract section markers
    if 'AMAÇ' in text.upper() or 'Amaç' in text:
        metadata['section_type'] = 'amaç'
    elif 'KAPSAM' in text.upper() or 'Kapsam' in text:
        metadata['section_type'] = 'kapsam'
    elif 'Madde' in text or 'MADDE' in text:
        metadata['section_type'] = 'madde'

    elif 'YÖ-' in text.upper() or 'YÖNERGESİ' in text.upper() or 'YÖNETMELİK' in text.upper():
        metadata['doc_type'] = 'yonerge'  # Yüksek öncelik
    elif 'ANLAŞMA' in text.upper() or 'anlaşma' in text[:200]:
        metadata['doc_type'] = 'anlaşma'  # Düşük öncelik
    elif 'TAKVİM' in text.upper():
        metadata['doc_type'] = 'takvim'
    else:
        metadata['section_type'] = 'genel'
    
    return metadata

def process_document(document: dict) -> list[dict]:
    """
    Tek bir yönerge metnini alır, temizler, chunk'lara böler ve
    metadata ile zenginleştirir.
    """
    source_title = document['source']
    clean_content = clean_text(document['content'])
    
    # Optimized text splitter - chunk_size biraz azaltıldı
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,  # 800'den 700'e düşürdüm
        chunk_overlap=150,
        separators=[
            "\n\n\n",
            "\n\n",
            "\nMadde ",
            "\nMADDE ",
            "\n",
            ". ",
            " "
        ],
        keep_separator=True,
        length_function=len
    )
    
    chunks_texts = text_splitter.split_text(clean_content)
    
    chunks = []
    for idx, text in enumerate(chunks_texts):
        # Skip very short chunks
        if len(text.strip()) < 100:
            continue
            
        metadata = extract_metadata(text)
        
        chunk_data = {
            "text_chunk": f"{source_title}\n{source_title}\n{text.strip()}",
            "source_document": source_title,
            "chunk_id": f"{source_title}_{idx}",
            "chunk_index": idx,
            "char_count": len(text),
            "word_count": len(text.split()),
            **metadata
        }
        chunks.append(chunk_data)
    
    return chunks

def add_context_windows(chunks: list[dict], context_size: int = 150) -> list[dict]:
    """Add sliding context window from adjacent chunks"""
    for i, chunk in enumerate(chunks):
        # Previous context
        if i > 0:
            prev_text = chunks[i-1]['text_chunk']
            chunk['context_before'] = prev_text[-context_size:] if len(prev_text) > context_size else prev_text
        else:
            chunk['context_before'] = ""
        
        # Next context
        if i < len(chunks) - 1:
            next_text = chunks[i+1]['text_chunk']
            chunk['context_after'] = next_text[:context_size] if len(next_text) > context_size else next_text
        else:
            chunk['context_after'] = ""
    
    return chunks

def print_statistics(df: pd.DataFrame):
    """Print comprehensive statistics about the processed data"""
    print("\n" + "="*60)
    print("VERİ İSTATİSTİKLERİ")
    print("="*60)
    print(f"Toplam chunk sayısı: {len(df)}")
    print(f"Ortalama chunk uzunluğu: {df['char_count'].mean():.0f} karakter")
    print(f"Min chunk uzunluğu: {df['char_count'].min()} karakter")
    print(f"Max chunk uzunluğu: {df['char_count'].max()} karakter")
    print(f"Ortalama kelime sayısı: {df['word_count'].mean():.0f}")
    print(f"Benzersiz kaynak sayısı: {df['source_document'].nunique()}")
    
    if 'embedding' in df.columns:
        print(f"Embedding boyutu: {df['embedding'].iloc[0].shape}")
    
    print(f"\nBölüm tipine göre dağılım:")
    if 'section_type' in df.columns:
        print(df['section_type'].value_counts())
    
    print(f"\nKaynaklara göre chunk dağılımı:")
    source_counts = df['source_document'].value_counts()
    for source, count in source_counts.head(10).items():
        print(f"  {source[:50]}: {count}")
    print("="*60)

def main():
    print("="*60)
    print("GELİŞMİŞ RAG VERİ İŞLEME SCRIPT'İ BAŞLATILDI")
    print("="*60)

    # 1. Load and split documents
    documents = load_and_split_documents(settings.RAW_DATA_DIR)
    if not documents:
        print("İşlenecek veri bulunamadı. Script sonlandırılıyor.")
        return

    # 2. Process all documents
    all_chunks = []
    print("\nTüm yönergeler parçalara ayrılıyor (chunking)...")
    for doc in tqdm(documents, desc="Yönergeler işleniyor"):
        chunks = process_document(doc)
        if chunks:
            all_chunks.extend(chunks)
    
    print(f"Toplam {len(all_chunks)} adet chunk oluşturuldu.")
    
    if not all_chunks:
        print("HATA: Hiçbir chunk oluşturulamadı!")
        return

    # 3. Add context windows (optional but recommended for RAG)
    print("Context window'lar ekleniyor...")
    all_chunks = add_context_windows(all_chunks)

    # 4. Create DataFrame
    df = pd.DataFrame(all_chunks)

    # 5. Load embedding model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nEmbedding modeli yükleniyor ({device})...")
    embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL, device=device)

    # 6. Generate embeddings
    text_to_embed = df["text_chunk"].tolist()
    
    print("Embedding'ler oluşturuluyor...")
    embeddings = embedding_model.encode(
        text_to_embed,
        batch_size=32,
        show_progress_bar=True,
        convert_to_tensor=True,
        normalize_embeddings=True  # Normalize for cosine similarity
    )
    df["embedding"] = [emb.cpu().numpy() for emb in embeddings]
    
    # 7. Save processed data
    os.makedirs(os.path.dirname(settings.PROCESSED_DATA_PATH), exist_ok=True)
    df.to_parquet(settings.PROCESSED_DATA_PATH, index=False)
    
    # 8. Print statistics
    print_statistics(df)
    
    print("\n" + "="*60)
    print("VERİ İŞLEME BAŞARIYLA TAMAMLANDI!")
    print(f"Oluşturulan dosya: {settings.PROCESSED_DATA_PATH}")
    print(f"DataFrame kolonları: {df.columns.tolist()}")
    print("="*60)

if __name__ == "__main__":
    main()