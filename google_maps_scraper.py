import os
import csv
import time
import random
import re
import urllib.parse
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

# ============== CONFIGURATION ==============
# Full list of European cities and categories
EUROPE_CITIES = {
    "Germany": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt"],
    "France": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
    "United Kingdom": ["London", "Birmingham", "Manchester", "Leeds", "Glasgow"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"],
    "Belgium": ["Brussels", "Antwerp", "Ghent", "Charleroi", "Liège"],
    "Luxembourg": ["Luxembourg City", "Esch-sur-Alzette", "Differdange"],
    "Switzerland": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne"],
    "Austria": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck"],
    "Italy": ["Rome", "Milan", "Naples", "Turin", "Palermo"],
    "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza"],
    "Portugal": ["Lisbon", "Porto", "Amadora", "Braga", "Coimbra"],
    "Greece": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa"],
    "Malta": ["Valletta", "Birkirkara", "Mosta", "Qormi"],
    "Cyprus": ["Nicosia", "Limassol", "Larnaca", "Paphos"],
    "Sweden": ["Stockholm", "Gothenburg", "Malmö", "Uppsala", "Västerås"],
    "Norway": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen"],
    "Denmark": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg"],
    "Finland": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu"],
    "Ireland": ["Dublin", "Cork", "Limerick", "Galway", "Waterford"],
    "Poland": ["Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan"],
    "Czech Republic": ["Prague", "Brno", "Ostrava", "Plzen", "Liberec"],
    "Slovakia": ["Bratislava", "Košice", "Prešov", "Žilina", "Nitra"],
    "Hungary": ["Budapest", "Debrecen", "Szeged", "Miskolc", "Pécs"],
    "Romania": ["Bucharest", "Cluj-Napoca", "Timișoara", "Iași", "Constanța"],
    "Bulgaria": ["Sofia", "Plovdiv", "Varna", "Burgas", "Ruse"],
    "Ukraine": ["Kyiv", "Kharkiv", "Odesa", "Dnipro", "Lviv"],
    "Croatia": ["Zagreb", "Split", "Rijeka", "Osijek", "Zadar"],
    "Serbia": ["Belgrade", "Novi Sad", "Niš", "Kragujevac", "Subotica"],
    "Albania": ["Tirana", "Durrës", "Vlorë", "Shkodër", "Elbasan"],
    "Kosovo": ["Pristina", "Prizren", "Ferizaj", "Gjilan", "Peja"],
}

# Mapping for language detection
CITY_TO_COUNTRY = {}
for country, cities in EUROPE_CITIES.items():
    for city in cities:
        CITY_TO_COUNTRY[city] = country

COUNTRY_LANGUAGE = {
    "Germany": "de", "Austria": "de", "Switzerland": "de",
    "France": "fr", "Belgium": "fr", "Luxembourg": "fr",
    "Italy": "it", "Malta": "it", "Spain": "es", "Portugal": "pt",
    "Netherlands": "nl", "Poland": "pl", "United Kingdom": "en", "Ireland": "en",
    "Albania": "sq", "Kosovo": "sq", "Croatia": "hr", "Serbia": "sr",
    "Romania": "ro", "Bulgaria": "bg", "Greece": "el", "Cyprus": "el",
    "Sweden": "sv", "Norway": "no", "Denmark": "da", "Finland": "fi",
}

CATEGORIES = [
    "dentist", "restaurant", "plumber", "lawyer", "accountant", "real estate agent",
    "gym", "salon", "barber", "car repair", "photographer"
]

HIGH_VALUE_CATEGORIES = {
    "dentist": 15, "lawyer": 15, "clinic": 15, "accountant": 12, "real estate": 12,
    "car repair": 10, "restaurant": 10, "gym": 10, "salon": 8, "plumber": 8
}

