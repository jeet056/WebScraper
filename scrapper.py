#!/usr/bin/env python3
import sys, json, re, os, yaml
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup, Tag
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

# -- HELPER FUNCTIONS --
def find_linkedin_in_subpages(base_url, company_name):
    """Search for LinkedIn links in common subpages"""
    common_pages = [
        '/about',
        '/about-us',
        '/contact',
        '/contact-us',
        '/company',
        '/team',
        '/careers',
        '/press',
        '/media',
        '/investors',
        '/footer'  # Sometimes links are in footer
    ]
    
    for page_path in common_pages:
        try:
            page_url = urljoin(base_url, page_path)
            print(f"Checking {page_url} for LinkedIn links...")
            
            # Use requests for faster checking
            resp = requests.get(page_url, 
                              headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                              timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                linkedin_links = soup.select('a[href*="linkedin.com"]')
                
                for link in linkedin_links:
                    href = link.get('href')
                    if href:
                        href = str(href)
                        if '/company/' in href:
                            linkedin_url = href if href.startswith('http') else urljoin(base_url, href)
                            print(f"Found LinkedIn URL in {page_path}: {linkedin_url}")
                            return linkedin_url
                        
        except Exception as e:
            print(f"Error checking {page_path}: {e}")
            continue
    
    return None

def generate_linkedin_url(company_name):
    """Generate potential LinkedIn URL from company name"""
    if not company_name:
        return None
    
    # Clean company name for URL
    clean_name = company_name.lower()
    
    # Remove common company suffixes
    suffixes = ['inc', 'corp', 'corporation', 'company', 'co', 'ltd', 'limited', 
                'llc', 'group', 'holdings', 'the', 'and', '&']
    
    for suffix in suffixes:
        clean_name = re.sub(rf'\b{suffix}\b', '', clean_name)
    
    # Clean up special characters and spaces
    clean_name = re.sub(r'[^\w\s-]', '', clean_name)
    clean_name = re.sub(r'\s+', '-', clean_name.strip())
    clean_name = re.sub(r'-+', '-', clean_name)
    clean_name = clean_name.strip('-')
    
    if clean_name:
        potential_urls = [
            f"https://www.linkedin.com/company/{clean_name}",
            f"https://www.linkedin.com/company/{clean_name}-inc",
            f"https://www.linkedin.com/company/{clean_name}-corp",
            f"https://www.linkedin.com/company/{clean_name}-company",
        ]
        
        # For well-known companies, try common variations
        if any(x in company_name.lower() for x in ['google', 'alphabet']):
            potential_urls.append("https://www.linkedin.com/company/google")
        elif 'apple' in company_name.lower():
            potential_urls.append("https://www.linkedin.com/company/apple")
        elif 'microsoft' in company_name.lower():
            potential_urls.append("https://www.linkedin.com/company/microsoft")
        elif 'amazon' in company_name.lower():
            potential_urls.append("https://www.linkedin.com/company/amazon")
        elif 'meta' in company_name.lower() or 'facebook' in company_name.lower():
            potential_urls.append("https://www.linkedin.com/company/meta")
        elif 'netflix' in company_name.lower():
            potential_urls.append("https://www.linkedin.com/company/netflix")
        
        return potential_urls
    
    return None

def search_google_for_linkedin(company_name):
    """Search Google for company LinkedIn page"""
    if not company_name:
        return None
    
    # Construct Google search query
    search_query = f"{company_name} linkedin"
    google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    
    try:
        print(f"Searching Google for: {search_query}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        resp = requests.get(google_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find search result links
            search_results = soup.find_all('a', href=True)
            
            for link in search_results:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href:
                        href = str(href)
                        if 'linkedin.com/company/' in href:
                            # Extract the actual LinkedIn URL from Google's redirect
                            if href.startswith('/url?q='):
                                # Google wraps URLs like: /url?q=https://linkedin.com/company/...&sa=...
                                import urllib.parse
                                parsed = urllib.parse.urlparse(href)
                                actual_url = urllib.parse.parse_qs(parsed.query).get('q')
                                if actual_url:
                                    linkedin_url = actual_url[0]
                                    # Verify it's a valid LinkedIn company URL
                                    if 'linkedin.com/company/' in linkedin_url:
                                        print(f"Found LinkedIn URL via Google search: {linkedin_url}")
                                        return linkedin_url
                            elif href.startswith('https://linkedin.com/company/') or href.startswith('https://www.linkedin.com/company/'):
                                print(f"Found LinkedIn URL via Google search: {href}")
                                return href
        
        print("No LinkedIn company page found in Google search results")
        return None
        
    except Exception as e:
        print(f"Error searching Google: {e}")
        return None

def search_duckduckgo_for_linkedin(company_name):
    """Search DuckDuckGo for company LinkedIn page (alternative to Google)"""
    if not company_name:
        return None
    
    # Construct DuckDuckGo search query
    search_query = f"{company_name} site:linkedin.com/company"
    ddg_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
    
    try:
        print(f"Searching DuckDuckGo for: {search_query}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        resp = requests.get(ddg_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find search result links in DuckDuckGo
            search_results = soup.find_all('a', {'class': 'result__a'})
            
            for link in search_results:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href:
                        href = str(href)
                        if 'linkedin.com/company/' in href:
                            print(f"Found LinkedIn URL via DuckDuckGo search: {href}")
                            return href
        
        print("No LinkedIn company page found in DuckDuckGo search results")
        return None
        
    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
        return None

def search_engines_for_linkedin(company_name):
    """Try multiple search engines to find LinkedIn company page"""
    if not company_name:
        return None
    
    # Try Google first
    linkedin_url = search_google_for_linkedin(company_name)
    if linkedin_url:
        return linkedin_url
    
    # If Google fails, try DuckDuckGo
    print("Google search failed, trying DuckDuckGo...")
    time.sleep(2)  # Be polite with requests
    linkedin_url = search_duckduckgo_for_linkedin(company_name)
    if linkedin_url:
        return linkedin_url
    
    return None

def verify_linkedin_url(linkedin_urls):
    """Verify if LinkedIn URL(s) exist and return the valid one"""
    if isinstance(linkedin_urls, str):
        linkedin_urls = [linkedin_urls]
    
    if not linkedin_urls:
        return None
    
    for url in linkedin_urls:
        try:
            print(f"Verifying LinkedIn URL: {url}")
            resp = requests.head(url, 
                               headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                               timeout=10,
                               allow_redirects=True)
            
            if resp.status_code == 200:
                print(f"Verified LinkedIn URL: {url}")
                return url
            else:
                print(f"LinkedIn URL returned {resp.status_code}: {url}")
                
        except Exception as e:
            print(f"Error verifying {url}: {e}")
            continue
    
    return None

# -- HELPER: Extract name robustly --
def extract_name_from_title(doc, url):

    # Strategy 1: Check for common company name meta tags
    company_name_selectors = [
        'meta[property="og:site_name"]',
        'meta[name="application-name"]',
        'meta[name="apple-mobile-web-app-title"]',
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
        '.company-name',
        '.brand-name',
        '.logo-text',
        'h1.company-name',
        '[data-testid="company-name"]'
    ]
    
    for selector in company_name_selectors:
        element = doc.select_one(selector)
        if element:
            if selector.startswith('meta'):
                name = element.get('content', '').strip()
            else:
                name = element.get_text().strip()
            
            if name and len(name) > 1 and len(name) < 100:
                print(f"Found company name via {selector}: {name}")
                return name

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
    junk = {"home", "welcome", "dashboard", "page", "watch", "online", "streaming", "movies", "tv shows"}
    candidates = [p for p in parts if p.lower() not in junk]
    if candidates:
        return max(candidates, key=len)
    return parts[0] if parts else ''

def is_overview_empty_or_insufficient(overview):
    """Check if overview is empty or insufficient (too generic/short)"""
    if not overview:
        return True
    
    # Remove extra whitespace
    overview = overview.strip()
    
    # Check if it's too short (less than 20 characters)
    if len(overview) < 20:
        return True
    
    # Check for generic/insufficient descriptions
    generic_phrases = [
        "welcome to",
        "coming soon",
        "under construction",
        "page not found",
        "home page",
        "official website",
        "main page",
        "default page"
    ]
    
    overview_lower = overview.lower()
    for phrase in generic_phrases:
        if phrase in overview_lower:
            return True
    
    # Check if it's just the company name repeated
    if len(overview.split()) < 5:  # Less than 5 words
        return True
    
    return False

# -- LINKEDIN SCRAPING --
def scrape_linkedin_info(linkedin_url, need_overview=False, extract_name=False):
    """
    Visit LinkedIn company page to extract:
    - Company size
    - Specialties (services offered)
    - Industry
    - Founded date
    - Overview/About section (if needed)
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

            # Extract company name if requested
            if extract_name:
                name_selectors = [
                    'h1[data-test-id="company-name"]',
                    'h1.org-top-card-summary__title',
                    'h1.t-24.t-black.t-normal',
                    '.org-top-card-summary__title',
                    'h1',
                    '.company-name',
                    '[data-test-id="company-name"]'
                ]
                
                for selector in name_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            name = elements[0].text.strip()
                            if name and len(name) > 1 and len(name) < 100:
                                # Validate it's not generic text
                                if not any(generic in name.lower() for generic in ['loading', 'error', 'page']):
                                    print(f"Found LinkedIn company name: {name}")
                                    data['name'] = name
                                    break
                    except Exception as e:
                        print(f"Error with name selector {selector}: {e}")
                        continue
                
                # Fallback: try to extract name from page title
                if 'name' not in data:
                    title = driver.title
                    if title and 'LinkedIn' in title:
                        # LinkedIn titles are often like "Company Name | LinkedIn"
                        parts = title.split('|')
                        if len(parts) > 1:
                            company_name = parts[0].strip()
                            if company_name and len(company_name) > 1:
                                print(f"Found company name from LinkedIn title: {company_name}")
                                data['name'] = company_name
            
            # ENHANCED: Extract overview/about section if needed
            if need_overview:
                print("Extracting overview from LinkedIn...")
                overview_patterns = [
                    r'<p[^>]*class="[^"]*break-words[^"]*"[^>]*>(.*?)</p>',
                    r'<div[^>]*class="[^"]*org-about-us-organization-description[^"]*"[^>]*>(.*?)</div>',
                    r'<section[^>]*data-section="about"[^>]*>.*?<p[^>]*>(.*?)</p>',
                    r'About\s*</h[1-6]>\s*<[^>]*>(.*?)</[^>]*>',
                    r'<div[^>]*class="[^"]*about[^"]*"[^>]*>(.*?)</div>',
                ]
                
                for pattern in overview_patterns:
                    match = re.search(pattern, page_source, re.IGNORECASE | re.DOTALL)
                    if match:
                        overview_text = match.group(1)
                        # Clean HTML tags and normalize whitespace
                        overview_text = re.sub(r'<[^>]+>', '', overview_text)
                        overview_text = re.sub(r'\s+', ' ', overview_text).strip()
                        
                        # Validate the overview text
                        if (overview_text and 
                            len(overview_text) > 30 and 
                            len(overview_text) < 1000 and
                            not is_overview_empty_or_insufficient(overview_text)):
                            data['overview'] = overview_text
                            print(f"Found LinkedIn overview: {overview_text[:100]}...")
                            break
                
                # Alternative approach using BeautifulSoup if patterns fail
                if 'overview' not in data:
                    # Look for common About section containers
                    about_containers = [
                        '.org-about-us-organization-description',
                        '.break-words',
                        '[data-test-id="about-us"]',
                        '.company-about-us'
                    ]
                    
                    for container in about_containers:
                        elements = soup.select(container)
                        for elem in elements:
                            text = elem.get_text().strip()
                            if text and len(text) > 30 and not is_overview_empty_or_insufficient(text):
                                data['overview'] = text
                                print(f"Found LinkedIn overview via BeautifulSoup: {text[:100]}...")
                                break
                        if 'overview' in data:
                            break
            
            # Look for company size patterns (fixed to handle commas and better formatting)
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
            
            # Look for industry (improved patterns for LinkedIn structure)
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
        print(f"Initially extracted name: {name}")
        
        # Step 2: Validate extracted name against URL
        url_expected_name = extract_company_name_from_url(url)
        print(f"URL suggests company name: {url_expected_name}")
        
        name_is_valid = validate_name_against_url(name, url)
        
        final_name = name
        linkedin_url = None
        
        if not name_is_valid and url_expected_name:
            print(f"Name '{name}' doesn't match URL expectation. Trying LinkedIn fallback...")
            
            # Search for LinkedIn page using URL-based name
            linkedin_url = search_engines_for_linkedin(url_expected_name)
            
            if linkedin_url:
                # Verify the LinkedIn URL
                verified_url = verify_linkedin_url([linkedin_url])
                if verified_url:
                    linkedin_url = verified_url
                    print(f"Found LinkedIn URL via search: {linkedin_url}")
                    
                    # Extract name from LinkedIn using merged function
                    linkedin_info = scrape_linkedin_info(linkedin_url, need_overview=False, extract_name=True)
                    if linkedin_info.get('name'):
                        print(f"Using LinkedIn name: {linkedin_info['name']}")
                        final_name = linkedin_info['name']
                    else:
                        print(f"Could not extract name from LinkedIn, using URL-based name: {url_expected_name}")
                        final_name = url_expected_name
                else:
                    print(f"LinkedIn URL verification failed, using URL-based name: {url_expected_name}")
                    final_name = url_expected_name
            else:
                print(f"No LinkedIn URL found via search, using URL-based name: {url_expected_name}")
                final_name = url_expected_name

        out['name'] = final_name
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
                    overview = element.get(attribute, '')
                print(f"Found overview: {overview}")
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
        
        # Check if overview is insufficient
        need_linkedin_overview = is_overview_empty_or_insufficient(overview)
        if need_linkedin_overview:
            print(f"Overview is insufficient, will try to get from LinkedIn")
        
        out['overview'] = overview
        
        # Strategy 2: Search entire page for LinkedIn links
        if not linkedin_url:
            linkedin_links = doc.select('a[href*="linkedin.com"]')
            if linkedin_links:
                for link in linkedin_links:
                    href = link.get('href')
                    if href:
                        href = str(href)
                        if '/company/' in href:
                            linkedin_url = href if href.startswith('http') else urljoin(url, href)
                            break
        
        # Strategy 3: Search Google/DuckDuckGo for LinkedIn company page
        if not linkedin_url and name:
            print(f"Searching search engines for LinkedIn page of: {name}")
            linkedin_url = search_engines_for_linkedin(name)
            # Verify the found URL
            if linkedin_url:
                verified_url = verify_linkedin_url([linkedin_url])
                linkedin_url = verified_url

        # Strategy 4: Check common pages for LinkedIn links
        if not linkedin_url:
            linkedin_url = find_linkedin_in_subpages(url, name)
        
        # Strategy 5: Generate LinkedIn URL from company name
        if not linkedin_url and name:
            potential_urls = generate_linkedin_url(name)
            if potential_urls:
                linkedin_url = verify_linkedin_url(potential_urls)
        
        out['linkedin'] = linkedin_url
        print(f"Final LinkedIn URL: {linkedin_url}")
        
        # LinkedIn enrichment - ENHANCED to handle overview fallback
        if linkedin_url:
            try:
                print("Attempting to scrape LinkedIn info...")
                extract_name = bool(linkedin_url) and not bool(final_name)
                li_info = scrape_linkedin_info(linkedin_url, need_overview=need_linkedin_overview, extract_name=extract_name)
                
                # If we got a better overview from LinkedIn, use it
                if need_linkedin_overview and li_info.get('overview'):
                    print(f"Using LinkedIn overview instead of homepage overview")
                    out['overview'] = li_info['overview']
                    # Remove overview from li_info to avoid duplication
                    li_info.pop('overview', None)
                
                out.update(li_info)
                print(f"LinkedIn info extracted: {li_info}")
            except Exception as e:
                print(f"LinkedIn scraping error: {e}")
                out['linkedinError'] = str(e)
        elif need_linkedin_overview:
            print(f"Warning: No LinkedIn URL found but overview is insufficient")
            out['overviewWarning'] = "Overview is insufficient and no LinkedIn URL found for fallback"
        
        return out
        
    except Exception as e:
        print(f"Error scraping company: {e}")
        return {'url': url, 'error': str(e)}

def extract_company_name_from_url(url):
    """Extract expected company name from URL domain using string manipulation"""
    try:
        host = urlparse(url).hostname or ""
        domain = host.replace("www.", "").split(".")[0]
        
        # Simple string manipulation to make it presentable
        # Handle common patterns like hyphens, underscores, numbers
        clean_domain = domain.lower()
        
        # Remove common prefixes/suffixes that aren't part of company name
        prefixes_to_remove = ['get', 'my', 'the', 'app', 'web', 'site', 'go', 'try']
        suffixes_to_remove = ['app', 'web', 'site', 'io', 'ai', 'tech', 'co', 'inc']
        
        # Remove prefixes
        for prefix in prefixes_to_remove:
            if clean_domain.startswith(prefix) and len(clean_domain) > len(prefix):
                clean_domain = clean_domain[len(prefix):]
                break
        
        # Remove suffixes (but keep them if they're the entire domain)
        for suffix in suffixes_to_remove:
            if clean_domain.endswith(suffix) and len(clean_domain) > len(suffix):
                clean_domain = clean_domain[:-len(suffix)]
                break
        
        # Handle special characters
        if '-' in clean_domain:
            # For hyphenated domains, capitalize each part
            parts = clean_domain.split('-')
            return ' '.join(word.capitalize() for word in parts if word)
        elif '_' in clean_domain:
            # For underscore domains, capitalize each part
            parts = clean_domain.split('_')
            return ' '.join(word.capitalize() for word in parts if word)
        else:
            # For single words, just capitalize
            return clean_domain.capitalize()
        
    except Exception as e:
        print(f"Error extracting name from URL: {e}")
        return None

def validate_name_against_url(extracted_name, url):
    """Check if extracted name reasonably matches the URL domain"""
    if not extracted_name or not url:
        return False
    
    try:
        host = urlparse(url).hostname or ""
        domain = host.replace("www.", "").split(".")[0].lower()
        extracted_lower = extracted_name.lower()
        
        # Remove common punctuation for comparison
        clean_extracted = re.sub(r'[^\w\s]', '', extracted_lower)
        clean_extracted = re.sub(r'\s+', '', clean_extracted)
        
        # Direct match
        if domain in clean_extracted or clean_extracted in domain:
            return True
        
        # Check if domain parts match extracted name parts
        if '-' in domain:
            domain_parts = domain.split('-')
            extracted_parts = extracted_name.lower().split()
            
            # Check if any domain part matches any extracted part
            for domain_part in domain_parts:
                for extracted_part in extracted_parts:
                    if domain_part in extracted_part or extracted_part in domain_part:
                        return True
        
        # Check reverse - if extracted name has multiple words, see if domain contains any
        extracted_words = extracted_name.lower().split()
        if len(extracted_words) > 1:
            for word in extracted_words:
                if len(word) > 2 and word in domain:  # Avoid matching short words like "a", "the"
                    return True
        
        # Fuzzy matching for slight variations
        similarity_threshold = 0.6
        if len(clean_extracted) > 3 and len(domain) > 3:
            # Simple similarity check
            common_chars = sum(1 for c in clean_extracted if c in domain)
            similarity = common_chars / max(len(clean_extracted), len(domain))
            if similarity >= similarity_threshold:
                return True
        
        return False
        
    except Exception as e:
        print(f"Error validating name against URL: {e}")
        return False

# -- MAIN --
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python scraper.py <URL>')
        sys.exit(1)
    
    result = scrape_company(sys.argv[1])
    print(json.dumps(result, indent=2))