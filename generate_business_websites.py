#!/usr/bin/env python3
import json
import os
import re

def sanitize_name(name):
    """Convert business name to folder-friendly name"""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'-+', '-', name)
    return name.lower().strip('-')

def format_phone_for_url(phone):
    """Convert phone like '044 406 405' to '38344406405'"""
    digits = phone.replace(' ', '').replace('-', '')
    if digits.startswith('0'):
        return '383' + digits[1:]
    return digits

def get_business_config(category):
    """Get configuration based on business category"""
    configs = {
        'dentist': {
            'title_suffix': 'Klinike Dentare',
            'subtitle': 'Shërbime Dentare Profesionale',
            'hero_image': 'https://images.unsplash.com/photo-1600988360767-2ab82995279c?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Kontroll Dentar', 'desc': 'Ekzaminim i plotë dentar', 'icon': 'fa-search'},
                {'name': 'Pastrim Dental', 'desc': 'Pastrim profesional dhëmbësh', 'icon': 'fa-tooth'},
                {'name': 'Trajtament Kanali', 'desc': 'Trajtime specializu kanali', 'icon': 'fa-bolt'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(59, 130, 246, 0.75) 0%, rgba(147, 51, 234, 0.65) 50%, rgba(59, 130, 246, 0.75) 100%)',
            'colors': {'primary': 'blue', 'secondary': 'purple'}
        },
        'restaurant': {
            'title_suffix': 'Restorant',
            'subtitle': 'Ushqim Tradicional & Modern',
            'hero_image': 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Gatim Tradicional', 'desc': 'Gatime autentike shqiptare', 'icon': 'fa-utensils'},
                {'name': 'Menu Ndërkombëtare', 'desc': 'Specialitete nga bota', 'icon': 'fa-globe'},
                {'name': 'Organizime Evente', 'desc': 'Dasma & festime private', 'icon': 'fa-glass-cheers'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(239, 68, 68, 0.75) 0%, rgba(249, 115, 22, 0.65) 50%, rgba(239, 68, 68, 0.75) 100%)',
            'colors': {'primary': 'red', 'secondary': 'orange'}
        },
        'salon': {
            'title_suffix': 'Salon Bukurosie',
            'subtitle': 'Shërbime Profesionale të Bukurisë',
            'hero_image': 'https://images.unsplash.com/photo-1560066984-76d77438c60b?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Trajtime Flokësh', 'desc': 'Stilim dhe kujdes flokësh', 'icon': 'fa-cut'},
                {'name': 'Makeup Profesional', 'desc': 'Makeup për evente dhe dasma', 'icon': 'fa-paint-brush'},
                {'name': 'Kujdes Lëkure', 'desc': 'Trajtime profesional për lëkurë', 'icon': 'fa-spa'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(236, 72, 153, 0.75) 0%, rgba(219, 39, 119, 0.65) 50%, rgba(236, 72, 153, 0.75) 100%)',
            'colors': {'primary': 'pink', 'secondary': 'rose'}
        },
        'barber': {
            'title_suffix': 'Barber Shop',
            'subtitle': 'Stilist Profesional i Flokëve',
            'hero_image': 'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Prerje Flokësh', 'desc': 'Prerje moderne dhe klasike', 'icon': 'fa-cut'},
                {'name': 'Ngjyrosje Flokësh', 'desc': 'Ngjyra moderne dhe trendi', 'icon': 'fa-paint-brush'},
                {'name': 'Stilime Speciale', 'desc': 'Stilime për evente dhe dasma', 'icon': 'fa-magic'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(75, 0, 130, 0.75) 0%, rgba(138, 43, 226, 0.65) 50%, rgba(75, 0, 130, 0.75) 100%)',
            'colors': {'primary': 'purple', 'secondary': 'indigo'}
        },
        'gym': {
            'title_suffix': 'Fitness Center',
            'subtitle': 'Shëndet & Formë Fizike',
            'hero_image': 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Trajtim Personale', 'desc': 'Trajner personal për rezultat', 'icon': 'fa-dumbbell'},
                {'name': 'Klasa Grupi', 'desc': 'Yoga, aerobik, dhe shumë më shumë', 'icon': 'fa-users'},
                {'name': 'Plan Ushqimi', 'desc': 'Këshilla nutritioniste', 'icon': 'fa-apple-alt'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(34, 197, 94, 0.75) 0%, rgba(16, 185, 129, 0.65) 50%, rgba(34, 197, 94, 0.75) 100%)',
            'colors': {'primary': 'green', 'secondary': 'emerald'}
        },
        'cafe': {
            'title_suffix': 'Café',
            'subtitle': 'Kafë & Atmosferë Relaksuese',
            'hero_image': 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?auto=format&fit=crop&w=1200&q=80',
            'services': [
                {'name': 'Kafë Specialitet', 'desc': 'Kafë e freskët dhe specialitete', 'icon': 'fa-coffee'},
                {'name': 'Deserte & Ëmbëlsira', 'desc': 'Ëmbëlsira të freskëta ditore', 'icon': 'fa-birthday-cake'},
                {'name': 'Work Space', 'desc': 'Wi-Fi dhe ambient për punë', 'icon': 'fa-wifi'}
            ],
            'gradient': 'linear-gradient(135deg, rgba(245, 158, 11, 0.75) 0%, rgba(217, 119, 6, 0.65) 50%, rgba(245, 158, 11, 0.75) 100%)',
            'colors': {'primary': 'amber', 'secondary': 'yellow'}
        }
    }
    
    return configs.get(category, configs['barber'])  # Default to barber config

