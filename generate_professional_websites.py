#!/usr/bin/env python3
"""
Enhanced Professional Website Generator
Creates ultra-professional websites with advanced features
"""
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import random

try:
    from jinja2 import Template, Environment, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    print("Warning: Jinja2 not available. Using string templates instead.")

# Constants
DEFAULT_CITY = 'Prishtina'
DEFAULT_COUNTRY = 'Kosovo'
DEFAULT_CATEGORY = 'barber'
DEFAULT_RATING = 5.0
DEFAULT_BASE_DIR = '/home/behar/Desktop/professional-websites'
LEADS_FILE = 'selected_leads.json'

# Tailwind color mappings for dynamic class generation
TAILWIND_COLORS = {
    'blue': {
        '50': '#eff6ff', '100': '#dbeafe', '200': '#bfdbfe', '300': '#93c5fd',
        '400': '#60a5fa', '500': '#3b82f6', '600': '#2563eb', '700': '#1d4ed8'
    },
    'purple': {
        '50': '#faf5ff', '100': '#f3e8ff', '200': '#e9d5ff', '300': '#d8b4fe',
        '400': '#c084fc', '500': '#a855f7', '600': '#9333ea', '700': '#7e22ce'
    },
    'indigo': {
        '50': '#eef2ff', '100': '#e0e7ff', '200': '#c7d2fe', '300': '#a5b4fc',
        '400': '#818cf8', '500': '#6366f1', '600': '#4f46e5', '700': '#4338ca'
    },
    'red': {
        '50': '#fef2f2', '100': '#fee2e2', '200': '#fecaca', '300': '#fca5a5',
        '400': '#f87171', '500': '#ef4444', '600': '#dc2626', '700': '#b91c1c'
    },
    'orange': {
        '50': '#fff7ed', '100': '#ffedd5', '200': '#fed7aa', '300': '#fdba74',
        '400': '#fb923c', '500': '#f97316', '600': '#ea580c', '700': '#c2410c'
    },
    'yellow': {
        '50': '#fefce8', '100': '#fef9c3', '200': '#fef08a', '300': '#fde047',
        '400': '#facc15', '500': '#eab308', '600': '#ca8a04', '700': '#a16207'
    },
    'pink': {
        '50': '#fdf2f8', '100': '#fce7f3', '200': '#fbcfe8', '300': '#f9a8d4',
        '400': '#f472b6', '500': '#ec4899', '600': '#db2777', '700': '#be185d'
    },
    'rose': {
        '50': '#fff1f2', '100': '#ffe4e6', '200': '#fecdd3', '300': '#fda4af',
        '400': '#fb7185', '500': '#f43f5e', '600': '#e11d48', '700': '#be123c'
    },
    'fuchsia': {
        '50': '#fdf4ff', '100': '#fae8ff', '200': '#f5d0fe', '300': '#f0abfc',
        '400': '#e879f9', '500': '#d946ef', '600': '#c026d3', '700': '#a21caf'
    },
    'green': {
        '50': '#f0fdf4', '100': '#dcfce7', '200': '#bbf7d0', '300': '#86efac',
        '400': '#4ade80', '500': '#22c55e', '600': '#16a34a', '700': '#15803d'
    },
    'emerald': {
        '50': '#ecfdf5', '100': '#d1fae5', '200': '#a7f3d0', '300': '#6ee7b7',
        '400': '#34d399', '500': '#10b981', '600': '#059669', '700': '#047857'
    },
    'teal': {
        '50': '#f0fdfa', '100': '#ccfbf1', '200': '#99f6e4', '300': '#5eead4',
        '400': '#2dd4bf', '500': '#14b8a6', '600': '#0d9488', '700': '#0f766e'
    },
    'amber': {
        '50': '#fffbeb', '100': '#fef3c7', '200': '#fde68a', '300': '#fcd34d',
        '400': '#fbbf24', '500': '#f59e0b', '600': '#d97706', '700': '#b45309'
    },
}

def get_tailwind_color_hex(color_name: str, shade: str = '500') -> str:
    """Map Tailwind color names to hex values for CSS"""
    color_data = TAILWIND_COLORS.get(color_name, TAILWIND_COLORS['blue'])
    return color_data.get(shade, color_data['500'])

def get_tailwind_class(color_name: str, property_type: str, shade: str = '500') -> str:
    """Generate proper Tailwind CSS class name"""
    return f"{property_type}-{color_name}-{shade}"

def sanitize_name(name: str) -> str:
    """Convert business name to folder-friendly name"""
    if not name or not isinstance(name, str):
        raise ValueError("Name must be a non-empty string")
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'-+', '-', name)
    result = name.lower().strip('-')
    if not result:
        raise ValueError("Name resulted in empty string after sanitization")
    return result

def format_phone_for_url(phone: str) -> str:
    """Convert phone like '044 406 405' to '38344406405'"""
    if not phone or not isinstance(phone, str):
        raise ValueError("Phone must be a non-empty string")
    digits = phone.replace(' ', '').replace('-', '').replace('+', '')
    if not digits.isdigit():
        raise ValueError(f"Phone number contains invalid characters: {phone}")
    if digits.startswith('383'):
        return digits
    elif digits.startswith('0'):
        return '383' + digits[1:]
    return digits

def validate_lead(lead: Dict[str, Any]) -> None:
    """Validate lead data structure"""
    required_fields = ['name', 'phone']
    for field in required_fields:
        if field not in lead:
            raise ValueError(f"Missing required field: {field}")
        if not lead[field] or not isinstance(lead[field], str):
            raise ValueError(f"Field '{field}' must be a non-empty string")
    
    # Validate optional fields
    if 'rating' in lead:
        rating = lead['rating']
        if not isinstance(rating, (int, float)) or not (0 <= rating <= 5):
            raise ValueError(f"Rating must be a number between 0 and 5, got: {rating}")
    
    if 'category' in lead:
        valid_categories = ['dentist', 'restaurant', 'salon', 'barber', 'gym', 'cafe']
        if lead['category'] not in valid_categories:
            print(f"Warning: Unknown category '{lead['category']}', using default '{DEFAULT_CATEGORY}'")

def get_business_hours(category: str) -> Dict[str, str]:
    """Get business hours by category"""
    hours = {
        'dentist': {
            'mon_fri': '08:00 - 20:00',
            'saturday': '09:00 - 16:00',
            'sunday': 'Mbyllur'
        },
        'restaurant': {
            'mon_fri': '10:00 - 23:00',
            'saturday': '10:00 - 00:00',
            'sunday': '12:00 - 22:00'
        },
        'salon': {
            'mon_fri': '09:00 - 19:00',
            'saturday': '08:00 - 18:00',
            'sunday': '10:00 - 16:00'
        },
        'barber': {
            'mon_fri': '09:00 - 20:00',
            'saturday': '08:00 - 18:00',
            'sunday': 'Mbyllur'
        },
        'gym': {
            'mon_fri': '06:00 - 23:00',
            'saturday': '07:00 - 21:00',
            'sunday': '08:00 - 20:00'
        },
        'cafe': {
            'mon_fri': '07:00 - 22:00',
            'saturday': '08:00 - 23:00',
            'sunday': '09:00 - 21:00'
        }
    }
    return hours.get(category, hours[DEFAULT_CATEGORY])

def get_gallery_images(category: str) -> List[str]:
    """Get diverse gallery images for each category"""
    gallery_configs = {
        'dentist': [
            'https://images.unsplash.com/photo-1600988360767-2ab82995279c?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1606811971618-4486d14f3f99?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1606811841689-23dfddce3e95?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1621293954908-907159247fc8?auto=format&fit=crop&w=800&q=80',
        ],
        'restaurant': [
            'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1552569973-6103e7b6a5a7?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1551218808-94e220e084d2?auto=format&fit=crop&w=800&q=80',
        ],
        'salon': [
            'https://images.unsplash.com/photo-1560066984-76d77438c60b?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1522338243-2061a8e01a52?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1560472354-b33ff0c44a43?auto=format&fit=crop&w=800&q=80',
        ],
        'barber': [
            'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1585747860715-2ba37e788b7d?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1621605815971-fbc98d665033?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1622286342621-4bd786c2447c?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=800&q=80',
        ],
        'gym': [
            'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1517836357043-836509765618?auto=format&fit=crop&w=800&q=80',
        ],
        'cafe': [
            'https://images.unsplash.com/photo-1554118811-1e0d58224f24?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1445116572660-236099ec97a0?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1511920170033-83939cdbb2c6?auto=format&fit=crop&w=800&q=80',
            'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?auto=format&fit=crop&w=800&q=80',
        ]
    }
    return gallery_configs.get(category, gallery_configs['barber'])

