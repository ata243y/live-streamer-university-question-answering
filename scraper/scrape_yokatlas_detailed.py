from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep, time
import json
import os
import re

# Global Configurations
OUTPUT_FILE = "yokatlas_detailed.json"
BASE_URL = "https://yokatlas.yok.gov.tr/"

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def save_data(item, filename=OUTPUT_FILE):
    """
    Appends a single item to the JSON file properly.
    """
    exist_data = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    exist_data = json.loads(content)
        except:
            pass
    
    exist_data.append(item)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(exist_data, f, indent=4, ensure_ascii=False)

def handle_popup(driver):
    """
    Checks for and closes the accreditation popup if it appears.
    Identified as a 'featherlight' modal with a close icon.
    """
    try:
        # Wait for potential popup animation
        sleep(3)
        
        # Method 1: Featherlight close button
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, ".featherlight-close, .featherlight-close-icon")
            if close_btn.is_displayed():
                print("   [POPUP] Found 'Featherlight' popup. Closing...")
                close_btn.click()
                sleep(1) # Wait for fade out
                return
        except:
            pass

        # Method 2: Fallback for other modals (Bootstrap)
        modals = driver.find_elements(By.CSS_SELECTOR, ".modal.in, .modal.show")
        for modal in modals:
            if modal.is_displayed():
                print("   [POPUP] Found Bootstrap modal. Closing...")
                try:
                    close_btn = modal.find_element(By.CSS_SELECTOR, "button.close, button[data-dismiss='modal']")
                    close_btn.click()
                    sleep(1)
                except:
                    pass
    except Exception as e:
        pass

def extract_panel_content(driver, panel_id):
    """
    Extracts text/table content from an expanded panel.
    Retries if content is 'Yükleniyor...'.
    """
    retries = 0
    max_retries = 5
    
    while retries < max_retries:
        try:
            panel = driver.find_element(By.ID, panel_id)
            html = panel.get_attribute("innerHTML")
            soup = BeautifulSoup(html, "html.parser")
            
            raw_text = clean_text(soup.get_text())
            
            # Check for loading state
            if "Yükleniyor" in raw_text:
                retries += 1
                # print(f"      [WAIT] Content loading... ({retries}/{max_retries})")
                sleep(2)
                continue
            
            # Parsing Logic
            data = {}
            tables = soup.find_all("table")
            
            if tables:
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        cols = row.find_all(["td", "th"])
                        if len(cols) >= 2:
                            key = clean_text(cols[0].get_text())
                            val = clean_text(cols[1].get_text())
                            if key:
                                data[key] = val
                return data if data else raw_text
                
            else:
                return raw_text
                
        except Exception as e:
            return f"Error extracting content: {str(e)}"
    
    return "Timeout: Content stuck on Loading."

def main():
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    
    try:
        # 1. Get List of Universities
        print("[INIT] Getting University List...")
        driver.get(BASE_URL + "lisans-anasayfa.php")
        sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        uni_select = soup.find("select", id="univ")
        
        universities = []
        if uni_select:
            for option in uni_select.find_all("option"):
                val = option.get("value")
                name = clean_text(option.get_text())
                if val:
                    universities.append({"id": val, "name": name})
        
        print(f"[INIT] Found {len(universities)} universities.")
        
        # LIMIT FOR TESTING - User can remove this slice to run full crawl
        # universities = universities[:2] 
        
        for uni in universities:
            uni_id = uni["id"]
            uni_name = uni["name"]
            
            print(f"\n[UNI] Processing: {uni_name} ({uni_id})")
            
            # 2. Get Program List for University
            uni_url = f"{BASE_URL}lisans-univ.php?u={uni_id}"
            driver.get(uni_url)
            sleep(2)
            
            prog_soup = BeautifulSoup(driver.page_source, "html.parser")
            program_links = prog_soup.find_all("a", href=re.compile(r"^lisans\.php\?y="))
            
            programs = []
            for link in program_links:
                href = link.get("href")
                prog_name = clean_text(link.get_text())
                if href:
                    programs.append({"url": BASE_URL + href, "name": prog_name})
            
            print(f"   found {len(programs)} programs.")
            
            # LIMIT PROGRAMS FOR TESTING per UNI
            # programs = programs[:2]

            for prog in programs:
                prog_url = prog["url"]
                prog_name = prog["name"]
                
                print(f"   [PROG] Scraping: {prog_name}")
                driver.get(prog_url)
                
                # Check for Popup
                handle_popup(driver)
                
                # 3. Expand Dropdowns and Extract Details
                details = {}
                
                accordions = driver.find_elements(By.CSS_SELECTOR, "a.accordion-toggle")
                
                # We need to re-find elements sometimes if DOM changes, 
                # but accordions usually stay static. 
                # Better approach: Get list of hrefs/ids first, then click by selector.
                
                accordion_meta = []
                for acc in accordions:
                    try:
                        title = acc.text.strip()
                        target_id = acc.get_attribute("href").split("#")[-1]
                        accordion_meta.append({"title": title, "target_id": target_id, "element": acc})
                    except:
                        continue
                        
                for meta in accordion_meta:
                    title = meta["title"]
                    target_id = meta["target_id"]
                    
                    # Skip irrelevant sections
                    if not title or "YÖK" in title: 
                        continue
                        
                    try:
                        # Find fresh element to avoid StaleRef
                        toggle_btn = driver.find_element(By.CSS_SELECTOR, f"a[href='#{target_id}']")
                        
                        # Click to expand
                        # Check if already visible? usually collapsed.
                        toggle_btn.click()
                        sleep(1) # Wait for animation/load
                        
                        content = extract_panel_content(driver, target_id)
                        details[title] = content
                        
                    except Exception as e:
                        # print(f"      [WARN] Could not expand {title}: {e}")
                        details[title] = "Extraction Failed"

                # Save Result
                result = {
                    "universite": uni_name,
                    "program": prog_name,
                    "url": prog_url,
                    "detaylar": details
                }
                
                # Append immediately to avoid data loss
                save_data(result)

    except KeyboardInterrupt:
        print("\n[STOP] Manual stop.")
    except Exception as e:
        print(f"[FAIL] Critical Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
