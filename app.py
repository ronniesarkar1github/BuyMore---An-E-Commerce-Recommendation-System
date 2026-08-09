from flask import Flask, session
from flask_cors import CORS
from dotenv import load_dotenv
from core.database import init_db
from routes.user import user_bp
from routes.admin import admin_bp
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    # We use a persistent secret key from .env to maintain sessions across restarts.
    app.secret_key = os.getenv("SECRET_KEY", "fallback_dev_key_if_none")

    
    # Initialize Database
    init_db()

    # Warm up recommendation model (new productrecommendation.py)
    try:
        from productrecommendation import ensure_recommendation_model_loaded
        ok = ensure_recommendation_model_loaded()
        if not ok:
            print("⚠️ Recommendation model not loaded (no products or DB unavailable).")
    except Exception as e:
        print(f"⚠️ Recommendation model warmup failed: {e}")
    
    # Enable CORS
    CORS(app)
    
    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app

app = create_app()

if __name__ == "__main__":
    # Get port from environment or default to 5000
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
