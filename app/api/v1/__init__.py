"""
QuizMarker API v1 Blueprint

This module defines the API v1 blueprint and registers all API routes.
All API routes are prefixed with /api/v1
"""

from flask import Blueprint

# Create the API v1 blueprint
api_v1_bp = Blueprint('api_v1', __name__)

# Import routes after blueprint creation to avoid circular imports
from app.api.v1 import auth, quizzes, upload, grading, standards, organizations, jobs

# Register sub-blueprints or routes
# Routes are automatically registered when imported above


@api_v1_bp.route('/')
def index():
    """API v1 index endpoint"""
    return {
        'success': True,
        'message': 'QuizMarker API v1',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/v1/auth/*',
            'quizzes': '/api/v1/quizzes/*',
            'organizations': '/api/v1/organizations/*',
            'jobs': '/api/v1/jobs/*',
            'upload': '/api/v1/upload',
            'grade': '/api/v1/grade',
            'standards': '/api/v1/standards'
        }
    }


@api_v1_bp.route('/health')
def health():
    """Health check endpoint"""
    return {
        'success': True,
        'status': 'healthy',
        'message': 'API is running'
    }
