"""
Phone number formatting service for European countries
"""
import re


# Country codes mapping
COUNTRY_CODES = {
    # Balkans
    "Kosovo": "383",
    "Albania": "355",
    "Serbia": "381",
    "North Macedonia": "389",
    "Montenegro": "382",
    "Bosnia and Herzegovina": "387",
    "Croatia": "385",
    "Slovenia": "386",
    
    # Western Europe
    "Germany": "49",
    "Austria": "43",
    "Switzerland": "41",
    "France": "33",
    "Belgium": "32",
    "Luxembourg": "352",
    "Netherlands": "31",
    
    # Southern Europe
    "Italy": "39",
    "Spain": "34",
    "Portugal": "351",
    "Greece": "30",
    
    # Northern Europe
    "United Kingdom": "44",
    "Ireland": "353",
    "Denmark": "45",
    "Sweden": "46",
    "Norway": "47",
    "Finland": "358",
    
    # Eastern Europe
    "Poland": "48",
    "Romania": "40",
    "Hungary": "36",
    "Czech Republic": "420",
    "Slovakia": "421",
    "Bulgaria": "359",
}


def clean_phone(phone):
    """Remove all non-digit characters except +"""
    if not phone:
        return None
    return re.sub(r'[^\d+]', '', phone)


def format_phone_international(phone, country="Kosovo"):
    """
    Format phone number to international format
    Returns: +XXXXXXXXXXX format
    """
    if not phone:
        return None
    
    # Clean the phone
    phone = clean_phone(phone)
    if not phone:
        return None
    
    # Already has + prefix
    if phone.startswith('+'):
        return phone
    
    # Remove leading zeros
    phone = phone.lstrip('0')
    
    # Kosovo-specific patterns
    if country == "Kosovo" or not country:
        # Kosovo mobile: 044, 045, 043, 049, 048
        if phone.startswith('4') and len(phone) == 8:
            return f"+383{phone}"
        # Already has country code
        if phone.startswith('383'):
            return f"+{phone}"
    
    # Albania-specific patterns
    if country == "Albania":
        # Albania mobile: 06x, 07x
        if (phone.startswith('6') or phone.startswith('7')) and len(phone) == 9:
            return f"+355{phone}"
        if phone.startswith('355'):
            return f"+{phone}"
    
    # Generic handling with country code
    country_code = COUNTRY_CODES.get(country, "383")  # Default to Kosovo
    
    # Check if already has a known country code
    for code in COUNTRY_CODES.values():
        if phone.startswith(code):
            return f"+{phone}"
    
    # Add country code
    return f"+{country_code}{phone}"


def format_for_whatsapp(phone, country="Kosovo"):
    """
    Format phone for WhatsApp API (without +)
    Returns: whatsapp:+XXXXXXXXXXX format for Twilio
    """
    formatted = format_phone_international(phone, country)
    if not formatted:
        return None
    
    # For Twilio WhatsApp
    return f"whatsapp:{formatted}"


def format_for_whatsapp_link(phone, country="Kosovo"):
    """
    Format phone for wa.me links (without +)
    Returns: Just the digits for wa.me/XXXXXXXXXXX
    """
    formatted = format_phone_international(phone, country)
    if not formatted:
        return None
    
    return formatted.replace('+', '')


def validate_phone(phone, country="Kosovo"):
    """
    Validate if phone number looks correct
    Returns: (is_valid, error_message)
    """
    if not phone:
        return False, "No phone number"
    
    formatted = format_phone_international(phone, country)
    if not formatted:
        return False, "Could not format phone"
    
    # Remove + for length check
    digits = formatted.replace('+', '')
    
    # Most international numbers are 10-15 digits
    if len(digits) < 10:
        return False, "Phone too short"
    if len(digits) > 15:
        return False, "Phone too long"
    
    return True, None


def detect_country_from_phone(phone):
    """
    Try to detect country from phone number
    Returns: Country name or None
    """
    if not phone:
        return None
    
    phone = clean_phone(phone)
    if not phone:
        return None
    
    # Remove + if present
    phone = phone.lstrip('+')
    
    # Check against known country codes (longest first)
    sorted_codes = sorted(COUNTRY_CODES.items(), key=lambda x: len(x[1]), reverse=True)
    
    for country, code in sorted_codes:
        if phone.startswith(code):
            return country
    
    return None