def create_business_html(lead):
    """Create HTML for any business type"""
    name = lead['name']
    phone = lead['phone']
    phone_url = format_phone_for_url(phone)
    rating = lead.get('rating', 5.0)
    city = lead.get('city', 'Pristina')
    category = lead.get('category', 'barber')
    
    config = get_business_config(category)
    colors = config['colors']
    
    # Generate service cards HTML
    service_cards = ""
    for service in config['services']:
        service_cards += f'''
                <div class="service-card bg-white p-8 rounded-2xl shadow-xl border-t-4 border-{colors["primary"]}-500">
                    <div class="text-center mb-6">
                        <div class="w-20 h-20 mx-auto bg-gradient-to-br from-{colors["primary"]}-100 to-{colors["primary"]}-200 rounded-full flex items-center justify-center mb-4">
                            <i class="fas {service['icon']} text-{colors["primary"]}-600 text-3xl"></i>
                        </div>
                        <h3 class="elegant-font text-xl font-bold text-gray-800 mb-3">
                            {service['name']}
                        </h3>
                    </div>
                    <p class="text-gray-600 text-center text-base leading-relaxed mb-4">
                        {service['desc']}
                    </p>
                </div>'''
    
    html = f'''<!DOCTYPE html>
<html lang="sq">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - {config['title_suffix']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Poppins:wght@300;400;500;600&display=swap');
        
        body {{
            font-family: 'Poppins', sans-serif;
        }}
        
        .elegant-font {{
            font-family: 'Playfair Display', serif;
        }}
        
        .hero-overlay {{
            background: {config['gradient']};
        }}
        
        .service-card {{
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .service-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
        }}
        
        .gradient-text {{
            background: linear-gradient(135deg, #4B0082 0%, #8A2BE2 50%, #9370DB 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
    </style>
</head>
<body class="bg-gray-50 text-gray-900">

    <!-- Hero Section -->
    <section class="relative h-screen flex items-center justify-center bg-cover bg-center" style="background-image: url('{config['hero_image']}');">
        <div class="hero-overlay absolute inset-0"></div>
        <div class="relative z-10 text-center px-4 max-w-5xl mx-auto">
            <h1 class="elegant-font text-5xl md:text-7xl font-bold text-white mb-6 drop-shadow-2xl">
                {name}
            </h1>
            <p class="text-2xl md:text-3xl text-white mb-8 font-light tracking-wide drop-shadow-lg">
                {config['subtitle']}
            </p>
            <p class="text-lg md:text-xl text-gray-100 mb-10 max-w-2xl mx-auto italic">
                Shërbime profesionalë në {city}
            </p>
            <a href="#services" class="bg-gradient-to-r from-{colors['primary']}-600 to-{colors['primary']}-700 hover:from-{colors['primary']}-700 hover:to-{colors['primary']}-800 text-white font-semibold py-4 px-10 rounded-full text-lg transition duration-300 shadow-2xl inline-block transform hover:scale-105">
                <i class="fas fa-star mr-2"></i> Shikoni Shërbimet Tona
            </a>
        </div>
        <div class="absolute bottom-10 left-1/2 transform -translate-x-1/2 animate-bounce">
            <i class="fas fa-chevron-down text-white text-2xl"></i>
        </div>
    </section>

    <!-- Services Section -->
    <section id="services" class="py-20 px-4 bg-gradient-to-b from-gray-50 to-white">
        <div class="max-w-6xl mx-auto">
            <div class="text-center mb-16">
                <h2 class="elegant-font text-4xl md:text-5xl font-bold mb-4 gradient-text">
                    Shërbimet Tona
                </h2>
                <p class="text-gray-600 text-lg max-w-2xl mx-auto">
                    Ne ofrojmë shërbime profesionalë për të krijuar përvojën tuaj të përsosur
                </p>
            </div>
            
            <div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                {service_cards}
            </div>
        </div>
    </section>

    <!-- Why Choose Us Section -->
    <section class="py-16 px-4 bg-white">
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-12">
                <h2 class="elegant-font text-3xl md:text-4xl font-bold mb-4 gradient-text">
                    Pse Na Zgjedhni?
                </h2>
            </div>
            <div class="grid md:grid-cols-2 gap-8">
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-{colors['primary']}-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-award text-{colors['primary']}-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Ekspertizë Profesionale</h3>
                        <p class="text-gray-600">Staf me vite përvojë në industri</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-{colors['primary']}-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-star text-{colors['primary']}-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Vlerësim {rating}⭐</h3>
                        <p class="text-gray-600">Klientë të kënaqur dhe vlerësime të shkëlqyera</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-{colors['primary']}-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-heart text-{colors['primary']}-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Kujdes Personalizuar</h3>
                        <p class="text-gray-600">Çdo klient merr vëmendje të plotë</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-{colors['primary']}-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-clock text-{colors['primary']}-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Orar Fleksibël</h3>
                        <p class="text-gray-600">Rezervime të lehta dhe orar i përshtatshëm</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Contact Section -->
    <section class="py-16 px-4 bg-gray-900 text-white">
        <div class="max-w-4xl mx-auto text-center">
            <h2 class="elegant-font text-3xl md:text-4xl font-bold mb-6">
                Na Kontaktoni
            </h2>
            <p class="text-gray-300 mb-8 text-lg">
                Rezervoni termin tuaj dhe shijoni shërbimet tona sot
            </p>
            <div class="flex flex-col md:flex-row gap-4 justify-center items-center">
                <a href="tel:+{phone_url}" class="bg-white text-gray-900 hover:bg-gray-100 font-semibold py-3 px-8 rounded-full transition duration-300 inline-flex items-center">
                    <i class="fas fa-phone mr-2"></i> {phone}
                </a>
                <a href="https://wa.me/{phone_url}" class="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-8 rounded-full transition duration-300 inline-flex items-center">
                    <i class="fab fa-whatsapp mr-2"></i> WhatsApp
                </a>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="bg-gray-800 text-gray-400 py-10 text-center">
        <div class="max-w-4xl mx-auto px-4">
            <p class="elegant-font text-xl text-white mb-2">{name}</p>
            <p class="text-sm mb-4">{config['title_suffix']}</p>
            <p class="text-xs text-gray-500">
                © 2024 {name}. Të gjitha të drejtat e rezervuara.
            </p>
        </div>
    </footer>

    <script>
        // Smooth scroll for anchor links
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
    </script>

</body>
</html>'''
    return html

