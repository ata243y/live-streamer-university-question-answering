import json
import os
from collections import defaultdict

def process_yokatlas_data():
    input_path = "scraper/yokatlas_data.json"
    output_path = "qa_app/data/raw/yokatlas_processed.txt"
    
    print(f"Reading JSON from {input_path}...")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {input_path}")
        return

    # Group by University + Program
    # Key: (Universite, Program)
    # Value: List of entries (variants like Burslu, %50, etc.)
    grouped_data = defaultdict(list)
    
    print("Grouping data by University and Program...")
    for entry in data:
        univ = entry.get('universite', '').strip()
        prog = entry.get('program', '').strip()
        if univ and prog:
            grouped_data[(univ, prog)].append(entry)

    print(f"Found {len(grouped_data)} unique University-Program pairs.")
    
    # Format as text
    # Delimiter for ingest.py is usually "=================================================="
    # or just separate files. ingest.py splits by r'={40,}'
    
    output_lines = []
    
    for (univ, prog), variants in grouped_data.items():
        # Separator for splitting chunks
        output_lines.append("=" * 50)
        
        # Title of the chunk
        output_lines.append(f"{univ} - {prog}")
        output_lines.append("") # Empty line
        
        # Process each variant (e.g. Burslu, %50 İndirimli)
        for variant in variants:
            burs = variant.get('burs', 'Belirtilmemiş')
            fakulte = variant.get('fakulte', '')
            ozellikler = variant.get('ozellikler', '')
            stats = variant.get('istatistikler', {})
            
            output_lines.append(f"--- {burs} ---")
            output_lines.append(f"Fakülte: {fakulte}")
            if ozellikler:
                output_lines.append(f"Özellikler: {ozellikler}")
            
            output_lines.append("Taban Puan ve Başarı Sıralamaları:")
            # Sort years descending
            years = sorted(stats.keys(), reverse=True)
            for year in years:
                y_data = stats[year]
                puan = y_data.get('taban_puani')
                sira = y_data.get('basari_sirasi')
                
                # Format nicely
                line = f"  • {year}: "
                if puan:
                    line += f"Puan {puan}"
                else:
                    line += "Puan Yok"
                    
                if sira:
                    line += f", Sıra {sira}"
                
                output_lines.append(line)
            
            output_lines.append("") # Empty line between variants
            
        output_lines.append("") # Empty line at end of chunk

    print(f"Writing processed text to {output_path}...")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
        
    print("Done! Data is ready for ingestion.")

if __name__ == "__main__":
    process_yokatlas_data()
