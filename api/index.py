from flask import Flask, render_template_string, request, redirect, url_for
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Login - Lead Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; }
        .card { border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
    </style>
</head>
<body>
    <div class="container">
        <div class="card mx-auto" style="max-width: 400px;">
            <div class="card-body p-5">
                <h3 class="text-center mb-4">Lead Dashboard CRM</h3>
                <div class="alert alert-info">
                    <strong>Vercel Demo</strong><br>
                    For full functionality, run locally:
                    <pre class="mt-2 mb-0">git clone https://github.com/behark/lead-dashboard
cd lead-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run</pre>
                </div>
                <a href="/portfolio" class="btn btn-primary w-100 mt-3">View Portfolio Page</a>
                <a href="https://github.com/behark/lead-dashboard" class="btn btn-outline-dark w-100 mt-2">GitHub Repo</a>
            </div>
        </div>
    </div>
</body>
</html>
'''

PORTFOLIO_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional Web Design for Local Businesses</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 0; }
        nav { max-width: 1200px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: space-between; align-items: center; }
        nav h1 { font-size: 1.5rem; }
        nav a { color: white; text-decoration: none; margin: 0 1rem; }
        .hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 6rem 2rem; text-align: center; }
        .hero h2 { font-size: 3rem; margin-bottom: 1rem; }
        .hero p { font-size: 1.3rem; margin-bottom: 2rem; opacity: 0.9; }
        .section { max-width: 1200px; margin: 4rem auto; padding: 0 2rem; }
        .section h2 { font-size: 2.5rem; margin-bottom: 2rem; text-align: center; }
        .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; }
        .feature-card { text-align: center; padding: 2rem; background: #f8f9fa; border-radius: 10px; }
        .feature-card h3 { font-size: 2rem; margin: 1rem 0; color: #667eea; }
        .pricing-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; }
        .price-card { border: 2px solid #e0e0e0; padding: 2rem; border-radius: 10px; text-align: center; }
        .price-card.featured { border-color: #667eea; background: #f0f4ff; transform: scale(1.05); }
        .price { font-size: 2.5rem; color: #667eea; margin: 1rem 0; font-weight: bold; }
        .price-card ul { list-style: none; text-align: left; margin: 1.5rem 0; }
        .price-card li { padding: 0.5rem 0; border-bottom: 1px solid #e0e0e0; }
        .price-card li:before { content: "✓ "; color: #667eea; font-weight: bold; }
        .cta { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4rem 2rem; text-align: center; border-radius: 10px; margin: 3rem auto; max-width: 1200px; }
        .cta h2 { margin-bottom: 1rem; }
        .cta button { background: white; color: #667eea; border: none; padding: 1rem 2.5rem; font-size: 1.1rem; border-radius: 5px; cursor: pointer; font-weight: bold; margin-top: 1rem; }
        footer { background: #333; color: white; text-align: center; padding: 2rem; margin-top: 3rem; }
        @media (max-width: 768px) { .hero h2 { font-size: 2rem; } .price-card.featured { transform: scale(1); } }
    </style>
</head>
<body>
    <header><nav><h1>Behar Kabashi - Web Design</h1><div><a href="#pricing">Pricing</a><a href="#contact">Contact</a></div></nav></header>
    <section class="hero">
        <h2>Professional Websites for Local Businesses</h2>
        <p>Get found on Google. Attract more customers. Built in 5-7 days.</p>
    </section>
    <section class="section">
        <h2>What Can a Website Do For Your Business?</h2>
        <div class="features">
            <div class="feature-card"><div style="font-size: 3rem;">🔍</div><h3>Get Found</h3><p>Show up when customers search</p></div>
            <div class="feature-card"><div style="font-size: 3rem;">📞</div><h3>Capture Leads</h3><p>Get inquiries 24/7</p></div>
            <div class="feature-card"><div style="font-size: 3rem;">💰</div><h3>Grow Revenue</h3><p>Turn visitors into customers</p></div>
        </div>
    </section>
    <section class="section" id="pricing">
        <h2>Simple Pricing</h2>
        <div class="pricing-cards">
            <div class="price-card"><h3>STARTER</h3><div class="price">€250</div><ul><li>1 page</li><li>Contact form</li><li>Mobile-friendly</li></ul></div>
            <div class="price-card featured"><h3>PROFESSIONAL ⭐</h3><div class="price">€500</div><p style="color: #667eea; font-weight: bold;">MOST POPULAR</p><ul><li>5 pages</li><li>Photo gallery</li><li>Google integration</li><li>1 month support</li></ul></div>
            <div class="price-card"><h3>PREMIUM</h3><div class="price">€1,000</div><ul><li>Everything + </li><li>Online booking</li><li>Payments</li><li>3 months support</li></ul></div>
        </div>
    </section>
    <section class="cta" id="contact">
        <h2>Ready to Get More Customers?</h2>
        <p>Your business deserves a professional online presence.</p>
        <button onclick="window.open('https://wa.me/38344123456?text=Hi! I saw your portfolio and I am interested.', '_blank')">Contact on WhatsApp</button>
    </section>
    <footer><p>© 2025 Behar Kabashi - Professional Web Design</p></footer>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/login')
def login():
    return render_template_string(LOGIN_HTML)

@app.route('/portfolio')
def portfolio():
    return render_template_string(PORTFOLIO_HTML)
