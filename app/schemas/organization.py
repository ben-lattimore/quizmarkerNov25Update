"""
Marshmallow schemas for organization-related validation.
"""

from marshmallow import Schema, fields, validate, validates, ValidationError, validates_schema
from datetime import datetime


class OrganizationSchema(Schema):
    """Schema for organization data"""
    id = fields.Int(dump_only=True)
    name = fields.Str(
        required=True,
        validate=[
            validate.Length(min=2, max=200, error="Organization name must be 2-200 characters"),
            validate.Regexp(
                r'^[a-zA-Z0-9\s\'\-\.]+$',
                error="Organization name can only contain letters, numbers, spaces, apostrophes, hyphens, and periods"
            )
        ]
    )
    plan = fields.Str(
        validate=validate.OneOf(
            ['free', 'pro', 'enterprise'],
            error="Plan must be one of: free, pro, enterprise"
        ),
        load_default='free'
    )
    max_quizzes_per_month = fields.Int(
        validate=validate.Range(min=1, max=10000, error="Quiz limit must be between 1 and 10000"),
        load_default=10
    )
    active = fields.Bool(load_default=True)
    created_at = fields.DateTime(dump_only=True)

    # Relationships (for output)
    member_count = fields.Int(dump_only=True)
    quiz_count = fields.Int(dump_only=True)


class CreateOrganizationSchema(Schema):
    """Schema for creating a new organization"""
    name = fields.Str(
        required=True,
        validate=[
            validate.Length(min=2, max=200, error="Organization name must be 2-200 characters"),
            validate.Regexp(
                r'^[a-zA-Z0-9\s\'\-\.]+$',
                error="Organization name can only contain letters, numbers, spaces, apostrophes, hyphens, and periods"
            )
        ]
    )
    plan = fields.Str(
        validate=validate.OneOf(
            ['free', 'pro', 'enterprise'],
            error="Plan must be one of: free, pro, enterprise"
        ),
        load_default='free'
    )


class UpdateOrganizationSchema(Schema):
    """Schema for updating an organization"""
    name = fields.Str(
        validate=[
            validate.Length(min=2, max=200, error="Organization name must be 2-200 characters"),
            validate.Regexp(
                r'^[a-zA-Z0-9\s\'\-\.]+$',
                error="Organization name can only contain letters, numbers, spaces, apostrophes, hyphens, and periods"
            )
        ]
    )
    plan = fields.Str(
        validate=validate.OneOf(
            ['free', 'pro', 'enterprise'],
            error="Plan must be one of: free, pro, enterprise"
        )
    )
    max_quizzes_per_month = fields.Int(
        validate=validate.Range(min=1, max=10000, error="Quiz limit must be between 1 and 10000")
    )
    active = fields.Bool()


class OrganizationMemberSchema(Schema):
    """Schema for organization member data"""
    id = fields.Int(dump_only=True)
    organization_id = fields.Int(required=True)
    user_id = fields.Int(required=True)
    role = fields.Str(
        validate=validate.OneOf(
            ['owner', 'admin', 'member'],
            error="Role must be one of: owner, admin, member"
        ),
        load_default='member'
    )
    joined_at = fields.DateTime(dump_only=True)

    # Include user info when dumping
    user = fields.Nested('UserSchema', dump_only=True, only=['id', 'username', 'email'])


class AddOrganizationMemberSchema(Schema):
    """Schema for adding a member to an organization"""
    email = fields.Email(required=True)
    role = fields.Str(
        validate=validate.OneOf(
            ['admin', 'member'],
            error="Role must be 'admin' or 'member' (owner role cannot be assigned)"
        ),
        load_default='member'
    )

    @validates('email')
    def validate_email_format(self, value):
        """Validate email format"""
        if not value or '@' not in value:
            raise ValidationError("Invalid email format")


class UpdateOrganizationMemberSchema(Schema):
    """Schema for updating a member's role"""
    role = fields.Str(
        required=True,
        validate=validate.OneOf(
            ['owner', 'admin', 'member'],
            error="Role must be one of: owner, admin, member"
        )
    )


class APIUsageLogSchema(Schema):
    """Schema for API usage log data"""
    id = fields.Int(dump_only=True)
    organization_id = fields.Int(required=True)
    user_id = fields.Int(required=True)
    endpoint = fields.Str(required=True, validate=validate.Length(max=200))
    method = fields.Str(
        required=True,
        validate=validate.OneOf(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    )
    status_code = fields.Int(validate=validate.Range(min=100, max=599))
    timestamp = fields.DateTime(dump_only=True)
    openai_tokens_used = fields.Int(load_default=0)

    # Include user info when dumping
    user = fields.Nested('UserSchema', dump_only=True, only=['id', 'username'])


class OrganizationUsageQuerySchema(Schema):
    """Schema for querying organization usage statistics"""
    start_date = fields.DateTime(format='%Y-%m-%d')
    end_date = fields.DateTime(format='%Y-%m-%d')
    include_details = fields.Bool(load_default=False)

    @validates_schema
    def validate_date_range(self, data, **kwargs):
        """Ensure start_date is before end_date"""
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] > data['end_date']:
                raise ValidationError("start_date must be before end_date")


class OrganizationUsageStatsSchema(Schema):
    """Schema for organization usage statistics output"""
    organization_id = fields.Int()
    organization_name = fields.Str()
    total_api_calls = fields.Int()
    total_openai_tokens = fields.Int()
    quiz_count_this_month = fields.Int()
    quiz_limit = fields.Int()
    quizzes_remaining = fields.Int()
    plan = fields.Str()
    active = fields.Bool()
    period_start = fields.DateTime()
    period_end = fields.DateTime()
    usage_details = fields.List(fields.Nested(APIUsageLogSchema), dump_only=True)


class OrganizationListQuerySchema(Schema):
    """Schema for listing organizations with pagination"""
    page = fields.Int(
        validate=validate.Range(min=1, error="Page must be >= 1"),
        load_default=1
    )
    per_page = fields.Int(
        validate=validate.Range(min=1, max=100, error="Per page must be between 1 and 100"),
        load_default=10
    )
    active_only = fields.Bool(load_default=True)
