"""
Background tasks for async processing using Redis Queue (RQ)

This module contains all background task definitions for Phase 3:
- Image processing tasks
- Quiz grading tasks
- Email notification tasks
- Job cleanup tasks

Usage:
    # Start a worker process
    $ rq worker --url redis://localhost:6379/0

    # Or specify queue name
    $ rq worker high default low --url redis://localhost:6379/0
"""

import os
import logging
from datetime import datetime, timedelta
from redis import Redis
from rq import Queue
from rq.decorators import job

from database import db
from models import BackgroundJob, Student, Quiz, QuizSubmission, QuizQuestion
import image_processor
import email_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
redis_conn = Redis.from_url(REDIS_URL, decode_responses=False)

# Define queues with different priorities
high_queue = Queue('high', connection=redis_conn)
default_queue = Queue('default', connection=redis_conn)
low_queue = Queue('low', connection=redis_conn)

# Job timeouts (in seconds)
IMAGE_PROCESSING_TIMEOUT = 600  # 10 minutes
GRADING_TIMEOUT = 600  # 10 minutes
EMAIL_TIMEOUT = 120  # 2 minutes


def get_job_from_db(job_id):
    """Helper function to get BackgroundJob from database"""
    from app import create_app
    app = create_app()
    with app.app_context():
        return BackgroundJob.query.get(job_id)


def update_job_progress(job_id, progress, current_step):
    """Helper function to update job progress in database"""
    from app import create_app
    app = create_app()
    with app.app_context():
        job = BackgroundJob.query.get(job_id)
        if job:
            job.update_progress(progress, current_step)
            logger.info(f"Job {job_id}: {progress}% - {current_step}")


@job('default', connection=redis_conn, timeout=IMAGE_PROCESSING_TIMEOUT)
def process_images_task(job_id, image_paths):
    """
    Background task for processing uploaded images

    Args:
        job_id: UUID of the BackgroundJob record
        image_paths: List of file paths to process

    Returns:
        dict: Processing results with extracted text from all images
    """
    import os
    from app import create_app

    # Create app context for this worker
    app = create_app()

    logger.info(f"Starting image processing task for job {job_id}")
    logger.info(f"Processing {len(image_paths)} images")

    # Track files for cleanup
    cleanup_files = list(image_paths)

    try:
        with app.app_context():
            # Mark job as started
            job = BackgroundJob.query.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found in database")

            job.mark_started()
            update_job_progress(job_id, 5, "Starting image processing")

            # Get original filenames from job input data
            input_data = job.get_input_data()
            original_filenames = input_data.get('original_filenames', [])

            # Process images using existing image processor
            # The image_processor.process_images function already handles sequential processing
            # with delays and retries
            results = image_processor.process_images(
                image_paths,
                progress_callback=lambda i, total: update_job_progress(
                    job_id,
                    int(5 + (i / total) * 90),  # Progress from 5% to 95%
                    f"Processing image {i} of {total}"
                )
            )

            update_job_progress(job_id, 95, "Processing complete, cleaning up files")

            # Replace unique filenames with original ones in results
            for i, result in enumerate(results):
                if i < len(original_filenames) and 'filename' in result:
                    result['filename'] = original_filenames[i]

            # Clean up temporary files
            cleanup_count = 0
            for filepath in cleanup_files:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        cleanup_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove temporary file {filepath}: {e}")

            logger.info(f"Cleaned up {cleanup_count}/{len(cleanup_files)} temporary files")

            update_job_progress(job_id, 100, "Image processing complete")

            # Mark job as completed with results
            job.mark_completed(results)

            logger.info(f"Successfully completed image processing for job {job_id}")
            return results

    except Exception as e:
        logger.error(f"Error processing images for job {job_id}: {str(e)}", exc_info=True)

        # Clean up files even on failure
        for filepath in cleanup_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as clean_error:
                logger.error(f"Failed to remove file {filepath}: {clean_error}")

        with app.app_context():
            job = BackgroundJob.query.get(job_id)
            if job:
                # Check if we can retry
                if job.can_retry():
                    job.increment_retry()
                    logger.info(f"Retrying job {job_id} (attempt {job.retry_count + 1}/{job.max_retries})")
                    # Re-queue the job
                    process_images_task.delay(job_id, image_paths)
                else:
                    # Max retries reached, mark as failed
                    job.mark_failed(str(e))
                    logger.error(f"Job {job_id} failed after {job.max_retries} attempts")

        raise


