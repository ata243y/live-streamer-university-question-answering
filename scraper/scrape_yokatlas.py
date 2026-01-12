from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
import json
import os
import re

# Global Configurations
DEBUG = True
OUTPUT_FILE = "yokatlas_data.json"

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def parse_scholarship(text):
    """
    Extracts scholarship info from the program details string.
    Example: "(İngilizce) (Burslu) (6 Yıllık)" -> "Burslu"
    """
    if not text:
        return "Bilinmiyor"
    
    text = text.lower()
    if "burslu" in text:
        return "Burslu"
    if "%50" in text:
        return "%50 İndirimli"
    if "%25" in text:
        return "%25 İndirimli"
    if "ücretli" in text:
        return "Ücretli"
    if "devlet" in text: # Usually just implied if no scholarship info, but checking explicitly
        return "Devlet"
    
    return "Genel/Devlet"

def extract_year_value(font_tag):
    """
    Maps font color to year and extracts value.
    Red: 2025, Purple: 2024, Blue: 2023, Green: 2022
    """
    color = font_tag.get("color", "").lower()
    value = clean_text(font_tag.get_text())
    
    # Handle "Dolmadı", "---", etc.
    if not value or value == "---":
        value = None

    if "red" in color:
        return "2025", value
    elif "purple" in color:
        return "2024", value
    elif "blue" in color:
        return "2023", value
    elif "green" in color:
        return "2022", value
    return None, None

def extract_table_data(html_content):
    """
    Parses the HTML to extract structured data from #mydata table.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="mydata")
    if not table:
        print("[WARN] Table #mydata not found.")
        return []

    extracted_rows = []
    
    # Iterate over body rows
    rows = table.find("tbody").find_all("tr")
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
            
        # Column Indices (0-based from inspect):
        # 0: Control (Hidden?)
        # 1: Uni Name & Faculty
        # 2: Program & Scholarship
        # 3: Ranking (Sıralama)
        # 4: Score (Puan)
        
        # NOTE: Verify indices. Usually 1st visible is 1. 0 might be the hidden one.
        # Based on subagent report:
        # Col 2: Uni
        # Col 3: Program
        # Col 4: Rank
        # Col 5: Score
        
        # Let's try explicit nth-child logic equivalent
        # cells list in BS4 contains all tds.
        # If there is a hidden td at start, cells[1] is Uni.
        
        try:
            # 1. University & Faculty
            uni_cell = cells[1]
            uni_name = clean_text(uni_cell.find("strong").get_text())
            faculty = clean_text(uni_cell.find("font").get_text())

            # 2. Program & Scholarship
            prog_cell = cells[2]
            program_name = clean_text(prog_cell.find("strong").get_text())
            details_text = clean_text(prog_cell.find("font").get_text())
            scholarship = parse_scholarship(details_text)

            # 3. Structuring Year Data
            year_data = {
                "2025": {"taban_puani": None, "basari_sirasi": None},
                "2024": {"taban_puani": None, "basari_sirasi": None},
                "2023": {"taban_puani": None, "basari_sirasi": None},
                "2022": {"taban_puani": None, "basari_sirasi": None},
            }

            # 4. Rankings (Col 3 in cells array?)
            rank_cell = cells[3]
            for font in rank_cell.find_all("font"):
                year, val = extract_year_value(font)
                if year:
                    year_data[year]["basari_sirasi"] = val

            # 5. Scores (Col 4 in cells array?)
            score_cell = cells[4]
            for font in score_cell.find_all("font"):
                year, val = extract_year_value(font)
                if year:
                    year_data[year]["taban_puani"] = val
            
            # Construct Final Object
            item = {
                "universite": uni_name,
                "fakulte": faculty,
                "program": program_name,
                "burs": scholarship,
                "ozellikler": details_text,
                "istatistikler": year_data
            }
            extracted_rows.append(item)
            
        except AttributeError as e:
            # Skip rows that don't match structure (headers etc)
            continue
        except IndexError:
            continue
            
    return extracted_rows

def save_data_to_json(new_data, filename=OUTPUT_FILE):
    existing_data = []
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    loaded = json.loads(content)
                    existing_data = loaded if isinstance(loaded, list) else [loaded]
        except Exception as e:
            print(f"[WARN] Could not read {filename}: {e}")

    if isinstance(new_data, list):
        existing_data.extend(new_data)
    else:
        existing_data.append(new_data)

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"[SAVE] Saved {len(new_data) if isinstance(new_data, list) else 1} items to {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save to {filename}: {e}")


def main():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    url = "https://yokatlas.yok.gov.tr/tercih-sihirbazi-t4-tablo.php"
    
    try:
        print(f"[INIT] Opening {url}...")
        driver.get(url)
        sleep(5) # Initial load

        page_num = 1
        
        while True:
            print(f"\n[PAGE] Processing Page {page_num}...")
            
            # 1. Scrape Content
            html = driver.page_source
            
            # 2. Extract Data Manually
            data = extract_table_data(html)
            
            if data:
                print(f"[EXTRACT] Found {len(data)} rows.")
                save_data_to_json(data)
            else:
                print("[WARN] No data found on this page.")

            # 3. Check Pagination
            try:
                next_btn_li = driver.find_element(By.ID, "mydata_next")
                classes = next_btn_li.get_attribute("class")
                
                if "disabled" in classes:
                    print("[DONE] Reached last page (Next button disabled).")
                    break
                
                # Click Next
                next_link = next_btn_li.find_element(By.TAG_NAME, "a")
                next_link.click()
                print("[NAV] Clicked Next. Waiting for reload...")
                
                sleep(3) # Wait for table to update
                page_num += 1
                
            except Exception as e:
                print(f"[ERROR] Pagination failed: {e}")
                break
                
    except KeyboardInterrupt:
        print("\n[STOP] Manual stop.")
    except Exception as e:
        print(f"[FAIL] Critical error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
