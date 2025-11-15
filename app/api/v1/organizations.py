"""
Organization management API endpoints.

Provides routes for:
- Creating and managing organizations
- Managing organization members
- Viewing organization usage statistics
"""

from flask import request, jsonify, g
from flask_login import login_required, current_user
from marshmallow import ValidationError as MarshmallowValidationError
from datetime import datetime
from sqlalchemy import func

from app.api.v1 import api_v1_bp
from database import db
from models import Organization, OrganizationMember, User, Quiz, APIUsageLog
from app.schemas.organization import (
    OrganizationSchema,
    CreateOrganizationSchema,
    UpdateOrganizationSchema,
    OrganizationMemberSchema,
    AddOrganizationMemberSchema,
    UpdateOrganizationMemberSchema,
    OrganizationUsageQuerySchema,
    OrganizationUsageStatsSchema,
    OrganizationListQuerySchema
)
from app.utils import (
    validate_request,
    require_organization_access,
    require_organization_admin,
    require_organization_owner,
    get_user_organizations,
    user_can_access_organization
)
from app import limiter


@api_v1_bp.route('/organizations', methods=['GET'])
@login_required
@validate_request(OrganizationListQuerySchema, location='args')
def list_organizations(validated_data):
    """
    List all organizations the current user has access to.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Results per page (default: 10, max: 100)
    - active_only: Show only active organizations (default: true)

    Returns:
    - 200: List of organizations with pagination
    """
    args = validated_data
    page = args.get('page', 1)
    per_page = args.get('per_page', 10)
    active_only = args.get('active_only', True)

    # Get user's organizations
    organizations = get_user_organizations(current_user)

    # Filter active only if requested
    if active_only:
        organizations = [org for org in organizations if org.active]

    # Manual pagination (since we already have a list)
    total = len(organizations)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_orgs = organizations[start:end]

    # Serialize
    schema = OrganizationSchema(many=True)
    org_data = schema.dump(paginated_orgs)

    # Add member count and quiz count for each org
    for i, org in enumerate(paginated_orgs):
        org_data[i]['member_count'] = len(org.members)
        org_data[i]['quiz_count'] = Quiz.query.filter_by(organization_id=org.id).count()

    return jsonify({
        'success': True,
        'organizations': org_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        }
    }), 200


@api_v1_bp.route('/organizations', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
@validate_request(CreateOrganizationSchema)
def create_organization(validated_data):
    """
    Create a new organization.
    The current user becomes the owner.

    Request body:
    - name: Organization name (required)
    - plan: Plan type (free/pro/enterprise, default: free)

    Returns:
    - 201: Organization created successfully
    - 400: Validation error
    """
    data = validated_data

    try:
        # Create organization
        organization = Organization(
            name=data['name'],
            plan=data.get('plan', 'free'),
            max_quizzes_per_month=10 if data.get('plan', 'free') == 'free' else 100,
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(organization)
        db.session.flush()  # Get the organization ID

        # Add current user as owner
        membership = OrganizationMember(
            organization_id=organization.id,
            user_id=current_user.id,
            role='owner',
            joined_at=datetime.utcnow()
        )
        db.session.add(membership)

        # Set as user's default organization if they don't have one
        if current_user.default_organization_id is None:
            current_user.default_organization_id = organization.id

        db.session.commit()

        # Serialize response
        schema = OrganizationSchema()
        org_data = schema.dump(organization)
        org_data['member_count'] = 1
        org_data['quiz_count'] = 0

        return jsonify({
            'success': True,
            'message': 'Organization created successfully',
            'organization': org_data
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to create organization',
            'details': str(e)
        }), 500


@api_v1_bp.route('/organizations/<int:organization_id>', methods=['GET'])
@login_required
@require_organization_access
def get_organization(organization_id):
    """
    Get details of a specific organization.

    Path parameters:
    - organization_id: Organization ID

    Returns:
    - 200: Organization details
    - 403: Access denied
    - 404: Organization not found
    """
    organization = g.current_organization

    # Serialize
    schema = OrganizationSchema()
    org_data = schema.dump(organization)

    # Add counts
    org_data['member_count'] = len(organization.members)
    org_data['quiz_count'] = Quiz.query.filter_by(organization_id=organization.id).count()
    org_data['quiz_count_this_month'] = organization.get_quiz_count_this_month()
    org_data['quizzes_remaining'] = organization.max_quizzes_per_month - organization.get_quiz_count_this_month()

    # Add user's role
    org_data['your_role'] = next(
        (m.role for m in organization.members if m.user_id == current_user.id),
        None
    )

    return jsonify({
        'success': True,
        'organization': org_data
    }), 200


@api_v1_bp.route('/organizations/<int:organization_id>', methods=['PUT'])
@login_required
@require_organization_admin
@validate_request(UpdateOrganizationSchema)
def update_organization(validated_data, organization_id):
    """
    Update organization details.
    Requires admin or owner access.

    Path parameters:
    - organization_id: Organization ID

    Request body:
    - name: Organization name (optional)
    - plan: Plan type (optional)
    - max_quizzes_per_month: Quiz limit (optional)
    - active: Active status (optional, owner only)

    Returns:
    - 200: Organization updated successfully
    - 403: Permission denied
    - 404: Organization not found
    """
    organization = g.current_organization
    data = validated_data

    try:
        # Update fields
        if 'name' in data:
            organization.name = data['name']

        if 'plan' in data:
            organization.plan = data['plan']

        if 'max_quizzes_per_month' in data:
            organization.max_quizzes_per_month = data['max_quizzes_per_month']

        # Only owner can change active status
        if 'active' in data:
            from app.utils import user_is_organization_owner
            if not user_is_organization_owner(current_user, organization_id):
                return jsonify({
                    'success': False,
                    'error': 'Permission denied',
                    'message': 'Only organization owners can change active status'
                }), 403
            organization.active = data['active']

        db.session.commit()

        # Serialize response
        schema = OrganizationSchema()
        org_data = schema.dump(organization)

        return jsonify({
            'success': True,
            'message': 'Organization updated successfully',
            'organization': org_data
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update organization',
            'details': str(e)
        }), 500


@api_v1_bp.route('/organizations/<int:organization_id>', methods=['DELETE'])
@login_required
@require_organization_owner
def delete_organization(organization_id):
    """
    Delete an organization.
    Requires owner access.

    WARNING: This will delete all associated data (quizzes, submissions, etc.)

    Path parameters:
    - organization_id: Organization ID

    Returns:
    - 200: Organization deleted successfully
    - 403: Permission denied (not owner)
    - 404: Organization not found
    """
    organization = g.current_organization

    try:
        # Delete organization (cascade will handle members, quizzes, etc.)
        db.session.delete(organization)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Organization deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to delete organization',
            'details': str(e)
        }), 500