@job('default', connection=redis_conn, timeout=GRADING_TIMEOUT)
def grade_quiz_task(job_id):
    """
    Background task for grading quiz submissions

    Args:
        job_id: UUID of the BackgroundJob record

    The job's input_data should contain:
        - extracted_data: Extracted text from images
        - pdf_path: Path to reference PDF
        - standard_id: Standard number
        - student_name: Student name
        - quiz_title: Quiz title
        - user_id: ID of user who created the quiz
        - organization_id: ID of organization (for multi-tenancy)

    Returns:
        dict: Grading results with submission_id and total_mark
    """
    from app import create_app
    app = create_app()

    logger.info(f"Starting quiz grading task for job {job_id}")

    try:
        with app.app_context():
            # Get job and input data
            job = BackgroundJob.query.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found in database")

            job.mark_started()
            update_job_progress(job_id, 5, "Starting quiz grading")

            input_data = job.get_input_data()
            extracted_data = input_data['extracted_data']
            pdf_path = input_data['pdf_path']
            standard_id = input_data['standard_id']
            student_name = input_data['student_name']
            quiz_title = input_data['quiz_title']
            user_id = input_data['user_id']
            organization_id = input_data.get('organization_id')

            update_job_progress(job_id, 10, "Loading reference material")

            # Grade answers using existing grading function
            grading_results = image_processor.grade_answers(
                extracted_data,
                pdf_path,
                progress_callback=lambda progress, step: update_job_progress(
                    job_id,
                    int(10 + progress * 0.5),  # Progress from 10% to 60%
                    step
                )
            )

            update_job_progress(job_id, 65, "Storing quiz results")

            # Store results in database
            # Find or create student
            student = Student.query.filter_by(
                name=student_name,
                organization_id=organization_id
            ).first()

            if not student:
                student = Student(
                    name=student_name,
                    organization_id=organization_id
                )
                db.session.add(student)
                db.session.commit()

            update_job_progress(job_id, 70, "Creating quiz record")

            # Create quiz
            quiz = Quiz(
                title=quiz_title,
                standard_id=standard_id,
                user_id=user_id,
                organization_id=organization_id
            )
            db.session.add(quiz)
            db.session.commit()

            update_job_progress(job_id, 75, "Creating submission record")

            # Create submission
            submission = QuizSubmission(
                quiz_id=quiz.id,
                student_id=student.id,
                total_mark=grading_results['total_mark']
            )
            submission.set_raw_data(extracted_data)
            db.session.add(submission)
            db.session.commit()

            update_job_progress(job_id, 80, "Storing individual question results")

            # Store individual question results
            for question_data in grading_results['questions']:
                question = QuizQuestion(
                    quiz_submission_id=submission.id,
                    question_number=question_data['question_number'],
                    question_text=question_data['question_text'],
                    student_answer=question_data['student_answer'],
                    correct_answer=question_data.get('correct_answer', ''),
                    mark_received=question_data['mark_received'],
                    feedback=question_data['feedback']
                )
                db.session.add(question)

            db.session.commit()

            update_job_progress(job_id, 90, "Preparing email notification")

            # Queue email notification task
            send_email_task.delay(
                job.user_id,
                'quiz_completion',
                {
                    'student_name': student_name,
                    'quiz_title': quiz_title,
                    'total_mark': grading_results['total_mark'],
                    'submission_id': submission.id
                }
            )

            update_job_progress(job_id, 100, "Grading complete")

            # Prepare result data
            result = {
                'submission_id': submission.id,
                'total_mark': grading_results['total_mark'],
                'student_name': student_name,
                'quiz_title': quiz_title,
                'questions_count': len(grading_results['questions'])
            }

            job.mark_completed(result)

            logger.info(f"Successfully completed grading for job {job_id}")
            return result

    except Exception as e:
        logger.error(f"Error grading quiz for job {job_id}: {str(e)}", exc_info=True)

        with app.app_context():
            job = BackgroundJob.query.get(job_id)
            if job:
                if job.can_retry():
                    job.increment_retry()
                    logger.info(f"Retrying job {job_id} (attempt {job.retry_count + 1}/{job.max_retries})")
                    grade_quiz_task.delay(job_id)
                else:
                    job.mark_failed(str(e))
                    logger.error(f"Job {job_id} failed after {job.max_retries} attempts")

        raise


@job('low', connection=redis_conn, timeout=EMAIL_TIMEOUT)
def send_email_task(user_id, email_type, data):
    """
    Background task for sending email notifications

    Args:
        user_id: ID of user to send email to
        email_type: Type of email ('quiz_completion', 'password_reset', etc.)
        data: Email data (varies by type)
    """
    from app import create_app
    from models import User
    app = create_app()

    logger.info(f"Sending {email_type} email to user {user_id}")

    try:
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            if email_type == 'quiz_completion':
                email_service.send_quiz_submission_notification(
                    user.email,
                    user.username,
                    data['student_name'],
                    data['quiz_title'],
                    data['total_mark'],
                    data['submission_id']
                )
            else:
                logger.warning(f"Unknown email type: {email_type}")

            logger.info(f"Successfully sent {email_type} email to {user.email}")

    except Exception as e:
        logger.error(f"Error sending email to user {user_id}: {str(e)}", exc_info=True)
        # Don't retry email tasks automatically - they may be sent multiple times
        raise


@job('low', connection=redis_conn)
def cleanup_old_jobs():
    """
    Background task to clean up old completed/failed jobs

    Deletes jobs that:
    - Have status 'completed' or 'failed'
    - Are older than 24 hours
    """
    from app import create_app
    app = create_app()

    logger.info("Starting job cleanup task")

    try:
        with app.app_context():
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            old_jobs = BackgroundJob.query.filter(
                BackgroundJob.status.in_(['completed', 'failed']),
                BackgroundJob.completed_at < cutoff_time
            ).all()

            count = len(old_jobs)

            for job in old_jobs:
                db.session.delete(job)

            db.session.commit()

            logger.info(f"Cleaned up {count} old jobs")
            return {'cleaned_jobs': count}

    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {str(e)}", exc_info=True)
        raise


def enqueue_job(queue_name, task_func, *args, **kwargs):
    """
    Helper function to enqueue a job

    Args:
        queue_name: 'high', 'default', or 'low'
        task_func: The task function to execute
        *args, **kwargs: Arguments to pass to the task function

    Returns:
        RQ Job object
    """
    queues = {
        'high': high_queue,
        'default': default_queue,
        'low': low_queue
    }

    queue = queues.get(queue_name, default_queue)
    return queue.enqueue(task_func, *args, **kwargs)
