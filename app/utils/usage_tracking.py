"""
Usage tracking middleware for API billing and analytics.

Logs all API requests to the APIUsageLog model for organization billing,
usage analytics, and monitoring.
"""

import logging
from datetime import datetime
from flask import request, g
from flask_login import current_user
from database import db
from models import APIUsageLog

logger = logging.getLogger(__name__)


def init_usage_tracking(app):
    """
    Initialize usage tracking middleware.

    This registers before_request and after_request handlers to track
    all API requests for billing and analytics.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def before_request_tracking():
        """
        Store request start time and prepare for tracking.
        """
        g.request_start_time = datetime.utcnow()
        g.openai_tokens_used = 0  # Can be set by endpoints that use OpenAI


    @app.after_request
    def after_request_tracking(response):
        """
        Log API usage after each request.

        Only tracks requests to /api/* endpoints.
        Logs organization_id, user_id, endpoint, method, status, and OpenAI tokens.
        """
        try:
            # Only track API endpoints
            if not request.path.startswith('/api/'):
                return response

            # Skip health check and index endpoints
            if request.path in ['/api/v1/', '/api/v1/health']:
                return response

            # Get organization and user info
            organization_id = None
            user_id = None

            if current_user and current_user.is_authenticated:
                user_id = current_user.id

                # Try to get organization from various sources
                if hasattr(g, 'current_organization') and g.current_organization:
                    organization_id = g.current_organization.id
                elif hasattr(current_user, 'default_organization_id') and current_user.default_organization_id:
                    organization_id = current_user.default_organization_id

            # Skip logging if no user (shouldn't happen for authenticated endpoints)
            if not user_id:
                return response

            # Get OpenAI tokens used (set by grading endpoint)
            openai_tokens = getattr(g, 'openai_tokens_used', 0)

            # Log the request
            try:
                usage_log = APIUsageLog(
                    organization_id=organization_id,
                    user_id=user_id,
                    endpoint=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    timestamp=getattr(g, 'request_start_time', datetime.utcnow()),
                    openai_tokens_used=openai_tokens
                )
                db.session.add(usage_log)
                db.session.commit()

                # Log significant requests
                if openai_tokens > 0:
                    logger.info(f"API usage logged: {request.method} {request.path} ({response.status_code}) - {openai_tokens} tokens")

            except Exception as log_error:
                # Don't let logging errors break the response
                logger.error(f"Failed to log API usage: {log_error}")
                db.session.rollback()

        except Exception as e:
            # Don't let middleware errors break the application
            logger.error(f"Error in usage tracking middleware: {e}")

        return response


def track_openai_tokens(token_count):
    """
    Set the OpenAI token count for the current request.

    This should be called by endpoints that use OpenAI API to track
    token usage for billing purposes.

    Args:
        token_count: Number of tokens used in the request
    """
    g.openai_tokens_used = token_count
    logger.debug(f"Tracked {token_count} OpenAI tokens for current request")
