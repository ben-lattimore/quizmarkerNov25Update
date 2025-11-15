"""
Request validation utilities
"""

from functools import wraps
from flask import request, jsonify
from marshmallow import ValidationError as MarshmallowValidationError


# Re-export ValidationError for convenience
ValidationError = MarshmallowValidationError


def validate_request(schema_class, location='json'):
    """
    Decorator to validate request data using a Marshmallow schema

    Args:
        schema_class: Marshmallow schema class to use for validation
        location: Where to get data from ('json', 'args', 'form')

    Usage:
        @validate_request(RegisterSchema)
        def register(validated_data):
            # validated_data is guaranteed to be valid
            username = validated_data['username']
            ...

    Returns:
        Decorator function that validates and passes validated_data to the route
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get data based on location
            if location == 'json':
                data = request.get_json(force=True, silent=True)
            elif location == 'args':
                data = request.args.to_dict()
            elif location == 'form':
                data = request.form.to_dict()
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid validation location',
                    'code': 'INTERNAL_ERROR'
                }), 500

            # Check if data exists
            if data is None:
                return jsonify({
                    'success': False,
                    'error': 'No data provided',
                    'code': 'NO_DATA'
                }), 400

            # Validate using schema
            schema = schema_class()
            try:
                # For password confirmation, we need to pass password in context
                if hasattr(schema, 'context') and 'password' in data:
                    schema.context = {'password': data.get('password')}

                validated_data = schema.load(data)
            except MarshmallowValidationError as e:
                # Format validation errors nicely
                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'code': 'VALIDATION_ERROR',
                    'details': e.messages
                }), 400

            # Call the original function with validated data
            return f(validated_data, *args, **kwargs)

        return decorated_function
    return decorator


def format_validation_error(error):
    """
    Format a Marshmallow ValidationError into a standard API response

    Args:
        error: MarshmallowValidationError instance

    Returns:
        Tuple of (response_dict, status_code)
    """
    return {
        'success': False,
        'error': 'Validation failed',
        'code': 'VALIDATION_ERROR',
        'details': error.messages
    }, 400
