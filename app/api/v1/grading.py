"""
Grading API endpoints

Handles AI-powered quiz grading against reference PDFs
"""

import os
import logging
import time
import json
import uuid
from datetime import datetime, timedelta
from flask import request, jsonify, url_for, current_app
from flask_login import login_required, current_user

from app.api.v1 import api_v1_bp
from app import limiter
from app.schemas import GradeQuizSchema
from app.utils.validation import validate_request
from database import db
from models import Student, Quiz, QuizSubmission, QuizQuestion, Organization, BackgroundJob
from image_processor import grade_answers
from email_service import email_service
from app.utils import get_user_organization_ids

logger = logging.getLogger(__name__)


@api_v1_bp.route('/grade', methods=['POST'])
@login_required
@limiter.limit("15 per hour")  # Expensive AI operation - strict limit
@validate_request(GradeQuizSchema)
def grade_quiz(validated_data):
    """
    Grade handwritten answers against reference PDF

    Request JSON:
        {
            "data": [
                {
                    "filename": "string",
                    "data": {
                        "handwritten_content": "string"
                    }
                }
            ],
            "standard_id": int,
            "student_name": "string",
            "quiz_title": "string" (optional)
        }

    Response JSON:
        {
            "success": true,
            "data": {
                "standard_id": int,
                "student_name": "string",
                "total_mark": float,
                "submission_id": int,
                "results": {...}
            }
        }
    """
    try:
        # Verify we have data in the request
        if not request.json or 'data' not in request.json:
            return jsonify({
                'success': False,
                'error': 'No data provided. Expected JSON with "data" field.',
                'code': 'NO_DATA'
            }), 400

        # Get the extracted data
        extracted_data = request.json['data']

        if not extracted_data or not isinstance(extracted_data, list):
            return jsonify({
                'success': False,
                'error': 'Invalid data format. Expected a list of extraction results.',
                'code': 'INVALID_FORMAT'
            }), 400

        # Get the standard ID (default to 2 if not provided)
        standard_id = request.json.get('standard_id', 2)
        student_name = request.json.get('student_name', 'Unknown Student')
        quiz_title = request.json.get('quiz_title', f'Standard {standard_id} Quiz')

        # Check for optional fallback mode for Standard 9
        force_fallback = request.args.get('force_fallback', 'false').lower() == 'true'

        logger.info(f"Grading request: Standard {standard_id}, Student: {student_name}, User: {current_user.username}")

        # Organization verification and plan limit check
        if not current_user.is_super_admin:
            # Regular users must have an organization
            if not current_user.default_organization_id:
                logger.warning(f"User {current_user.username} has no default organization")
                return jsonify({
                    'success': False,
                    'error': 'You must belong to an organization to grade quizzes',
                    'code': 'NO_ORGANIZATION'
                }), 403

            # Get the user's organization
            organization = Organization.query.get(current_user.default_organization_id)
            if not organization:
                logger.error(f"Organization {current_user.default_organization_id} not found for user {current_user.username}")
                return jsonify({
                    'success': False,
                    'error': 'Organization not found',
                    'code': 'ORGANIZATION_NOT_FOUND'
                }), 404

            # Check if organization can create quiz (plan limits)
            can_create, error_message = organization.can_create_quiz()
            if not can_create:
                logger.warning(f"Organization {organization.name} cannot create quiz: {error_message}")
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'code': 'PLAN_LIMIT_EXCEEDED',
                    'details': {
                        'plan': organization.plan,
                        'quiz_limit': organization.max_quizzes_per_month,
                        'quizzes_this_month': organization.get_quiz_count_this_month(),
                        'quizzes_remaining': organization.max_quizzes_per_month - organization.get_quiz_count_this_month()
                    }
                }), 403

            logger.info(f"Organization {organization.name} verified, {organization.max_quizzes_per_month - organization.get_quiz_count_this_month()} quizzes remaining")

        # Determine the PDF path
        reference_pdf_dir = current_app.config.get('REFERENCE_PDF_DIR', 'attached_assets')
        pdf_filename = f"Standard-{standard_id}.pdf"
        pdf_path = os.path.join(reference_pdf_dir, pdf_filename)

        # Filter out any failed extractions
        valid_extractions = [item for item in extracted_data if "error" not in item]

        if not valid_extractions:
            return jsonify({
                'success': False,
                'error': 'No valid extractions to grade.',
                'code': 'NO_VALID_EXTRACTIONS'
            }), 400

        logger.info(f"Grading {len(valid_extractions)} valid extractions against Standard {standard_id}")

        # Check if the reference PDF exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return jsonify({
                'success': False,
                'error': f'Reference PDF for Standard {standard_id} not found.',
                'code': 'PDF_NOT_FOUND'
            }), 404

        # Create background job for async grading
        logger.info(f"Creating background job for grading Standard {standard_id}")

        job_id = str(uuid.uuid4())
        organization_id = None if current_user.is_super_admin else current_user.default_organization_id

        job = BackgroundJob(
            id=job_id,
            job_type='grading',
            status='queued',
            user_id=current_user.id,
            organization_id=organization_id,
            progress=0,
            current_step=f'Queued grading for {student_name}',
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )

        # Store input data for the background task
        job.set_input_data({
            'extracted_data': valid_extractions,
            'pdf_path': pdf_path,
            'standard_id': standard_id,
            'student_name': student_name,
            'quiz_title': quiz_title,
            'user_id': current_user.id,
            'organization_id': organization_id,
            'force_fallback': force_fallback
        })

        db.session.add(job)
        db.session.commit()

        logger.info(f"Created job {job_id} for grading")

        # Queue the background task
        try:
            from tasks import grade_quiz_task
            grade_quiz_task.delay(job_id)
            logger.info(f"Queued grade_quiz_task for job {job_id}")
        except Exception as queue_error:
            logger.error(f"Failed to queue grading task: {queue_error}")
            job.mark_failed(f"Failed to queue task: {str(queue_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to queue grading job',
                'code': 'QUEUE_ERROR'
            }), 500

        # Return job information
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': 'queued',
            'message': f'Grading queued for {student_name}. This may take 30-60 seconds.',
            'data': {
                'standard_id': standard_id,
                'student_name': student_name,
                'quiz_title': quiz_title,
                'job_status_url': f'/api/v1/jobs/{job_id}',
                'estimated_time': '30-60 seconds'
            }
        }), 202

    except Exception as e:
        logger.error(f"Critical error in grade endpoint: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}",
            'code': 'SERVER_ERROR'
        }), 500


