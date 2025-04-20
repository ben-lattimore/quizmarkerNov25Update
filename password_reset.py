import os
import logging
import secrets
import time
from datetime import datetime, timedelta
from app import db
from models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store tokens in memory with expiration time
# In a production environment, these would be stored in a database
reset_tokens = {}  # Format: {token: {'user_id': user_id, 'expires': timestamp}}

def generate_reset_token(user):
    """
    Generate a secure token for password reset
    
    Args:
        user (User): User object for whom to generate token
        
    Returns:
        str: Secure reset token
    """
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    # Store token with user ID and expiration time (24 hours from now)
    expiration = datetime.now() + timedelta(hours=24)
    reset_tokens[token] = {
        'user_id': user.id,
        'expires': expiration.timestamp()
    }
    
    logger.info(f"Generated password reset token for user {user.username}")
    return token

def validate_reset_token(token):
    """
    Validate a password reset token
    
    Args:
        token (str): Token to validate
        
    Returns:
        User or None: User object if token is valid, None otherwise
    """
    # Check if token exists
    if token not in reset_tokens:
        logger.warning(f"Invalid reset token: {token}")
        return None
    
    # Check if token is expired
    token_data = reset_tokens[token]
    if time.time() > token_data['expires']:
        # Remove expired token
        del reset_tokens[token]
        logger.warning(f"Expired reset token: {token}")
        return None
    
    # Get user
    user_id = token_data['user_id']
    user = User.query.get(user_id)
    
    if not user:
        # Remove invalid token
        del reset_tokens[token]
        logger.warning(f"Reset token for non-existent user: {token}")
        return None
    
    return user

def reset_password(token, new_password):
    """
    Reset a user's password using a valid token
    
    Args:
        token (str): Valid reset token
        new_password (str): New password to set
        
    Returns:
        bool: True if password was reset successfully, False otherwise
    """
    # Validate token and get user
    user = validate_reset_token(token)
    if not user:
        return False
    
    try:
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        # Remove used token
        del reset_tokens[token]
        
        logger.info(f"Password reset successful for user {user.username}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting password: {str(e)}")
        return False