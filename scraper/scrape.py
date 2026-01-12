from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from time import sleep
import json
import os
from urllib.parse import urljoin, urlparse
from openai import OpenAI

import heapq
from typing import NamedTuple

from dotenv import load_dotenv
load_dotenv()

# Global Configurations
DEBUG = True 
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini" # Fast, cheap, and great for JSON extraction
MAX_DEPTH = 8
MAX_TRIES = 3
CHECKPOINT_FILE = "scraper_checkpoint.json"
START_FROM_CHECKPOINT = True # Set to False to restart from scratch
USE_AI_LINK_FILTER = True # If True, uses AI to select relevant links

class ScrapeTask(NamedTuple):
    depth: int
    tries: int
    url: str
    max_depth: int
    link_filter: str = "" # Optional filter, default empty string means no filter

def save_checkpoint(queue, visited, filename=CHECKPOINT_FILE):
    """
    Saves the current queue and visited set to a JSON file.
    """
    try:
        # Convert queue (heap of NamedTuples) to list of dicts
        queue_data = [
            {
                "depth": t.depth,
                "tries": t.tries,
                "url": t.url,
                "max_depth": t.max_depth,
                "link_filter": t.link_filter
            }
            for t in queue
        ]
        
        data = {
            "queue": queue_data,
            "visited": list(visited)
        }
        
        # Write to temp file first then rename to avoid corruption
        temp_filename = filename + ".tmp"
        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        os.replace(temp_filename, filename)
        print(f"[CHECKPOINT] Saved {len(queue)} tasks and {len(visited)} visited URLs.")
        
    except Exception as e:
        print(f"[ERROR] Failed to save checkpoint: {e}")

def load_checkpoint(filename=CHECKPOINT_FILE):
    """
    Loads queue and visited set from a JSON file.
    Returns (queue, visited) tuple or (None, None) if failed/not found.
    """
    if not os.path.exists(filename):
        return None, None
        
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        visited = set(data.get("visited", []))
        
        raw_queue = data.get("queue", [])
        queue = []
        for item in raw_queue:
            task = ScrapeTask(
                depth=item["depth"],
                tries=item["tries"],
                url=item["url"],
                max_depth=item["max_depth"],
                link_filter=item.get("link_filter", "")
            )
            heapq.heappush(queue, task)
            
        print(f"[RESUME] Loaded checkpoint: {len(queue)} tasks, {len(visited)} visited.")
        return queue, visited
        
    except Exception as e:
        print(f"[ERROR] Failed to load checkpoint: {e}")
        return None, None


    # Define custom comparison to skip URL comparison if depths/tries are equal (url might not be comparable or needed for sorting)
    # The default tuple comparison works fine: (depth, tries, url, max_depth). 
    # Python compares element by element.
    # Lower depth -> higher priority (popped first in min-heap)
    # Lower tries -> higher priority (fresh tries preferred over retries)

# --- THE RAG PROMPT ---
# This prompt is engineered to create "Dense Vector Embeddings" later.
RAG_SYSTEM_PROMPT = """
You are an expert Data Extraction AI for a RAG system.
Your goal is to extract ANY and ALL information that typically interests a university student.

OUTPUT INSTRUCTIONS:
1. Return PLAIN TEXT in TURKISH LANGUAGE (Türkçe).
2. Structure the text with clear headings and bullet points.
3. IGNORE TECHNICAL NOISE: 
   - Cookie policies, "Accept Cookies" buttons.
   - Login instructions to systems (unless it explains what the system IS).
   - "Javascript required" warnings.
   - Software version numbers (e.g., "v2.0.2.138").
   - Browser compatibility lists.
   
4. EXTRACT EVERYTHING ELSE:
   - If it's a forum, extract the discussion topic and useful replies.
   - If it's a policy, extract the rules.
   - If it's an announcement, extract the content.
   - If it's a cafeteria menu, extract it.
   - If it's a generic page about the university, extract all details.

The goal is to build a knowledge base that answers ANY question a student might have (academic, social, logistical, administrative).
If the text contains ONLY ignored technical noise, return an empty string.
"""

