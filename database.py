import os
import logging
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize SQLAlchemy
db = SQLAlchemy()

def init_db(app):
    """Initialize the database with the application"""
    # Configure the database connection
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        logging.info(f"Using database URL: {DATABASE_URL}")
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
    else:
        logging.error("DATABASE_URL environment variable is not set")
        # Fallback to SQLite for development (not recommended for production)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz_app.db"
    
    # Initialize the db with the app
    db.init_app(app)
    
    # Create all tables
    with app.app_context():
        db.create_all()
        logging.info("Database tables created or verified")
    
    return db