# Member management endpoints

@api_v1_bp.route('/organizations/<int:organization_id>/members', methods=['GET'])
@login_required
@require_organization_access
def list_members(organization_id):
    """
    List all members of an organization.

    Path parameters:
    - organization_id: Organization ID

    Returns:
    - 200: List of members
    - 403: Access denied
    - 404: Organization not found
    """
    organization = g.current_organization

    # Serialize members
    schema = OrganizationMemberSchema(many=True)
    members_data = schema.dump(organization.members)

    return jsonify({
        'success': True,
        'members': members_data,
        'total': len(members_data)
    }), 200


@api_v1_bp.route('/organizations/<int:organization_id>/members', methods=['POST'])
@login_required
@require_organization_admin
@limiter.limit("10 per hour")
@validate_request(AddOrganizationMemberSchema)
def add_member(validated_data, organization_id):
    """
    Add a new member to the organization.
    Requires admin or owner access.

    Path parameters:
    - organization_id: Organization ID

    Request body:
    - email: User email (required)
    - role: Member role (admin/member, default: member)

    Returns:
    - 201: Member added successfully
    - 400: User not found or already a member
    - 403: Permission denied
    """
    data = validated_data
    organization = g.current_organization

    # Find user by email
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({
            'success': False,
            'error': 'User not found',
            'message': f"No user found with email: {data['email']}"
        }), 404

    # Check if already a member
    existing = OrganizationMember.query.filter_by(
        organization_id=organization_id,
        user_id=user.id
    ).first()

    if existing:
        return jsonify({
            'success': False,
            'error': 'Already a member',
            'message': 'This user is already a member of the organization'
        }), 400

    try:
        # Add member
        membership = OrganizationMember(
            organization_id=organization_id,
            user_id=user.id,
            role=data.get('role', 'member'),
            joined_at=datetime.utcnow()
        )
        db.session.add(membership)
        db.session.commit()

        # Serialize response
        schema = OrganizationMemberSchema()
        member_data = schema.dump(membership)

        return jsonify({
            'success': True,
            'message': 'Member added successfully',
            'member': member_data
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to add member',
            'details': str(e)
        }), 500