LINK_SELECTION_PROMPT = """
You are a crawler assistant for a university student.
Your task is to select links that are likely to contain useful information for a student (courses, announcements, events, rules, campus life,university).

INPUT: A list of {"url": "...", "text": "..."} objects. 
The 'text' field may contain additional context like [Title: ...] or [Aria: ...]. Use this extra info to better judge relevance.

INSTRUCTIONS:
1. Select only links that are RELEVANT to a student or possibly contain university information.
2. IGNORE:
   - Login pages / Portals (unless it's a guide about them).
   - "Forgot Password" / "Help" technical pages.
   - Genuine language toggles (EN/TR) unless it leads to a disparate content section.
   - Privacy Policies, Legal disclaimers, Sitemaps.

OUTPUT:
Return a JSON object with a single key "selected_urls" containing a list of strings (the URLs).
Example: {"selected_urls": ["https://.../announcements", "https://.../courses"]}
"""

def extract_clean_text(html_content):
    """
    Generic function to strip HTML tags, scripts, and styles.
    Returns clean, readable text suitable for AI/RAG.
    Saves output to 'cleaned_text_debug.json' if DEBUG is True.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Remove "noise" tags that contain code or navigation, not content
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe", "svg"]):
        tag.decompose()

    # 2. Extract text with a separator to keep paragraphs distinct
    text = soup.get_text(separator="\n", strip=True)

    # 3. Post-processing: Remove excessive newlines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # --- DEBUG SAVING LOGIC ---
    if DEBUG:
        try:
            # We wrap it in a JSON object so it handles newlines/special characters correctly
            debug_data = {
                "char_count": len(clean_text),
                "content": clean_text
            }
            
            with open("cleaned_text_debug.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=4, ensure_ascii=False)
                
            print(f"[DEBUG] Saved cleaned text ({len(clean_text)} chars) to 'cleaned_text_debug.json'")
        except Exception as e:
            print(f"[DEBUG] Error saving debug file: {e}")
    # --------------------------

    return clean_text


def extract_links(html_content, base_url):
    """
    Extracts all hrefs from <a> tags, converting to absolute URLs.
    Returns a list of dicts: [{"url": "...", "text": "..."}, ...]
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    found_links = {} # Use dict to store unique URLs with best text
    
    # 1. Parse all <a> tags
    for a_tag in soup.find_all("a", href=True):
        raw_link = a_tag['href']
        
        # Skip noise (javascript triggers, anchors, empty links)
        if raw_link.startswith(("javascript:", "#", "mailto:", "tel:")) or not raw_link.strip():
            continue

        # 2. Convert to Absolute URL
        full_url = urljoin(base_url, raw_link)
        
        # 3. Extract Text & Attributes for Context
        visible_text = " ".join(a_tag.get_text().split()).strip()
        title_attr = a_tag.get("title", "").strip()
        aria_label = a_tag.get("aria-label", "").strip()
        
        # Check for image alt text
        img_alt = ""
        img = a_tag.find("img")
        if img:
            img_alt = img.get("alt", "").strip()
            
        # Combine into a single descriptive string
        parts = [visible_text]
        if title_attr and title_attr != visible_text:
            parts.append(f"[Title: {title_attr}]")
        if aria_label and aria_label != visible_text:
            parts.append(f"[Aria: {aria_label}]")
        if img_alt and img_alt != visible_text:
            parts.append(f"[Img Alt: {img_alt}]")
            
        final_text = " ".join(parts).strip()
        
        # Fallback if empty
        if not final_text:
            final_text = "No Text"
        
        # Store. If URL exists, prefer longer text (likely more descriptive)
        if full_url not in found_links or len(final_text) > len(found_links[full_url]):
            found_links[full_url] = final_text

    # Convert to list of dicts for AI
    link_objects = [{"url": u, "text": t} for u, t in found_links.items()]

    # 3. Debug Saving Logic
    if DEBUG:
        debug_data = {
            "source_page": base_url,
            "total_found": len(link_objects),
            "links": link_objects
        }
        
        try:
            with open("link.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[DEBUG] Failed to save link.json: {e}")

    return link_objects