LANGUAGE_TEMPLATES = {
    "en": {
        "greeting": "Hi 👋",
        "saw_business": "I came across *{name}* on Google — {rating}⭐ looks great!",
        "question_website": "Question: Do you have a website where customers can find you online?",
        "no_website_problem": "Most businesses without a website lose customers to competitors who have one.",
        "help_offer": "I help local businesses get professional websites that bring more customers.",
        "cta": "Would you be open to a quick 5-min chat?"
    },
    "de": {
        "greeting": "Hallo 👋",
        "saw_business": "Ich habe *{name}* auf Google gesehen — {rating}⭐ sieht toll aus!",
        "question_website": "Frage: Haben Sie eine Website, auf der Kunden Sie online finden können?",
        "no_website_problem": "Die meisten Unternehmen ohne Website verlieren Kunden an Konkurrenten.",
        "help_offer": "Ich helfe lokalen Unternehmen, professionelle Websites zu erstellen, die mehr Kunden bringen.",
        "cta": "Hätten Sie Zeit für ein kurzes 5-Minuten-Gespräch?"
    },
    "fr": {
        "greeting": "Bonjour 👋",
        "saw_business": "J'ai vu *{name}* sur Google — {rating}⭐ c'est super!",
        "question_website": "Question: Avez-vous un site web où les clients peuvent vous trouver?",
        "no_website_problem": "La plupart des entreprises sans site web perdent des clients au profit de concurrents.",
        "help_offer": "J'aide les entreprises locales à créer des sites web professionnels qui attirent plus de clients.",
        "cta": "Seriez-vous disponible pour une discussion de 5 minutes?"
    },
    "sq": {
        "greeting": "Përshëndetje 👋",
        "saw_business": "Pashë *{name}* në Google — {rating}⭐ super!",
        "question_website": "Pyetje: A keni uebsajt ku klientët mund t'ju gjejnë online?",
        "no_website_problem": "Shumica e bizneseve pa uebsajt humbin klientë te konkurrentët.",
        "help_offer": "Unë ndihmoj bizneset lokale të kenë uebsajte profesionale që sjellin më shumë klientë.",
        "cta": "A keni 5 minuta për një bisedë të shkurtër?"
    },
    # Add other languages as needed...
}

OUTPUT_FILE = "leads_google_maps.csv"
MAX_RESULTS_PER_QUERY = 15
HEADLESS = True

# ============== SMART LOGIC ==============
def get_language_for_city(city):
    country = CITY_TO_COUNTRY.get(city, "")
    return COUNTRY_LANGUAGE.get(country, "en")

def clean_phone(phone):
    if not phone: return ""
    return phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

def is_mobile_phone(phone, city):
    """Detect if phone is a mobile number based on country rules"""
    phone_clean = clean_phone(phone)
    country = CITY_TO_COUNTRY.get(city, "")
    
    # German Mobile: starts with +4915, +4916, +4917
    if country == "Germany":
        if phone_clean.startswith("+4915") or phone_clean.startswith("+4916") or phone_clean.startswith("+4917"):
            return True
        # Sometimes formatted as 0176...
        if phone_clean.startswith("015") or phone_clean.startswith("016") or phone_clean.startswith("017"):
            return True

    # French Mobile: starts with +336, +337
    elif country == "France":
        if phone_clean.startswith("+336") or phone_clean.startswith("+337"):
            return True
        if (phone_clean.startswith("06") or phone_clean.startswith("07")) and len(phone_clean) == 10:
            return True

    # UK Mobile: starts with +447
    elif country == "United Kingdom":
        if phone_clean.startswith("+447"):
            return True
        if phone_clean.startswith("07") and len(phone_clean) == 11:
            return True

    # Kosovo Mobile: +383 4x, 04x
    elif country == "Kosovo":
        if phone_clean.startswith("+3834") or phone_clean.startswith("+3834"):
            return True
        if phone_clean.startswith("04") and len(phone_clean) >= 9:
            return True

    # Albania Mobile: +355 6x, 06x
    elif country == "Albania":
        if phone_clean.startswith("+3556"):
            return True
        if phone_clean.startswith("06") and len(phone_clean) == 10:
            return True
            
    # Generic rule: If it has a mobile-like structure (for testing)
    if phone_clean.startswith("+"):
         # Assume numbers starting with + might be valid if length is reasonable
         if 10 <= len(phone_clean) <= 14:
             return True

    return False

