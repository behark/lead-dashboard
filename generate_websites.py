#!/usr/bin/env python3
import json
import os
import re
import subprocess

def sanitize_name(name):
    """Convert business name to folder-friendly name"""
    # Remove special characters, keep only alphanumeric and spaces
    name = re.sub(r'[^\w\s-]', '', name)
    # Replace spaces and multiple dashes with single dash
    name = re.sub(r'[\s_]+', '-', name)
    # Remove multiple dashes
    name = re.sub(r'-+', '-', name)
    # Convert to lowercase
    return name.lower().strip('-')

def format_phone_for_url(phone):
    """Convert phone like '044 406 405' to '38344406405'"""
    # Remove spaces and add country code
    digits = phone.replace(' ', '').replace('-', '')
    if digits.startswith('0'):
        return '383' + digits[1:]
    return digits

def create_barbershop_html(lead):
    """Create HTML for a barbershop"""
    name = lead['name']
    phone = lead['phone']
    phone_url = format_phone_for_url(phone)
    rating = lead.get('rating', 5.0)
    city = lead.get('city', 'Pristina')
    
    html = f'''<!DOCTYPE html>
<html lang="sq">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - Stilist Profesional i Flokëve</title>
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
            background: linear-gradient(135deg, rgba(75, 0, 130, 0.75) 0%, rgba(138, 43, 226, 0.65) 50%, rgba(75, 0, 130, 0.75) 100%);
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
    <section class="relative h-screen flex items-center justify-center bg-cover bg-center" style="background-image: url('https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1200&q=80');">
        <div class="hero-overlay absolute inset-0"></div>
        <div class="relative z-10 text-center px-4 max-w-5xl mx-auto">
            <h1 class="elegant-font text-5xl md:text-7xl font-bold text-white mb-6 drop-shadow-2xl">
                {name}
            </h1>
            <p class="text-2xl md:text-3xl text-white mb-8 font-light tracking-wide drop-shadow-lg">
                Stilist Profesional i Flokëve
            </p>
            <p class="text-lg md:text-xl text-gray-100 mb-10 max-w-2xl mx-auto italic">
                Transformoni stilin tuaj me ekspertët tanë
            </p>
            <a href="#services" class="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white font-semibold py-4 px-10 rounded-full text-lg transition duration-300 shadow-2xl inline-block transform hover:scale-105">
                <i class="fas fa-scissors mr-2"></i> Shikoni Shërbimet Tona
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
                    Ne ofrojmë shërbime profesionale për të krijuar stilin tuaj të përsosur
                </p>
            </div>
            
            <div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                <!-- Haircut Service -->
                <div class="service-card bg-white p-8 rounded-2xl shadow-xl border-t-4 border-purple-500">
                    <div class="text-center mb-6">
                        <div class="w-20 h-20 mx-auto bg-gradient-to-br from-purple-100 to-purple-200 rounded-full flex items-center justify-center mb-4">
                            <i class="fas fa-cut text-purple-600 text-3xl"></i>
                        </div>
                        <h3 class="elegant-font text-xl font-bold text-gray-800 mb-3">
                            Prerje Flokësh
                        </h3>
                    </div>
                    <p class="text-gray-600 text-center text-base leading-relaxed mb-4">
                        Prerje moderne dhe klasike për çdo stil
                    </p>
                    <ul class="text-gray-600 space-y-2 text-sm">
                        <li><i class="fas fa-check text-purple-500 mr-2"></i> Prerje për meshkuj</li>
                        <li><i class="fas fa-check text-purple-500 mr-2"></i> Prerje për femra</li>
                        <li><i class="fas fa-check text-purple-500 mr-2"></i> Stilime moderne</li>
                    </ul>
                </div>

                <!-- Hair Coloring Service -->
                <div class="service-card bg-white p-8 rounded-2xl shadow-xl border-t-4 border-pink-500">
                    <div class="text-center mb-6">
                        <div class="w-20 h-20 mx-auto bg-gradient-to-br from-pink-100 to-pink-200 rounded-full flex items-center justify-center mb-4">
                            <i class="fas fa-paint-brush text-pink-600 text-3xl"></i>
                        </div>
                        <h3 class="elegant-font text-xl font-bold text-gray-800 mb-3">
                            Ngjyrosje Flokësh
                        </h3>
                    </div>
                    <p class="text-gray-600 text-center text-base leading-relaxed mb-4">
                        Ngjyra moderne dhe trendi për një pamje të re
                    </p>
                    <ul class="text-gray-600 space-y-2 text-sm">
                        <li><i class="fas fa-check text-pink-500 mr-2"></i> Ngjyrosje plotësuese</li>
                        <li><i class="fas fa-check text-pink-500 mr-2"></i> Highlights & Balayage</li>
                        <li><i class="fas fa-check text-pink-500 mr-2"></i> Ngjyra trendi</li>
                    </ul>
                </div>

                <!-- Hair Styling Service -->
                <div class="service-card bg-white p-8 rounded-2xl shadow-xl border-t-4 border-indigo-500">
                    <div class="text-center mb-6">
                        <div class="w-20 h-20 mx-auto bg-gradient-to-br from-indigo-100 to-indigo-200 rounded-full flex items-center justify-center mb-4">
                            <i class="fas fa-magic text-indigo-600 text-3xl"></i>
                        </div>
                        <h3 class="elegant-font text-xl font-bold text-gray-800 mb-3">
                            Stilime Speciale
                        </h3>
                    </div>
                    <p class="text-gray-600 text-center text-base leading-relaxed mb-4">
                        Stilime profesionale për evente dhe dasma
                    </p>
                    <ul class="text-gray-600 space-y-2 text-sm">
                        <li><i class="fas fa-check text-indigo-500 mr-2"></i> Stilime për dasma</li>
                        <li><i class="fas fa-check text-indigo-500 mr-2"></i> Stilime për evente</li>
                        <li><i class="fas fa-check text-indigo-500 mr-2"></i> Konsultime stili</li>
                    </ul>
                </div>
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
                    <div class="flex-shrink-0 w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-award text-purple-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Ekspertizë Profesionale</h3>
                        <p class="text-gray-600">Stilistë me vite përvojë në industri</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-star text-purple-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Vlerësim {rating}⭐</h3>
                        <p class="text-gray-600">Klientë të kënaqur dhe vlerësime perfekte</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-heart text-purple-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Kujdes Personalizuar</h3>
                        <p class="text-gray-600">Çdo klient merr vëmendje dhe kujdes individual</p>
                    </div>
                </div>
                <div class="flex items-start space-x-4">
                    <div class="flex-shrink-0 w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                        <i class="fas fa-clock text-purple-600 text-xl"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-xl mb-2 text-gray-800">Orar Fleksibël</h3>
                        <p class="text-gray-600">Rezervime të lehta dhe orar që ju përshtatet</p>
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
                Rezervoni termin tuaj dhe transformoni stilin tuaj sot
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
            <p class="text-sm mb-4">Stilist Profesional i Flokëve</p>
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
        folder_name = sanitize_name(name)
        folder_path = os.path.join(base_dir, folder_name)
        
        print(f"{i}. Creating website for: {name}")
        
        # Create folder
        os.makedirs(folder_path, exist_ok=True)
        
        # Create HTML
        html_content = create_barbershop_html(lead)
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
            'folder': folder_name,
            'path': folder_path,
            'phone': lead['phone']
        })
        
        print(f"   ✓ Created: {folder_path}\n")
    
    print(f"\n✅ Successfully created {len(results)} websites!")
    print("\nReady to deploy. Would you like to deploy all to Vercel now?")
    
    return results

if __name__ == '__main__':
    main()
