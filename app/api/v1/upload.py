"""
File Upload API endpoints

Handles image and PDF uploads for quiz grading
"""

import os
import logging
import uuid
import time
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.api.v1 import api_v1_bp
from app import limiter
from image_processor import process_images

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

        logger.info(f"Processing {total_images} images with optimized processor")

        # Process all images
        process_start = time.time()
        results = process_images(filepaths)
        process_time = time.time() - process_start

        logger.info(f"Processed {len(results)} images in {process_time:.2f} seconds")

        # Replace unique filenames with original ones in results
        for i, result in enumerate(results):
            if i < len(original_filenames) and 'filename' in result:
                result['filename'] = original_filenames[i]

        # Log success/error status
        success_count = sum(1 for r in results if "error" not in r)
        logger.info(f"Successfully processed {success_count}/{total_images} images")

        # Check if we have any results at all
        if not results:
            return jsonify({
                'success': False,
                'error': 'Failed to process any images',
                'code': 'PROCESSING_FAILED'
            }), 500

        # Build response
        response_data = {
            'success': True,
            'data': results
        }

        if invalid_files:
            response_data['invalid_files'] = invalid_files

        # Clean up all uploaded files
        cleanup_count = 0
        for filepath in saved_filepaths:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    cleanup_count += 1
            except Exception as e:
                logger.error(f"Failed to remove temporary file {filepath}: {e}")

        logger.info(f"Cleaned up {cleanup_count} temporary files")
        return jsonify(response_data), 200

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