def generate_whatsapp_link(phone, message):
    if not phone: return ""
    phone_clean = clean_phone(phone)
    
    # Basic cleanup for wa.me
    if phone_clean.startswith("+"):
        phone_clean = phone_clean[1:]
    elif phone_clean.startswith("00"):
        phone_clean = phone_clean[2:]
        
    return f"https://wa.me/{phone_clean}?text={urllib.parse.quote(message)}"

def score_lead(lead):
    score = 0
    if not lead.get("website"): score += 30
    if lead.get("phone"): score += 20
    
    try:
        rating = float(lead.get("rating", 0))
        if rating >= 4.5: score += 25
        elif rating >= 4.0: score += 15
        elif rating >= 3.5: score += 5
    except: pass
    
    category = lead.get("category", "").lower()
    for key, value in HIGH_VALUE_CATEGORIES.items():
        if key in category:
            score += value
            
    return min(score, 100)

def lead_temperature(score):
    if score >= 80: return "HOT"
    elif score >= 60: return "WARM"
    return "COLD"

def suggest_price(lead):
    base = 200
    if lead.get("lead_score", 0) >= 80: base += 200
    if "dentist" in lead.get("category", "") or "lawyer" in lead.get("category", ""): base += 200
    return f"{base} - {base + 200}"

def generate_first_message(lead, city):
    lang = get_language_for_city(city)
    tmpl = LANGUAGE_TEMPLATES.get(lang, LANGUAGE_TEMPLATES["en"])
    
    return (
        f"{tmpl['greeting']}\n\n"
        f"{tmpl['saw_business'].format(name=lead['name'], rating=lead['rating'])}\n\n"
        f"{tmpl['question_website']}\n\n"
        f"{tmpl['no_website_problem']}\n\n"
        f"{tmpl['help_offer']}\n\n"
        f"{tmpl['cta']}"
    )

def extract_rating(text):
    if not text: return ""
    match = re.search(r"(\d+(\.\d+)?)", text)
    return match.group(1) if match else ""

