"""
Authentication API endpoints

Handles user registration, login, logout, and password reset
"""

import logging
from flask import request, jsonify, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from app.api.v1 import api_v1_bp
from app.schemas import RegisterSchema, LoginSchema, ForgotPasswordSchema, ResetPasswordSchema
from app.utils.validation import validate_request
from database import db
from models import User
from password_reset import generate_reset_token, validate_reset_token, reset_password
from email_service import email_service

logger = logging.getLogger(__name__)


@api_v1_bp.route('/auth/register', methods=['POST'])
@validate_request(RegisterSchema)
def register(validated_data):
    """
    Register a new user

    Request JSON:
        {
            "username": "string" (3-50 chars, alphanumeric + _ -),
            "email": "string" (valid email),
            "password": "string" (8-128 chars),
            "confirm_password": "string" (must match password)
        }

    Response JSON:
        {
            "success": true,
            "message": "Registration successful",
            "data": {
                "id": int,
                "username": "string",
                "email": "string"
            }
        }
    """
    try:
        # Extract validated data (already validated by decorator!)
        username = validated_data['username']
        email = validated_data['email']
        password = validated_data['password']

        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Username or email already exists',
                'code': 'USER_EXISTS'
            }), 409

        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)

        # Make first user an admin
        if User.query.count() == 0:
            new_user.is_admin = True

        db.session.add(new_user)
        db.session.commit()

        logger.info(f"New user registered: {username} ({email})")

        # Send welcome email
        try:
            email_service.send_welcome_email(new_user.email, new_user.username)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")

        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'data': {
                'id': new_user.id,
                'username': new_user.username,
                'email': new_user.email,
                'is_admin': new_user.is_admin
            }
        }), 201

    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Registration failed',
            'code': 'REGISTRATION_ERROR'
        }), 500


@api_v1_bp.route('/auth/login', methods=['POST'])
@validate_request(LoginSchema)
def login(validated_data):
    """
    Login user

    Request JSON:
        {
            "username": "string" (can be username or email),
            "password": "string",
            "remember": boolean (optional, default: false)
        }

    Response JSON:
        {
            "success": true,
            "message": "Login successful",
            "data": {
                "id": int,
                "username": "string",
                "email": "string",
                "is_admin": boolean
            }
        }
    """
    try:
        username = validated_data['username']
        password = validated_data['password']
        remember = validated_data.get('remember', False)

        # Try to find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            logger.info(f"User logged in: {user.username}")

            return jsonify({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin,
                    'is_super_admin': user.is_super_admin
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password',
                'code': 'INVALID_CREDENTIALS'
            }), 401

    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Login failed',
            'code': 'LOGIN_ERROR'
        }), 500


@api_v1_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """
    Logout current user

    Response JSON:
        {
            "success": true,
            "message": "Logout successful"
        }
    """
    try:
        username = current_user.username
        logout_user()
        logger.info(f"User logged out: {username}")

        return jsonify({
            'success': True,
            'message': 'Logout successful'
        }), 200

    except Exception as e:
        logger.error(f"Logout error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Logout failed',
            'code': 'LOGOUT_ERROR'
        }), 500


@api_v1_bp.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """
    Get current authenticated user

    Response JSON:
        {
            "success": true,
            "data": {
                "id": int,
                "username": "string",
                "email": "string",
                "is_admin": boolean
            }
        }
    """
    try:
        return jsonify({
            'success': True,
            'data': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'is_admin': current_user.is_admin,
                'is_super_admin': current_user.is_super_admin
            }
        }), 200

    except Exception as e:
        logger.error(f"Get current user error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get user information',
            'code': 'USER_INFO_ERROR'
        }), 500


@api_v1_bp.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request password reset

    Request JSON:
        {
            "email": "string"
        }

    Response JSON:
        {
            "success": true,
            "message": "Password reset link sent to email"
        }
    """
    try:
        data = request.get_json(force=True, silent=True)

        if not data or not data.get('email'):
            return jsonify({
                'success': False,
                'error': 'Email is required',
                'code': 'MISSING_EMAIL'
            }), 400

        email = data['email']
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate reset token
            token = generate_reset_token(user)

            # Build reset URL (will need to be frontend URL in production)
            reset_url = url_for('reset_password_route', token=token, _external=True)

            # Send password reset email
            try:
                email_service.send_password_reset_email(user.email, user.username, token, reset_url)
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")

        # Always return success (don't reveal if email exists)
        return jsonify({
            'success': True,
            'message': 'If your email is registered, you will receive a password reset link'
        }), 200

    except Exception as e:
        logger.error(f"Forgot password error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to process password reset request',
            'code': 'PASSWORD_RESET_ERROR'
        }), 500


@api_v1_bp.route('/auth/reset-password', methods=['POST'])
def reset_password_endpoint():
    """
    Reset password with token

    Request JSON:
        {
            "token": "string",
            "password": "string",
            "confirm_password": "string"
        }

    Response JSON:
        {
            "success": true,
            "message": "Password reset successful"
        }
    """
    try:
        data = request.get_json(force=True, silent=True)

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided',
                'code': 'NO_DATA'
            }), 400

        token = data.get('token')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if not token or not password or not confirm_password:
            return jsonify({
                'success': False,
                'error': 'Token, password, and confirm_password are required',
                'code': 'MISSING_FIELDS'
            }), 400

        if password != confirm_password:
            return jsonify({
                'success': False,
                'error': 'Passwords do not match',
                'code': 'PASSWORD_MISMATCH'
            }), 400

        # Validate token and reset password
        if reset_password(token, password):
            logger.info("Password reset successful")
            return jsonify({
                'success': True,
                'message': 'Password reset successful'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token',
                'code': 'INVALID_TOKEN'
            }), 400

    except Exception as e:
        logger.error(f"Reset password error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to reset password',
            'code': 'PASSWORD_RESET_ERROR'
        }), 500