@api_v1_bp.route('/organizations/<int:organization_id>/members/<int:user_id>', methods=['PUT'])
@login_required
@require_organization_admin
@validate_request(UpdateOrganizationMemberSchema)
def update_member_role(validated_data, organization_id, user_id):
    """
    Update a member's role in the organization.
    Requires admin or owner access.

    Path parameters:
    - organization_id: Organization ID
    - user_id: User ID

    Request body:
    - role: New role (owner/admin/member)

    Returns:
    - 200: Member role updated
    - 403: Permission denied
    - 404: Member not found
    """
    data = validated_data

    membership = OrganizationMember.query.filter_by(
        organization_id=organization_id,
        user_id=user_id
    ).first()

    if not membership:
        return jsonify({
            'success': False,
            'error': 'Member not found'
        }), 404

    # Only owner can assign owner role
    if data['role'] == 'owner':
        from app.utils import user_is_organization_owner
        if not user_is_organization_owner(current_user, organization_id):
            return jsonify({
                'success': False,
                'error': 'Permission denied',
                'message': 'Only organization owners can assign owner role'
            }), 403

    try:
        membership.role = data['role']
        db.session.commit()

        # Serialize response
        schema = OrganizationMemberSchema()
        member_data = schema.dump(membership)

        return jsonify({
            'success': True,
            'message': 'Member role updated successfully',
            'member': member_data
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update member role',
            'details': str(e)
        }), 500


@api_v1_bp.route('/organizations/<int:organization_id>/members/<int:user_id>', methods=['DELETE'])
@login_required
@require_organization_admin
def remove_member(organization_id, user_id):
    """
    Remove a member from the organization.
    Requires admin or owner access.

    Path parameters:
    - organization_id: Organization ID
    - user_id: User ID

    Returns:
    - 200: Member removed successfully
    - 403: Permission denied
    - 404: Member not found
    """
    membership = OrganizationMember.query.filter_by(
        organization_id=organization_id,
        user_id=user_id
    ).first()

    if not membership:
        return jsonify({
            'success': False,
            'error': 'Member not found'
        }), 404

    # Cannot remove yourself
    if user_id == current_user.id:
        return jsonify({
            'success': False,
            'error': 'Cannot remove yourself',
            'message': 'Use the leave organization endpoint to leave'
        }), 400

    # Cannot remove owner (must transfer ownership first)
    if membership.role == 'owner':
        return jsonify({
            'success': False,
            'error': 'Cannot remove owner',
            'message': 'Transfer ownership before removing the owner'
        }), 400

    try:
        db.session.delete(membership)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Member removed successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to remove member',
            'details': str(e)
        }), 500


# Usage statistics endpoint

@api_v1_bp.route('/organizations/<int:organization_id>/usage', methods=['GET'])
@login_required
@require_organization_access
@validate_request(OrganizationUsageQuerySchema, location='args')
def get_usage_stats(validated_data, organization_id):
    """
    Get usage statistics for an organization.

    Path parameters:
    - organization_id: Organization ID

    Query parameters:
    - start_date: Start date (YYYY-MM-DD, optional)
    - end_date: End date (YYYY-MM-DD, optional)
    - include_details: Include detailed usage logs (default: false)

    Returns:
    - 200: Usage statistics
    - 403: Access denied
    """
    organization = g.current_organization
    args = validated_data

    start_date = args.get('start_date')
    end_date = args.get('end_date')
    include_details = args.get('include_details', False)

    # Get usage stats
    total_tokens = APIUsageLog.get_total_tokens_used(
        organization_id,
        start_date,
        end_date
    )

    # Count API calls
    api_calls_query = APIUsageLog.query.filter_by(organization_id=organization_id)
    if start_date:
        api_calls_query = api_calls_query.filter(APIUsageLog.timestamp >= start_date)
    if end_date:
        api_calls_query = api_calls_query.filter(APIUsageLog.timestamp <= end_date)

    total_api_calls = api_calls_query.count()

    # Get quiz count for this month
    quiz_count_this_month = organization.get_quiz_count_this_month()
    quizzes_remaining = organization.max_quizzes_per_month - quiz_count_this_month

    # Build response
    stats = {
        'organization_id': organization_id,
        'organization_name': organization.name,
        'total_api_calls': total_api_calls,
        'total_openai_tokens': total_tokens,
        'quiz_count_this_month': quiz_count_this_month,
        'quiz_limit': organization.max_quizzes_per_month,
        'quizzes_remaining': quizzes_remaining,
        'plan': organization.plan,
        'active': organization.active,
        'period_start': start_date,
        'period_end': end_date
    }

    # Include usage details if requested
    if include_details:
        usage_logs = APIUsageLog.get_organization_usage(
            organization_id,
            start_date,
            end_date
        )
        from app.schemas.organization import APIUsageLogSchema
        log_schema = APIUsageLogSchema(many=True)
        stats['usage_details'] = log_schema.dump(usage_logs)

    return jsonify({
        'success': True,
        'usage': stats
    }), 200
