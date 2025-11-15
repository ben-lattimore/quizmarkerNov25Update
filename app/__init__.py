"""
QuizMarker Flask Application Factory

This module implements the Flask app factory pattern for better testability,
configuration management, and blueprint organization.
"""

import os
import logging
import json
from flask import Flask
from flask_login import LoginManager
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import database instance
from database import db

# Initialize Flask-Login
login_manager = LoginManager()


def create_app(config_name=None):
    """
    Flask application factory

    Args:
        config_name: Configuration name (development, production, testing)

    Returns:
        Configured Flask application instance
    """
    # Create Flask app instance
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')

    # Load configuration
    configure_app(app, config_name)

    # Initialize extensions
    initialize_extensions(app)

    # Register blueprints
    register_blueprints(app)

    # Register template filters
    register_template_filters(app)

    # Create upload folder if it doesn't exist
    upload_folder = app.config.get('UPLOAD_FOLDER', '/tmp/image_uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    logger.info(f"Flask app created successfully (Environment: {config_name or 'default'})")

    return app


def configure_app(app, config_name=None):
    """Configure the Flask application"""
    # Basic configuration
    app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24).hex())

    # Upload configuration
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/tmp/image_uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}

    # Reference PDF directory
    app.config['REFERENCE_PDF_DIR'] = 'attached_assets'

    # Database configuration
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        logger.info(f"Using database URL from environment")
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
    else:
        logger.warning("DATABASE_URL not set, falling back to SQLite")
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz_app.db"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # JWT Configuration (for Phase 2)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.secret_key)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # 1 hour
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000))  # 30 days

    # CORS Configuration
    app.config['CORS_ORIGINS'] = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')

    # Environment-specific configuration
    flask_env = os.environ.get('FLASK_ENV', 'development')

    if config_name == 'testing' or flask_env == 'testing':
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    elif config_name == 'production' or flask_env == 'production':
        app.config['DEBUG'] = False
        # Add production-specific settings
    else:
        # Development settings
        app.config['DEBUG'] = True

    logger.info(f"App configured for {flask_env} environment")


def initialize_extensions(app):
    """Initialize Flask extensions"""
    # Initialize database
    db.init_app(app)

    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created or verified")

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'login'  # Will be updated to blueprint route later

    # Configure Flask-Login to return JSON for API routes instead of redirecting
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify
        # Check if this is an API request
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'code': 'UNAUTHORIZED'
            }), 401
        else:
            # For non-API routes, redirect to login
            from flask import redirect, url_for
            return redirect(url_for('login'))

    # Set up user loader for Flask-Login
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Initialize CORS
    CORS(app,
         resources={r"/api/*": {"origins": app.config['CORS_ORIGINS']}},
         supports_credentials=True)

    logger.info("Extensions initialized successfully")


def register_blueprints(app):
    """Register Flask blueprints"""
    # Register API v1 Blueprint
    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')

    logger.info("Blueprints registered successfully (API v1)")


def register_template_filters(app):
    """Register custom Jinja2 template filters"""
    @app.template_filter('from_json')
    def from_json(value):
        """Convert a JSON string to Python objects"""
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}

    logger.info("Template filters registered successfully")


# Helper function to check allowed file extensions
def allowed_file(filename, app=None):
    """Check if a file extension is allowed"""
    if app is None:
        from flask import current_app
        app = current_app

    allowed_extensions = app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