def create_fallback_grading(extractions):
    """Create fallback grading results when API fails"""
    grading_results = {"images": []}

    for i, extract in enumerate(extractions):
        data = extract.get('data', {})
        handwritten = data.get('handwritten_content', 'No content extracted')

        # Default score based on content length
        if handwritten and len(handwritten) > 100:
            score = 8
            feedback = "Good answer that addresses key points."
        elif handwritten and len(handwritten) > 50:
            score = 6
            feedback = "Answer contains relevant information but could include more detail."
        else:
            score = 5
            feedback = "Answer is very brief. Consider providing more information."

        grading_results["images"].append({
            "filename": extract.get('filename', f"image_{i+1}.jpg"),
            "score": score,
            "handwritten_content": handwritten,
            "feedback": feedback
        })

    return grading_results


def store_quiz_results(extracted_data, grading_results, standard_id, student_name, quiz_title, organization_id=None):
    """Store quiz results in database"""
    try:
        # Find or create the student (scoped to organization)
        if organization_id:
            student = Student.query.filter_by(name=student_name, organization_id=organization_id).first()
        else:
            # Super admins without org - use global scope
            student = Student.query.filter_by(name=student_name, organization_id=None).first()

        if not student:
            student = Student(name=student_name, organization_id=organization_id)
            db.session.add(student)
            logger.info(f"Created new student: {student_name} (org_id: {organization_id})")

        # Find or create the quiz (scoped to organization)
        if organization_id:
            quiz = Quiz.query.filter_by(title=quiz_title, standard_id=standard_id, organization_id=organization_id).first()
        else:
            # Super admins without org - use global scope
            quiz = Quiz.query.filter_by(title=quiz_title, standard_id=standard_id, organization_id=None).first()

        if not quiz:
            quiz = Quiz(
                title=quiz_title,
                standard_id=standard_id,
                user_id=current_user.id if current_user.is_authenticated else None,
                organization_id=organization_id
            )
            db.session.add(quiz)
            logger.info(f"Created new quiz: {quiz_title} (org_id: {organization_id})")

        # Create the quiz submission
        quiz_submission = QuizSubmission(
            quiz=quiz,
            student=student,
            submission_date=datetime.utcnow()
        )

        # Store the raw extracted data
        quiz_submission.set_raw_data(extracted_data)

        # Calculate total mark and add questions
        total_mark = 0
        questions_added = 0

        # Process grading results based on structure
        if 'images' in grading_results and isinstance(grading_results['images'], list):
            for image in grading_results['images']:
                score = image.get('score', 0)
                total_mark += score

                handwritten_content = image.get('handwritten_content', '')
                if isinstance(handwritten_content, (dict, list)):
                    handwritten_content = json.dumps(handwritten_content)

                question = QuizQuestion(
                    submission=quiz_submission,
                    question_number=questions_added + 1,
                    question_text=f"Image #{questions_added + 1}",
                    student_answer=handwritten_content,
                    correct_answer='',
                    mark_received=score,
                    feedback=image.get('feedback', '')
                )
                db.session.add(question)
                questions_added += 1

        elif 'results' in grading_results and isinstance(grading_results['results'], list):
            for result in grading_results['results']:
                question_data = result.get('question_data', {})

                student_response = question_data.get('student_response', '')
                reference_answer = question_data.get('reference_answer', '')

                if isinstance(student_response, (dict, list)):
                    student_response = json.dumps(student_response)
                if isinstance(reference_answer, (dict, list)):
                    reference_answer = json.dumps(reference_answer)

                question = QuizQuestion(
                    submission=quiz_submission,
                    question_number=question_data.get('question_number', questions_added + 1),
                    question_text=question_data.get('title', ''),
                    student_answer=student_response,
                    correct_answer=reference_answer,
                    mark_received=result.get('grade', {}).get('score', 0),
                    feedback=result.get('grade', {}).get('feedback', '')
                )
                db.session.add(question)
                total_mark += question.mark_received
                questions_added += 1

        logger.info(f"Processed {questions_added} questions with total mark: {total_mark}")

        # Update the total mark on the submission
        quiz_submission.total_mark = total_mark
        db.session.add(quiz_submission)

        # Commit the transaction
        db.session.commit()
        logger.info(f"Saved quiz submission to database: ID {quiz_submission.id}")

        return quiz_submission.id, total_mark

    except Exception as db_error:
        db.session.rollback()
        logger.error(f"Database error: {db_error}", exc_info=True)
        # Return None values if database storage fails
        return None, 0
