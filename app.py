import os
import logging
import uuid
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from image_processor import process_single_image, process_images, grade_answers

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", str(uuid.uuid4()))

# Configure the database connection
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    logging.info(f"Using database URL: {DATABASE_URL}")
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
else:
    logging.error("DATABASE_URL environment variable is not set")
    # Fallback to SQLite for development (not recommended for production)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz_app.db"
    
db = SQLAlchemy(app)

# Import models after database initialization to avoid circular imports
from models import Student, Quiz, QuizSubmission, QuizQuestion

# Create all database tables
with app.app_context():
    db.create_all()
    logging.info("Database tables created or verified")

# Configure uploads
UPLOAD_FOLDER = '/tmp/image_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Path to the reference PDFs for grading
REFERENCE_PDF_DIR = "attached_assets"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/standards')
def get_standards():
    """
    Return a list of available standards in the attached_assets directory
    """
    try:
        available_standards = []
        # Look for files matching the pattern "Standard-*.pdf"
        for file in os.listdir(REFERENCE_PDF_DIR):
            if file.startswith("Standard-") and file.endswith(".pdf"):
                # Extract the standard number from the filename
                standard_num = file.replace("Standard-", "").replace(".pdf", "")
                try:
                    standard_num = int(standard_num)
                    available_standards.append({
                        "id": standard_num,
                        "name": f"Standard {standard_num}",
                        "file": file
                    })
                except ValueError:
                    # Skip files if the numbering isn't an integer
                    continue
        
        # Sort standards by their number
        available_standards.sort(key=lambda s: s["id"])
        
        return jsonify({
            "success": True,
            "standards": available_standards
        })
    except Exception as e:
        logging.error(f"Error getting standards: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to get standards"
        }), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/quizzes')
def list_quizzes():
    """List all quiz submissions in the database"""
    try:
        # Get all quiz submissions, ordered by submission date (newest first)
        submissions = QuizSubmission.query.order_by(QuizSubmission.submission_date.desc()).all()
        
        # Format the data for rendering
        quiz_data = []
        for submission in submissions:
            quiz_data.append({
                'id': submission.id,
                'quiz_title': submission.quiz.title,
                'standard_id': submission.quiz.standard_id,
                'student_name': submission.student.name,
                'submission_date': submission.submission_date.strftime('%Y-%m-%d %H:%M:%S'),
                'total_mark': submission.total_mark,
                'question_count': len(submission.questions)
            })
        
        return render_template('quizzes.html', quizzes=quiz_data)
    except Exception as e:
        logging.error(f"Error listing quizzes: {e}")
        return render_template('error.html', error=f"Error listing quizzes: {str(e)}")

@app.route('/quiz/<int:quiz_id>')
def view_quiz(quiz_id):
    """View a specific quiz submission"""
    try:
        # Get the quiz submission
        submission = QuizSubmission.query.get_or_404(quiz_id)
        
        # Get questions for this submission
        questions = submission.questions
        
        # Format the data for rendering
        quiz_data = {
            'id': submission.id,
            'quiz_title': submission.quiz.title,
            'standard_id': submission.quiz.standard_id,
            'student_name': submission.student.name,
            'submission_date': submission.submission_date.strftime('%Y-%m-%d %H:%M:%S'),
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
        
        return render_template('quiz_detail.html', quiz=quiz_data)
    except Exception as e:
        logging.error(f"Error viewing quiz {quiz_id}: {e}")
        return render_template('error.html', error=f"Error viewing quiz {quiz_id}: {str(e)}")

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
    Grade handwritten answers against the selected reference PDF
    
    Expects a JSON payload with:
    - 'data' field containing the extracted text results
    - 'standard_id' field specifying which standard PDF to use for grading
    - 'student_name' field containing the student's name
    - 'quiz_title' field containing a title for the quiz (optional)
    """
    try:
        # Verify we have data in the request
        if not request.json or 'data' not in request.json:
            return jsonify({'error': 'No data provided. Expected JSON with "data" field.'}), 400
        
        # Get the extracted data
        extracted_data = request.json['data']
        
        if not extracted_data or not isinstance(extracted_data, list):
            return jsonify({'error': 'Invalid data format. Expected a list of extraction results.'}), 400
        
        # Get the standard ID (default to 2 if not provided for backward compatibility)
        standard_id = request.json.get('standard_id', 2)
        student_name = request.json.get('student_name', 'Unknown Student')
        quiz_title = request.json.get('quiz_title', f'Standard {standard_id} Quiz')
        
        logging.info(f"Request JSON: {request.json}")
        logging.info(f"Selected standard_id: {standard_id}, Student: {student_name}")
        
        # Determine the PDF path
        pdf_filename = f"Standard-{standard_id}.pdf"
        pdf_path = os.path.join(REFERENCE_PDF_DIR, pdf_filename)
        logging.info(f"Using PDF path: {pdf_path}")
        
        # Filter out any failed extractions
        valid_extractions = [item for item in extracted_data if "error" not in item]
        
        if not valid_extractions:
            return jsonify({'error': 'No valid extractions to grade.'}), 400
        
        logging.info(f"Grading {len(valid_extractions)} valid extractions against Standard {standard_id}")
        
        # Check if the reference PDF exists
        if not os.path.exists(pdf_path):
            return jsonify({'error': f'Reference PDF for Standard {standard_id} not found.'}), 500
        
        # Grade the answers
        try:
            grading_start = time.time()
            grading_results = grade_answers(valid_extractions, pdf_path)
            grading_time = time.time() - grading_start
            
            logging.info(f"Graded answers in {grading_time:.2f} seconds")
            
            # Store the quiz results in the database
            try:
                # Find or create the student
                student = Student.query.filter_by(name=student_name).first()
                if not student:
                    student = Student(name=student_name)
                    db.session.add(student)
                    logging.info(f"Created new student: {student_name}")
                
                # Find or create the quiz
                quiz = Quiz.query.filter_by(title=quiz_title, standard_id=standard_id).first()
                if not quiz:
                    quiz = Quiz(title=quiz_title, standard_id=standard_id)
                    db.session.add(quiz)
                    logging.info(f"Created new quiz: {quiz_title} (Standard {standard_id})")
                
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
                
                for result in grading_results.get('results', []):
                    # Extract the data for each question
                    question_data = result.get('question_data', {})
                    
                    # Create a new question record
                    question = QuizQuestion(
                        submission=quiz_submission,
                        question_number=question_data.get('question_number', 0),
                        question_text=question_data.get('title', ''),
                        student_answer=question_data.get('student_response', ''),
                        correct_answer=question_data.get('reference_answer', ''),
                        mark_received=result.get('grade', {}).get('score', 0),
                        feedback=result.get('grade', {}).get('feedback', '')
                    )
                    db.session.add(question)
                    
                    # Add to total mark
                    total_mark += question.mark_received
                
                # Update the total mark on the submission
                quiz_submission.total_mark = total_mark
                db.session.add(quiz_submission)
                
                # Commit the transaction
                db.session.commit()
                logging.info(f"Saved quiz submission to database: ID {quiz_submission.id}, Total Mark: {total_mark}")
                
            except Exception as db_error:
                db.session.rollback()
                logging.error(f"Database error: {db_error}", exc_info=True)
                # Continue with the response even if database storage fails
                logging.warning("Continuing without database storage due to error")
            
            # Return the grading results
            return jsonify({
                'success': True,
                'standard_id': standard_id,
                'student_name': student_name,
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