def get_business_config(category: str) -> Dict[str, Any]:
    """Get comprehensive configuration based on business category"""
    configs = {
        'dentist': {
            'title_suffix': 'Klinike Dentare',
            'subtitle': 'Shërbime Dentare Profesionale & Modernë',
            'description': 'Ofrojmë shërbime dentare të nivelit të lartë me teknologji moderne dhe ekspertizë të provuar',
            'hero_image': 'https://images.unsplash.com/photo-1600988360767-2ab82995279c?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Kontroll & Diagnozë',
                    'desc': 'Ekzaminim i plotë dentar me teknologji dixhitale',
                    'price': '€30-50',
                    'icon': 'fa-search',
                    'features': ['X-Ray dixhital', 'Diagnozë 3D', 'Konsultë experte']
                },
                {
                    'name': 'Pastrim & Whitening',
                    'desc': 'Pastrim profesional dhe whitening dhëmbësh',
                    'price': '€40-80',
                    'icon': 'fa-tooth',
                    'features': ['Pastrim thellë', 'Whitening laser', 'Mbrojtje vrimash']
                },
                {
                    'name': 'Implante & Proteza',
                    'desc': 'Zëvendësim dhëmbësh me implant moderne',
                    'price': '€300-1500',
                    'icon': 'fa-bolt',
                    'features': ['Implante titan', 'Proteza akryl', 'Garanti 10 vjet']
                },
                {
                    'name': 'Ortodonti',
                    'desc': 'Trajtament drejtimi dhëmbësh',
                    'price': '€800-3000',
                    'icon': 'fa-align-center',
                    'features': ['Braces metal', 'Invisalign', 'Retainer']
                }
            ],
            'testimonials': [
                {'name': 'Arbnor M.', 'text': 'Shërbim i shkëlqyer! Stafi shumë profesional.', 'rating': 5},
                {'name': 'Elena K.', 'text': 'Klinika më moderne në Prishtinë.', 'rating': 5},
                {'name': 'Besian H.', 'text': 'Rezultatet e mrekullueshme!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(59, 130, 246, 0.85) 0%, rgba(147, 51, 234, 0.75) 50%, rgba(59, 130, 246, 0.85) 100%)',
            'colors': {'primary': 'blue', 'secondary': 'purple', 'accent': 'indigo'},
            'cta_text': 'Rezervoni Termin Tuaj Sot'
        },
        'restaurant': {
            'title_suffix': 'Restorant',
            'subtitle': 'Eksperienë Unike Gastronomike',
            'description': 'Shijoni shijet më të mira të kuzhinës tradicionale dhe ndërkombëtare në një ambient elegant',
            'hero_image': 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Kuzhina Tradicionale',
                    'desc': 'Gatime autentike shqiptare me receta të vjetra',
                    'price': '€8-15',
                    'icon': 'fa-utensils',
                    'features': ['Specialitete rajonale', 'Produkte lokale', 'Përgatitje tradicionale']
                },
                {
                    'name': 'Menu Ndërkombëtare',
                    'desc': 'Specialitete nga kuzhina italiane, franceze dhe aziatike',
                    'price': '€12-25',
                    'icon': 'fa-globe',
                    'features': ['Pizza italiane', 'Sushi', 'Steakhouse']
                },
                {
                    'name': 'Organizime Evente',
                    'desc': 'Dasma, festime dhe evente korporate',
                    'price': '€25-50/person',
                    'icon': 'fa-glass-cheers',
                    'features': ['Menu personalizuar', 'Dekorim', 'Muzikë live']
                },
                {
                    'name': 'Delivery & Catering',
                    'desc': 'Shërbim delivery dhe catering për evente',
                    'price': '€2-5 delivery',
                    'icon': 'fa-truck',
                    'features': ['Delivery 30 min', 'Catering', 'Menu ofruese']
                }
            ],
            'testimonials': [
                {'name': 'Lirim J.', 'text': 'Ushqim i shijshëm dhe ambient i mrekullueshëm!', 'rating': 5},
                {'name': 'Diana B.', 'text': 'Vendi më i mirë për dasma!', 'rating': 5},
                {'name': 'Marko T.', 'text': 'Shërbim 5 yje, çdo herë!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(239, 68, 68, 0.85) 0%, rgba(249, 115, 22, 0.75) 50%, rgba(239, 68, 68, 0.85) 100%)',
            'colors': {'primary': 'red', 'secondary': 'orange', 'accent': 'yellow'},
            'cta_text': 'Rezervoni Tavolinën'
        },
        'salon': {
            'title_suffix': 'Salon Bukurosie',
            'subtitle': 'Transformoni Pamjen Tuaj',
            'description': 'Shërbime profesionale të bukurisë me produkte premium dhe stilistë të certifikuar',
            'hero_image': 'https://images.unsplash.com/photo-1560066984-76d77438c60b?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Trajtime Flokësh',
                    'desc': 'Stilim, ngjyrosje, dhe trajtime flokësh',
                    'price': '€20-100',
                    'icon': 'fa-cut',
                    'features': ['Ngjyrosje profesionale', 'Keratinë', 'Trajtim dëmtimi']
                },
                {
                    'name': 'Makeup & Lashes',
                    'desc': 'Makeup artistik dhe zgjatje qerpikësh',
                    'price': '€30-80',
                    'icon': 'fa-paint-brush',
                    'features': ['Makeup dasma', 'Lash extensions', 'Microblading']
                },
                {
                    'name': 'Kujdes Lëkure',
                    'desc': 'Trajtime facial dhe kujdesi lëkure',
                    'price': '€25-70',
                    'icon': 'fa-spa',
                    'features': ['Trajtim anti-aging', 'Hidratim', 'Pastrim thellë']
                },
                {
                    'name': 'Manikyr & Pedikyr',
                    'desc': 'Shërbime komplet për duar dhe këmbë',
                    'price': '€15-40',
                    'icon': 'fa-hand-sparkles',
                    'features': ['Gel manicure', 'Pedikyr spa', 'Nail art']
                }
            ],
            'testimonials': [
                {'name': 'Sara L.', 'text': 'Stilistja më e mirë në qytet!', 'rating': 5},
                {'name': 'Mentor A.', 'text': 'Rezultatet janë të mrekullueshme!', 'rating': 5},
                {'name': 'Ana D.', 'text': 'Ambient i bukur dhe shërbim perfekt!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(236, 72, 153, 0.85) 0%, rgba(219, 39, 119, 0.75) 50%, rgba(236, 72, 153, 0.85) 100%)',
            'colors': {'primary': 'pink', 'secondary': 'rose', 'accent': 'fuchsia'},
            'cta_text': 'Rezervoni Termin'
        },
        'barber': {
            'title_suffix': 'Barber Shop',
            'subtitle': 'Stil & Precision për Burrat',
            'description': 'Specialistë në stilim burrash me teknika moderne dhe produkte premium',
            'hero_image': 'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Prerje Klasike & Modern',
                    'desc': 'Prerje të stilit të fundit dhe të klasik',
                    'price': '€8-15',
                    'icon': 'fa-cut',
                    'features': ['Fade', 'Undercut', 'Classic cut']
                },
                {
                    'name': 'Rrëmim & Rregullim Flokësh',
                    'desc': 'Rrëmim flokësh dhe rregullim me mjegull',
                    'price': '€5-10',
                    'icon': 'fa-wind',
                    'features': ['Pompadour', 'Quiff', 'Slick back']
                },
                {
                    'name': 'Bërje & Rruajtje Flokësh',
                    'desc': 'Bërje e rregullt dhe rruajtje flokësh',
                    'price': '€3-8',
                    'icon': 'fa-comb',
                    'features': ['Line up', 'Shape up', 'Beard trim']
                },
                {
                    'name': 'Trajtime & Ngjyrosje',
                    'desc': 'Trajtime flokësh dhe ngjyrosje',
                    'price': '€15-40',
                    'icon': 'fa-spray-can',
                    'features': ['Ngjyrosje gri', 'Trajtim kallami', 'Hidratim']
                }
            ],
            'testimonials': [
                {'name': 'Faton K.', 'text': 'Prerja më e mirë që kam pasur!', 'rating': 5},
                {'name': 'Bledi S.', 'text': 'Barber profesional dhe i shpejtë!', 'rating': 5},
                {'name': 'Armend R.', 'text': 'Vendi i preferuar barber!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(75, 0, 130, 0.85) 0%, rgba(138, 43, 226, 0.75) 50%, rgba(75, 0, 130, 0.85) 100%)',
            'colors': {'primary': 'purple', 'secondary': 'indigo', 'accent': 'violet'},
            'cta_text': 'Rezervoni Termin'
        },
        'gym': {
            'title_suffix': 'Fitness Center',
            'subtitle': 'Transformoni Trupin & Mendjen',
            'description': 'Qendër moderne fitness me pajisje të fundit dhe trainerë profesionalë',
            'hero_image': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Trajnim Personale',
                    'desc': 'Trajner personal për rezultat maksimal',
                    'price': '€30-60/session',
                    'icon': 'fa-dumbbell',
                    'features': ['Plan personalizuar', 'Nutrition', 'Tracking']
                },
                {
                    'name': 'Klasa Grupi',
                    'desc': 'Yoga, aerobik, HIIT, dhe shumë më shumë',
                    'price': '€5-15/class',
                    'icon': 'fa-users',
                    'features': ['Yoga', 'Zumba', 'CrossFit']
                },
                {
                    'name': 'Akses 24/7',
                    'desc': 'Qasje në palestër 24 orë në ditë',
                    'price': '€25-40/month',
                    'icon': 'fa-clock',
                    'features': ['24/7 access', 'Locker', 'Shower']
                },
                {
                    'name': 'Plan Ushqimi',
                    'desc': 'Këshilla nutritioniste dhe plan ushqimi',
                    'price': '€50-100/month',
                    'icon': 'fa-apple-alt',
                    'features': ['Meal plan', 'Supplements', 'Consulting']
                }
            ],
            'testimonials': [
                {'name': 'Fitnes B.', 'text': 'Tranformim komplet në 3 muaj!', 'rating': 5},
                {'name': 'Sportist A.', 'text': 'Trainerët më të mirë në Prishtinë!', 'rating': 5},
                {'name': 'Zana H.', 'text': 'Ambient motivues dhe pajisje moderne!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(34, 197, 94, 0.85) 0%, rgba(16, 185, 129, 0.75) 50%, rgba(34, 197, 94, 0.85) 100%)',
            'colors': {'primary': 'green', 'secondary': 'emerald', 'accent': 'teal'},
            'cta_text': 'Fillo Sot'
        },
        'cafe': {
            'title_suffix': 'Café',
            'subtitle': 'Kafë & Komunitet',
            'description': 'Hapësirë e ngrohtë për kafë të mirë, punë dhe shoqëri',
            'hero_image': 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {
                    'name': 'Kafë Specialitet',
                    'desc': 'Kafë e freskët dhe specialitete nga bota',
                    'price': '€1.5-4',
                    'icon': 'fa-coffee',
                    'features': ['Espresso', 'Cappuccino', 'Cold brew']
                },
                {
                    'name': 'Deserte & Ëmbëlsira',
                    'desc': 'Ëmbëlsira të freskëta dhe torta artizanale',
                    'price': '€2-6',
                    'icon': 'fa-birthday-cake',
                    'features': ['Torta ditore', 'Pastries', 'Vegan options']
                },
                {
                    'name': 'Brunch & Snacks',
                    'desc': 'Ushqime të lehta dhe sanduiça të freskët',
                    'price': '€4-10',
                    'icon': 'fa-sandwich',
                    'features': ['Sandwiches', 'Salads', 'Soups']
                },
                {
                    'name': 'Work Space',
                    'desc': 'Ambient për punë dhe studim',
                    'price': '€2-3/hour',
                    'icon': 'fa-wifi',
                    'features': ['Wi-Fi i shpejtë', 'Power outlets', 'Quiet zone']
                }
            ],
            'testimonials': [
                {'name': 'Kafexhiu M.', 'text': 'Kafja më e mirë në qytet!', 'rating': 5},
                {'name': 'Studentja A.', 'text': 'Vendet perfekt për studim!', 'rating': 5},
                {'name': 'Freelancer B.', 'text': 'Wi-Fi i shpejtë dhe kafë e shijshme!', 'rating': 5}
            ],
            'gradient': 'linear-gradient(135deg, rgba(245, 158, 11, 0.85) 0%, rgba(217, 119, 6, 0.75) 50%, rgba(245, 158, 11, 0.85) 100%)',
            'colors': {'primary': 'amber', 'secondary': 'yellow', 'accent': 'orange'},
            'cta_text': 'Na Vizitoni'
        }
    }
    
    return configs.get(category, configs[DEFAULT_CATEGORY])