def split_text_by_delimiter(text, delimiter="\n", max_chars=2000):
    """
    Splits text into chunks based on a delimiter, ensuring no chunk 
    exceeds the max_chars limit.
    """
    if not text:
        return []

    # 1. Split the text into atomic parts based on the delimiter
    parts = text.split(delimiter)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for part in parts:
        part_len = len(part)
        
        # Calculate length of delimiter (we only add it if it's not the first item)
        delimiter_len = len(delimiter) if current_chunk else 0
        
        # Check if adding this part would exceed the limit
        if current_length + delimiter_len + part_len > max_chars:
            # If the current chunk has content, save it
            if current_chunk:
                chunks.append(delimiter.join(current_chunk))
            
            # Start a new chunk with the current part
            current_chunk = [part]
            current_length = part_len
        else:
            # Add part to the current chunk
            current_chunk.append(part)
            current_length += delimiter_len + part_len
            
    # Add the final chunk if it exists
    if current_chunk:
        chunks.append(delimiter.join(current_chunk))
        
    return chunks

def save_data_to_json(new_data, filename="result.json"):
    """
    Appends new data to the existing JSON list in 'filename'.
    Creates the file if it doesn't exist.
    """
    existing_data = []

    # 1. Load existing data
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    loaded = json.loads(content)
                    if isinstance(loaded, list):
                        existing_data = loaded
                    else:
                        existing_data = [loaded]
        except json.JSONDecodeError:
            print(f"[WARN] {filename} corrupted or empty. Starting fresh.")
            existing_data = []
        except Exception as e:
            print(f"[ERROR] Could not read {filename}: {e}")

    # 2. Append new items
    if isinstance(new_data, list):
        existing_data.extend(new_data)
    else:
        existing_data.append(new_data)

    # 3. Write back
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"[SAVE] Successfully saved {len(new_data) if isinstance(new_data, list) else 1} items to {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save to {filename}: {e}")

def save_data_to_text(new_text_lines, filename="scraped_data.txt"):
    """
    Appends new text content to a plain text file.
    """
    if not new_text_lines:
        return

    try:
        # If input is a single string, wrap in list
        if isinstance(new_text_lines, str):
            new_text_lines = [new_text_lines]
            
        with open(filename, "a", encoding="utf-8") as f:
            for line in new_text_lines:
                f.write(line + "\n" + "="*80 + "\n") # Add separator
        
        print(f"[SAVE] Successfully saved {len(new_text_lines)} chunks to {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save to {filename}: {e}")


def extract_rag_data_with_ai(cleaned_text):
    """
    Sends cleaned text to the AI and returns a structured dictionary.
    Includes Timeout (20s) and Retry Logic.
    """
    chunks = split_text_by_delimiter(cleaned_text, max_chars=4000)

    # USER REQUEST: if there are more than 12 chunk just process first 12 skip the rest
    if len(chunks) > 12:
        print(f"[INFO] Limiting chunks from {len(chunks)} to 12")
        chunks = chunks[:12]

    client = OpenAI(api_key=API_KEY)
    results = []

    for i, chunk in enumerate(chunks):
        print(f"[AI] Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                # This call blocks execution until the full response is received
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": chunk}
                    ],
                    # response_format={"type": "json_object"},  <-- REMOVED
                    temperature=0.3,
                    timeout=60 # 20 seconds timeout
                )
    
                # Parse the output
                raw_text = response.choices[0].message.content
                # structured_data = json.loads(raw_json) <-- REMOVED
                
                print("[AI] Success.")
                results.append(raw_text)
                break # Break retry loop on success

            except Exception as e:
                retries += 1
                print(f"[AI] Error (Attempt {retries}/{max_retries}): {e}")
                if retries >= max_retries:
                    print("[AI] Max retries reached for this chunk. Skipping.")
                    print({
                        "error": "Max retries reached", 
                        "chunk_index": i, 
                        "details": str(e)
                    })
    
    return results

