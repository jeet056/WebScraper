#!/usr/bin/env python3
import sys, json, re, os, yaml
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

# -- CONFIGURATION --
def load_selectors():
    try:
        with open("selectors.yml") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Warning: selectors.yml not found, using default selectors")
        return {
            'default': {
                'container': 'body',
                'overview': 'meta[name="description"]::content',
                'linkedin': 'a[href*="linkedin.com"]'
            }
        }

SELECTORS = load_selectors()

# -- FETCHING --
def fetch_page(url, use_js=False, wait_selector=None, timeout=10):
    """Fetch page via Selenium (JS) or Requests (static)."""
    if use_js:
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        driver = webdriver.Chrome(options=opts)
        try:
            driver.get(url)
            # Wait for page to load
            time.sleep(3)
            if wait_selector:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            html = driver.page_source
        finally:
            driver.quit()
        return BeautifulSoup(html, "html.parser")
    
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

# -- HELPER: Extract name robustly --
def extract_name_from_title(doc, url):
    raw = (doc.title.string or "").strip()
    parts = re.split(r"[|\-:@–•]", raw)
    parts = [p.strip() for p in parts if p.strip()]
    host = urlparse(url).hostname or ""
    domain = host.replace("www.", "").split(".")[0].lower()
    # match parts containing all words in domain
    for p in parts:
        words = p.lower().split()
        if all(word in domain for word in words):
            return p
    # fallback: choose longest non-junk
    junk = {"home", "welcome", "dashboard", "page"}
    candidates = [p for p in parts if p.lower() not in junk]
    if candidates:
        return max(candidates, key=len)
    return parts[0] if parts else ''

# -- LINKEDIN SCRAPING --
def scrape_linkedin_info(linkedin_url):
    """
    Visit LinkedIn company page to extract:
    - Company size
    - Specialties (services offered)
    - Industry
    - Founded date
    """
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=opts)
    data = {}
    try:
        print(f"Accessing LinkedIn URL: {linkedin_url}")
        driver.get(linkedin_url)
        
        # Wait for page to load
        time.sleep(5)
        
        # Try different selectors for LinkedIn company info
        # LinkedIn often uses different structures
        try:
            # Wait for any content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )
            
            # Try to find About section or company details
            about_selectors = [
                "section[data-section='about']",
                ".company-about-us",
                "[data-test-id='about-us']",
                ".org-about-us-organization-description",
                ".break-words"
            ]
            
            for selector in about_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found elements with selector: {selector}")
                        break
                except:
                    continue
            
            # Try to extract company info using various methods
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Look for company size patterns
            size_patterns = [
                r'([\d,]+[-–][\d,]+|\d[\d,]*\+?)\s*employees?',
                r'Company size[:\s]*([\d,]+[-–][\d,]+|\d[\d,]*\+?)',
                r'([\d,]+[-–][\d,]+|\d[\d,]*\+?)\s*people?',
                r'(\d+,\d+|\d+\+?)\s*employees?',
                r'employees?[:\s]*([\d,]+[-–][\d,]+|\d[\d,]*\+?)',
            ]
            
            for pattern in size_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    company_size = match.group(1).strip()
                    # Clean up the extracted size
                    company_size = re.sub(r'[^\d,\-–+]', '', company_size)
                    data['companySize'] = company_size
                    print(f"Found company size: {company_size}")
                    break
            
            # Look for industry (fixed to handle HTML entities and better content extraction)
            industry_patterns = [
                r'Industry\s*</dt>\s*<dd[^>]*>\s*([^<]+?)\s*</dd>',
                r'Industry\s*</dt>\s*<dd[^>]*>\s*([A-Za-z\s&]+?)\s*(?:<|$)',
                r'<dt[^>]*>Industry</dt>\s*<dd[^>]*>\s*([^<]+?)\s*</dd>',
                r'Industry\s*\n\s*([A-Za-z\s&]+?)\s*\n',
                r'Industry[:\s]*\n\s*([A-Za-z\s&]+?)(?:\s*\n|$)',
                r'"industry"[:\s]*"([^"]+)"',
                r'Industry[^>]*>\s*([A-Za-z\s&]+?)\s*<',
                r'Industry\s*([A-Za-z\s&]+?)\s*(?:Company size|Headquarters|Founded|$)',
            ]
            
            for i, pattern in enumerate(industry_patterns):
                match = re.search(pattern, page_source, re.IGNORECASE | re.DOTALL)
                if match:
                    industry = match.group(1).strip()
                    # Clean up HTML entities and extra whitespace
                    industry = re.sub(r'&[^;]*;', '', industry)  # Remove HTML entities
                    industry = re.sub(r'\s+', ' ', industry)  # Normalize whitespace
                    industry = industry.strip()
                    
                    # Validate the industry text - should be reasonable length and contain letters
                    if (industry and 
                        len(industry) > 2 and 
                        len(industry) < 100 and 
                        re.search(r'[A-Za-z]', industry) and
                        not re.search(r'[<>"\']', industry)):  # No HTML remnants
                        data['industry'] = industry
                        print(f"Found industry with pattern {i}: {industry}")
                        break
                    else:
                        print(f"Pattern {i} matched but invalid: '{industry}'")
            
            # If no industry found with patterns, try alternative approach
            if 'industry' not in data:
                # Look for the word "Industry" and extract the next meaningful text
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Try to find dt/dd structure
                for dt in soup.find_all('dt'):
                    if dt.get_text().strip().lower() == 'industry':
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            industry_text = dd.get_text().strip()
                            if industry_text and len(industry_text) > 2:
                                data['industry'] = industry_text
                                print(f"Found industry via BeautifulSoup: {industry_text}")
                                break
            
            
            # Look for founded date
            founded_patterns = [
                r'Founded[:\s]*(\d{4})',
                r'<dt[^>]*>Founded</dt>\s*<dd[^>]*>([^<]+)',
            ]
            
            for pattern in founded_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    data['foundedDate'] = match.group(1).strip()
                    break
                    
        except Exception as e:
            print(f"Error extracting LinkedIn data: {e}")
            data['linkedinError'] = str(e)
            
    except Exception as e:
        print(f"Error accessing LinkedIn: {e}")
        data['linkedinError'] = str(e)
    finally:
        driver.quit()
    
    return data

