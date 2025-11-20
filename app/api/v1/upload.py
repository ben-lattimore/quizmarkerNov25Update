"""
File Upload API endpoints

Handles image and PDF uploads for quiz grading
"""

import os
import logging
import uuid
import time
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.api.v1 import api_v1_bp
from app import limiter
from image_processor import process_images
from models import Organization, BackgroundJob
from database import db

logger = logging.getLogger(__name__)


def allowed_file(filename):
    """Check if a file extension is allowed"""
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@api_v1_bp.route('/upload', methods=['POST'])
@login_required
@limiter.limit("20 per hour")  # Expensive operation - limit to prevent abuse
def upload_files():
    """
    Upload and process image files

    Form Data:
        files[]: Multiple image files

    Response JSON:
        {
            "success": true,
            "data": [
                {
                    "filename": "string",
                    "data": {
                        "handwritten_content": "string",
                        "question_count": int
                    }
                }
            ],
            "invalid_files": ["string"] (optional)
        }
    """
    # Track all saved files for reliable cleanup
    saved_filepaths = []

    try:
        # Organization verification (only for non-super-admins)
        if not current_user.is_super_admin:
            # Regular users must have an organization
            if not current_user.default_organization_id:
                logger.warning(f"User {current_user.username} has no default organization")
                return jsonify({
                    'success': False,
                    'error': 'You must belong to an organization to upload files',
                    'code': 'NO_ORGANIZATION'
                }), 403

            # Verify organization exists and is active
            organization = Organization.query.get(current_user.default_organization_id)
            if not organization:
                logger.error(f"Organization {current_user.default_organization_id} not found for user {current_user.username}")
                return jsonify({
                    'success': False,
                    'error': 'Organization not found',
                    'code': 'ORGANIZATION_NOT_FOUND'
                }), 404

            if not organization.active:
                logger.warning(f"User {current_user.username} attempted upload with inactive organization {organization.name}")
                return jsonify({
                    'success': False,
                    'error': 'Organization subscription is inactive',
                    'code': 'ORGANIZATION_INACTIVE'
                }), 403

            logger.info(f"User {current_user.username} verified for organization {organization.name}")

        # Check if files exist in the request
        if 'files[]' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No files in request',
                'code': 'NO_FILES'
            }), 400

        files = request.files.getlist('files[]')

        if not files or files[0].filename == '':
            return jsonify({
                'success': False,
                'error': 'No files selected',
                'code': 'NO_FILES_SELECTED'
            }), 400

        logger.info(f"Received {len(files)} files for processing from user {current_user.username}")

        # Check files are valid and save them
        valid_files = []
        invalid_files = []

        upload_folder = current_app.config['UPLOAD_FOLDER']

        for file in files:
            if file and allowed_file(file.filename):
                try:
                    # Create unique filename to avoid conflicts
                    original_filename = secure_filename(file.filename)
                    unique_id = str(uuid.uuid4())[:8]
                    unique_filename = f"{unique_id}_{original_filename}"
                    filepath = os.path.join(upload_folder, unique_filename)

                    # Save the file
                    file.save(filepath)

                    # Add to lists for processing and cleanup tracking
                    valid_files.append({
                        'filepath': filepath,
                        'original_filename': original_filename
                    })
                    saved_filepaths.append(filepath)

                    logger.info(f"Saved file: {original_filename} as {unique_filename}")

                except Exception as save_error:
                    logger.error(f"Error saving file {file.filename}: {save_error}")
                    invalid_files.append(file.filename)
            else:
                invalid_files.append(file.filename if file else "unknown file")

        if not valid_files:
            return jsonify({
                'success': False,
                'error': 'No valid image files provided',
                'code': 'NO_VALID_FILES'
            }), 400

        # Extract just the filepaths for processing
        total_images = len(valid_files)
        filepaths = [file_info['filepath'] for file_info in valid_files]
        original_filenames = [file_info['original_filename'] for file_info in valid_files]

        logger.info(f"Creating background job to process {total_images} images")

        # Create background job for async processing
        job_id = str(uuid.uuid4())
        job = BackgroundJob(
            id=job_id,
            job_type='upload',
            status='queued',
            user_id=current_user.id,
            organization_id=current_user.default_organization_id if not current_user.is_super_admin else None,
            progress=0,
            current_step=f'Queued {total_images} images for processing',
            expires_at=datetime.utcnow() + timedelta(hours=24)  # Job results expire in 24 hours
        )

        # Store input data (file paths and original filenames)
        job.set_input_data({
            'filepaths': filepaths,
            'original_filenames': original_filenames,
            'total_images': total_images
        })

        db.session.add(job)
        db.session.commit()

        logger.info(f"Created job {job_id} for processing {total_images} images")

        # Queue the background task
        try:
            from tasks import process_images_task
            process_images_task.delay(job_id, filepaths)
            logger.info(f"Queued process_images_task for job {job_id}")
        except Exception as queue_error:
            logger.error(f"Failed to queue background task: {queue_error}")
            # Mark job as failed
            job.mark_failed(f"Failed to queue task: {str(queue_error)}")

            # Clean up files since we can't process them
            for filepath in saved_filepaths:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as e:
                    logger.error(f"Failed to remove file {filepath}: {e}")

            return jsonify({
                'success': False,
                'error': 'Failed to queue processing job',
                'code': 'QUEUE_ERROR'
            }), 500

        # Build response with job information
        response_data = {
            'success': True,
            'job_id': job_id,
            'status': 'queued',
            'message': f'Upload successful. Processing {total_images} images in background.',
            'data': {
                'total_images': total_images,
                'job_status_url': f'/api/v1/jobs/{job_id}',
                'estimated_time': f'{total_images * 15}-{total_images * 30} seconds'
            }
        }

        if invalid_files:
            response_data['invalid_files'] = invalid_files

        logger.info(f"Upload endpoint returning job {job_id} to user")

        # Return 202 Accepted status (request accepted but processing not complete)
        return jsonify(response_data), 202

    except Exception as e:
        logger.error(f"Critical error in upload endpoint: {e}", exc_info=True)

        # Clean up any files that might have been saved
        for filepath in saved_filepaths:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as clean_e:
                logger.error(f"Failed to remove temporary file {filepath}: {clean_e}")

        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}",
            'code': 'SERVER_ERROR'
        }), 500