def get_faq_data(category: str) -> List[Dict[str, str]]:
    """Get FAQ data based on category"""
    faqs = {
        'barber': [
            {'q': 'Sa kohë zgjat një prerje?', 'a': 'Një prerje standarde zgjat rreth 30-45 minuta, ndërsa stilime më komplekse mund të zgjasin deri në 1 orë.'},
            {'q': 'A pranoni rezervime online?', 'a': 'Po, mund të rezervoni online ose na telefononi direkt. Rekomandojmë rezervim për të garantuar kohën tuaj.'},
            {'q': 'Çfarë çmimesh keni?', 'a': 'Çmimet fillojnë nga €8 për prerje bazë dhe variojnë sipas stilit dhe kompleksitetit. Kontaktoni për çmime të detajuara.'},
            {'q': 'A ofroni shërbime për fëmijë?', 'a': 'Po, ofrojmë shërbime për të gjitha moshët. Kemi eksperiencë në stilim fëmijësh dhe adoleshentësh.'}
        ],
        'dentist': [
            {'q': 'A është e dhimbshme trajtamenti?', 'a': 'Përdorim anestezi lokale për të siguruar që trajtimet tona të jenë sa më pak të dhimbshme. Shumica e pacientëve raportojnë pak ose aspak dhimbje.'},
            {'q': 'Sa kohë zgjat një konsultë?', 'a': 'Konsulta fillestare zgjat rreth 30-45 minuta. Kjo përfshin ekzaminimin dhe diskutimin e planit të trajtimit.'},
            {'q': 'A pranoni sigurim shëndeti?', 'a': 'Po, pranojmë shumë plane sigurimi. Kontaktoni për të verifikuar nëse sigurimi juaj është i pranuar.'},
            {'q': 'Sa shpesh duhet të vij për kontroll?', 'a': 'Rekomandojmë kontroll çdo 6 muaj për mirëmbajtjen e shëndetit të dhëmbëve dhe parandalimin e problemeve.'}
        ],
        'restaurant': [
            {'q': 'A pranoni rezervime?', 'a': 'Po, rekomandojmë rezervime, veçanërisht për fundjavë dhe mbrëmje. Mund të rezervoni online ose telefononi.'},
            {'q': 'A keni menu për vegjetarianë?', 'a': 'Po, ofrojmë opsione të shumta vegjetariane dhe vegane në menu tonë. Të gjitha opsionet janë të shënuara qartë.'},
            {'q': 'A ofroni organizime evente?', 'a': 'Po, organizojmë dasma, festime, dhe evente korporate. Kontaktoni për të diskutuar nevojat tuaja.'},
            {'q': 'A keni parking?', 'a': 'Po, kemi parking falas për klientët tanë. Parkingu është i disponueshëm gjatë gjithë orarit të punës.'}
        ],
        'salon': [
            {'q': 'Sa kohë zgjat një stilim flokësh?', 'a': 'Stilimi bazë zgjat rreth 45 minuta, ndërsa ngjyrosje dhe trajtime komplekse mund të zgjasin 2-3 orë.'},
            {'q': 'A pranoni rezervime online?', 'a': 'Po, mund të rezervoni online përmes faqes sonë ose telefononi direkt. Rekomandojmë rezervim për kohë më të mira.'},
            {'q': 'Çfarë produkte përdorni?', 'a': 'Përdorim vetëm produkte premium dhe profesionale nga markat më të mira në treg për rezultate optimale.'},
            {'q': 'A ofroni shërbime për burra?', 'a': 'Po, ofrojmë shërbime për të gjithë. Kemi ekspertizë në stilim për të gjitha moshët dhe gjinitë.'}
        ],
        'gym': [
            {'q': 'A keni trajner personal?', 'a': 'Po, ofrojmë trajnim personal me trainerë të certifikuar. Çmimet fillojnë nga €30 për sesion.'},
            {'q': 'A keni klasa grupi?', 'a': 'Po, ofrojmë klasa të shumta grupi si Yoga, Zumba, HIIT, dhe CrossFit. Orari i klasave është i disponueshëm online.'},
            {'q': 'A keni akses 24/7?', 'a': 'Po, anëtarët tanë premium kanë akses 24 orë në ditë, 7 ditë në javë në palestër.'},
            {'q': 'Çfarë pajisjesh keni?', 'a': 'Kemi pajisje moderne dhe të fundit, duke përfshirë pesha, makina kardio, dhe zona për stërvitje funksionale.'}
        ],
        'cafe': [
            {'q': 'A keni Wi-Fi falas?', 'a': 'Po, ofrojmë Wi-Fi falas dhe të shpejtë për të gjithë klientët tanë.'},
            {'q': 'A keni opsione vegjetariane?', 'a': 'Po, ofrojmë shumë opsione vegjetariane dhe vegane në menu tonë.'},
            {'q': 'A pranoni rezervime?', 'a': 'Pranojmë rezervime për grupe më të mëdha. Për tavolina individuale, vini direkt.'},
            {'q': 'A keni ambient për punë?', 'a': 'Po, kemi hapësirë të dedikuar për punë me priza dhe ambient të qetë për fokusim.'}
        ]
    }
    return faqs.get(category, faqs['barber'])

