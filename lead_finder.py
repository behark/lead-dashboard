import requests
import csv
import time
import os
import urllib.parse
import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lead_finder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed. Install it with: pip install python-dotenv")

# ============== CONFIGURATION ==============
# Load API keys from environment variables
YELP_API_KEY = os.getenv("YELP_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validate required environment variables
if not YELP_API_KEY:
    raise ValueError("YELP_API_KEY environment variable is required. Please set it in .env file")
if not TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram notifications will be disabled.")
if not TELEGRAM_CHAT_ID:
    logger.warning("TELEGRAM_CHAT_ID not set. Telegram notifications will be disabled.")

# Yelp Fusion API endpoints
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
YELP_BUSINESS_URL = "https://api.yelp.com/v3/businesses/{business_id}"

# European countries with top 5 cities each
EUROPE_CITIES = {
    # Western Europe
    "Germany": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt"],
    "France": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
    "United Kingdom": ["London", "Birmingham", "Manchester", "Leeds", "Glasgow"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"],
    "Belgium": ["Brussels", "Antwerp", "Ghent", "Charleroi", "Liège"],
    "Luxembourg": ["Luxembourg City", "Esch-sur-Alzette", "Differdange"],
    "Switzerland": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne"],
    "Austria": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck"],
    
    # Southern Europe
    "Italy": ["Rome", "Milan", "Naples", "Turin", "Palermo"],
    "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza"],
    "Portugal": ["Lisbon", "Porto", "Amadora", "Braga", "Coimbra"],
    "Greece": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa"],
    "Malta": ["Valletta", "Birkirkara", "Mosta", "Qormi"],
    "Cyprus": ["Nicosia", "Limassol", "Larnaca", "Paphos"],
    
    # Northern Europe
    "Sweden": ["Stockholm", "Gothenburg", "Malmö", "Uppsala", "Västerås"],
    "Norway": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen"],
    "Denmark": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg"],
    "Finland": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu"],
    "Iceland": ["Reykjavik", "Kópavogur", "Hafnarfjörður"],
    "Ireland": ["Dublin", "Cork", "Limerick", "Galway", "Waterford"],
    
    # Eastern Europe
    "Poland": ["Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan"],
    "Czech Republic": ["Prague", "Brno", "Ostrava", "Plzen", "Liberec"],
    "Slovakia": ["Bratislava", "Košice", "Prešov", "Žilina", "Nitra"],
    "Hungary": ["Budapest", "Debrecen", "Szeged", "Miskolc", "Pécs"],
    "Romania": ["Bucharest", "Cluj-Napoca", "Timișoara", "Iași", "Constanța"],
    "Bulgaria": ["Sofia", "Plovdiv", "Varna", "Burgas", "Ruse"],
    "Ukraine": ["Kyiv", "Kharkiv", "Odesa", "Dnipro", "Lviv"],
    "Moldova": ["Chișinău", "Tiraspol", "Bălți", "Bender"],
    
    # Baltic States
    "Estonia": ["Tallinn", "Tartu", "Narva", "Pärnu"],
    "Latvia": ["Riga", "Daugavpils", "Liepāja", "Jelgava"],
    "Lithuania": ["Vilnius", "Kaunas", "Klaipėda", "Šiauliai", "Panevėžys"],
    
    # Balkans
    "Slovenia": ["Ljubljana", "Maribor", "Celje", "Kranj", "Koper"],
    "Croatia": ["Zagreb", "Split", "Rijeka", "Osijek", "Zadar"],
    "Bosnia and Herzegovina": ["Sarajevo", "Banja Luka", "Tuzla", "Zenica", "Mostar"],
    "Serbia": ["Belgrade", "Novi Sad", "Niš", "Kragujevac", "Subotica"],
    "Montenegro": ["Podgorica", "Nikšić", "Herceg Novi", "Budva", "Bar"],
    "North Macedonia": ["Skopje", "Bitola", "Kumanovo", "Prilep", "Tetovo"],
    "Albania": ["Tirana", "Durrës", "Vlorë", "Shkodër", "Elbasan"],
    "Kosovo": ["Pristina", "Prizren", "Ferizaj", "Gjilan", "Peja"],
    
    # Other
    "Belarus": ["Minsk", "Gomel", "Mogilev", "Vitebsk", "Grodno"],
}

# Flatten all cities into one list
CITIES = []
for country, cities in EUROPE_CITIES.items():
    CITIES.extend(cities)

# City to Country mapping (for language detection)
CITY_TO_COUNTRY = {}
for country, cities in EUROPE_CITIES.items():
    for city in cities:
        CITY_TO_COUNTRY[city] = country

# Country to Language mapping
COUNTRY_LANGUAGE = {
    "Germany": "de", "Austria": "de", "Switzerland": "de",
    "France": "fr", "Belgium": "fr", "Luxembourg": "fr",
    "Italy": "it", "Malta": "it",
    "Spain": "es",
    "Portugal": "pt",
    "Netherlands": "nl",
    "Poland": "pl",
    "Czech Republic": "cs",
    "Slovakia": "sk",
    "Hungary": "hu",
    "Romania": "ro", "Moldova": "ro",
    "Bulgaria": "bg",
    "Greece": "el", "Cyprus": "el",
    "Sweden": "sv",
    "Norway": "no",
    "Denmark": "da",
    "Finland": "fi",
    "Iceland": "is",
    "Ireland": "en", "United Kingdom": "en",
    "Ukraine": "uk",
    "Estonia": "et",
    "Latvia": "lv",
    "Lithuania": "lt",
    "Slovenia": "sl",
    "Croatia": "hr",
    "Bosnia and Herzegovina": "bs",
    "Serbia": "sr",
    "Montenegro": "sr",
    "North Macedonia": "mk",
    "Albania": "sq", "Kosovo": "sq",
    "Belarus": "be",
}

# Expanded categories
CATEGORIES = [
    # Health & Beauty
    "dentist", "barber", "salon", "spa", "massage", "nail salon", "tattoo",
    # Automotive
    "car repair", "auto mechanic", "car wash", "tire shop", "auto parts",
    # Food & Hospitality
    "restaurant", "cafe", "bakery", "pizzeria", "fast food", "catering",
    # Professional Services
    "lawyer", "accountant", "real estate agent", "insurance agent", "notary",
    # Fitness & Wellness
    "gym", "fitness center", "yoga studio", "personal trainer", "martial arts",
    # Home Services
    "plumber", "electrician", "carpenter", "painter", "cleaning service", "locksmith",
    # Retail & Shopping
    "clothing store", "jewelry store", "furniture store", "flower shop", "pet shop",
    # Education & Training
    "driving school", "language school", "tutoring", "music school",
    # Other Services
    "photographer", "wedding planner", "printing shop", "tailor", "veterinarian"
]

OUTPUT_FILE = "leads_clean.csv"

# Follow-up timing (4-step sequence)
FOLLOW_UP_HOURS = {
    1: 24,   # Day 1: Gentle follow-up
    2: 48,   # Day 2: Problem rephrased
    3: 72,   # Day 3: Portfolio/social proof
    4: 120,  # Day 5: Final message
}

HIGH_VALUE_CATEGORIES = {
    # High value (€500+)
    "dentist": 15, "lawyer": 15, "clinic": 15, "accountant": 12,
    "real estate": 12, "insurance": 10, "notary": 10,
    # Medium-high value (€300-500)
    "car repair": 10, "restaurant": 10, "gym": 10, "auto mechanic": 10,
    "veterinarian": 10, "photographer": 10, "wedding planner": 12,
    # Medium value (€200-400)
    "salon": 8, "spa": 8, "cafe": 8, "bakery": 8, "pizzeria": 8,
    "fitness": 8, "driving school": 8, "language school": 8,
    "plumber": 8, "electrician": 8,
    # Lower value (€150-300)
    "barber": 5, "nail salon": 5, "tattoo": 5, "car wash": 5,
    "tailor": 5, "printing": 5, "flower shop": 5,
}

# Status values: NEW, CONTACTED, REPLIED, CLOSED, LOST


# ============== RATE LIMITING ==============
import threading

class RateLimiter:
    """Simple rate limiter for API calls"""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: List[float] = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded (thread-safe)"""
        wait_time = 0.0
        
        with self.lock:
            now = time.time()
            # Remove old calls
            self.calls = [t for t in self.calls if now - t < self.period]
            
            if len(self.calls) >= self.max_calls:
                oldest = min(self.calls) if self.calls else now
                wait_time = self.period - (now - oldest) + 0.1
                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
            
            self.calls.append(now)
        
        # Sleep outside the lock to avoid blocking other threads unnecessarily
        # This allows other threads to check rate limit while we wait
        if wait_time > 0:
            time.sleep(wait_time)


# Yelp API: 5,000 requests per day (free tier)
# Rate limit: Max 5 requests per second (Yelp's limit)
# We'll use 3 requests per second to stay safe
yelp_limiter = RateLimiter(max_calls=3, period=1.0)  # 3 calls per second = safe limit


# ============== API FUNCTIONS ==============
def search_places(query: str, pagetoken: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for places using Yelp Fusion API
    
    Args:
        query: Search query string (e.g., "dentist in Berlin")
        pagetoken: Optional pagination offset (Yelp uses offset, not token)
    
    Returns:
        API response as dictionary (converted to Google Places format for compatibility)
    """
    yelp_limiter.wait_if_needed()
    
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}"
    }
    
    # Parse query: "category in city" -> term="category", location="city"
    parts = query.lower().split(" in ")
    if len(parts) == 2:
        term = parts[0].strip()
        location = parts[1].strip()
    else:
        # Fallback: use whole query as term, try to extract location
        term = query
        location = None
    
    params = {
        "term": term,
        "limit": 50,  # Yelp max is 50 per request
    }
    
    if location:
        params["location"] = location
    
    # Yelp uses offset for pagination
    if pagetoken:
        try:
            params["offset"] = int(pagetoken)
        except ValueError:
            pass
    
    try:
        response = requests.get(YELP_SEARCH_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Convert Yelp format to Google Places format for compatibility
        places = []
        for business in data.get("businesses", []):
            places.append({
                "place_id": business.get("id", ""),
                "name": business.get("name", ""),
                "formatted_address": ", ".join(business.get("location", {}).get("display_address", [])),
                "rating": business.get("rating"),
                "yelp_data": business  # Store full Yelp data for later use
            })
        
        # Calculate next page offset
        total = data.get("total", 0)
        current_offset = params.get("offset", 0)
        next_offset = current_offset + len(places)
        next_page_token = str(next_offset) if next_offset < total else None
        
        result = {
            "results": places,
            "status": "OK",
            "next_page_token": next_page_token
        }
        return result
    except requests.RequestException as e:
        logger.error(f"Error searching places for '{query}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"Yelp API Error: {error_data}")
            except:
                logger.error(f"HTTP Status: {e.response.status_code}")
        return {"results": [], "status": "ERROR"}


def get_place_details(place_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a place using Yelp Fusion API
    
    Args:
        place_id: Yelp business ID
    
    Returns:
        Place details dictionary (converted to Google Places format for compatibility)
    """
    yelp_limiter.wait_if_needed()
    
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}"
    }
    
    url = YELP_BUSINESS_URL.format(business_id=place_id)
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Convert Yelp format to Google Places format for compatibility
        location = data.get("location", {})
        address_parts = location.get("display_address", [])
        
        result = {
            "name": data.get("name", ""),
            "formatted_address": ", ".join(address_parts) if address_parts else "",
            "formatted_phone_number": data.get("phone", ""),
            "website": "",  # Yelp Fusion API doesn't provide actual business websites (free tier)
            "rating": data.get("rating"),
            "url": data.get("url", ""),  # Yelp business page URL
            "yelp_data": data  # Store full Yelp data
        }
        return result
    except requests.RequestException as e:
        is_expected_error = False
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_code = error_data.get('error', {}).get('code')
                
                # specific handling for BUSINESS_UNAVAILABLE
                if error_code == 'BUSINESS_UNAVAILABLE':
                    logger.warning(f"Skipping business '{place_id}': details unavailable (likely no reviews).")
                    is_expected_error = True
                else:
                    logger.error(f"Yelp API Error: {error_data}")
            except:
                logger.error(f"HTTP Status: {e.response.status_code}")
        
        if not is_expected_error:
            logger.error(f"Error getting place details for '{place_id}': {e}")
            
        return {}


# ============== SCORING FUNCTIONS ==============
def score_lead(lead: Dict[str, Any]) -> int:
    """
    Calculate lead score based on various factors
    
    Args:
        lead: Lead dictionary with business information
    
    Returns:
        Lead score (0-100)
    """
    score = 0

    if not lead.get("website"):
        score += 30

    if lead.get("phone"):
        score += 20

    rating = lead.get("rating")
    if rating:
        if rating >= 4.5:
            score += 25
        elif rating >= 4.0:
            score += 15
        elif rating >= 3.5:
            score += 5

    category = lead.get("category", "").lower()
    for key, value in HIGH_VALUE_CATEGORIES.items():
        if key in category:
            score += value

    if lead.get("city") in ["Pristina", "Tirana"]:
        score += 10

    return min(score, 100)


def lead_temperature(score: int) -> str:
    """
    Determine lead temperature based on score
    
    Args:
        score: Lead score (0-100)
    
    Returns:
        Temperature string: "HOT", "WARM", or "COLD"
    """
    if score >= 80:
        return "HOT"
    elif score >= 60:
        return "WARM"
    else:
        return "COLD"


def suggest_price(lead):
    """Suggest price for a lead based on score and category"""
    base_price = 200

    lead_score = lead.get("lead_score", 0)
    category = lead.get("category", "").lower()

    if lead_score >= 85:
        base_price += 200
    elif lead_score >= 70:
        base_price += 100

    if "dentist" in category:
        base_price += 200
    if "lawyer" in category:
        base_price += 300
    if "gym" in category:
        base_price += 100

    return f"{base_price} - {base_price + 200}"


# ============== MULTI-LANGUAGE MESSAGE TEMPLATES ==============
# Generic templates by language (used for all categories)
LANGUAGE_TEMPLATES = {
    "en": {  # English
        "greeting": "Hi 👋",
        "saw_business": "I came across *{name}* on Google — {rating}⭐ looks great!",
        "question_website": "Question: Do you have a website where customers can find you online?",
        "no_website_problem": "Most businesses without a website lose customers to competitors who have one.",
        "help_offer": "I help local businesses get professional websites that bring more customers.",
        "cta": "Would you be open to a quick 5-min chat?",
        "followup_1": "Hi 👋\n\nJust following up on my message about *{name}*.\n\nNo rush — just wanted to check if you're interested?",
        "followup_2": "Hi,\n\nQuick thought: When someone searches for your services in {city}, can they find you easily?\n\nA website helps you get found 24/7.\n\nChat?",
        "followup_3": "Hi,\n\nWanted to share something.\n\nI helped a similar business in {city} get a professional website.\n\nThey now get 5-10 more inquiries per month.\n\nInterested?",
        "followup_4": "Hi,\n\nLast message from me — if you ever need help with a website, just reach out.\n\nWishing you success! 🙌",
    },
    "de": {  # German
        "greeting": "Hallo 👋",
        "saw_business": "Ich habe *{name}* auf Google gesehen — {rating}⭐ sieht toll aus!",
        "question_website": "Frage: Haben Sie eine Website, auf der Kunden Sie online finden können?",
        "no_website_problem": "Die meisten Unternehmen ohne Website verlieren Kunden an Konkurrenten.",
        "help_offer": "Ich helfe lokalen Unternehmen, professionelle Websites zu erstellen, die mehr Kunden bringen.",
        "cta": "Hätten Sie Zeit für ein kurzes 5-Minuten-Gespräch?",
        "followup_1": "Hallo 👋\n\nIch melde mich nochmal wegen *{name}*.\n\nKeine Eile — wollte nur fragen, ob Sie interessiert sind?",
        "followup_2": "Hallo,\n\nKurze Frage: Wenn jemand in {city} nach Ihren Diensten sucht, findet er Sie leicht?\n\nEine Website hilft, rund um die Uhr gefunden zu werden.\n\nGespräch?",
        "followup_3": "Hallo,\n\nIch wollte etwas teilen.\n\nIch habe einem ähnlichen Unternehmen in {city} geholfen.\n\nSie bekommen jetzt 5-10 mehr Anfragen pro Monat.\n\nInteressiert?",
        "followup_4": "Hallo,\n\nLetzte Nachricht — wenn Sie jemals Hilfe mit einer Website brauchen, melden Sie sich.\n\nViel Erfolg! 🙌",
    },
    "fr": {  # French
        "greeting": "Bonjour 👋",
        "saw_business": "J'ai vu *{name}* sur Google — {rating}⭐ c'est super!",
        "question_website": "Question: Avez-vous un site web où les clients peuvent vous trouver?",
        "no_website_problem": "La plupart des entreprises sans site web perdent des clients au profit de concurrents.",
        "help_offer": "J'aide les entreprises locales à créer des sites web professionnels qui attirent plus de clients.",
        "cta": "Seriez-vous disponible pour une discussion de 5 minutes?",
        "followup_1": "Bonjour 👋\n\nJe reviens vers vous concernant *{name}*.\n\nPas de pression — je voulais juste savoir si vous êtes intéressé?",
        "followup_2": "Bonjour,\n\nPetite question: Quand quelqu'un cherche vos services à {city}, vous trouve-t-il facilement?\n\nUn site web aide à être trouvé 24h/24.\n\nOn en parle?",
        "followup_3": "Bonjour,\n\nJe voulais partager quelque chose.\n\nJ'ai aidé une entreprise similaire à {city}.\n\nIls reçoivent maintenant 5-10 demandes de plus par mois.\n\nIntéressé?",
        "followup_4": "Bonjour,\n\nDernier message — si vous avez besoin d'aide pour un site web, contactez-moi.\n\nBonne continuation! 🙌",
    },
    "es": {  # Spanish
        "greeting": "Hola 👋",
        "saw_business": "Vi *{name}* en Google — {rating}⭐ se ve genial!",
        "question_website": "Pregunta: ¿Tiene una página web donde los clientes puedan encontrarlo?",
        "no_website_problem": "La mayoría de negocios sin web pierden clientes frente a competidores.",
        "help_offer": "Ayudo a negocios locales a crear páginas web profesionales que atraen más clientes.",
        "cta": "¿Tendría 5 minutos para una charla rápida?",
        "followup_1": "Hola 👋\n\nLe escribo de nuevo sobre *{name}*.\n\nSin prisa — solo quería saber si está interesado?",
        "followup_2": "Hola,\n\nPregunta rápida: Cuando alguien busca sus servicios en {city}, ¿lo encuentran fácilmente?\n\nUna web ayuda a ser encontrado 24/7.\n\n¿Hablamos?",
        "followup_3": "Hola,\n\nQuería compartir algo.\n\nAyudé a un negocio similar en {city}.\n\nAhora reciben 5-10 consultas más al mes.\n\n¿Interesado?",
        "followup_4": "Hola,\n\nÚltimo mensaje — si necesita ayuda con una web, escríbame.\n\n¡Mucho éxito! 🙌",
    },
    "it": {  # Italian
        "greeting": "Ciao 👋",
        "saw_business": "Ho visto *{name}* su Google — {rating}⭐ sembra ottimo!",
        "question_website": "Domanda: Avete un sito web dove i clienti possono trovarvi?",
        "no_website_problem": "La maggior parte delle aziende senza sito perde clienti a favore dei concorrenti.",
        "help_offer": "Aiuto le aziende locali a creare siti web professionali che portano più clienti.",
        "cta": "Avreste 5 minuti per una breve chiacchierata?",
        "followup_1": "Ciao 👋\n\nTorno a scrivervi riguardo *{name}*.\n\nNessuna fretta — volevo solo sapere se siete interessati?",
        "followup_2": "Ciao,\n\nDomanda veloce: Quando qualcuno cerca i vostri servizi a {city}, vi trova facilmente?\n\nUn sito aiuta ad essere trovati 24/7.\n\nNe parliamo?",
        "followup_3": "Ciao,\n\nVolevo condividere qualcosa.\n\nHo aiutato un'azienda simile a {city}.\n\nOra ricevono 5-10 richieste in più al mese.\n\nInteressati?",
        "followup_4": "Ciao,\n\nUltimo messaggio — se avete bisogno di aiuto con un sito, scrivetemi.\n\nBuona fortuna! 🙌",
    },
    "pt": {  # Portuguese
        "greeting": "Olá 👋",
        "saw_business": "Vi *{name}* no Google — {rating}⭐ parece ótimo!",
        "question_website": "Pergunta: Tem um site onde os clientes podem encontrá-lo?",
        "no_website_problem": "A maioria dos negócios sem site perde clientes para concorrentes.",
        "help_offer": "Ajudo negócios locais a criar sites profissionais que trazem mais clientes.",
        "cta": "Teria 5 minutos para uma conversa rápida?",
        "followup_1": "Olá 👋\n\nEstou a dar seguimento sobre *{name}*.\n\nSem pressa — só queria saber se está interessado?",
        "followup_2": "Olá,\n\nPergunta rápida: Quando alguém procura os seus serviços em {city}, encontra-o facilmente?\n\nUm site ajuda a ser encontrado 24/7.\n\nConversamos?",
        "followup_3": "Olá,\n\nQueria partilhar algo.\n\nAjudei um negócio similar em {city}.\n\nAgora recebem 5-10 pedidos a mais por mês.\n\nInteressado?",
        "followup_4": "Olá,\n\nÚltima mensagem — se precisar de ajuda com um site, contacte-me.\n\nMuito sucesso! 🙌",
    },
    "nl": {  # Dutch
        "greeting": "Hallo 👋",
        "saw_business": "Ik zag *{name}* op Google — {rating}⭐ ziet er goed uit!",
        "question_website": "Vraag: Heeft u een website waar klanten u kunnen vinden?",
        "no_website_problem": "De meeste bedrijven zonder website verliezen klanten aan concurrenten.",
        "help_offer": "Ik help lokale bedrijven professionele websites te maken die meer klanten brengen.",
        "cta": "Heeft u 5 minuten voor een kort gesprek?",
        "followup_1": "Hallo 👋\n\nIk kom terug op mijn bericht over *{name}*.\n\nGeen haast — wilde even vragen of u geïnteresseerd bent?",
        "followup_2": "Hallo,\n\nSnelle vraag: Als iemand in {city} naar uw diensten zoekt, vindt hij u dan gemakkelijk?\n\nEen website helpt om 24/7 gevonden te worden.\n\nPraten?",
        "followup_3": "Hallo,\n\nIk wilde iets delen.\n\nIk heb een vergelijkbaar bedrijf in {city} geholpen.\n\nZe krijgen nu 5-10 meer aanvragen per maand.\n\nGeïnteresseerd?",
        "followup_4": "Hallo,\n\nLaatste bericht — als u ooit hulp nodig heeft met een website, neem contact op.\n\nVeel succes! 🙌",
    },
    "pl": {  # Polish
        "greeting": "Cześć 👋",
        "saw_business": "Znalazłem *{name}* w Google — {rating}⭐ wygląda świetnie!",
        "question_website": "Pytanie: Czy macie stronę internetową, gdzie klienci mogą Was znaleźć?",
        "no_website_problem": "Większość firm bez strony traci klientów na rzecz konkurencji.",
        "help_offer": "Pomagam lokalnym firmom tworzyć profesjonalne strony, które przyciągają więcej klientów.",
        "cta": "Czy mielibyście 5 minut na krótką rozmowę?",
        "followup_1": "Cześć 👋\n\nWracam do mojej wiadomości o *{name}*.\n\nBez pośpiechu — chciałem tylko zapytać, czy jesteście zainteresowani?",
        "followup_2": "Cześć,\n\nSzybkie pytanie: Gdy ktoś w {city} szuka Waszych usług, czy łatwo Was znajdzie?\n\nStrona pomaga być znalezionym 24/7.\n\nPorozmawiamy?",
        "followup_3": "Cześć,\n\nChciałem się czymś podzielić.\n\nPomogłem podobnej firmie w {city}.\n\nTeraz dostają 5-10 więcej zapytań miesięcznie.\n\nZainteresowani?",
        "followup_4": "Cześć,\n\nOstatnia wiadomość — jeśli kiedykolwiek potrzebujecie pomocy ze stroną, napiszcie.\n\nPowodzenia! 🙌",
    },
    "ro": {  # Romanian
        "greeting": "Bună 👋",
        "saw_business": "Am văzut *{name}* pe Google — {rating}⭐ arată grozav!",
        "question_website": "Întrebare: Aveți un site web unde clienții vă pot găsi?",
        "no_website_problem": "Majoritatea afacerilor fără site pierd clienți în favoarea concurenței.",
        "help_offer": "Ajut afacerile locale să creeze site-uri profesionale care aduc mai mulți clienți.",
        "cta": "Ați avea 5 minute pentru o discuție rapidă?",
        "followup_1": "Bună 👋\n\nRevin la mesajul meu despre *{name}*.\n\nFără grabă — voiam doar să întreb dacă sunteți interesat?",
        "followup_2": "Bună,\n\nÎntrebare rapidă: Când cineva caută serviciile dvs. în {city}, vă găsește ușor?\n\nUn site ajută să fiți găsit 24/7.\n\nDiscutăm?",
        "followup_3": "Bună,\n\nVoiam să vă spun ceva.\n\nAm ajutat o afacere similară în {city}.\n\nAcum primesc 5-10 cereri în plus pe lună.\n\nInteresat?",
        "followup_4": "Bună,\n\nUltimul mesaj — dacă aveți nevoie de ajutor cu un site, contactați-mă.\n\nMult succes! 🙌",
    },
    "sq": {  # Albanian
        "greeting": "Përshëndetje 👋",
        "saw_business": "Pashë *{name}* në Google — {rating}⭐ super!",
        "question_website": "Pyetje: A keni uebsajt ku klientët mund t'ju gjejnë online?",
        "no_website_problem": "Shumica e bizneseve pa uebsajt humbin klientë te konkurrentët.",
        "help_offer": "Unë ndihmoj bizneset lokale të kenë uebsajte profesionale që sjellin më shumë klientë.",
        "cta": "A keni 5 minuta për një bisedë të shkurtër?",
        "followup_1": "Përshëndetje 👋\n\nPo ju shkruaj përsëri për *{name}*.\n\nS'ka nxitim — thjesht doja me pyt a jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nPyetje e shpejtë: Kur dikush kërkon shërbimet tuaja në {city}, a ju gjen lehtë?\n\nNjë uebsajt ndihmon të gjendeni 24/7.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nNdihmova një biznes të ngjashëm në {city}.\n\nTani marrin 5-10 pyetje më shumë/muaj.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit — nëse keni nevojë për ndihmë me uebsajt, më shkruani.\n\nSuksese! 🙌",
    },
    "hr": {  # Croatian
        "greeting": "Bok 👋",
        "saw_business": "Vidio sam *{name}* na Googleu — {rating}⭐ izgleda odlično!",
        "question_website": "Pitanje: Imate li web stranicu gdje vas kupci mogu pronaći?",
        "no_website_problem": "Većina tvrtki bez weba gubi kupce konkurenciji.",
        "help_offer": "Pomažem lokalnim tvrtkama napraviti profesionalne web stranice koje donose više kupaca.",
        "cta": "Imate li 5 minuta za kratki razgovor?",
        "followup_1": "Bok 👋\n\nVraćam se na poruku o *{name}*.\n\nBez žurbe — samo sam htio pitati jeste li zainteresirani?",
        "followup_2": "Bok,\n\nBrzo pitanje: Kad netko traži vaše usluge u {city}, nalazi li vas lako?\n\nWeb stranica pomaže da budete pronađeni 24/7.\n\nRazgovaramo?",
        "followup_3": "Bok,\n\nHtio sam podijeliti nešto.\n\nPomogao sam sličnoj tvrtki u {city}.\n\nSad dobivaju 5-10 upita više mjesečno.\n\nZainteresirani?",
        "followup_4": "Bok,\n\nZadnja poruka — ako trebate pomoć s webom, javite se.\n\nSretno! 🙌",
    },
    "sr": {  # Serbian
        "greeting": "Zdravo 👋",
        "saw_business": "Video sam *{name}* na Google-u — {rating}⭐ izgleda odlično!",
        "question_website": "Pitanje: Da li imate web sajt gde vas kupci mogu pronaći?",
        "no_website_problem": "Većina firmi bez sajta gubi kupce konkurenciji.",
        "help_offer": "Pomažem lokalnim firmama da naprave profesionalne sajtove koji donose više kupaca.",
        "cta": "Da li imate 5 minuta za kratak razgovor?",
        "followup_1": "Zdravo 👋\n\nVraćam se na poruku o *{name}*.\n\nBez žurbe — samo sam hteo da pitam da li ste zainteresovani?",
        "followup_2": "Zdravo,\n\nBrzo pitanje: Kad neko traži vaše usluge u {city}, da li vas lako pronalazi?\n\nSajt pomaže da budete pronađeni 24/7.\n\nRazgovaramo?",
        "followup_3": "Zdravo,\n\nHteo sam da podelim nešto.\n\nPomogao sam sličnoj firmi u {city}.\n\nSad dobijaju 5-10 upita više mesečno.\n\nZainteresovani?",
        "followup_4": "Zdravo,\n\nPoslednja poruka — ako vam treba pomoć sa sajtom, javite se.\n\nSrećno! 🙌",
    },
}

# Default to English for languages not explicitly defined
DEFAULT_LANG = "en"

def get_language_for_city(city):
    """Get language code for a city"""
    country = CITY_TO_COUNTRY.get(city, "")
    return COUNTRY_LANGUAGE.get(country, DEFAULT_LANG)

def get_country_for_city(city):
    """Get country name for a city"""
    return CITY_TO_COUNTRY.get(city, "Unknown")


CATEGORY_MESSAGES = {
    "dentist": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ super!\n\n"
            "Pyetje: A po humbni pacientë sepse nuk mund të marrin radhë online?\n\n"
            "Pyes sepse shumica e dentistëve më thonë se humbin radhë pas orarit. "
            "Dikush dëshiron të marri radhë në 21:00 — nuk mund, pra shkon te konkurrenti.\n\n"
            "Unë ndihmoj klinikat dentare me uebsajt + sistem online për radhë. "
            "Zakonisht, dentistët marrin 10-15 radhë të reja/muaj nga radhët online.\n\n"
            "Doni të flasim 5 minuta?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo ju shkruaj përsëri për *{name}*.\n\nS'ka nxitim — thjesht doja me pyt a jeni të interesuar për radhë online?",
        "followup_2": "Përshëndetje {name},\n\nPyetje: Sa telefonata për radhë merrni në 21:00 kur zyra është mbyllur?\n\nProbabla shumë mundësi të humbura, apo jo?\n\nKjo është ajo që radhët online zgjidhin.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ju tregue diçka.\n\nMuajin e kaluar shtuam radhë online për një klinikë dentare në {city}.\n\nRezultati: 12 radhë të reja atë muaj që nuk do t'i kishin marrë.\n\nNëse doni të njëjtën për *{name}*, mund ta vendos në 5-7 ditë.\n\nInteresoheni?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit, premtoj! 😊\n\nNëse ndryshoni mendje për radhët online dhe doni t'i shtoni në *{name}*, më shkruani kurdo.\n\nSuksese me praktikën! 🙌",
    },
    "restaurant": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ shpresëlindëse!\n\n"
            "Pyetje: Po humbni klientë sepse nuk gjejnë menu tuaj online?\n\n"
            "Ja çfarë shoh: Dikush kërkon \"{city} restorant\" në Google, ju gjen, klikon listën tuaj... pa menu, pa opsion porosit. Shkon.\n\n"
            "Restorante me menu online + porosje marrin 20-30% më shumë të ardhura.\n\n"
            "Doni të flasim?"
        ),
        "followup_1": "Hey {name} 👋\n\nPo kontrolloj për mesazhin tim për vizibilitetin e menusë në Google.\n\nMë tregoni nëse doni të bisedojmë!",
        "followup_2": "Përshëndetje {name},\n\nJa një pyetje: Kur dikush kërkon \"{city} restorant\" dhe gjen listën tuaj në Google, çfarë sheh?\n\nProbabla pa menu. Pra shkon.\n\nMenu + porosje online = më shumë klientë.\n\nInteresoheni për një bisedë 5-min?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nShtuam menu online + porosje për një restorant si juaji.\n\nMorën 15 porosi shtesë atë javë vetëm nga menuja online.\n\nNëse e doni këtë për *{name}*, më tregoni.\n\nInteresante?",
        "followup_4": "Hey {name},\n\nMesazhi i fundit këtu.\n\nNëse ndonjëherë doni të shtoni menunë tuaj online ose të rrisni vizibilitetin në Google, jam vetëm një mesazh larg.\n\nJu uroj sukses të madh! 🙏",
    },
    "salon": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ shumë mirë!\n\n"
            "Pyetje: Sa orë në ditë shpenzoni në telefonat për radhë?\n\n"
            "Shumica e saloneve thonë 1-2 orë/ditë. Me sistem radhë online, bie në 15 minuta — dhe marrin MË SHUMË radhë!\n\n"
            "Plus: Klientët adhuroj të marrin radhë në mesnatë, jo të thërrasin gjatë orarit.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje {name} 👋\n\nFollow-up i shpejtë për sistemin e radhëve online që përmenda.\n\nA jeni të interesuar të kurseni kohë në thirrje?",
        "followup_2": "Përshëndetje {name},\n\nMendim i shpejtë: Sa të ardhura po humbni sepse dikush dëshiron të marri radhë në mesnatë por nuk mundet?\n\nRadhët online i kapin ato radhë automatikisht.\n\nDoni të bisedojmë për këtë?",
        "followup_3": "Përshëndetje,\n\nNdarje e shpejtë - shtuam radhë online për një salon si juaji.\n\nUlën kohën e telefonatave përgjysmë dhe morën 20 radhë shtesë atë muaj.\n\nMund të keni të njëjtën.\n\nShikojeni: [PORTFOLIO_LINK]\n\nDoni të flasim?",
        "followup_4": "Përshëndetje {name},\n\nKy është follow-up im i fundit.\n\nNëse doni të kurseni kohë dhe të merrni më shumë radhë, jam këtu kurdo të jeni gati.\n\nFat të mbarë! 💪",
    },
    "barber": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ shumë mirë!\n\n"
            "Pyetje: Sa orë në ditë shpenzoni në telefonat për radhë?\n\n"
            "Shumica e berberave thonë 1-2 orë/ditë. Me sistem radhë online, bie në 15 minuta — dhe marrin MË SHUMË radhë!\n\n"
            "Plus: Klientët adhuroj të marrin radhë në mesnatë, jo të thërrasin gjatë orarit.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje {name} 👋\n\nFollow-up i shpejtë për sistemin e radhëve online që përmenda.\n\nA jeni të interesuar të kurseni kohë në thirrje?",
        "followup_2": "Përshëndetje {name},\n\nMendim i shpejtë: Sa të ardhura po humbni sepse dikush dëshiron të marri radhë në mesnatë por nuk mundet?\n\nRadhët online i kapin ato radhë automatikisht.\n\nDoni të bisedojmë për këtë?",
        "followup_3": "Përshëndetje,\n\nNdarje e shpejtë - shtuam radhë online për një berber si juaji.\n\nUlën kohën e telefonatave përgjysmë dhe morën 20 radhë shtesë atë muaj.\n\nMund të keni të njëjtën.\n\nDoni të flasim?",
        "followup_4": "Përshëndetje {name},\n\nKy është follow-up im i fundit.\n\nNëse doni të kurseni kohë dhe të merrni më shumë radhë, jam këtu kurdo të jeni gati.\n\nFat të mbarë! 💪",
    },
    "lawyer": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* — {rating}⭐ punë e mirë!\n\n"
            "Vërejtje: Kur dikush në {city} kërkon \"avokat\" ose \"juridik\", a e pasin juve në faqen e parë të Google?\n\n"
            "Shumica thonë \"jo\" ose \"jo gjithmonë\". Problemi: 80% e njerëzve nuk shkojnë përtej faqes 1.\n\n"
            "Ndaj humbni klientë që kërkojnë JUVE në Google.\n\n"
            "Unë ndihmoj avokatë të shfaqen më mirë në Google. Zakonisht, marrin 2-4 klientë të rinj/muaj vetëm nga Google.\n\n"
            "Doni të bisedojmë?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo ju shkruaj përsëri për *{name}*.\n\nS'ka presion — thjesht doja me pyt a jeni të interesuar të bisedojmë?",
        "followup_2": "Përshëndetje {name},\n\nPyetje e shpejtë: Kur dikush në {city} kërkon \"avokat divorci\" ose \"avokat biznesi\", a shfaqeni në faqen e parë të Google?\n\nShumica e avokatëve thonë \"jo realisht\" ose \"jo vazhdimisht.\"\n\nKjo është problem sepse 80% e njerëzve nuk shkojnë përtej faqes 1.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ju tregue diçka.\n\nNdihmova një avokat në {city} të shfaqet më mirë në Google.\n\nRezultati: 3 klientë të rinj atë muaj vetëm nga kërkimet në Google.\n\nNëse doni të njëjtën për *{name}*, jam këtu.\n\nInteresante?",
        "followup_4": "Përshëndetje {name},\n\nMesazhi i fundit, premtoj!\n\nNëse ndryshoni mendje për vizibilitetin në Google dhe doni ndihmë, jam vetëm një mesazh larg.\n\nFat të mbarë me praktikën! 🙌",
    },
    "car repair": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ të besueshëm!\n\n"
            "Pyetje: Sa klientë po humbni sepse nuk mund të marrin radhë për riparim online?\n\n"
            "Ja çfarë ndodh: Makina ndërpret, klienti kërkon \"riparim makine {city}\", ju gjen, dëshiron të marri radhë... por duhet të thirret ose të vijë në person. Shkon tek të tjeri.\n\n"
            "Riparime me radhë online zakonisht marrin 15-20 radhë më shumë/muaj.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për radhët online për *{name}*.\n\nA jeni të interesuar të flasim?",
        "followup_2": "Përshëndetje {name},\n\nMendim i shpejtë: Kur makina e dikujt prishet dhe kërkojnë \"riparim makine afër meje\", a mund të marrin radhë lehtë tek ju?\n\nNëse jo, probabla po shkojnë tek konkurrenti që mund ta bëjnë.\n\nRadhët online e zgjidhin këtë.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nShtuam radhë online për një dyqan riparimi si juaji.\n\nMorën 18 radhë më shumë atë muaj.\n\nNëse e doni këtë për *{name}*, mund ta vendos shpejt.\n\nInteresante?",
        "followup_4": "Përshëndetje {name},\n\nMesazhi i fundit këtu.\n\nNëse ndonjëherë doni të shtoni radhë online për *{name}*, jam vetëm një mesazh larg.\n\nJu uroj sukses! 🙏",
    },
    "gym": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ ngrit!\n\n"
            "Pyetje: Sa lehtë është për dikë të regjistrohet në membership online?\n\n"
            "Shumica: \"Duhet të vijë në person\" ose \"Të thërrasë\".\n\n"
            "Problem: Njerëzit duan të regjistrohen në 23:00 nga telefoni, jo të thërrasin.\n\n"
            "Gymt me membership online marrin 30-40% më shumë anëtarë.\n\n"
            "Doni të bisedojmë?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për regjistrimin online për *{name}*.\n\nA jeni të interesuar të flasim?",
        "followup_2": "Përshëndetje {name},\n\nPyetje e shpejtë: Sa lehtë është për dikë të regjistrohet në gym tuaj në 23:00?\n\nNëse përgjigja është \"nuk mundet\", po humbni anëtarë.\n\nRegjistrimi online e rregullon këtë.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nShtuam regjistrim online + pagesë për një gym si juaji.\n\nPanë 35% më shumë anëtarë atë muaj.\n\nNëse e doni këtë për *{name}*, mund ta bëj shpejt.\n\nInteresante?",
        "followup_4": "Përshëndetje {name},\n\nMesazhi i fundit këtu.\n\nNëse ndonjëherë doni të shtoni regjistrim online, jam këtu.\n\nFat të mbarë! 💪",
    },
    "cafe": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ duket shumë mirë!\n\n"
            "Pyetje: A mund të shohin klientët menunë tuaj online para se të vijnë?\n\n"
            "Shumica e kafenesë/pasticerië nuk kanë menu online. Rezultati: klientët shkojnë tek konkurrenti që e ka.\n\n"
            "Me menu online + porosi, bizneset marrin 20-30% më shumë porosi.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar për menu online?",
        "followup_2": "Përshëndetje,\n\nMendim i shpejtë: Kur dikush kërkon \"kafene afër meje\" në {city}, a e gjejnë menunë tuaj?\n\nNëse jo, probabla shkojnë diku tjetër.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nShtuam menu online për një kafene në {city}.\n\nMorën 15 porosi më shumë atë javë.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni menu online për *{name}*, jam këtu.\n\nSuksese! 🙌",
    },
    "accountant": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* — {rating}⭐ punë e mirë!\n\n"
            "Pyetje: Kur dikush në {city} kërkon \"kontabilist\" në Google, a ju gjejnë lehtë?\n\n"
            "Shumica e kontabilistëve nuk shfaqen në faqen e parë. Problem: 80% e njerëzve nuk shkojnë përtej faqes 1.\n\n"
            "Unë ndihmoj kontabilistë të kenë prezencë profesionale online dhe të gjenden lehtë.\n\n"
            "Doni të bisedojmë?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nPyetje: Sa klientë të rinj merrni nga Google çdo muaj?\n\nNëse përgjigja është \"pak\" ose \"nuk e di\", mund të ndihmoj.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nDoja me ndaju diçka.\n\nNdihmova një kontabilist në {city} të ketë uebsajt profesional.\n\nTani merr 3-4 pyetje të reja çdo muaj nga Google.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni ndihmë me prezencën online, jam këtu.\n\nSuksese! 🙌",
    },
    "real_estate": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* — {rating}⭐ punë e mirë!\n\n"
            "Pyetje: A keni uebsajt ku klientët mund të shohin pronat tuaja 24/7?\n\n"
            "Agjencitë me uebsajt të mirë marrin 2-3x më shumë pyetje sepse klientët mund të shikojnë pronat kurdo.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nMendim: Sa lehtë është për dikë në {city} të gjejë pronat tuaja online?\n\nMe uebsajt, pronat janë të dukshme 24/7.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nNdihmova një agjenci në {city} me uebsajt + katalog pronash.\n\nTani marrin pyetje edhe në mesnatë.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni uebsajt për agjenci, jam këtu.\n\nSuksese! 🙌",
    },
    "home_services": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ punë e besueshme!\n\n"
            "Pyetje: Kur dikush në {city} ka emergjencë dhe kërkon shërbimet tuaja, a ju gjejnë lehtë?\n\n"
            "Shumica e bizneseve të shërbimeve nuk kanë prezencë të fortë online. Kjo do të thotë që klientët shkojnë tek konkurrenti.\n\n"
            "Me uebsajt + radhë online, merrni më shumë thirrje.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim.\n\nA jeni të interesuar për prezencë online?",
        "followup_2": "Përshëndetje,\n\nMendim: Sa klientë ju gjejnë përmes Google vs. rekomandimeve?\n\nMe uebsajt, mund të rrisni kërkimet.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nNdihmova një biznes shërbimesh në {city} me uebsajt.\n\nTani merr 5-10 thirrje më shumë/muaj.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni uebsajt, jam këtu.\n\nSuksese! 🙌",
    },
    "school": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ vlerësim i mirë!\n\n"
            "Pyetje: Sa lehtë është për prindërit/studentët të regjistrohen online?\n\n"
            "Shkollat me regjistrim online + informacione të qarta marrin 30-40% më shumë regjistrime.\n\n"
            "Njerëzit duan të shohin programet dhe çmimet online para se të telefonojnë.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nMendim: Sa pyetje merrni nga prindër që nuk mund të gjejnë informacione online?\n\nMe uebsajt të mirë, zvogëlohen pyetjet dhe rriten regjistrimet.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nNdihmova një shkollë në {city} me uebsajt + regjistrim online.\n\nMorën 25% më shumë regjistrime.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni uebsajt për shkollën, jam këtu.\n\nSuksese! 🙌",
    },
    "photographer": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ punë e mrekullueshme!\n\n"
            "Pyetje: A keni portfolio online ku klientët mund të shohin punën tuaj?\n\n"
            "Fotografët me portfolio profesionale online marrin 2-3x më shumë rezervime.\n\n"
            "Klientët duan të shohin stilin tuaj para se të rezervojnë.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nMendim: Ku i dërgoni klientët potencial të shohin punën tuaj?\n\nMe portfolio online, duket më profesionale.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nNdihmova një fotograf në {city} me portfolio online.\n\nTani merr rezervime direkt nga uebsajti.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni portfolio online, jam këtu.\n\nSuksese! 🙌",
    },
    "veterinarian": {
        "first": (
            "Përshëndetje 👋\n\n"
            "Pashë *{name}* në Google — {rating}⭐ kujdes i mirë për kafshët!\n\n"
            "Pyetje: A mund të marrin klientët radhë online për kafshët e tyre?\n\n"
            "Veterinerët me radhë online marrin 20-30% më shumë vizita sepse pronarët e kafshëve duan komoditet.\n\n"
            "Interesoheni?"
        ),
        "followup_1": "Përshëndetje 👋\n\nPo kontrolloj për mesazhin tim për *{name}*.\n\nA jeni të interesuar?",
        "followup_2": "Përshëndetje,\n\nMendim: Sa thirrje telefonike merrni për radhë çdo ditë?\n\nMe radhë online, kurseni kohë dhe merrni më shumë pacientë.\n\nBisedë?",
        "followup_3": "Përshëndetje,\n\nNdihmova një veteriner në {city} me uebsajt + radhë online.\n\nMorën 15 vizita më shumë/muaj.\n\nInteresante?",
        "followup_4": "Përshëndetje,\n\nMesazhi i fundit - nëse doni radhë online, jam këtu.\n\nSuksese! 🙌",
    },
}

def get_category_key(category):
    """Map category to message template key"""
    category_lower = category.lower()
    
    # Health & Medical
    if "dentist" in category_lower or "dental" in category_lower:
        return "dentist"
    elif "veterinar" in category_lower:
        return "veterinarian"
    
    # Beauty & Personal Care
    elif "salon" in category_lower or "spa" in category_lower or "nail" in category_lower or "massage" in category_lower:
        return "salon"
    elif "barber" in category_lower or "frizer" in category_lower:
        return "barber"
    
    # Food & Hospitality
    elif "restaurant" in category_lower or "restorant" in category_lower:
        return "restaurant"
    elif "cafe" in category_lower or "bakery" in category_lower or "pizzeria" in category_lower or "catering" in category_lower:
        return "cafe"
    
    # Professional Services
    elif "lawyer" in category_lower or "avokat" in category_lower:
        return "lawyer"
    elif "accountant" in category_lower or "kontabilist" in category_lower:
        return "accountant"
    elif "real estate" in category_lower or "patundshmeri" in category_lower:
        return "real_estate"
    
    # Automotive
    elif "car" in category_lower or "auto" in category_lower or "repair" in category_lower or "mechanic" in category_lower or "tire" in category_lower:
        return "car repair"
    
    # Fitness
    elif "gym" in category_lower or "fitness" in category_lower or "yoga" in category_lower or "martial" in category_lower or "trainer" in category_lower:
        return "gym"
    
    # Home Services
    elif "plumber" in category_lower or "electrician" in category_lower or "carpenter" in category_lower or "painter" in category_lower or "cleaning" in category_lower or "locksmith" in category_lower:
        return "home_services"
    
    # Education
    elif "school" in category_lower or "tutoring" in category_lower:
        return "school"
    
    # Photography & Events
    elif "photographer" in category_lower or "wedding" in category_lower:
        return "photographer"
    
    return None


def generate_first_message(lead):
    """Generate language-specific first message based on city/country and category"""
    city = lead.get('city', '')
    category = lead.get('category', '')
    lang = get_language_for_city(city)
    
    # Try to use category-specific messages if available (currently only for Albanian)
    category_key = get_category_key(category)
    if category_key and category_key in CATEGORY_MESSAGES and lang == "sq":
        # Use category-specific message for Albanian language
        rating = lead.get('rating', '')
        rating_text = f"{rating}" if rating else "⭐"
        template = CATEGORY_MESSAGES[category_key].get("first", "")
        if template:
            return template.format(
                name=lead.get('name', ''),
                rating=rating_text,
                city=city
            )
    
    # Fall back to language templates (multi-language support)
    templates = LANGUAGE_TEMPLATES.get(lang, LANGUAGE_TEMPLATES["en"])
    
    rating = lead.get('rating', '')
    rating_text = f"{rating}" if rating else "⭐"
    
    # Build the message from language templates
    message = (
        f"{templates['greeting']}\n\n"
        f"{templates['saw_business'].format(name=lead.get('name', ''), rating=rating_text)}\n\n"
        f"{templates['question_website']}\n\n"
        f"{templates['no_website_problem']}\n\n"
        f"{templates['help_offer']}\n\n"
        f"{templates['cta']}"
    )
    
    return message


def get_follow_up_message(lead, step):
    """Get language-specific follow-up message for a specific step (1-4)"""
    city = lead.get('city', '')
    category = lead.get('category', '')
    lang = get_language_for_city(city)
    
    # Try to use category-specific messages if available (currently only for Albanian)
    category_key = get_category_key(category)
    if category_key and category_key in CATEGORY_MESSAGES and lang == "sq":
        key = f"followup_{step}"
        template = CATEGORY_MESSAGES[category_key].get(key, "")
        if template:
            return template.format(
                name=lead.get('name', ''),
                city=city
            )
    
    # Fall back to language templates (multi-language support)
    templates = LANGUAGE_TEMPLATES.get(lang, LANGUAGE_TEMPLATES["en"])
    
    key = f"followup_{step}"
    template = templates.get(key, LANGUAGE_TEMPLATES["en"].get(key, ""))
    
    return template.format(
        name=lead.get('name', ''),
        city=city
    )


def generate_whatsapp_link(phone, message, city=""):
    if not phone:
        return ""

    # Clean the phone number
    phone_clean = (
        phone.replace(" ", "")
             .replace("-", "")
             .replace("(", "")
             .replace(")", "")
    )
    
    # Check if phone already has a country code (starts with + or known country codes)
    # Known country codes: 383 (Kosovo), 355 (Albania), 49 (Germany), 33 (France), etc.
    has_country_code = phone_clean.startswith("+")
    
    # Remove + if present
    if phone_clean.startswith("+"):
        phone_clean = phone_clean[1:]
    
    # Check if it already starts with a known country code (2-3 digits)
    if not has_country_code and len(phone_clean) >= 2:
        # Check for known country codes
        known_codes = ["383", "355", "49", "33", "39", "34", "44"]
        if any(phone_clean.startswith(code) for code in known_codes):
            has_country_code = True
    
    # Only add country code if phone doesn't already have one and starts with 0
    if not has_country_code and phone_clean.startswith("0"):
        if city in ["Pristina", "Prizren", "Ferizaj", "Gjilan", "Peja", "Mitrovica"]:
            # Kosovo - remove leading 0, add 383
            phone_clean = "383" + phone_clean[1:]
        elif city in ["Tirana", "Durrës", "Shkodër", "Vlorë"]:
            # Albania - remove leading 0, add 355
            phone_clean = "355" + phone_clean[1:]
        elif phone_clean.startswith("04") or phone_clean.startswith("03"):
            # Kosovo mobile numbers
            phone_clean = "383" + phone_clean[1:]
        elif phone_clean.startswith("06") or phone_clean.startswith("07"):
            # Albania mobile numbers
            phone_clean = "355" + phone_clean[1:]

    return f"https://wa.me/{phone_clean}?text={urllib.parse.quote(message)}"


# ============== TELEGRAM FUNCTIONS ==============
def send_telegram_alert(lead):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN:
        return

    # Use .get() to prevent KeyError crashes
    message = (
        f"HOT LEAD FOUND\n\n"
        f"Name: {lead.get('name', 'Unknown')}\n"
        f"City: {lead.get('city', 'Unknown')}\n"
        f"Rating: {lead.get('rating', 'N/A')}\n"
        f"Phone: {lead.get('phone', 'N/A')}\n"
        f"Price: {lead.get('suggested_price', 'N/A')}\n\n"
        f"WhatsApp: {lead.get('whatsapp_link', 'N/A')}\n\n"
        f"Maps: {lead.get('maps_url', 'N/A')}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        }, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error sending Telegram alert: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram alert: {e}")


def send_follow_up_reminder(lead, follow_up_step):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    titles = {
        1: "FOLLOW-UP #1 (24h) - Gentle",
        2: "FOLLOW-UP #2 (48h) - Reframe",
        3: "FOLLOW-UP #3 (72h) - Portfolio",
        4: "FOLLOW-UP #4 FINAL (120h)",
    }
    
    msg = get_follow_up_message(lead, follow_up_step)
    title = titles.get(follow_up_step, f"FOLLOW-UP #{follow_up_step}")

    wa_link = generate_whatsapp_link(lead.get('phone', ''), msg, lead.get('city', ''))

    # Use .get() to prevent KeyError crashes
    message = (
        f"{title}\n\n"
        f"Name: {lead.get('name', 'Unknown')}\n"
        f"City: {lead.get('city', 'Unknown')}\n"
        f"Category: {lead.get('category', 'Unknown')}\n"
        f"Rating: {lead.get('rating', 'N/A')}\n"
        f"Price: {lead.get('suggested_price', 'N/A')}\n\n"
        f"WhatsApp: {wa_link}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        }, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error sending Telegram follow-up reminder: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram follow-up reminder: {e}")


# ============== FOLLOW-UP SYSTEM ==============
def get_lead_age_hours(lead):
    """Get lead age in hours, returns 0 if error"""
    try:
        created_at_str = lead.get("created_at")
        if not created_at_str:
            return 0
        
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - created_at).total_seconds() / 3600
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.debug(f"Error calculating lead age: {e}")
        return 0


def check_follow_ups():
    """Check existing leads and send follow-up reminders (4-step sequence)"""
    if not os.path.exists(OUTPUT_FILE):
        print("No leads file found.")
        return

    leads = []
    try:
        with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
            leads = list(csv.DictReader(f))
    except (IOError, OSError, csv.Error) as e:
        logger.error(f"Error reading leads file: {e}")
        return

    updated = False
    for lead in leads:
        # Skip if already replied, closed, or lost
        if lead.get("status") in ["REPLIED", "CLOSED", "LOST"]:
            continue

        age_hours = get_lead_age_hours(lead)
        current_step = lead.get("follow_up_sent", "0")
        
        # Convert to int, handle "NO" as 0
        try:
            current_step = int(current_step) if current_step != "NO" else 0
        except ValueError:
            current_step = 0

        # Check each follow-up step
        for step, hours in FOLLOW_UP_HOURS.items():
            if current_step < step and age_hours >= hours:
                send_follow_up_reminder(lead, step)
                lead["follow_up_sent"] = str(step)
                updated = True
                step_names = {1: "Gentle", 2: "Reframe", 3: "Portfolio", 4: "FINAL"}
                lead_name = lead.get('name', 'Unknown')
                lead_category = lead.get('category', 'Unknown')
                logger.info(f"[FOLLOW-UP #{step} - {step_names.get(step, '')}] {lead_name} ({lead_category})")
                break  # Only send one follow-up at a time

    if updated:
        try:
            if leads and len(leads) > 0:
                with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                    # Use get_fieldnames() for consistency
                    fieldnames = get_fieldnames()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(leads)
                print("Follow-ups sent and saved.")
            else:
                logger.warning("No leads to save")
        except (IOError, OSError, csv.Error) as e:
            logger.error(f"Error saving follow-ups: {e}")
    else:
        print("No follow-ups needed.")


# ============== CSV FUNCTIONS ==============
def get_fieldnames():
    return [
        "name", "phone", "city", "country", "language", "address", "category", "rating", "maps_url", "website",
        "whatsapp_link", "first_message",
        "lead_score", "temperature", "suggested_price",
        "status",
        "created_at", "last_contacted", "follow_up_sent",
        "notes"
    ]


def save_lead(lead):
    """Save a single lead to CSV (append mode)"""
    file_exists = os.path.exists(OUTPUT_FILE)
    fieldnames = get_fieldnames()

    try:
        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(lead)
    except (IOError, OSError, csv.Error) as e:
        logger.error(f"Error saving lead: {e}")
        raise


def load_existing_leads():
    """Load existing leads to avoid duplicates"""
    if not os.path.exists(OUTPUT_FILE):
        return set()

    existing = set()
    try:
        with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(f"{row.get('name', '')}|{row.get('phone', '')}")
    except (IOError, OSError, csv.Error) as e:
        logger.error(f"Error loading existing leads: {e}")
        return set()  # Return empty set on error to allow processing
    
    return existing


# ============== MAIN FUNCTION ==============
def process_place(place: Dict[str, Any], city: str, category: str, existing_leads: set) -> Optional[Dict[str, Any]]:
    """
    Process a single place result and convert to lead if valid
    
    Args:
        place: Place data from Google Places API
        city: City name
        category: Business category
        existing_leads: Set of existing lead keys to check duplicates
    
    Returns:
        Lead dictionary if valid, None otherwise
    """
    try:
        place_id = place.get("place_id")
        if not place_id:
            return None
        
        details = get_place_details(place_id)
        
        # Validate that we got valid details
        if not details or not details.get("name"):
            logger.debug(f"Invalid or empty details for place_id: {place_id}")
            return None
        
        # FILTER: must have phone
        # Note: Yelp Fusion API (free tier) doesn't provide actual business websites,
        # only Yelp page URLs. The website field will remain empty.
        
        phone = details.get("formatted_phone_number", "")
        if not phone:
            return None
        
        # FILTER: Only save mobile numbers (for WhatsApp compatibility)
        # Be conservative: only accept numbers we can verify as mobile
        is_mobile = False
        phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        if phone_clean.startswith('+49'):  # Germany
            # Remove +49 and check for mobile prefixes
            local = phone_clean.replace('+49', '')
            if local.startswith('0'):
                local = local[1:]
            # German mobile prefixes: 15x, 16x, 17x
            if local.startswith(('15', '16', '17')) and len(local) >= 10:
                is_mobile = True
        elif phone_clean.startswith('+383'):  # Kosovo
            # Kosovo mobile: 044, 045, 043, 049, 048, or 6x, 7x
            local = phone_clean.replace('+383', '')
            if local.startswith('0'):
                local = local[1:]
            if local.startswith(('4', '6', '7')) and len(local) >= 8:
                is_mobile = True
        elif phone_clean.startswith('+355'):  # Albania
            # Albania mobile: 06x, 07x (9 digits after country code)
            local = phone_clean.replace('+355', '')
            if local.startswith(('6', '7')) and len(local) >= 9:
                is_mobile = True
        elif phone_clean.startswith('+33'):  # France
            # French mobile: 06, 07 (10 digits total)
            local = phone_clean.replace('+33', '')
            if local.startswith(('6', '7')) and len(local) == 9:
                is_mobile = True
        elif phone_clean.startswith('+39'):  # Italy
            # Italian mobile: 3xx (10 digits total, starts with 3)
            local = phone_clean.replace('+39', '')
            if local.startswith('3') and len(local) == 10:
                is_mobile = True
        elif phone_clean.startswith('+34'):  # Spain
            # Spanish mobile: 6xx, 7xx (9 digits)
            local = phone_clean.replace('+34', '')
            if local.startswith(('6', '7')) and len(local) == 9:
                is_mobile = True
        elif phone_clean.startswith('+44'):  # UK
            # UK mobile: 7xxx (11 digits total, starts with 7)
            local = phone_clean.replace('+44', '')
            if local.startswith('7') and len(local) == 10:
                is_mobile = True
        else:
            # For other countries, try to detect mobile numbers more flexibly
            # Most European mobile numbers start with country code + mobile prefix
            # Common mobile prefixes: 3, 4, 5, 6, 7, 8, 9 (varies by country)
            # Accept if phone has country code and reasonable length (8-15 digits)
            if phone_clean.startswith('+'):
                # Has country code - check if it's a reasonable mobile length
                # Remove country code (1-3 digits) and check remaining length
                digits_only = ''.join(filter(str.isdigit, phone_clean[1:]))  # Remove + and non-digits
                if 8 <= len(digits_only) <= 15:
                    # Could be a mobile number - accept it
                    # Most European mobile numbers are 9-12 digits after country code
                    is_mobile = True
                    logger.debug(f"Accepting potential mobile number from unvalidated country: {phone}")
        
        # Skip landlines - only save mobile numbers
        if not is_mobile:
            logger.debug(f"Skipping landline: {details.get('name')} - {phone}")
            return None
        
        # Note: Duplicate check is done in main() with proper locking
        # We don't check here to avoid race conditions
        
        maps_url = details.get("url", "")
        
        # Build lead
        lead = {
            "name": details.get("name", ""),
            "phone": details.get("formatted_phone_number", ""),
            "city": city,
            "country": get_country_for_city(city),
            "language": get_language_for_city(city),
            "address": details.get("formatted_address", ""),
            "category": category,
            "rating": details.get("rating"),
            "maps_url": maps_url,
            "website": "",
        }
        
        # Calculate score and temperature
        lead["lead_score"] = score_lead(lead)
        lead["temperature"] = lead_temperature(lead["lead_score"])
        lead["suggested_price"] = suggest_price(lead)
        
        # Generate message and WhatsApp link
        lead["first_message"] = generate_first_message(lead)
        lead["whatsapp_link"] = generate_whatsapp_link(
            lead["phone"],
            lead["first_message"],
            lead["city"]
        )
        
        # Status and tracking
        lead["status"] = "NEW"
        lead["created_at"] = datetime.now(timezone.utc).isoformat()
        lead["last_contacted"] = ""
        lead["follow_up_sent"] = "NO"
        lead["notes"] = ""
        
        return lead
        
    except Exception as e:
        logger.error(f"Error processing place {place.get('place_id', 'unknown')}: {e}")
        return None


def main():
    """Main function to search and process leads"""
    existing_leads = load_existing_leads()
    # Use a lock for thread-safe access to existing_leads
    leads_lock = threading.Lock()
    new_count = 0
    stats = {"HOT": 0, "WARM": 0, "COLD": 0}
    
    logger.info(f"Starting lead search... (found {len(existing_leads)} existing leads)")
    
    # Use ThreadPoolExecutor for concurrent API calls
    max_workers = 5  # Limit concurrent requests to respect rate limits
    
    for city in CITIES:
        for category in CATEGORIES:
            logger.info(f"Searching {category} in {city}...")
            
            response = search_places(f"{category} in {city}")
            
            while True:
                places = response.get("results", [])
                if not places:
                    break
                
                # Process places with reduced concurrency to avoid rate limits
                # Yelp has strict rate limits, so we use fewer workers
                with ThreadPoolExecutor(max_workers=2) as executor:  # Reduced from 5 to 2
                    future_to_place = {
                        executor.submit(process_place, place, city, category, existing_leads): place
                        for place in places
                    }
                    
                    for future in as_completed(future_to_place):
                        lead = future.result()
                        if lead:
                            # Check again for duplicates (thread-safe with lock)
                            lead_key = f"{lead.get('name', '')}|{lead.get('phone', '')}"
                            
                            with leads_lock:
                                if lead_key not in existing_leads:
                                    existing_leads.add(lead_key)
                                    
                                    # Save lead
                                    try:
                                        save_lead(lead)
                                        new_count += 1
                                        stats[lead.get("temperature", "COLD")] += 1
                                        
                                        lead_name = lead.get('name', 'Unknown')
                                        lead_temp = lead.get('temperature', 'COLD')
                                        lead_score = lead.get('lead_score', 0)
                                        logger.info(f"[{lead_temp}] {lead_name} - Score: {lead_score}")
                                        
                                        # Send Telegram alert for HOT leads
                                        if lead.get("temperature") == "HOT":
                                            send_telegram_alert(lead)
                                    except Exception as e:
                                        logger.error(f"Error saving lead {lead_key}: {e}")
                                        # Remove from set if save failed
                                        existing_leads.discard(lead_key)
                
                # Check for next page
                token = response.get("next_page_token")
                if not token:
                    break
                
                time.sleep(2)  # Required delay for pagination token
                response = search_places(f"{category} in {city}", token)
    
    logger.info(f"DONE - {new_count} new leads saved to {OUTPUT_FILE}")
    logger.info(f"HOT: {stats['HOT']} | WARM: {stats['WARM']} | COLD: {stats['COLD']}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--check-followups":
        check_follow_ups()
    else:
        main()
