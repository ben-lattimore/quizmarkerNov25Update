import os
import logging
import uuid
import time
import json
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from image_processor import process_single_image, process_images, grade_answers

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", str(uuid.uuid4()))

# Configure uploads
UPLOAD_FOLDER = '/tmp/image_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Path to the reference PDF for grading
REFERENCE_PDF_PATH = "attached_assets/Standard-2.pdf"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    # Track all saved files for reliable cleanup
    saved_filepaths = []
    
    try:
        # Check if files exist in the request
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files in request'}), 400
        
        files = request.files.getlist('files[]')
        
        if not files or files[0].filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        logging.info(f"Received {len(files)} files for processing")
        
        # Check files are valid and save them
        valid_files = []
        invalid_files = []
        
        for file in files:
            if file and allowed_file(file.filename):
                try:
                    # Create unique filename to avoid conflicts with simultaneous uploads
                    original_filename = secure_filename(file.filename)
                    unique_id = str(uuid.uuid4())[:8]
                    unique_filename = f"{unique_id}_{original_filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    # Save the file
                    file.save(filepath)
                    
                    # Add to lists for processing and cleanup tracking
                    valid_files.append({
                        'filepath': filepath,
                        'original_filename': original_filename
                    })
                    saved_filepaths.append(filepath)
                    
                    logging.info(f"Saved file: {original_filename} as {unique_filename}")
                    
                except Exception as save_error:
                    logging.error(f"Error saving file {file.filename}: {save_error}")
                    invalid_files.append(file.filename)
            else:
                invalid_files.append(file.filename if file else "unknown file")
        
        if not valid_files:
            return jsonify({'error': 'No valid image files provided'}), 400
        
        # Extract just the filepaths for processing
        total_images = len(valid_files)
        filepaths = [file_info['filepath'] for file_info in valid_files]
        original_filenames = [file_info['original_filename'] for file_info in valid_files]
        
        logging.info(f"Processing {total_images} images with optimized processor")
        
        # Process all images with our improved process_images function
        # which handles delays and retries internally
        process_start = time.time()
        results = process_images(filepaths)
        process_time = time.time() - process_start
        
        logging.info(f"Processed {len(results)} images in {process_time:.2f} seconds")
        
        # Replace unique filenames with original ones in results
        for i, result in enumerate(results):
            if i < len(original_filenames) and 'filename' in result:
                result['filename'] = original_filenames[i]
        
        # Log success/error status
        success_count = sum(1 for r in results if "error" not in r)
        logging.info(f"Successfully processed {success_count}/{total_images} images")
        
        # Check if we have any results at all
        if not results:
            return jsonify({'error': 'Failed to process any images'}), 500
        
        # Build response
        response_data = {
            'success': True,
            'results': results
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
                logging.error(f"Failed to remove temporary file {filepath}: {e}")
        
        logging.info(f"Cleaned up {cleanup_count} temporary files")
        return jsonify(response_data)
    
    except Exception as e:
        logging.error(f"Critical error in upload endpoint: {e}", exc_info=True)
        
        # Clean up any files that might have been saved
        for filepath in saved_filepaths:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as clean_e:
                logging.error(f"Failed to remove temporary file {filepath}: {clean_e}")
        
        return jsonify({'error': f"Server error: {str(e)}"}), 500

@app.route('/grade', methods=['POST'])
def grade_answers_route():
    """
    Grade handwritten answers against the reference PDF
    
    Expects a JSON payload with the 'data' field containing the extracted text results
    """
    try:
        # Verify we have data in the request
        if not request.json or 'data' not in request.json:
            return jsonify({'error': 'No data provided. Expected JSON with "data" field.'}), 400
        
        # Get the extracted data
        extracted_data = request.json['data']
        
        if not extracted_data or not isinstance(extracted_data, list):
            return jsonify({'error': 'Invalid data format. Expected a list of extraction results.'}), 400
        
        # Filter out any failed extractions
        valid_extractions = [item for item in extracted_data if "error" not in item]
        
        if not valid_extractions:
            return jsonify({'error': 'No valid extractions to grade.'}), 400
        
        logging.info(f"Grading {len(valid_extractions)} valid extractions")
        
        # Check if the reference PDF exists
        if not os.path.exists(REFERENCE_PDF_PATH):
            return jsonify({'error': 'Reference PDF not found.'}), 500
        
        # Grade the answers
        try:
            grading_start = time.time()
            grading_results = grade_answers(valid_extractions, REFERENCE_PDF_PATH)
            grading_time = time.time() - grading_start
            
            logging.info(f"Graded answers in {grading_time:.2f} seconds")
            
            # Return the grading results
            return jsonify({
                'success': True,
                'results': grading_results
            })
            
        except Exception as grading_error:
            logging.error(f"Error during grading: {grading_error}", exc_info=True)
            return jsonify({'error': f"Grading failed: {str(grading_error)}"}), 500
    
    except Exception as e:
        logging.error(f"Critical error in grade endpoint: {e}", exc_info=True)
        return jsonify({'error': f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
