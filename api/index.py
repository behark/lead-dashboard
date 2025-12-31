import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Disable scheduler for serverless
os.environ['SCHEDULER_DISABLED'] = 'true'

from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from config import config
from models import db, User

login_manager = LoginManager()

def create_serverless_app():
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config['production'])
    app.config['SCHEDULER_API_ENABLED'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.analytics import analytics_bp
    from routes.templates_routes import templates_bp
    from routes.webhooks import webhooks_bp
    from routes.bulk import bulk_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(bulk_bp)
    
    @app.route('/portfolio')
    def portfolio():
        return render_template('portfolio.html')
    
    with app.app_context():
        db.create_all()
    
    return app

app = create_serverless_app()
