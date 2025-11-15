"""
Quiz and grading validation schemas
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class ExtractedDataItemSchema(Schema):
    """Schema for a single extracted text item"""
    filename = fields.Str(required=True)
    data = fields.Dict(required=True)


class GradeQuizSchema(Schema):
    """Schema for quiz grading request"""
    data = fields.List(
        fields.Nested(ExtractedDataItemSchema),
        required=True,
        validate=validate.Length(min=1, error="At least one extracted item is required")
    )
    standard_id = fields.Int(
        required=True,
        validate=validate.Range(min=1, max=20, error="Standard ID must be between 1 and 20")
    )
    student_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200, error="Student name must be between 1 and 200 characters")
    )
    quiz_title = fields.Str(
        load_default=None,
        validate=validate.Length(max=200, error="Quiz title must be less than 200 characters")
    )


class QuizQuestionSchema(Schema):
    """Schema for quiz question serialization"""
    id = fields.Int(dump_only=True)
    question_number = fields.Int()
    question_text = fields.Str()
    student_answer = fields.Str()
    correct_answer = fields.Str()
    mark_received = fields.Float()
    feedback = fields.Str()


class QuizSubmissionSchema(Schema):
    """Schema for quiz submission serialization"""
    id = fields.Int(dump_only=True)
    quiz_title = fields.Str()
    standard_id = fields.Int()
    student_name = fields.Str()
    submission_date = fields.DateTime()
    total_mark = fields.Float()
    question_count = fields.Int()
    organization_id = fields.Int(dump_only=True)
    questions = fields.List(fields.Nested(QuizQuestionSchema), dump_only=True)


class QuizListQuerySchema(Schema):
    """Schema for quiz list query parameters"""
    page = fields.Int(
        load_default=1,
        validate=validate.Range(min=1, error="Page must be at least 1")
    )
    per_page = fields.Int(
        load_default=20,
        validate=validate.Range(min=1, max=100, error="Per page must be between 1 and 100")
    )
    student_name = fields.Str(
        load_default=None,
        validate=validate.Length(max=200)
    )
    standard_id = fields.Int(
        load_default=None,
        validate=validate.Range(min=1, max=20)
    )
    organization_id = fields.Int(
        load_default=None,
        validate=validate.Range(min=1, error="Organization ID must be positive")
    )


class QuizStatsSchema(Schema):
    """Schema for quiz statistics response"""
    total_submissions = fields.Int()
    average_score = fields.Float()
    submissions_by_standard = fields.Dict(keys=fields.Int(), values=fields.Int())
    recent_submissions = fields.Int()