def filter_links_with_ai(links_data):
    """
    Uses OpenAI to select relevant links from a list of {"url":, "text":} objects.
    Processes links in batches to handle large lists.
    """
    if not links_data:
        return []

    print(f"[AI-FILTER] Filtering {len(links_data)} links...")

    all_selected_urls = []
    batch_size = 50
    client = OpenAI(api_key=API_KEY)

    for i in range(0, len(links_data), batch_size):
        batch = links_data[i : i + batch_size]
        print(f"[AI-FILTER] Processing batch {i//batch_size + 1}/{(len(links_data) + batch_size - 1)//batch_size} ({len(batch)} links)...")

        # DEBUG: Print what we are sending
        # print(f"[DEBUG-AI-INPUT] Sending {len(batch)} links to AI:")

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": LINK_SELECTION_PROMPT},
                    {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                timeout=30
            )

            content = response.choices[0].message.content

            # DEBUG: Print what we received
            # print(f"[DEBUG-AI-OUTPUT] Raw AI response: {content}")

            result = json.loads(content)
            selected_urls = result.get("selected_urls", [])
            print(f"[AI-FILTER] Batch result: Selected {len(selected_urls)} relevant links.")
            all_selected_urls.extend(selected_urls)

        except Exception as e:
            print(f"[AI-FILTER] Batch failed: {e}. Fallback to ALL links in this batch.")
            # Fallback: keep all URLs from this failed batch
            all_selected_urls.extend([l["url"] for l in batch])

    print(f"[AI-FILTER] Completed. Total selected: {len(all_selected_urls)} relevant links out of {len(links_data)}.")
    return all_selected_urls

def is_page_loaded(driver):
    """
    Checks if the page is successfully loaded.
    Custom logic can be added here (e.g. checking specific elements).
    """
    try:
        # 1. Check title
        if driver.title:
            return True, "Loaded (Title found)"

        # 2. Fallback: Check body content length
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            text_content = body.text
            if len(text_content) > 500:
                return True, "Loaded (Body content found)"
        except:
            pass
        
        # 3. Last check: URL correctness?
        # If we are here, it means no title and little content.
        # But some pages are just weird. Let's be lenient if URL didn't change unexpectedly?
        
        return False, "Empty Title and insufficient Body content"
        
    except Exception as e:
        return False, str(e)




