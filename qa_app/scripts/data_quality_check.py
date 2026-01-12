"""
Veri kalitesini kontrol eden script.
İşlenmiş veride sorun var mı diye bakar.
"""

import pandas as pd
import numpy as np
from collections import Counter
import re

def check_data_quality(parquet_path: str):
    """İşlenmiş veriyi detaylı kontrol eder"""
    
    print("="*70)
    print("VERİ KALİTE KONTROLÜ BAŞLATILIYOR")
    print("="*70)
    
    # 1. Load data
    df = pd.read_parquet(parquet_path)
    print(f" Veri yüklendi: {len(df)} chunk\n")
    
    # 2. Chunk boyut kontrolü
    print(" CHUNK BOYUT ANALİZİ")
    print("-" * 70)
    
    very_short = df[df['char_count'] < 100]
    very_long = df[df['char_count'] > 750]
    
    print(f"Çok kısa (<100 kar): {len(very_short)} chunk ({len(very_short)/len(df)*100:.1f}%)")
    print(f"Çok uzun (>750 kar): {len(very_long)} chunk ({len(very_long)/len(df)*100:.1f}%)")
    print(f"İdeal aralık (100-750): {len(df) - len(very_short) - len(very_long)} chunk")
    
    if len(very_short) > 0:
        print(f"\n  En kısa 3 chunk:")
        for idx, row in very_short.nsmallest(3, 'char_count').iterrows():
            print(f"   [{row['char_count']} kar] {row['text_chunk'][:80]}...")
    
    # 3. Kaynak doküman kontrolü
    print(f"\n📚 KAYNAK DOKÜMAN ANALİZİ")
    print("-" * 70)
    
    source_counts = df['source_document'].value_counts()
    print(f"Benzersiz kaynak sayısı: {len(source_counts)}")
    print(f"\nKaynak dağılımı:")
    
    for source, count in source_counts.head(10).items():
        pct = count / len(df) * 100
        bar = "" * int(pct / 2)
        print(f"  {source[:45]:45s} │ {count:4d} chunks ({pct:5.1f}%) {bar}")
    
    # 4. Kaynak isim tutarlılık kontrolü
    print(f"\n  KAYNAK İSİM TUTARLILIK KONTROLÜ")
    print("-" * 70)
    
    problematic_sources = []
    for source in source_counts.index:
        # T.C. varyasyonları
        if 'T.C' in source or 'T. C' in source:
            if source not in ['T.C.', 'T.C']:
                problematic_sources.append(source)
        
        # Döküman kodları
        if re.search(r'\b\d{4}\b', source):
            problematic_sources.append(source)
        
        # PDF uzantıları
        if '.pdf' in source.lower():
            problematic_sources.append(source)
    
    if problematic_sources:
        print(" Normalize edilmesi gereken kaynaklar:")
        for source in set(problematic_sources):
            print(f"   - {source}")
    else:
        print(" Tüm kaynak isimleri tutarlı görünüyor")
    
    # 5. Madde numarası kontrolü
    print(f"\n MADDE NUMARASI ANALİZİ")
    print("-" * 70)
    
    has_madde = df[df['madde_no'].notna()]
    print(f"Madde numarası olan chunk: {len(has_madde)} ({len(has_madde)/len(df)*100:.1f}%)")
    
    if len(has_madde) > 0:
        madde_counts = Counter(has_madde['madde_no'])
        print(f"En sık görülen madde numaraları:")
        for madde, count in madde_counts.most_common(10):
            print(f"   Madde {madde}: {count} chunk")
    
    # 6. Section type dağılımı
    print(f"\n BÖLÜM TİPİ DAĞILIMI")
    print("-" * 70)
    
    section_dist = df['section_type'].value_counts()
    total = len(df)
    
    for section, count in section_dist.items():
        pct = count / total * 100
        bar = "" * int(pct / 3)
        print(f"  {section:12s} │ {count:4d} chunks ({pct:5.1f}%) {bar}")
    
    # 7. Context window kontrolü
    print(f"\n CONTEXT WINDOW ANALİZİ")
    print("-" * 70)
    
    no_prev_context = df[df['context_before'] == '']
    no_next_context = df[df['context_after'] == '']
    
    print(f"Önceki context yok: {len(no_prev_context)} chunk")
    print(f"Sonraki context yok: {len(no_next_context)} chunk")
    print(f"Her iki context da var: {len(df) - len(no_prev_context) - len(no_next_context)} chunk")
    
    # 8. Embedding kontrolü
    print(f"\n EMBEDDING ANALİZİ")
    print("-" * 70)
    
    emb_shape = df['embedding'].iloc[0].shape
    print(f"Embedding boyutu: {emb_shape}")
    
    # Null embedding kontrolü
    null_embeddings = 0
    zero_embeddings = 0
    
    for emb in df['embedding'].head(100):  # İlk 100'ü kontrol et
        if emb is None:
            null_embeddings += 1
        elif np.all(emb == 0):
            zero_embeddings += 1
    
    if null_embeddings > 0:
        print(f" NULL embedding: {null_embeddings}")
    if zero_embeddings > 0:
        print(f" Sıfır embedding: {zero_embeddings}")
    if null_embeddings == 0 and zero_embeddings == 0:
        print(f" Tüm embedding'ler geçerli")
    
    # 9. Duplicate kontrolü
    print(f"\n🔍 DUPLİKAT KONTROLÜ")
    print("-" * 70)
    
    duplicate_texts = df[df.duplicated(subset=['text_chunk'], keep=False)]
    if len(duplicate_texts) > 0:
        print(f"  Aynı text'e sahip {len(duplicate_texts)} chunk bulundu")
        print(f"   Benzersiz duplicate text sayısı: {duplicate_texts['text_chunk'].nunique()}")
    else:
        print(f" Duplicate chunk yok")
    
    # 10. İçerik kalitesi spot check
    print(f"\n İÇERİK KALİTESİ SPOT CHECK")
    print("-" * 70)
    
    # Random 3 chunk göster
    sample_chunks = df.sample(min(3, len(df)))
    
    for idx, row in sample_chunks.iterrows():
        print(f"\n Örnek Chunk #{idx}")
        print(f"   Kaynak: {row['source_document']}")
        print(f"   Madde: {row['madde_no'] or 'N/A'}")
        print(f"   Tip: {row['section_type']}")
        print(f"   Uzunluk: {row['char_count']} karakter, {row['word_count']} kelime")
        print(f"   İçerik: {row['text_chunk'][:200]}...")
    
    # 11. GENEL SKOR
    print(f"\n" + "="*70)
    print(" GENEL KALİTE SKORU")
    print("="*70)
    
    score = 100
    issues = []
    
    # Chunk boyut kontrolü
    if len(very_short) / len(df) > 0.1:
        score -= 10
        issues.append("Çok fazla kısa chunk var")
    
    # Kaynak tutarlılık
    if len(problematic_sources) > 0:
        score -= 15
        issues.append("Kaynak isimleri normalize edilmeli")
    
    # Embedding kontrolü
    if null_embeddings > 0 or zero_embeddings > 0:
        score -= 20
        issues.append("Geçersiz embedding'ler var")
    
    # Duplicate kontrolü
    if len(duplicate_texts) / len(df) > 0.05:
        score -= 10
        issues.append("Çok fazla duplicate chunk")
    
    print(f"\n Kalite Skoru: {score}/100")
    
    if score >= 90:
        print(" MÜKEMMEL! Veri kullanıma hazır.")
    elif score >= 70:
        print("  İYİ ama iyileştirme yapılabilir:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(" SORUNLAR VAR! Düzeltme gerekli:")
        for issue in issues:
            print(f"   - {issue}")
    
    print("="*70)
    
    return {
        'total_chunks': len(df),
        'quality_score': score,
        'issues': issues,
        'very_short_chunks': len(very_short),
        'duplicate_chunks': len(duplicate_texts),
        'problematic_sources': len(problematic_sources)
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        parquet_path = sys.argv[1]
    else:
        # Default path
        parquet_path = "qa_app/data/processed/gtu_rules_embeddings.parquet"
    
    try:
        result = check_data_quality(parquet_path)
        
        # Exit code: 0 if perfect, 1 if warnings, 2 if critical issues
        if result['quality_score'] >= 90:
            sys.exit(0)
        elif result['quality_score'] >= 70:
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print(f"\n HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)