def create_vercel_json(folder_name):
    """Create vercel.json for deployment"""
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
        ]
    }
    return json.dumps(json_content, indent=2)

def main():
    # Read selected leads
    with open('selected_leads.json', 'r') as f:
        leads = json.load(f)
    
    base_dir = '/home/behar/Desktop'
    results = []
    
    print(f"Processing {len(leads)} leads...\n")
    
    for i, lead in enumerate(leads, 1):
        name = lead['name']
        category = lead.get('category', 'business')
        folder_name = sanitize_name(name)
        folder_path = os.path.join(base_dir, folder_name)
        
        print(f"{i}. Creating website for: {name} ({category})")
        
        # Create folder
        os.makedirs(folder_path, exist_ok=True)
        
        # Create HTML
        html_content = create_business_html(lead)
        html_path = os.path.join(folder_path, 'index.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Create vercel.json
        vercel_json = create_vercel_json(folder_name)
        vercel_path = os.path.join(folder_path, 'vercel.json')
        with open(vercel_path, 'w') as f:
            f.write(vercel_json)
        
        results.append({
            'name': name,
            'category': category,
            'folder': folder_name,
            'path': folder_path,
            'phone': lead['phone']
        })
        
        print(f"   ✓ Created: {folder_path}\n")
    
    print(f"\n✅ Successfully created {len(results)} websites!")
    
    # Show summary by category
    categories = {}
    for result in results:
        cat = result['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print(f"\n📊 Websites by category:")
    for cat, count in categories.items():
        print(f"   {cat}: {count}")
    
    print(f"\n🚀 Ready to deploy! All websites include:")
    print(f"   • Responsive design")
    print(f"   • Click-to-call & WhatsApp buttons")
    print(f"   • Professional imagery")
    print(f"   • SEO optimization")
    print(f"   • Vercel deployment ready")
    
    return results

if __name__ == '__main__':
    main()
