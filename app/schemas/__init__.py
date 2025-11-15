"""
Marshmallow Validation Schemas

This module contains all validation schemas for API endpoints.
"""

from app.schemas.auth import (
    RegisterSchema,
    LoginSchema,
    ForgotPasswordSchema,
    ResetPasswordSchema
)

from app.schemas.quiz import (
    GradeQuizSchema,
    QuizSubmissionSchema,
    QuizQuestionSchema,
    QuizStatsSchema
)

__all__ = [
    'RegisterSchema',
    'LoginSchema',
    'ForgotPasswordSchema',
    'ResetPasswordSchema',
    'GradeQuizSchema',
    'QuizSubmissionSchema',
    'QuizQuestionSchema',
    'QuizStatsSchema',
]
