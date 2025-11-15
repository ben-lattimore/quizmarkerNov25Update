"""
Authentication validation schemas
"""

from marshmallow import Schema, fields, validate, validates, ValidationError


class RegisterSchema(Schema):
    """Schema for user registration"""
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50, error="Username must be between 3 and 50 characters"),
            validate.Regexp(
                r'^[a-zA-Z0-9_-]+$',
                error="Username can only contain letters, numbers, hyphens, and underscores"
            )
        ]
    )
    email = fields.Email(
        required=True,
        validate=validate.Length(max=120, error="Email must be less than 120 characters")
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8, max=128, error="Password must be between 8 and 128 characters"),
        load_only=True  # Never include in serialized output
    )
    confirm_password = fields.Str(
        required=True,
        load_only=True
    )

    @validates('confirm_password')
    def validate_passwords_match(self, value, **kwargs):
        """Validate that password and confirm_password match"""
        # Get the password from the data being validated
        password = self.context.get('password')
        if password and value != password:
            raise ValidationError("Passwords do not match")


class LoginSchema(Schema):
    """Schema for user login"""
    username = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=120, error="Username/email is required")
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=1, error="Password is required"),
        load_only=True
    )
    remember = fields.Bool(
        load_default=False  # Default value if not provided
    )


class ForgotPasswordSchema(Schema):
    """Schema for password reset request"""
    email = fields.Email(
        required=True,
        validate=validate.Length(max=120, error="Email must be less than 120 characters")
    )


class ResetPasswordSchema(Schema):
    """Schema for password reset with token"""
    token = fields.Str(
        required=True,
        validate=validate.Length(min=1, error="Reset token is required")
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8, max=128, error="Password must be between 8 and 128 characters"),
        load_only=True
    )
    confirm_password = fields.Str(
        required=True,
        load_only=True
    )

    @validates('confirm_password')
    def validate_passwords_match(self, value, **kwargs):
        """Validate that password and confirm_password match"""
        password = self.context.get('password')
        if password and value != password:
            raise ValidationError("Passwords do not match")


class UserSchema(Schema):
    """Schema for user data serialization (responses)"""
    id = fields.Int(dump_only=True)
    username = fields.Str()
    email = fields.Email()
    is_admin = fields.Bool()
    is_super_admin = fields.Bool()
    created_at = fields.DateTime(dump_only=True)
