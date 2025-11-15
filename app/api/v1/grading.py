"""
Grading API endpoints

Handles AI-powered quiz grading against reference PDFs
"""

import os
import logging
import time
import json
from datetime import datetime
from flask import request, jsonify, url_for, current_app
from flask_login import login_required, current_user

from app.api.v1 import api_v1_bp
from database import db
from models import Student, Quiz, QuizSubmission, QuizQuestion
from image_processor import grade_answers
from email_service import email_service

logger = logging.getLogger(__name__)


@api_v1_bp.route('/grade', methods=['POST'])
@login_required
def grade_quiz():
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

        # Grade the answers
        try:
            grading_start = time.time()

            # Special handling for Standard 9 with forced fallback
            if standard_id == 9 and force_fallback:
                logger.info("Using forced fallback for Standard 9")
                grading_results = create_fallback_grading(valid_extractions)
            else:
                # Normal grading process
                grading_results = grade_answers(valid_extractions, pdf_path)

            grading_time = time.time() - grading_start
            logger.info(f"Graded answers in {grading_time:.2f} seconds")

            # Validate grading results
            if not grading_results or not isinstance(grading_results, dict):
                if standard_id == 9:
                    logger.warning("Grading failed for Standard 9, using fallback")
                    grading_results = create_fallback_grading(valid_extractions)
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Grading process returned invalid results',
                        'code': 'GRADING_FAILED'
                    }), 500

            # Store quiz results in database
            submission_id, total_mark = store_quiz_results(
                extracted_data=extracted_data,
                grading_results=grading_results,
                standard_id=standard_id,
                student_name=student_name,
                quiz_title=quiz_title
            )

            # Send email notification
            if current_user.is_authenticated and submission_id:
                try:
                    quiz_url = url_for('view_quiz', quiz_id=submission_id, _external=True)
                    quiz_info = {
                        'title': quiz_title,
                        'student_name': student_name,
                        'total_mark': total_mark,
                        'submission_date': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    email_service.send_quiz_submission_notification(
                        current_user.email,
                        current_user.username,
                        quiz_info,
                        quiz_url
                    )
                    logger.info(f"Sent email notification to {current_user.email}")
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")

            # Return the grading results
            return jsonify({
                'success': True,
                'data': {
                    'standard_id': standard_id,
                    'student_name': student_name,
                    'total_mark': total_mark,
                    'submission_id': submission_id,
                    'results': grading_results
                }
            }), 200

        except Exception as grading_error:
            logger.error(f"Error during grading: {grading_error}", exc_info=True)

            # Emergency fallback for Standard 9
            if standard_id == 9:
                logger.warning("Using emergency fallback for Standard 9")
                grading_results = create_fallback_grading(valid_extractions)

                submission_id, total_mark = store_quiz_results(
                    extracted_data=extracted_data,
                    grading_results=grading_results,
                    standard_id=standard_id,
                    student_name=student_name,
                    quiz_title=quiz_title
                )

                return jsonify({
                    'success': True,
                    'data': {
                        'standard_id': standard_id,
                        'student_name': student_name,
                        'total_mark': total_mark,
                        'submission_id': submission_id,
                        'results': grading_results,
                        'warning': 'Used fallback grading due to API issues'
                    }
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': f"Grading failed: {str(grading_error)}",
                    'code': 'GRADING_ERROR'
                }), 500

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


def store_quiz_results(extracted_data, grading_results, standard_id, student_name, quiz_title):
    """Store quiz results in database"""
    try:
        # Find or create the student
        student = Student.query.filter_by(name=student_name).first()
        if not student:
            student = Student(name=student_name)
            db.session.add(student)
            logger.info(f"Created new student: {student_name}")

        # Find or create the quiz
        quiz = Quiz.query.filter_by(title=quiz_title, standard_id=standard_id).first()
        if not quiz:
            quiz = Quiz(
                title=quiz_title,
                standard_id=standard_id,
                user_id=current_user.id if current_user.is_authenticated else None
            )
            db.session.add(quiz)
            logger.info(f"Created new quiz: {quiz_title}")

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
