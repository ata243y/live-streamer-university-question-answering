# quick_clean.py
import pandas as pd

from qa_app.config import settings

df = pd.read_parquet(settings.PROCESSED_DATA_PATH)

# Gürültülü kaynakları filtrele
noise_patterns = [
    'DIŞ KAPAK', 
    'Oturum Tarihi',
    '^T\.C\.$',  # Sadece "T.C." olanlar
    'REPUBLIC OF TÜRKİYE',  # 292 chunk boş İngilizce kapak
    '^Sayfa$',  # Sadece "Sayfa" yazanlar (117 chunk)
    'Toplam Hazırlık Toplam 1\. Sınıf',  # Tablo başlıkları (283 chunk)
    '^\d{4} MALİ YILI$',  # "2024 MALİ YILI" gibi (sadece başlık)
    'ANLAŞMA TARİHİ:',  # Boş anlaşma formları
    'Bu belge, güvenli elektronik imza',  # İmza sayfaları
    '^\d{4} -\d{4} Akademik Takvimi$',  # Sadece başlık olanlar
]

mask = df['source_document'].str.contains('|'.join(noise_patterns), case=False, na=False, regex=True)
df_cleaned = df[~mask]

print(f"  Silinen: {mask.sum()} chunk")
print(f" Kalan: {len(df_cleaned)} chunk")
print(f"\n Silinen kaynaklar:")
print(df[mask]['source_document'].value_counts().head(10))

df_cleaned.to_parquet(settings.PROCESSED_DATA_PATH, index=False)
print("\n✨ Temizlik tamamlandı!")