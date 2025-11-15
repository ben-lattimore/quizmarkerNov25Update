"""
Organization middleware and permission decorators for multi-tenancy.

This module provides:
- Decorators to require organization access
- Permission checking functions
- Organization context helpers
"""

from functools import wraps
from flask import request, jsonify, g
from flask_login import current_user
from models import Organization, OrganizationMember
from database import db


def get_user_organizations(user):
    """
    Get all organizations a user has access to.

    Args:
        user: User object

    Returns:
        List of Organization objects the user is a member of
    """
    if not user or not user.is_authenticated:
        return []

    memberships = OrganizationMember.query.filter_by(user_id=user.id).all()
    return [membership.organization for membership in memberships]


def get_user_organization_ids(user):
    """
    Get all organization IDs a user has access to.

    Args:
        user: User object

    Returns:
        List of organization IDs
    """
    if not user or not user.is_authenticated:
        return []

    memberships = OrganizationMember.query.filter_by(user_id=user.id).all()
    return [membership.organization_id for membership in memberships]


def get_organization_role(user, organization_id):
    """
    Get user's role in a specific organization.

    Args:
        user: User object
        organization_id: Organization ID

    Returns:
        Role string ('owner', 'admin', 'member') or None if not a member
    """
    if not user or not user.is_authenticated:
        return None

    membership = OrganizationMember.query.filter_by(
        user_id=user.id,
        organization_id=organization_id
    ).first()

    return membership.role if membership else None


def user_can_access_organization(user, organization_id):
    """
    Check if user has any access to an organization.

    Args:
        user: User object
        organization_id: Organization ID

    Returns:
        Boolean
    """
    return get_organization_role(user, organization_id) is not None


def user_is_organization_admin(user, organization_id):
    """
    Check if user is admin or owner of an organization.

    Args:
        user: User object
        organization_id: Organization ID

    Returns:
        Boolean
    """
    role = get_organization_role(user, organization_id)
    return role in ['owner', 'admin']


def user_is_organization_owner(user, organization_id):
    """
    Check if user is owner of an organization.

    Args:
        user: User object
        organization_id: Organization ID

    Returns:
        Boolean
    """
    role = get_organization_role(user, organization_id)
    return role == 'owner'


def get_current_organization():
    """
    Get the current organization from request context.

    This checks:
    1. 'organization_id' in request args (query params)
    2. 'organization_id' in request JSON body
    3. User's default organization

    Returns:
        Organization object or None
    """
    if not current_user.is_authenticated:
        return None

    organization_id = None

    # Check query parameters
    if 'organization_id' in request.args:
        try:
            organization_id = int(request.args.get('organization_id'))
        except (ValueError, TypeError):
            return None

    # Check JSON body
    elif request.is_json and request.get_json(silent=True):
        data = request.get_json()
        organization_id = data.get('organization_id')

    # Fall back to user's default organization
    if organization_id is None and current_user.default_organization_id:
        organization_id = current_user.default_organization_id

    if organization_id is None:
        return None

    # Verify user has access to this organization
    if not user_can_access_organization(current_user, organization_id):
        return None

    return Organization.query.get(organization_id)


def set_current_organization(organization):
    """
    Store the current organization in Flask's g object for this request.

    Args:
        organization: Organization object
    """
    g.current_organization = organization
    g.current_organization_id = organization.id if organization else None


def require_organization_access(f):
    """
    Decorator to require that user has access to an organization.

    The organization can be specified via:
    - URL parameter: organization_id
    - Query parameter: organization_id
    - JSON body: organization_id
    - User's default organization (fallback)

    The organization is stored in g.current_organization for use in the view.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        # Get organization_id from URL params, query params, or body
        organization_id = kwargs.get('organization_id')

        if organization_id is None:
            organization_id = request.args.get('organization_id')

        if organization_id is None and request.is_json:
            data = request.get_json(silent=True)
            if data:
                organization_id = data.get('organization_id')

        # Fall back to user's default organization
        if organization_id is None:
            organization_id = current_user.default_organization_id

        if organization_id is None:
            return jsonify({
                'error': 'No organization specified',
                'message': 'Please provide organization_id or set a default organization'
            }), 400

        try:
            organization_id = int(organization_id)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid organization_id format'}), 400

        # Check if user has access to this organization
        if not user_can_access_organization(current_user, organization_id):
            return jsonify({
                'error': 'Access denied',
                'message': 'You do not have access to this organization'
            }), 403

        # Load the organization
        organization = Organization.query.get(organization_id)
        if not organization:
            return jsonify({'error': 'Organization not found'}), 404

        # Store in g for use in view
        set_current_organization(organization)

        return f(*args, **kwargs)

    return decorated_function


def require_organization_admin(f):
    """
    Decorator to require admin or owner access to an organization.
    """
    @wraps(f)
    @require_organization_access
    def decorated_function(*args, **kwargs):
        if not user_is_organization_admin(current_user, g.current_organization_id):
            return jsonify({
                'error': 'Permission denied',
                'message': 'Admin or owner access required'
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def require_organization_owner(f):
    """
    Decorator to require owner access to an organization.
    """
    @wraps(f)
    @require_organization_access
    def decorated_function(*args, **kwargs):
        if not user_is_organization_owner(current_user, g.current_organization_id):
            return jsonify({
                'error': 'Permission denied',
                'message': 'Organization owner access required'
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def filter_by_organization(query, model):
    """
    Helper to filter a query by current user's accessible organizations.

    Args:
        query: SQLAlchemy query object
        model: Model class that has organization_id field

    Returns:
        Filtered query
    """
    if not current_user.is_authenticated:
        return query.filter(False)  # Return empty query

    # Get user's organization IDs
    org_ids = get_user_organization_ids(current_user)

    if not org_ids:
        return query.filter(False)  # Return empty query

    # Filter by organization_id
    return query.filter(model.organization_id.in_(org_ids))


def ensure_organization_access(organization_id):
    """
    Ensure user has access to the specified organization.
    Raises 403 if not.

    Args:
        organization_id: Organization ID to check

    Returns:
        Organization object if access granted

    Raises:
        HTTP 403 error if access denied
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401

    if not user_can_access_organization(current_user, organization_id):
        return jsonify({
            'error': 'Access denied',
            'message': 'You do not have access to this organization'
        }), 403

    organization = Organization.query.get(organization_id)
    if not organization:
        return jsonify({'error': 'Organization not found'}), 404

    return organization