def run_scraping_session(start_from_checkpoint=True):
    """
    Runs one session of scraping. 
    Returns True if completed successfully (queue empty).
    Returns False if crashed/interrupted (needs restart).
    """
    # 1. Try to load checkpoint
    queue, visited = None, None
    if start_from_checkpoint:
        queue, visited = load_checkpoint()
    else:
        # If explicitly starting fresh, remove old checkpoint
        if os.path.exists(CHECKPOINT_FILE):
            try:
                os.remove(CHECKPOINT_FILE)
                print("[INIT] Removed old checkpoint.")
            except:
                pass
    
    # 2. If no checkpoint, initialize from config
    if queue is None:
        queue = []
        visited = set()
        
        # Initial seeds configuration
        start_configs = [
            {"url": "https://yokatlas.yok.gov.tr/", "max_depth": 8, "link_filter": ""},
        ]

        for config in start_configs:
            filter_str = config.get("link_filter", "")
            initial_task = ScrapeTask(depth=0, tries=0, url=config["url"], max_depth=config["max_depth"], link_filter=filter_str)
            heapq.heappush(queue, initial_task)
    
    if not queue:
        print("[INFO] Queue is empty. Nothing to do.")
        return True

    driver = None
    try:
        print("[INIT] Starting new driver session...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        
        tasks_processed = 0
        last_content_length = -1
        while queue:
            current_task = heapq.heappop(queue)
            depth, tries, url, max_depth, link_filter = current_task
            
            print(f"\n[QUEUE] Popping: Depth={depth}, Tries={tries}, URL={url}, MaxDepth={max_depth}, Filter='{link_filter}'")

            if depth > max_depth:
                print(f"[SKIP] Max depth {max_depth} reached for this branch.")
                continue
            
            if url in visited and tries == 0:
                print("[SKIP] Already visited.")
                continue

            try:
                driver.get(url)
                sleep(3) # Wait for JS

                success, message = is_page_loaded(driver)
                if not success:
                    raise Exception(f"Page load check failed: {message}")

                print(f"[SUCCESS] Page loaded. Processing...")
                visited.add(url)

                html = driver.page_source
                clean_text = extract_clean_text(html)
                
                # EXTRACT & SAVE RAG DATA
                if clean_text:
                    # USER REQUEST: if there is same number of information with previous page dont scrape it skip it
                    pass  # Placeholder just to anchor, logic continues below

                if clean_text:
                    current_len = len(clean_text)
                    if current_len == last_content_length:
                        print(f"[SKIP] Content length ({current_len}) same as previous page. Skipping.")
                        continue
                    
                    last_content_length = current_len
                    
                    rag_data = extract_rag_data_with_ai(clean_text)
                    if rag_data:
                        save_data_to_text(rag_data, filename="scraped_data.txt")

                if depth < max_depth:
                    # new_links is now a list of dicts: [{"url":.., "text":..}, ..]
                    new_links_data = extract_links(html, url)
                    
                    # USER REQUEST: just get the first 150 links to process (3 chunk)
                    if len(new_links_data) > 150:
                         print(f"[INFO] Found {len(new_links_data)} links. Truncating to first 150.")
                         new_links_data = new_links_data[:150]

                    final_urls = []
                    
                    if USE_AI_LINK_FILTER:
                         # Use AI to pick relevant URLs
                         # Filter logic might reduce the list significantly
                         final_urls = filter_links_with_ai(new_links_data)
                    else:
                        # Use all URLs
                        final_urls = [x["url"] for x in new_links_data]

                    for link in final_urls:
                        # Apply Link Filter (if set)
                        if link_filter and not link.startswith(link_filter):
                            # Skip this link
                            continue

                        if link not in visited:
                            # Push new links with depth+1, fresh tries
                            heapq.heappush(queue, ScrapeTask(depth + 1, 0, link, max_depth, link_filter))
        
                tasks_processed += 1
                if tasks_processed % 5 == 0:
                     save_checkpoint(queue, visited)

            except Exception as e:
                error_msg = str(e).lower()
                critical_errors = [
                    "no such window",
                    "target window already closed",
                    "web view not found",
                    "session not created",
                    "chrome not reachable",
                    "disconnected"
                ]
                
                if any(err in error_msg for err in critical_errors):
                    print(f"\n[CRITICAL] Browser/Driver died while processing {url}: {e}")
                    raise e # Re-raise to be caught by outer try/except, triggering restart
                
                print(f"[FAIL] Error scraping {url}: {e}")
                if tries < MAX_TRIES:
                    new_tries = tries + 1
                    print(f"[RETRY] Re-queueing {url} with tries={new_tries}")
                    heapq.heappush(queue, ScrapeTask(depth, new_tries, url, max_depth, link_filter))
                else:
                    print(f"[GIVEUP] Max tries {MAX_TRIES} reached for {url}")
        
        return True # Queue finished

    except KeyboardInterrupt:
        print("\n[STOP] Scraper stopped manually. Saving checkpoint...")
        save_checkpoint(queue, visited)
        return True # Treat manual stop as "finished" (don't auto-restart immediately)
        
    except Exception as e:
        print(f"\n[CRITICAL] Session crashed: {e}. Saving checkpoint...")
        save_checkpoint(queue, visited)
        return False # Crash state, request restart
        
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def main():
    first_run = True
    
    while True:
        try:
            # On first run, check global config. On restarts, ALWAYS resume.
            resume = START_FROM_CHECKPOINT if first_run else True
            
            finished = run_scraping_session(start_from_checkpoint=resume)
            
            first_run = False # Subsequent runs are always restarts/continuations
            
            if finished:
                print("\n[DONE] Scraping session ended naturally or stopped manually.")
                break
            
            print("\n[RESTART] Session crashed. Restarting in 5 seconds...")
            sleep(5)
            
        except KeyboardInterrupt:
            print("\n[STOP] Main loop interrupted.")
            break
        except Exception as e:
            print(f"\n[FATAL] Main loop error: {e}")
            break

if __name__ == "__main__":
    main()