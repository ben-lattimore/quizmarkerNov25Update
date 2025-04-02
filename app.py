import os
import logging
import uuid
import time
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from image_processor import process_single_image

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", str(uuid.uuid4()))

# Configure uploads
UPLOAD_FOLDER = '/tmp/image_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

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
        
        # Process each image individually to avoid timeouts
        total_images = len(valid_files)
        logging.info(f"Starting to process {total_images} valid images")
        results = []
        
        # Determine delay between requests based on total images
        # Increase delay for more images to avoid rate limits
        base_delay = 1.0  # Base delay in seconds
        delay_multiplier = max(1, min(3, total_images / 2))  # Scale with number of images, capped at 3x
        inter_request_delay = base_delay * delay_multiplier
        
        logging.info(f"Using inter-request delay of {inter_request_delay:.1f} seconds")
        
        for i, file_info in enumerate(valid_files):
            filepath = file_info['filepath']
            original_filename = file_info['original_filename']
            
            # Log progress with percentage
            progress_pct = ((i + 1) / total_images) * 100
            logging.info(f"Processing image {i+1}/{total_images} ({progress_pct:.1f}%): {original_filename}")
            
            try:
                # Time the processing for monitoring
                process_start = time.time()
                
                # Process one image at a time with retry logic built in
                result = process_single_image(filepath, i+1)
                
                process_time = time.time() - process_start
                logging.info(f"Processed image {i+1} in {process_time:.2f} seconds")
                
                # Replace the unique filename with the original filename
                if 'filename' in result:
                    result['filename'] = original_filename
                
                # Add to results
                results.append(result)
                
                # Log success/error status
                if 'error' in result:
                    logging.warning(f"Image {i+1} processed with errors: {original_filename}")
                else:
                    logging.info(f"Successfully processed image {i+1}: {original_filename}")
                
                # Add a delay between API calls - longer for more files
                if i < total_images - 1:
                    logging.info(f"Waiting {inter_request_delay:.1f} seconds before next image")
                    time.sleep(inter_request_delay)
                
            except Exception as proc_error:
                logging.error(f"Critical error processing image {original_filename}: {proc_error}")
                
                # Add error info to results
                results.append({
                    "image_id": i + 1,
                    "filename": original_filename,
                    "error": f"Failed to process: {str(proc_error)}"
                })
        
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