# -- ORCHESTRATION --
def scrape_company(url):
    print(f"Scraping company: {url}")
    
    try:
        doc = fetch_page(url, use_js=True)
        out = {'url': url}
        
        # homepage selectors
        host = urlparse(url).hostname or ''
        host_key = host.replace('www.', '')
        print(f"HOST KEY: {host_key}")
        
        cfg = SELECTORS.get(host_key) or SELECTORS['default']
        print(f"Using config: {cfg}")
        
        container_sel = cfg.get('container', 'body')
        el = (doc.select(container_sel) or [doc])[0]

        # name via selectors or title
        name = extract_name_from_title(doc, url)
        out['name'] = name
        print(f"Extracted name: {name}")
        
        # overview - FIX: Handle the selector parsing correctly
        overview = ''
        if cfg.get('overview'):
            selector_config = cfg['overview']
            print(f"Overview selector config: {selector_config}")
            
            # Parse selector::attribute format
            if '::' in selector_config:
                selector, attribute = selector_config.split('::', 1)
            else:
                selector = selector_config
                attribute = 'text'
            
            print(f"Using selector: {selector}, attribute: {attribute}")
            
            # Find element
            element = el.select_one(selector)
            if element:
                if attribute == 'content':
                    overview = element.get('content', '')
                elif attribute == 'text':
                    overview = element.get_text().strip()
                else:
                    overview = element.get(attribute)
                    if overview is None:
                        overview = ''
                if overview:
                    print(f"Found overview: {overview}")
                else:
                    print(f"No overview found using attribute '{attribute}' on selector: {selector}")
            else:
                print(f"No element found with selector: {selector}")
                
                # Fallback: try common meta description selectors
                fallback_selectors = [
                    'meta[name="description"]',
                    'meta[property="og:description"]',
                    'meta[name="twitter:description"]',
                    '.company-description',
                    '.about-us',
                    '.overview'
                ]
                
                for fallback in fallback_selectors:
                    elem = doc.select_one(fallback)
                    if elem:
                        if fallback.startswith('meta'):
                            overview = elem.get('content', '')
                        else:
                            overview = elem.get_text().strip()
                        if overview:
                            print(f"Found overview with fallback selector {fallback}: {overview[:100]}...")
                            break
        
        out['overview'] = overview
        
        # linkedin URL
        linkedin_url = None
        if cfg.get('linkedin'):
            a = el.select_one(cfg['linkedin'])
            if a:
                linkedin_url = a.get('href')
                # Make sure it's a full URL
                if linkedin_url:
                    linkedin_url = str(linkedin_url)
                    if not linkedin_url.startswith('http'):
                        linkedin_url = urljoin(url, linkedin_url)
            else:
                # Fallback: look for any LinkedIn link
                linkedin_links = el.select('a[href*="linkedin.com"]')
                if linkedin_links:
                    linkedin_url = linkedin_links[0].get('href')
                    if linkedin_url:
                        linkedin_url = str(linkedin_url)
                        if not linkedin_url.startswith('http'):
                            linkedin_url = urljoin(url, linkedin_url)
        
        out['linkedin'] = linkedin_url
        print(f"Found LinkedIn URL: {linkedin_url}")
        
        # LinkedIn enrichment
        if linkedin_url:
            try:
                print("Attempting to scrape LinkedIn info...")
                li_info = scrape_linkedin_info(linkedin_url)
                out.update(li_info)
                print(f"LinkedIn info extracted: {li_info}")
            except Exception as e:
                print(f"LinkedIn scraping error: {e}")
                out['linkedinError'] = str(e)
        
        return out
        
    except Exception as e:
        print(f"Error scraping company: {e}")
        return {'url': url, 'error': str(e)}

# -- MAIN --
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python scraper.py <URL>')
        sys.exit(1)
    
    result = scrape_company(sys.argv[1])
    print(json.dumps(result, indent=2))