def get_social_media_links(lead: Dict[str, Any]) -> Dict[str, str]:
    """Extract or generate social media links"""
    # Try to extract from lead data, or generate placeholder links
    return {
        'facebook': lead.get('facebook', f"https://facebook.com/{sanitize_name(lead['name'])}"),
        'instagram': lead.get('instagram', f"https://instagram.com/{sanitize_name(lead['name'])}"),
        'maps': lead.get('maps_url', '')
    }

def generate_schema_data(lead: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate JSON-LD schema for SEO"""
    business_type = {
        'dentist': 'Dentist',
        'restaurant': 'Restaurant',
        'salon': 'BeautySalon',
        'barber': 'BarberShop',
        'gym': 'HealthClub',
        'cafe': 'CafeOrCoffeeShop'
    }.get(lead.get('category', DEFAULT_CATEGORY), 'LocalBusiness')
    
    hours = get_business_hours(lead.get('category', DEFAULT_CATEGORY))
    
    schema = {
        "@context": "https://schema.org",
        "@type": business_type,
        "name": lead['name'],
        "description": config['description'],
        "address": {
            "@type": "PostalAddress",
            "addressLocality": lead.get('city', DEFAULT_CITY),
            "addressCountry": lead.get('country', DEFAULT_COUNTRY),
            "streetAddress": lead.get('address', '')
        },
        "telephone": lead['phone'],
        "email": lead.get('email', ''),
        "priceRange": config['services'][0]['price'] if config.get('services') else '',
        "openingHours": [
            f"Mo-Fr {hours['mon_fri']}",
            f"Sa {hours['saturday']}",
            f"Su {hours['sunday']}"
        ],
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": str(lead.get('rating', DEFAULT_RATING)),
            "reviewCount": str(random.randint(20, 200))
        },
        "sameAs": lead.get('website', '')
    }
    
    return json.dumps(schema, indent=4, ensure_ascii=False)

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not isinstance(text, str):
        text = str(text)
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))

def create_professional_html(lead: Dict[str, Any]) -> str:
    """Create ultra-professional HTML website"""
    try:
        validate_lead(lead)
    except ValueError as e:
        raise ValueError(f"Invalid lead data: {e}") from e
    
    name = lead['name']
    phone = lead['phone']
    try:
        phone_url = format_phone_for_url(phone)
    except ValueError as e:
        raise ValueError(f"Invalid phone number: {e}") from e
    
    rating = lead.get('rating', DEFAULT_RATING)
    city = lead.get('city', DEFAULT_CITY)
    category = lead.get('category', DEFAULT_CATEGORY)
    address = lead.get('address', '')
    
    config = get_business_config(category)
    colors = config['colors']
    hours = get_business_hours(category)
    
    # Get color values for inline styles (fixes Tailwind dynamic class issue)
    primary_color_500 = get_tailwind_color_hex(colors["primary"], '500')
    primary_color_600 = get_tailwind_color_hex(colors["primary"], '600')
    primary_color_700 = get_tailwind_color_hex(colors["primary"], '700')
    primary_color_100 = get_tailwind_color_hex(colors["primary"], '100')
    primary_color_200 = get_tailwind_color_hex(colors["primary"], '200')
    primary_color_400 = get_tailwind_color_hex(colors["primary"], '400')
    secondary_color_600 = get_tailwind_color_hex(colors["secondary"], '600')
    
    # Generate service cards with pricing
    service_cards = ""
    for service in config['services']:
        features_html = ""
        for feature in service.get('features', []):
            features_html += f'<li><i class="fas fa-check mr-2" style="color: {primary_color_500};"></i>{escape_html(feature)}</li>'
        
        service_cards += f'''
                <div class="service-card bg-white p-8 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300" style="border-top: 4px solid {primary_color_500};">
                    <div class="text-center mb-6">
                        <div class="w-20 h-20 mx-auto rounded-full flex items-center justify-center mb-4" style="background: linear-gradient(to bottom right, {primary_color_100}, {primary_color_200});">
                            <i class="fas {service.get('icon', 'fa-star')} text-3xl" style="color: {primary_color_600};"></i>
                        </div>
                        <h3 class="elegant-font text-xl font-bold text-gray-800 mb-2">
                            {escape_html(service.get('name', ''))}
                        </h3>
                        <p class="text-gray-600 text-sm leading-relaxed mb-4">
                            {escape_html(service.get('desc', ''))}
                        </p>
                        <div class="text-2xl font-bold mb-4" style="color: {primary_color_600};">
                            {escape_html(service.get('price', ''))}
                        </div>
                    </div>
                    <ul class="text-gray-600 space-y-2 text-sm">
                        {features_html}
                    </ul>
                </div>'''
    
    # Generate testimonials
    testimonials_html = ""
    for testimonial in config.get('testimonials', []):
        stars_html = "⭐" * testimonial.get('rating', 5)
        testimonials_html += f'''
                <div class="bg-white p-6 rounded-xl shadow-lg">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 rounded-full flex items-center justify-center" style="background-color: {primary_color_100};">
                            <i class="fas fa-user" style="color: {primary_color_600};"></i>
                        </div>
                        <div class="ml-4">
                            <h4 class="font-bold text-gray-800">{escape_html(testimonial.get('name', ''))}</h4>
                            <div class="text-yellow-400 text-sm">{stars_html}</div>
                        </div>
                    </div>
                    <p class="text-gray-600 italic">"{escape_html(testimonial.get('text', ''))}"</p>
                </div>'''
    
    # Generate FAQ HTML
    faqs = get_faq_data(category)
    faq_html = ""
    for i, faq in enumerate(faqs):
        faq_html += f'''
                <div class="bg-white rounded-xl shadow-md overflow-hidden">
                    <button class="faq-question w-full text-left p-6 flex justify-between items-center hover:bg-gray-50 transition" onclick="toggleFaq({i})">
                        <span class="font-semibold text-gray-800">{escape_html(faq['q'])}</span>
                        <i class="fas fa-chevron-down faq-icon transition-transform" id="faq-icon-{i}"></i>
                    </button>
                    <div class="faq-answer hidden p-6 pt-0 text-gray-600" id="faq-answer-{i}">
                        {escape_html(faq['a'])}
                    </div>
                </div>'''
    
    # Generate image gallery (using diverse Unsplash images based on category)
    gallery_images = get_gallery_images(category)
    gallery_html = ""
    for img_url in gallery_images[:6]:  # Use up to 6 images
        gallery_html += f'''
                <div class="gallery-item overflow-hidden rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300">
                    <img src="{img_url}" alt="{escape_html(name)}" class="w-full h-64 object-cover hover:scale-110 transition-transform duration-500" loading="lazy" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'800\\' height=\\'600\\'%3E%3Crect fill=\\'%23f3f4f6\\' width=\\'800\\' height=\\'600\\'/%3E%3Ctext fill=\\'%239ca3af\\' font-family=\\'sans-serif\\' font-size=\\'24\\' x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\'%3E{escape_html(name)}%3C/text%3E%3C/svg%3E';">
                </div>'''
    
    # Generate before/after gallery for relevant categories (use first 3 images)
    before_after_html = ""
    if category in ['barber', 'salon', 'dentist']:
        before_after_gallery_html = ""
        for img_url in gallery_images[:3]:  # Use first 3 images for before/after
            before_after_gallery_html += f'''
                <div class="gallery-item overflow-hidden rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300">
                    <img src="{img_url}" alt="{escape_html(name)} - Para & Pas" class="w-full h-64 object-cover hover:scale-110 transition-transform duration-500" loading="lazy" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'800\\' height=\\'600\\'%3E%3Crect fill=\\'%23f3f4f6\\' width=\\'800\\' height=\\'600\\'/%3E%3Ctext fill=\\'%239ca3af\\' font-family=\\'sans-serif\\' font-size=\\'24\\' x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\'%3E{escape_html(name)}%3C/text%3E%3C/svg%3E';">
                </div>'''
        
        before_after_html = f'''
    <!-- Before/After Gallery -->
    <section id="gallery" class="py-20 px-4 bg-white">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Para & Pas
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Shikoni transformimet e mrekullueshme të klientëve tanë
                </p>
            </div>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {before_after_gallery_html}
            </div>
        </div>
    </section>'''
    
    # Get social media links
    social_links = get_social_media_links(lead)
    
    # Generate Google Maps embed URL
    maps_url = lead.get('maps_url', social_links.get('maps', ''))
    maps_embed = ""
    if maps_url and 'cid=' in maps_url:
        cid = maps_url.split('cid=')[1].split('&')[0]
        maps_embed = f'https://www.google.com/maps/embed?cid={cid}'
    elif address:
        # Fallback to address-based map (using place search)
        encoded_address = (address + ', ' + city).replace(' ', '+').replace(',', '%2C')
        maps_embed = f'https://www.google.com/maps?q={encoded_address}&output=embed'
    
    schema_data = generate_schema_data(lead, config)
    
    html = f'''<!DOCTYPE html>
<html lang="sq">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(name)} - {escape_html(config['title_suffix'])} | {escape_html(city)} | Rating {rating}⭐</title>
    <meta name="description" content="{escape_html(config['description'])} | Shërbime profesionale në {escape_html(city)}. Kontakt: {escape_html(phone)}">
    <meta name="keywords" content="{escape_html(name)}, {escape_html(config['title_suffix'])}, {escape_html(city)}, {escape_html(category)}, shërbime profesional">
    <meta name="author" content="{escape_html(name)}">
    
    <!-- Open Graph -->
    <meta property="og:title" content="{escape_html(name)} - {escape_html(config['title_suffix'])}">
    <meta property="og:description" content="{escape_html(config['description'])}">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="sq_AL">
    
    <!-- Favicon -->
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⭐</text></svg>">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <!-- Schema.org JSON-LD -->
    <script type="application/ld+json">
    {schema_data}
    </script>
    
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800&family=Poppins:wght@300;400;500;600;700&display=swap');
        
        * {{
            scroll-behavior: smooth;
        }}
        
        body {{
            font-family: 'Poppins', sans-serif;
        }}
        
        .elegant-font {{
            font-family: 'Playfair Display', serif;
        }}
        
        .hero-overlay {{
            background: {config['gradient']};
            backdrop-filter: blur(2px);
        }}
        
        .service-card {{
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        .service-card:hover {{
            transform: translateY(-15px) scale(1.02);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.2);
        }}
        
        .gradient-text {{
            background: linear-gradient(135deg, {primary_color_600} 0%, {secondary_color_600} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .floating {{
            animation: float 6s ease-in-out infinite;
        }}
        
        @keyframes float {{
            0%, 100% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-20px); }}
        }}
        
        .pulse {{
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: .8; }}
        }}
        
        .sticky-nav {{
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.95);
        }}
        
        .rating-stars {{
            color: #fbbf24;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .cta-button {{
            background: linear-gradient(135deg, {primary_color_600} 0%, {secondary_color_600} 100%);
            transition: all 0.3s ease;
        }}
        
        .cta-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        }}
        
        .faq-question {{
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .faq-answer {{
            transition: all 0.3s ease;
        }}
        
        .gallery-item {{
            cursor: pointer;
        }}
        
        .gallery-item img {{
            transition: transform 0.5s ease;
        }}
        
        input:focus, select:focus, textarea:focus {{
            border-color: {primary_color_500} !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }}
        
        #backToTop {{
            transition: opacity 0.3s, transform 0.3s;
        }}
        
        #backToTop:hover {{
            transform: translateY(-3px);
        }}
        
        #chatWidget {{
            animation: pulse-chat 2s infinite;
        }}
        
        @keyframes pulse-chat {{
            0%, 100% {{
                transform: scale(1);
            }}
            50% {{
                transform: scale(1.05);
            }}
        }}
        
        .counter {{
            transition: all 0.3s ease;
        }}
        
        #socialShareContainer {{
            opacity: 0.7;
            transition: opacity 0.3s ease;
        }}
        
        #socialShareContainer:hover {{
            opacity: 1;
        }}
        
        #socialShareMenu {{
            animation: slideUp 0.3s ease;
        }}
        
        @keyframes slideUp {{
            from {{
                opacity: 0;
                transform: translateY(10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body class="bg-gray-50 text-gray-900">
    
    <!-- Sticky Navigation -->
    <nav id="navbar" class="sticky-nav fixed top-0 w-full z-50 shadow-sm transition-all duration-300">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center py-4">
                <div class="flex items-center">
                    <h1 class="elegant-font text-xl font-bold text-gray-800">{escape_html(name)}</h1>
                </div>
                <div class="hidden md:flex space-x-8">
                    <a href="#services" class="text-gray-600 hover:opacity-75 transition" style="color: {primary_color_600};">Shërbimet</a>
                    <a href="#testimonials" class="text-gray-600 hover:opacity-75 transition" style="color: {primary_color_600};">Klientë</a>
                    <a href="#portfolio" class="text-gray-600 hover:opacity-75 transition" style="color: {primary_color_600};">Portofoli</a>
                    <a href="#faq" class="text-gray-600 hover:opacity-75 transition" style="color: {primary_color_600};">FAQ</a>
                    <a href="#contact" class="text-gray-600 hover:opacity-75 transition" style="color: {primary_color_600};">Kontakt</a>
                </div>
                <div class="flex items-center space-x-4">
                    <div class="rating-stars">
                        {rating}⭐
                    </div>
                    <a href="tel:+{phone_url}" class="text-white px-4 py-2 rounded-full hover:opacity-90 transition" style="background-color: {primary_color_600};">
                        <i class="fas fa-phone mr-2"></i>{escape_html(phone)}
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Hero Section -->
    <section class="relative min-h-screen flex items-center justify-center bg-cover bg-center" style="background-image: url('{config['hero_image']}');">
        <div class="hero-overlay absolute inset-0"></div>
        <div class="relative z-10 text-center px-4 max-w-5xl mx-auto">
            <div class="floating">
                <h1 class="elegant-font text-5xl md:text-7xl font-bold text-white mb-6 drop-shadow-2xl">
                    {escape_html(name)}
                </h1>
                <p class="text-2xl md:text-3xl text-white mb-8 font-light tracking-wide drop-shadow-lg">
                    {escape_html(config['subtitle'])}
                </p>
                <p class="text-lg md:text-xl text-gray-100 mb-10 max-w-2xl mx-auto italic">
                    {escape_html(config['description'])}
                </p>
                <div class="flex flex-col sm:flex-row gap-4 justify-center items-center">
                    <button onclick="openBookingModal()" class="cta-button text-white font-semibold py-4 px-10 rounded-full text-lg inline-flex items-center cursor-pointer">
                        <i class="fas fa-star mr-2"></i> {escape_html(config['cta_text'])}
                    </button>
                    <a href="https://wa.me/{phone_url}" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-4 px-10 rounded-full text-lg transition duration-300 inline-flex items-center">
                        <i class="fab fa-whatsapp mr-2"></i> WhatsApp
                    </a>
                </div>
            </div>
        </div>
        <div class="absolute bottom-10 left-1/2 transform -translate-x-1/2 animate-bounce">
            <i class="fas fa-chevron-down text-white text-2xl"></i>
        </div>
    </section>

    <!-- Trust Badges -->
    <section class="py-8 bg-white border-b">
        <div class="max-w-6xl mx-auto px-4">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                <div class="pulse">
                    <div class="text-3xl font-bold counter" data-target="{random.randint(5, 15)}" style="color: {primary_color_600};">0</div>
                    <div class="text-gray-600">+ Vjet Përvojë</div>
                </div>
                <div class="pulse" style="animation-delay: 0.5s;">
                    <div class="text-3xl font-bold counter" data-target="{random.randint(500, 5000)}" style="color: {primary_color_600};">0</div>
                    <div class="text-gray-600">+ Klientë të Kënaqur</div>
                </div>
                <div class="pulse" style="animation-delay: 1s;">
                    <div class="text-3xl font-bold" style="color: {primary_color_600};"><span class="counter" data-target="{int(rating * 10)}" data-decimals="1">0</span>⭐</div>
                    <div class="text-gray-600">Vlerësim</div>
                </div>
                <div class="pulse" style="animation-delay: 1.5s;">
                    <div class="text-3xl font-bold" style="color: {primary_color_600};"><span class="counter" data-target="100">0</span>%</div>
                    <div class="text-gray-600">Kënaqësi</div>
                </div>
            </div>
        </div>
    </section>

    <!-- Services Section -->
    <section id="services" class="py-20 px-4 bg-gradient-to-b from-gray-50 to-white">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Shërbimet Tona Premium
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Ofrojmë shërbime të nivelit të lartë me çmime konkurruese dhe rezultata të garantuara
                </p>
            </div>
            
            <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
                {service_cards}
            </div>
        </div>
    </section>

    <!-- Testimonials Section -->
    <section id="testimonials" class="py-20 px-4 bg-gray-100">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Ç' thonë Klientët Tanë
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Më shumë se {random.randint(100, 1000)} klientë të kënaqur na besojnë
                </p>
                <button onclick="openReviewModal()" class="mt-4 px-6 py-2 rounded-full text-sm font-semibold transition" style="background: linear-gradient(135deg, {primary_color_600} 0%, {secondary_color_600} 100%); color: white;">
                    <i class="fas fa-star mr-2"></i>Shkruani Vlerësimin Tuaj
                </button>
            </div>
            
            <div class="grid md:grid-cols-3 gap-8">
                {testimonials_html}
            </div>
        </div>
    </section>

    {before_after_html}

    <!-- Image Gallery Section -->
    <section id="portfolio" class="py-20 px-4 bg-gradient-to-b from-white to-gray-50">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Portofoli
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Shikoni punën tonë dhe eksperiencën profesionale
                </p>
            </div>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {gallery_html}
            </div>
        </div>
    </section>

    <!-- Business Hours & Location -->
    <section class="py-16 px-4 bg-white">
        <div class="max-w-4xl mx-auto">
            <div class="grid md:grid-cols-2 gap-12">
                <div>
                    <h3 class="elegant-font text-2xl font-bold mb-6 text-gray-800">Orari i Punës</h3>
                    <div class="space-y-3">
                        <div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span class="font-medium">E Hënë - E Premte</span>
                            <span class="font-bold" style="color: {primary_color_600};">{hours['mon_fri']}</span>
                        </div>
                        <div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span class="font-medium">E Shtunë</span>
                            <span class="font-bold" style="color: {primary_color_600};">{hours['saturday']}</span>
                        </div>
                        <div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                            <span class="font-medium">E Diel</span>
                            <span class="text-red-600 font-bold">{hours['sunday']}</span>
                        </div>
                    </div>
                </div>
                
                <div>
                    <h3 class="elegant-font text-2xl font-bold mb-6 text-gray-800">Lokacioni</h3>
                    <div class="bg-gray-50 p-6 rounded-lg">
                        <div class="flex items-start space-x-4">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style="background-color: {primary_color_100};">
                                <i class="fas fa-map-marker-alt" style="color: {primary_color_600};"></i>
                            </div>
                            <div>
                                <p class="font-medium mb-2">{escape_html(name)}</p>
                                <p class="text-gray-600">{escape_html(address)}</p>
                                <p class="text-gray-600">{escape_html(city)}, {escape_html(lead.get('country', DEFAULT_COUNTRY))}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Google Maps Section -->
    {f'<section class="py-16 px-4 bg-gray-50"><div class="max-w-6xl mx-auto"><h3 class="elegant-font text-2xl font-bold mb-6 text-center text-gray-800">Gjeni Ne</h3><div class="rounded-xl overflow-hidden shadow-xl" style="height: 400px;"><iframe width="100%" height="100%" frameborder="0" style="border:0;" src="{maps_embed}" allowfullscreen="" loading="lazy"></iframe></div></div></section>' if maps_embed else ''}

    <!-- FAQ Section -->
    <section id="faq" class="py-20 px-4 bg-white">
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Pyetje të Shpeshta
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Gjeni përgjigje për pyetjet më të shpeshta
                </p>
            </div>
            <div class="space-y-4">
                {faq_html}
            </div>
        </div>
    </section>

    <!-- Booking Modal -->
    <div id="bookingModal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl max-w-md w-full p-8 relative max-h-[90vh] overflow-y-auto">
            <button onclick="closeBookingModal()" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
                <i class="fas fa-times text-2xl"></i>
            </button>
            <h3 class="elegant-font text-2xl font-bold mb-6 text-gray-800">Rezervoni Termin</h3>
            <form onsubmit="event.preventDefault(); alert('Faleminderit! Do t\\'ju kontaktojmë së shpejti.'); closeBookingModal();" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Emri</label>
                    <input type="text" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none; focus:ring: 2px solid {primary_color_500};">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Telefoni</label>
                    <input type="tel" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Data</label>
                    <input type="date" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Koha</label>
                    <input type="time" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Shërbimi</label>
                    <select required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;">
                        <option value="">Zgjidhni shërbimin</option>
                        {''.join([f'<option value="{escape_html(s.get("name", ""))}">{escape_html(s.get("name", ""))}</option>' for s in config.get("services", [])])}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Mesazh (opsional)</label>
                    <textarea rows="3" class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;"></textarea>
                </div>
                <button type="submit" class="w-full cta-button text-white font-semibold py-3 px-6 rounded-lg">
                    Dërgo Rezervimin
                </button>
                <p class="text-xs text-gray-500 text-center">Ose na telefononi: <a href="tel:+{phone_url}" style="color: {primary_color_600};">{escape_html(phone)}</a></p>
            </form>
        </div>
    </div>

    <!-- Contact Section -->
    <section id="contact" class="py-20 px-4 bg-gray-900 text-white">
        <div class="max-w-4xl mx-auto text-center">
            <h2 class="elegant-font text-3xl md:text-4xl font-bold mb-6">
                Kontaktoni Sot
            </h2>
            <p class="text-gray-300 mb-12 text-lg">
                Gati t'ju shërbejmë! Kontaktoni për konsultë falas ose rezervoni termin tuaj.
            </p>
            <div class="grid md:grid-cols-3 gap-6 mb-12">
                <div class="bg-gray-800 p-6 rounded-xl">
                    <i class="fas fa-phone text-3xl mb-4" style="color: {primary_color_400};"></i>
                    <h3 class="font-bold mb-2">Telefon</h3>
                    <a href="tel:+{phone_url}" class="hover:opacity-75" style="color: {primary_color_400};">{escape_html(phone)}</a>
                </div>
                <div class="bg-gray-800 p-6 rounded-xl">
                    <i class="fab fa-whatsapp text-3xl text-green-400 mb-4"></i>
                    <h3 class="font-bold mb-2">WhatsApp</h3>
                    <a href="https://wa.me/{phone_url}" class="text-green-400 hover:text-green-300">Chat Live</a>
                </div>
                <div class="bg-gray-800 p-6 rounded-xl">
                    <i class="fas fa-clock text-3xl mb-4" style="color: {primary_color_400};"></i>
                    <h3 class="font-bold mb-2">Koha e Përgjigjes</h3>
                    <span class="text-gray-300">Minuta</span>
                </div>
            </div>
            <div class="flex flex-col sm:flex-row gap-4 justify-center">
                <button onclick="openBookingModal()" class="cta-button text-white font-semibold py-4 px-10 rounded-full text-lg inline-flex items-center cursor-pointer">
                    <i class="fas fa-calendar mr-2"></i> Rezervoni Tani
                </button>
                <a href="tel:+{phone_url}" class="bg-white bg-opacity-20 hover:bg-opacity-30 text-white font-semibold py-4 px-10 rounded-full text-lg transition duration-300 inline-flex items-center">
                    <i class="fas fa-phone mr-2"></i> Thirrni Tani
                </a>
                <a href="https://wa.me/{phone_url}" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-4 px-10 rounded-full text-lg transition duration-300 inline-flex items-center">
                    <i class="fab fa-whatsapp mr-2"></i> WhatsApp
                </a>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="bg-gray-800 text-gray-400 py-12">
        <div class="max-w-6xl mx-auto px-4">
            <div class="grid md:grid-cols-3 gap-8">
                <div>
                    <h3 class="elegant-font text-xl text-white mb-4">{escape_html(name)}</h3>
                    <p class="text-sm mb-4">{escape_html(config['title_suffix'])}</p>
                    <div class="flex space-x-4">
                        <a href="tel:+{phone_url}" class="text-gray-400 hover:text-white transition">
                            <i class="fas fa-phone"></i>
                        </a>
                        <a href="https://wa.me/{phone_url}" class="text-gray-400 hover:text-white transition">
                            <i class="fab fa-whatsapp"></i>
                        </a>
                        {f'<a href="{social_links.get("facebook", "#")}" target="_blank" class="text-gray-400 hover:text-white transition"><i class="fab fa-facebook"></i></a>' if social_links.get('facebook') else ''}
                        {f'<a href="{social_links.get("instagram", "#")}" target="_blank" class="text-gray-400 hover:text-white transition"><i class="fab fa-instagram"></i></a>' if social_links.get('instagram') else ''}
                    </div>
                </div>
                <div>
                    <h4 class="font-bold text-white mb-4">Shërbime</h4>
                    <ul class="space-y-2 text-sm">
                        <li><a href="#services" class="hover:text-white transition">Shërbimet Tona</a></li>
                        <li><a href="#testimonials" class="hover:text-white transition">Klientët</a></li>
                        <li><a href="#portfolio" class="hover:text-white transition">Portofoli</a></li>
                        <li><a href="#faq" class="hover:text-white transition">FAQ</a></li>
                        <li><a href="#contact" class="hover:text-white transition">Kontakt</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="font-bold text-white mb-4">Info</h4>
                    <ul class="space-y-2 text-sm">
                        <li>{escape_html(address)}</li>
                        <li>{escape_html(city)}, {escape_html(lead.get('country', DEFAULT_COUNTRY))}</li>
                        <li>{escape_html(phone)}</li>
                    </ul>
                </div>
            </div>
            <div class="border-t border-gray-700 mt-8 pt-8 text-center">
                <p class="text-xs text-gray-500">
                    © {datetime.now().year} {escape_html(name)}. Të gjitha të drejtat e rezervuara. | Krijuar me ❤️
                </p>
            </div>
        </div>
    </footer>

    <!-- Live Chat Widget -->
    <div id="chatWidget" class="fixed bottom-6 right-6 z-50">
        <div id="chatButton" onclick="toggleChat()" class="bg-green-500 hover:bg-green-600 text-white rounded-full p-4 shadow-2xl cursor-pointer transition-all duration-300 hover:scale-110" style="width: 60px; height: 60px; display: flex; align-items: center; justify-content: center;">
            <i class="fab fa-whatsapp text-3xl"></i>
        </div>
        <div id="chatBox" class="hidden fixed bottom-24 right-6 bg-white rounded-2xl shadow-2xl w-80 max-h-96 flex flex-col" style="z-index: 51;">
            <div class="bg-green-500 text-white p-4 rounded-t-2xl flex justify-between items-center">
                <div class="flex items-center">
                    <i class="fab fa-whatsapp text-xl mr-2"></i>
                    <span class="font-semibold">Chat Live</span>
                </div>
                <button onclick="toggleChat()" class="text-white hover:text-gray-200">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="p-4 flex-1 overflow-y-auto">
                <p class="text-gray-600 text-sm mb-4">👋 Përshëndetje! Si mund t'ju ndihmojmë?</p>
                <div class="space-y-2">
                    <a href="https://wa.me/{phone_url}?text=Përshëndetje%2C%20dëshiroj%20të%20rezervoj%20një%20termin" target="_blank" class="block bg-gray-100 hover:bg-gray-200 p-3 rounded-lg text-sm transition">
                        📅 Rezervo Termin
                    </a>
                    <a href="https://wa.me/{phone_url}?text=Përshëndetje%2C%20dëshiroj%20të%20mësoj%20më%20shumë%20për%20shërbimet" target="_blank" class="block bg-gray-100 hover:bg-gray-200 p-3 rounded-lg text-sm transition">
                        ℹ️ Informata më shumë
                    </a>
                    <a href="https://wa.me/{phone_url}" target="_blank" class="block bg-gray-100 hover:bg-gray-200 p-3 rounded-lg text-sm transition">
                        💬 Bisedë e lirë
                    </a>
                </div>
            </div>
            <div class="p-4 border-t">
                <a href="https://wa.me/{phone_url}" target="_blank" class="block w-full bg-green-500 hover:bg-green-600 text-white text-center py-2 rounded-lg transition">
                    Hap WhatsApp
                </a>
            </div>
        </div>
    </div>

    <!-- Back to Top Button -->
    <button id="backToTop" onclick="scrollToTop()" class="hidden fixed bottom-6 left-6 bg-gray-800 hover:bg-gray-900 text-white rounded-full p-3 shadow-2xl transition-all duration-300 z-40" style="width: 50px; height: 50px; display: flex; align-items: center; justify-content: center;">
        <i class="fas fa-arrow-up"></i>
    </button>

    <!-- Social Share Buttons - Subtle & Collapsible -->
    <div class="fixed top-1/2 right-0 transform -translate-y-1/2 z-40 hidden md:block" id="socialShareContainer">
        <div class="group relative">
            <!-- Main Share Button -->
            <button onclick="toggleSocialShare()" class="bg-gray-700 hover:bg-gray-800 text-white rounded-l-full p-3 shadow-lg transition-all duration-300 flex items-center" style="width: 50px; height: 50px; justify-content: center;" title="Share">
                <i class="fas fa-share-alt"></i>
            </button>
            <!-- Expanded Share Options -->
            <div id="socialShareMenu" class="hidden absolute right-0 bottom-full mb-2 bg-white rounded-lg shadow-xl p-2 space-y-2 min-w-[180px]">
                <a href="https://www.facebook.com/sharer/sharer.php?u={escape_html(lead.get('website', f'https://{sanitize_name(name)}.com'))}" target="_blank" class="flex items-center space-x-3 px-4 py-2 rounded-lg hover:bg-gray-100 transition text-gray-700">
                    <i class="fab fa-facebook-f text-blue-600 w-5"></i>
                    <span class="text-sm">Share on Facebook</span>
                </a>
                <a href="https://wa.me/?text={escape_html(name)}%20-%20{escape_html(config['description'])}%20{escape_html(lead.get('website', ''))}" target="_blank" class="flex items-center space-x-3 px-4 py-2 rounded-lg hover:bg-gray-100 transition text-gray-700">
                    <i class="fab fa-whatsapp text-green-500 w-5"></i>
                    <span class="text-sm">Share on WhatsApp</span>
                </a>
                <a href="https://twitter.com/intent/tweet?text={escape_html(name)}&url={escape_html(lead.get('website', ''))}" target="_blank" class="flex items-center space-x-3 px-4 py-2 rounded-lg hover:bg-gray-100 transition text-gray-700">
                    <i class="fab fa-twitter text-blue-400 w-5"></i>
                    <span class="text-sm">Share on Twitter</span>
                </a>
                <button onclick="copyLink(); toggleSocialShare();" class="w-full flex items-center space-x-3 px-4 py-2 rounded-lg hover:bg-gray-100 transition text-gray-700">
                    <i class="fas fa-link text-gray-600 w-5"></i>
                    <span class="text-sm">Copy Link</span>
                </button>
            </div>
        </div>
    </div>

    <!-- Review Submission Modal -->
    <div id="reviewModal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-2xl max-w-md w-full p-8 relative max-h-[90vh] overflow-y-auto">
            <button onclick="closeReviewModal()" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
                <i class="fas fa-times text-2xl"></i>
            </button>
            <h3 class="elegant-font text-2xl font-bold mb-6 text-gray-800">Shkruani Vlerësimin Tuaj</h3>
            <form onsubmit="event.preventDefault(); submitReview();" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Emri</label>
                    <input type="text" id="reviewName" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Vlerësimi</label>
                    <div class="flex space-x-2" id="ratingStars">
                        {''.join([f'<i class="far fa-star text-3xl cursor-pointer text-yellow-400 hover:text-yellow-500" onclick="setRating({i+1})" data-rating="{i+1}"></i>' for i in range(5)])}
                    </div>
                    <input type="hidden" id="reviewRating" value="5" required>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Komenti</label>
                    <textarea id="reviewComment" rows="4" required class="w-full px-4 py-2 border border-gray-300 rounded-lg" style="outline: none;"></textarea>
                </div>
                <button type="submit" class="w-full cta-button text-white font-semibold py-3 px-6 rounded-lg">
                    Dërgo Vlerësimin
                </button>
            </form>
        </div>
    </div>

    <!-- Scripts -->
    <script>
        // Smooth scroll and navigation effects
        document.addEventListener('DOMContentLoaded', function() {{
            // Smooth scrolling
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                anchor.addEventListener('click', function (e) {{
                    e.preventDefault();
                    const target = document.querySelector(this.getAttribute('href'));
                    if (target) {{
                        target.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'start'
                        }});
                    }}
                }});
            }});
            
            // Navbar background on scroll
            window.addEventListener('scroll', function() {{
                const navbar = document.getElementById('navbar');
                if (navbar) {{
                    if (window.scrollY > 50) {{
                        navbar.classList.add('shadow-lg');
                    }} else {{
                        navbar.classList.remove('shadow-lg');
                    }}
                }}
            }});
            
            // Animate elements on scroll
            const observerOptions = {{
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            }};
            
            const observer = new IntersectionObserver(function(entries) {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }}
                }});
            }}, observerOptions);
            
            // Observe service cards and testimonials
            document.querySelectorAll('.service-card, #testimonials > div > div').forEach(el => {{
                el.style.opacity = '0';
                el.style.transform = 'translateY(30px)';
                el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                observer.observe(el);
            }});
        }});
        
        // FAQ Toggle Function
        function toggleFaq(index) {{
            const answer = document.getElementById('faq-answer-' + index);
            const icon = document.getElementById('faq-icon-' + index);
            
            if (answer.classList.contains('hidden')) {{
                answer.classList.remove('hidden');
                icon.style.transform = 'rotate(180deg)';
            }} else {{
                answer.classList.add('hidden');
                icon.style.transform = 'rotate(0deg)';
            }}
        }}
        
        // Booking Modal Functions
        function openBookingModal() {{
            document.getElementById('bookingModal').classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeBookingModal() {{
            document.getElementById('bookingModal').classList.add('hidden');
            document.body.style.overflow = 'auto';
        }}
        
        // Close modal on outside click
        document.addEventListener('click', function(e) {{
            const modal = document.getElementById('bookingModal');
            if (e.target === modal) {{
                closeBookingModal();
            }}
            const reviewModal = document.getElementById('reviewModal');
            if (e.target === reviewModal) {{
                closeReviewModal();
            }}
        }});
        
        // Live Chat Widget Functions
        function toggleChat() {{
            const chatBox = document.getElementById('chatBox');
            chatBox.classList.toggle('hidden');
        }}
        
        // Back to Top Button
        const backToTopBtn = document.getElementById('backToTop');
        window.addEventListener('scroll', function() {{
            if (window.scrollY > 300) {{
                backToTopBtn.classList.remove('hidden');
            }} else {{
                backToTopBtn.classList.add('hidden');
            }}
        }});
        
        function scrollToTop() {{
            window.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
        }}
        
        // Social Share Functions
        function toggleSocialShare() {{
            const menu = document.getElementById('socialShareMenu');
            menu.classList.toggle('hidden');
        }}
        
        // Close social share menu when clicking outside
        document.addEventListener('click', function(e) {{
            const container = document.getElementById('socialShareContainer');
            if (container && !container.contains(e.target)) {{
                document.getElementById('socialShareMenu').classList.add('hidden');
            }}
        }});
        
        function copyLink() {{
            const url = window.location.href;
            navigator.clipboard.writeText(url).then(function() {{
                alert('Linku u kopjua!');
            }});
        }}
        
        // Review Modal Functions
        let currentRating = 5;
        function setRating(rating) {{
            currentRating = rating;
            document.getElementById('reviewRating').value = rating;
            const stars = document.querySelectorAll('#ratingStars i');
            stars.forEach((star, index) => {{
                if (index < rating) {{
                    star.classList.remove('far');
                    star.classList.add('fas');
                }} else {{
                    star.classList.remove('fas');
                    star.classList.add('far');
                }}
            }});
        }}
        
        function openReviewModal() {{
            document.getElementById('reviewModal').classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeReviewModal() {{
            document.getElementById('reviewModal').classList.add('hidden');
            document.body.style.overflow = 'auto';
            // Reset form
            document.getElementById('reviewName').value = '';
            document.getElementById('reviewComment').value = '';
            setRating(5);
        }}
        
        function submitReview() {{
            const name = document.getElementById('reviewName').value;
            const rating = document.getElementById('reviewRating').value;
            const comment = document.getElementById('reviewComment').value;
            
            // In a real implementation, this would send to a server
            // For now, we'll show a success message and send via WhatsApp
            const message = 'Vlerësim i ri nga ' + name + ':\\nVlerësim: ' + rating + '/5\\nKomenti: ' + comment;
            const whatsappUrl = 'https://wa.me/{phone_url}?text=' + encodeURIComponent(message);
            
            alert('Faleminderit për vlerësimin! Do t\\'ju kontaktojmë së shpejti.');
            window.open(whatsappUrl, '_blank');
            closeReviewModal();
        }}
        
        // Animated Counter Function
        function animateCounter(element) {{
            const target = parseInt(element.getAttribute('data-target'));
            const hasDecimals = element.getAttribute('data-decimals') === '1';
            const duration = 2000; // 2 seconds
            const increment = target / (duration / 16); // 60fps
            let current = 0;
            
            const timer = setInterval(function() {{
                current += increment;
                if (current >= target) {{
                    current = target;
                    clearInterval(timer);
                }}
                
                if (hasDecimals) {{
                    element.textContent = (current / 10).toFixed(1);
                }} else {{
                    element.textContent = Math.floor(current);
                }}
            }}, 16);
        }}
        
        // Observe counters for animation
        const counterObserver = new IntersectionObserver(function(entries) {{
            entries.forEach(entry => {{
                if (entry.isIntersecting && !entry.target.classList.contains('counted')) {{
                    entry.target.classList.add('counted');
                    animateCounter(entry.target);
                }}
            }});
        }}, {{ threshold: 0.5 }});
        
        // Observe all counters
        document.querySelectorAll('.counter').forEach(counter => {{
            counterObserver.observe(counter);
        }});
    </script>

</body>
</html>'''
    return html

def create_vercel_json(folder_name: str) -> str:
    """Create enhanced vercel.json for deployment"""
    json_content = {
        "name": folder_name,
        "version": 2,
        "builds": [
            {
                "src": "index.html",
                "use": "@vercel/static"
            }
        ],
        "routes": [
            {
                "src": "/(.*)",
                "dest": "/$1"
            }
        ],
        "headers": [
            {
                "source": "/(.*)",
                "headers": [
                    {
                        "key": "Cache-Control",
                        "value": "public, max-age=31536000, immutable"
                    }
                ]
            }
        ]
    }
    return json.dumps(json_content, indent=2)

def load_leads(file_path: str) -> List[Dict[str, Any]]:
    """Load and validate leads from JSON file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Leads file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            leads = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in leads file: {e}") from e
    except Exception as e:
        raise IOError(f"Error reading leads file: {e}") from e
    
    if not isinstance(leads, list):
        raise ValueError("Leads file must contain a JSON array")
    
    if not leads:
        raise ValueError("Leads file is empty")
    
    return leads

def main() -> List[Dict[str, Any]]:
    """Main function to generate professional websites"""
    try:
        # Load leads with error handling
        leads = load_leads(LEADS_FILE)
    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"❌ Error loading leads: {e}", file=sys.stderr)
        sys.exit(1)
    
    base_dir = DEFAULT_BASE_DIR
    results = []
    errors = []
    
    print(f"🚀 Generating {len(leads)} PROFESSIONAL websites...\n")
    
    # Create base directory
    try:
        os.makedirs(base_dir, exist_ok=True)
    except OSError as e:
        print(f"❌ Error creating base directory: {e}", file=sys.stderr)
        sys.exit(1)
    
    for i, lead in enumerate(leads, 1):
        try:
            # Validate lead
            validate_lead(lead)
            
            name = lead['name']
            category = lead.get('category', DEFAULT_CATEGORY)
            
            try:
                folder_name = sanitize_name(name)
            except ValueError as e:
                errors.append(f"Lead {i} ({name}): {e}")
                continue
            
            folder_path = os.path.join(base_dir, folder_name)
            
            print(f"{i}. 🎨 Creating professional website for: {name} ({category})")
            
            try:
                # Create folder
                os.makedirs(folder_path, exist_ok=True)
                
                # Create HTML
                html_content = create_professional_html(lead)
                html_path = os.path.join(folder_path, 'index.html')
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Create vercel.json
                vercel_json = create_vercel_json(folder_name)
                vercel_path = os.path.join(folder_path, 'vercel.json')
                
                with open(vercel_path, 'w', encoding='utf-8') as f:
                    f.write(vercel_json)
                
                results.append({
                    'name': name,
                    'category': category,
                    'folder': folder_name,
                    'path': folder_path,
                    'phone': lead['phone']
                })
                
                print(f"   ✅ Created: {folder_path}")
                print(f"   📱 Phone: {lead['phone']}")
                print(f"   ⭐ Rating: {lead.get('rating', DEFAULT_RATING)}")
                print()
                
            except (OSError, IOError) as e:
                error_msg = f"Lead {i} ({name}): File system error - {e}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")
                continue
            except Exception as e:
                error_msg = f"Lead {i} ({name}): Unexpected error - {e}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")
                continue
                
        except ValueError as e:
            error_msg = f"Lead {i}: Validation error - {e}"
            errors.append(error_msg)
            print(f"   ❌ {error_msg}")
            continue
        except Exception as e:
            error_msg = f"Lead {i}: Unexpected error - {e}"
            errors.append(error_msg)
            print(f"   ❌ {error_msg}")
            continue
    
    # Print summary
    print(f"\n🎉 Successfully created {len(results)} PROFESSIONAL websites!")
    
    if errors:
        print(f"\n⚠️  {len(errors)} error(s) encountered:")
        for error in errors:
            print(f"   • {error}")
    
    # Show summary by category
    if results:
        categories = {}
        for result in results:
            cat = result['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\n📊 Professional websites by category:")
        for cat, count in sorted(categories.items()):
            print(f"   {cat}: {count}")
    
    print(f"\n🚀 ENHANCED FEATURES INCLUDED:")
    print(f"   ✨ Sticky navigation with contact info")
    print(f"   💰 Pricing for all services")
    print(f"   ⭐ Customer testimonials")
    print(f"   🕐 Business hours display")
    print(f"   📍 Location information")
    print(f"   📱 Enhanced mobile experience")
    print(f"   🔍 SEO optimization with schema.org")
    print(f"   🎨 Advanced animations & interactions")
    print(f"   📊 Trust badges & statistics")
    print(f"   🌐 Social proof elements")
    print(f"   📞 Click-to-call & WhatsApp integration")
    print(f"   🚀 Vercel deployment ready")
    print(f"   🛡️  Error handling & validation")
    print(f"   🔒 HTML escaping for security")
    print(f"   🎯 Type hints for better code quality")
    
    print(f"\n🌟 All websites are now PROFESSIONAL GRADE!")
    print(f"📁 Location: {base_dir}")
    print(f"🌐 Ready for deployment and client presentation!")
    
    return results

if __name__ == '__main__':
    main()
