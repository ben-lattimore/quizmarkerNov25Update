"""
Quiz Management API endpoints

Handles listing, viewing, and managing quiz submissions
"""

import logging
from flask import request, jsonify
from flask_login import login_required, current_user

from app.api.v1 import api_v1_bp
from database import db
from models import Quiz, QuizSubmission, QuizQuestion, Student

logger = logging.getLogger(__name__)


@api_v1_bp.route('/quizzes', methods=['GET'])
@login_required
def list_quizzes():
    """
    List all quiz submissions for current user (or all if admin)

    Query Parameters:
        page: int (default: 1)
        per_page: int (default: 20)
        student_name: string (optional filter)
        standard_id: int (optional filter)

    Response JSON:
        {
            "success": true,
            "data": {
                "quizzes": [...],
                "total": int,
                "page": int,
                "per_page": int,
                "total_pages": int
            }
        }
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # Get filter parameters
        student_name = request.args.get('student_name')
        standard_id = request.args.get('standard_id', type=int)

        # Build base query
        if current_user.is_admin:
            logger.info(f"Admin user {current_user.username} viewing all submissions")
            query = db.session.query(
                QuizSubmission, Quiz, Student
            ).join(
                Quiz, QuizSubmission.quiz_id == Quiz.id
            ).join(
                Student, QuizSubmission.student_id == Student.id
            )
        else:
            logger.info(f"User {current_user.username} viewing their submissions")
            query = db.session.query(
                QuizSubmission, Quiz, Student
            ).join(
                Quiz, QuizSubmission.quiz_id == Quiz.id
            ).join(
                Student, QuizSubmission.student_id == Student.id
            ).filter(
                Quiz.user_id == current_user.id
            )

        # Apply filters
        if student_name:
            query = query.filter(Student.name.ilike(f'%{student_name}%'))

        if standard_id:
            query = query.filter(Quiz.standard_id == standard_id)

        # Order by submission date (most recent first)
        query = query.order_by(QuizSubmission.submission_date.desc())

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        # Format the data
        quiz_data = []
        for submission, quiz, student in paginated.items:
            # Count questions for this submission
            question_count = QuizQuestion.query.filter_by(quiz_submission_id=submission.id).count()

            quiz_data.append({
                'id': submission.id,
                'quiz_title': quiz.title,
                'standard_id': quiz.standard_id,
                'student_name': student.name,
                'submission_date': submission.submission_date.isoformat(),
                'total_mark': submission.total_mark,
                'question_count': question_count
            })

        logger.info(f"Returning {len(quiz_data)} quiz submissions (page {page}/{paginated.pages})")

        return jsonify({
            'success': True,
            'data': {
                'quizzes': quiz_data,
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': paginated.pages
            }
        }), 200

    except Exception as e:
        logger.error(f"Error listing quizzes: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Failed to list quizzes: {str(e)}",
            'code': 'LIST_ERROR'
        }), 500


@api_v1_bp.route('/quizzes/<int:quiz_id>', methods=['GET'])
@login_required
def get_quiz(quiz_id):
    """
    Get details of a specific quiz submission

    Response JSON:
        {
            "success": true,
            "data": {
                "id": int,
                "quiz_title": "string",
                "standard_id": int,
                "student_name": "string",
                "submission_date": "string",
                "total_mark": float,
                "raw_data": {...},
                "questions": [...]
            }
        }
    """
    try:
        # Get the quiz submission
        submission = QuizSubmission.query.get(quiz_id)

        if not submission:
            return jsonify({
                'success': False,
                'error': 'Quiz not found',
                'code': 'NOT_FOUND'
            }), 404

        # Check if user has permission to view this quiz
        if not current_user.is_admin and submission.quiz.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'You do not have permission to view this quiz',
                'code': 'PERMISSION_DENIED'
            }), 403

        # Get questions for this submission
        questions = submission.questions

        # Format the data
        quiz_data = {
            'id': submission.id,
            'quiz_title': submission.quiz.title,
            'standard_id': submission.quiz.standard_id,
            'student_name': submission.student.name,
            'submission_date': submission.submission_date.isoformat(),
            'total_mark': submission.total_mark,
            'raw_data': submission.get_raw_data(),
            'questions': []
        }

        for q in questions:
            quiz_data['questions'].append({
                'question_number': q.question_number,
                'question_text': q.question_text,
                'student_answer': q.student_answer,
                'correct_answer': q.correct_answer,
                'mark_received': q.mark_received,
                'feedback': q.feedback
            })

        logger.info(f"User {current_user.username} viewed quiz {quiz_id}")

        return jsonify({
            'success': True,
            'data': quiz_data
        }), 200

    except Exception as e:
        logger.error(f"Error viewing quiz {quiz_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Failed to view quiz: {str(e)}",
            'code': 'VIEW_ERROR'
        }), 500


@api_v1_bp.route('/quizzes/<int:quiz_id>', methods=['DELETE'])
@login_required
def delete_quiz(quiz_id):
    """
    Delete a quiz submission

    Response JSON:
        {
            "success": true,
            "message": "Quiz deleted successfully"
        }
    """
    try:
        # Get the quiz submission
        submission = QuizSubmission.query.get(quiz_id)

        if not submission:
            return jsonify({
                'success': False,
                'error': 'Quiz not found',
                'code': 'NOT_FOUND'
            }), 404

        # Check if user has permission to delete this quiz
        if not current_user.is_admin and submission.quiz.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'You do not have permission to delete this quiz',
                'code': 'PERMISSION_DENIED'
            }), 403

        # Delete associated questions first (cascade should handle this, but being explicit)
        QuizQuestion.query.filter_by(quiz_submission_id=submission.id).delete()

        # Delete the submission
        db.session.delete(submission)
        db.session.commit()

        logger.info(f"User {current_user.username} deleted quiz {quiz_id}")

        return jsonify({
            'success': True,
            'message': 'Quiz deleted successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error deleting quiz {quiz_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f"Failed to delete quiz: {str(e)}",
            'code': 'DELETE_ERROR'
        }), 500


@api_v1_bp.route('/quizzes/stats', methods=['GET'])
@login_required
def get_quiz_stats():
    """
    Get statistics about quiz submissions

    Response JSON:
        {
            "success": true,
            "data": {
                "total_submissions": int,
                "average_score": float,
                "submissions_by_standard": {...},
                "recent_submissions": int
            }
        }
    """
    try:
        # Build base query based on user role
        if current_user.is_admin:
            submissions = QuizSubmission.query.all()
        else:
            submissions = db.session.query(QuizSubmission).join(
                Quiz
            ).filter(
                Quiz.user_id == current_user.id
            ).all()

        total_submissions = len(submissions)

        if total_submissions == 0:
            return jsonify({
                'success': True,
                'data': {
                    'total_submissions': 0,
                    'average_score': 0,
                    'submissions_by_standard': {},
                    'recent_submissions': 0
                }
            }), 200

        # Calculate average score
        total_marks = sum(s.total_mark for s in submissions)
        average_score = total_marks / total_submissions if total_submissions > 0 else 0

        # Count submissions by standard
        submissions_by_standard = {}
        for submission in submissions:
            standard_id = submission.quiz.standard_id
            submissions_by_standard[standard_id] = submissions_by_standard.get(standard_id, 0) + 1

        # Count recent submissions (last 7 days)
        from datetime import datetime, timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_submissions = sum(1 for s in submissions if s.submission_date >= seven_days_ago)

        logger.info(f"User {current_user.username} viewed quiz statistics")

        return jsonify({
            'success': True,
            'data': {
                'total_submissions': total_submissions,
                'average_score': round(average_score, 2),
                'submissions_by_standard': submissions_by_standard,
                'recent_submissions': recent_submissions
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting quiz stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Failed to get quiz statistics: {str(e)}",
            'code': 'STATS_ERROR'
        }), 500