def save_to_csv(leads):
    file_exists = os.path.exists(OUTPUT_FILE)
    fieldnames = [
        "name", "phone", "city", "category", "lead_score", "temperature",
        "suggested_price", "website", "rating", "address", "whatsapp_link",
        "first_message", "maps_url", "scraped_at"
    ]
    
    try:
        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(leads)
        print(f"Saved {len(leads)} leads to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

# ============== SCRAPER ==============
def scrape_google_maps():
    # Build search queries
    # For testing, pick 3 random city/category pairs
    queries = []
    
    # Example: Search for Dentists in Berlin, Plumbers in Paris
    test_locations = [("Berlin", "Germany"), ("Paris", "France"), ("London", "United Kingdom")]
    for city, country in test_locations:
        cat = random.choice(CATEGORIES)
        queries.append({"query": f"{cat} in {city}", "city": city, "category": cat})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        print("Opening Google Maps...")
        page.goto("https://www.google.com/maps?hl=en", timeout=60000)

        # Consent Cookie Handling
        try:
            time.sleep(2)
            accept_pattern = re.compile(r"(Accept|Agree|Consent|Alle\s+akzeptieren|Tout\s+accepter|Prano|Aceptar|Accetta|Zgadzam)", re.IGNORECASE)
            consent_button = page.locator("button").filter(has_text=accept_pattern).first
            if consent_button.is_visible():
                consent_button.click(timeout=5000)
                print("Cookies accepted.")
                time.sleep(2)
        except Exception:
            print("Cookie handling skipped.")

        for q_obj in queries:
            query_text = q_obj["query"]
            city = q_obj["city"]
            category = q_obj["category"]
            
            print(f"Searching for: {query_text}")
            
            try:
                # Search Box Interaction - Robust Multi-Selector
                search_box = None
                potential_selectors = [
                    "input#searchboxinput", 
                    "input[name='q']", 
                    "input[aria-label='Search Google Maps']",
                    "input[class*='searchbox']"
                ]
                
                for selector in potential_selectors:
                    try:
                        if page.locator(selector).first.is_visible(timeout=2000):
                            search_box = page.locator(selector).first
                            break
                    except: pass
                
                if not search_box:
                    # Last resort: try to click the search icon then find input
                    try:
                        page.locator("button#searchbox-searchbutton").click(timeout=1000)
                        search_box = page.locator("input#searchboxinput").first
                    except: pass

                if search_box:
                    search_box.fill(query_text)
                    page.keyboard.press("Enter")
                else:
                    raise Exception("Could not find search box with any selector")
                
                # Wait for results
                page.wait_for_selector('div[role="feed"]', timeout=15000)
                
                # Scroll loop
                feed = page.locator('div[role="feed"]')
                leads_found = 0
                for _ in range(3): # Scroll a few times
                    feed.evaluate("node => node.scrollTo(0, node.scrollHeight)")
                    time.sleep(2)
                    leads_found = page.locator('a[href^="https://www.google.com/maps/place"]').count()
                    if leads_found >= MAX_RESULTS_PER_QUERY: break
                
                # Process Results
                results = page.locator('a[href^="https://www.google.com/maps/place"]').all()
                print(f"Processing {len(results)} results for {city}...")
                
                batch_leads = []
                for result in results[:MAX_RESULTS_PER_QUERY]:
                    try:
                        result.click(force=True)
                        time.sleep(1.5)
                        
                        # Extract Name (Robust)
                        name_locator = page.locator('h1.DUwDvf').first 
                        if not name_locator.is_visible():
                             name_locator = page.locator('h1').first
                        name = name_locator.inner_text() if name_locator.is_visible() else "Unknown"

                        # Extract Phone
                        phone = ""
                        try:
                            phone_btn = page.locator('button[data-item-id^="phone:"]')
                            if phone_btn.count() > 0:
                                aria = phone_btn.first.get_attribute("aria-label") or ""
                                phone = aria.replace("Phone:", "").strip()
                        except: pass
                        
                        # Extract Website
                        website = ""
                        try:
                            web_btn = page.locator('a[data-item-id="authority"]')
                            if web_btn.count() > 0:
                                website = web_btn.first.get_attribute("href")
                        except: pass
                        
                        # Extract Rating
                        rating = ""
                        try:
                             rating_el = page.locator('div.F7nice').first
                             if rating_el.count() > 0:
                                 rating = rating_el.inner_text().split("\n")[0]
                        except: pass

                        # Address
                        address = ""
                        try:
                             addr_btn = page.locator('button[data-item-id="address"]')
                             if addr_btn.count() > 0:
                                 addr = addr_btn.first.get_attribute("aria-label") or ""
                                 address = addr.replace("Address:", "").strip()
                        except: pass
                        
                        # Only keep if valid name
                        if not name or name == "Unknown": continue

                        # === SMART FILTERING ===
                        if not is_mobile_phone(phone, city):
                            # print(f"Skipping landline: {phone}")
                            continue
                            
                        lead = {
                            "name": name,
                            "phone": phone,
                            "city": city,
                            "category": category,
                            "website": website,
                            "rating": rating,
                            "address": address,
                            "maps_url": page.url,
                            "scraped_at": datetime.now().isoformat()
                        }
                        
                        # Enrich
                        lead["lead_score"] = score_lead(lead)
                        lead["temperature"] = lead_temperature(lead["lead_score"])
                        lead["suggested_price"] = suggest_price(lead)
                        lead["first_message"] = generate_first_message(lead, city)
                        lead["whatsapp_link"] = generate_whatsapp_link(phone, lead["first_message"])
                        
                        print(f"Found MOBILE lead: {name} ({lead['temperature']})")
                        batch_leads.append(lead)

                    except Exception as e:
                        # print(f"Error scraping lead: {e}")
                        continue
                
                if batch_leads:
                    save_to_csv(batch_leads)
                else:
                    print("No mobile leads found in this batch.")

                # Clear search
                try:
                    page.locator("button#searchbox-searchbutton").click()
                    page.locator("input#searchboxinput").fill("")
                except: pass

            except Exception as e:
                print(f"Query failed: {e}")
                continue

        browser.close()

if __name__ == "__main__":
    scrape_google_maps()

