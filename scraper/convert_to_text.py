import json

def convert_to_text(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for entry in data:
                # Construct the text representation
                # Using a pipe-separated format similar to the previous jsonl file's text field style
                # but cleaning it up for readability and consistency.
                
                parts = []
                
                # Basic Info
                if entry.get("universite"):
                    parts.append(f"Üniversite: {entry['universite']}")
                if entry.get("fakulte"):
                    parts.append(f"Fakülte: {entry['fakulte']}")
                if entry.get("program"):
                    parts.append(f"Program: {entry['program']}")
                if entry.get("burs"):
                    parts.append(f"Burs: {entry['burs']}")
                if entry.get("ozellikler"):
                    parts.append(f"Özellikler: {entry['ozellikler']}")
                
                # Statistics
                stats = entry.get("istatistikler", {})
                stat_parts = []
                for year, values in stats.items():
                    if values and isinstance(values, dict):
                        puan = values.get("taban_puani")
                        sira = values.get("basari_sirasi")
                        if puan or sira:
                            stat_str = f"{year} - Puan: {puan if puan else 'Yok'}, Sıra: {sira if sira else 'Yok'}"
                            stat_parts.append(stat_str)
                
                if stat_parts:
                    parts.append("İstatistikler: [" + " | ".join(stat_parts) + "]")
                
                # Join all parts for this entry
                line = " | ".join(parts)
                
                # Write to file
                f_out.write(line + "\n")
                
        print(f"Successfully converted {len(data)} items to {output_file}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    convert_to_text("yokatlas_data.json", "yokatlas_rag.txt")
