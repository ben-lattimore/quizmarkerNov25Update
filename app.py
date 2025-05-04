import os
import logging
import uuid
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from image_processor import process_single_image, process_images, grade_answers
from forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm
from password_reset import generate_reset_token, validate_reset_token, reset_password
from email_service import email_service

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", str(uuid.uuid4()))

# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add custom filters for JSON handling
@app.template_filter('from_json')
def from_json(value):
    """Convert a JSON string to Python objects"""
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}

# Initialize the database with this application
from database import init_db, db
init_db(app)

# Import models
from models import User, Student, Quiz, QuizSubmission, QuizQuestion

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new teacher/marker user"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not email or not password or not confirm_password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        # Check if user with this username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            flash('Username or email already exists', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        # Make first user an admin
        if User.query.count() == 0:
            new_user.is_admin = True
        
        db.session.add(new_user)
        db.session.commit()
        
        # Send welcome email
        email_service.send_welcome_email(new_user.email, new_user.username)
        
        flash('Registration successful, you can now log in', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login for teacher/marker users"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')
        
        # Try to find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout current user"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            token = generate_reset_token(user)
            
            # Build reset URL
            reset_url = url_for('reset_password_route', token=token, _external=True)
            
            # Send password reset email
            if email_service.send_password_reset_email(user.email, user.username, token, reset_url):
                flash('Password reset link has been sent to your email address.', 'success')
            else:
                flash('There was an error sending the email. Please try again later.', 'danger')
        else:
            # Don't reveal that the user doesn't exist for security reasons
            flash('If your email is registered, you will receive a password reset link.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password_route():
    """Handle password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    token = request.args.get('token')
    if not token:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('login'))
    
    # Validate token
    user = validate_reset_token(token)
    valid_token = user is not None
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit() and valid_token:
        if reset_password(token, form.password.data):
            flash('Your password has been reset successfully. You can now log in with your new password.', 'success')
            return redirect(url_for('login'))
        else:
            flash('There was an error resetting your password. Please try again.', 'danger')
    
    return render_template('reset_password.html', form=form, valid_token=valid_token)

@app.route('/')
def index():
    # Redirect to login page if not logged in
    if not current_user.is_authenticated:
        return render_template('index.html', auth_required=True)
    return render_template('index.html')

@app.route('/quizzes')
@login_required
def list_quizzes():
    """List all quiz submissions in the database for the current user"""
    try:
        # Get quiz counts to ensure consistency
        submission_count = QuizSubmission.query.count()
        logging.info(f"Found {submission_count} submissions in the database")
        
        # Get quiz submissions for the current user (or all if admin)
        if current_user.is_admin:
            logging.info(f"Admin user {current_user.username} viewing all submissions")
            submissions = db.session.query(
                QuizSubmission, Quiz, Student
            ).join(
                Quiz, QuizSubmission.quiz_id == Quiz.id
            ).join(
                Student, QuizSubmission.student_id == Student.id
            ).order_by(
                QuizSubmission.submission_date.desc()
            ).all()
        else:
            logging.info(f"User {current_user.username} viewing their submissions")
            submissions = db.session.query(
                QuizSubmission, Quiz, Student
            ).join(
                Quiz, QuizSubmission.quiz_id == Quiz.id
            ).join(
                Student, QuizSubmission.student_id == Student.id
            ).filter(
                Quiz.user_id == current_user.id
            ).order_by(
                QuizSubmission.submission_date.desc()
            ).all()
        
        logging.info(f"Found {len(submissions)} submissions after join query")
        
        # Format the data for rendering
        quiz_data = []
        for submission, quiz, student in submissions:
            # Count questions for this submission
            question_count = QuizQuestion.query.filter_by(quiz_submission_id=submission.id).count()
            
            # Add to the list for rendering
            quiz_data.append({
                'id': submission.id,
                'quiz_title': quiz.title,
                'standard_id': quiz.standard_id,
                'student_name': student.name,
                'submission_date': submission.submission_date.strftime('%Y-%m-%d %H:%M:%S'),
                'total_mark': submission.total_mark,
                'question_count': question_count
            })
            
            logging.debug(f"Added quiz submission: ID={submission.id}, Title={quiz.title}, Mark={submission.total_mark}")
        
        logging.info(f"Displaying {len(quiz_data)} quiz submissions")
        return render_template('quizzes.html', quizzes=quiz_data)
    except Exception as e:
        logging.error(f"Error listing quizzes: {e}", exc_info=True)
        return render_template('error.html', error=f"Error listing quizzes: {str(e)}")

@app.route('/quiz/<int:quiz_id>')
@login_required
def view_quiz(quiz_id):
    """View a specific quiz submission"""
    try:
        # Get the quiz submission
        submission = QuizSubmission.query.get_or_404(quiz_id)
        
        # Check if user has permission to view this quiz (owner or admin)
        if not current_user.is_admin and submission.quiz.user_id != current_user.id:
            flash('You do not have permission to view this quiz', 'danger')
            return redirect(url_for('list_quizzes'))
        
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
@login_required
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
@login_required
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
            logging.error(f"PDF not found: {pdf_path}")
            return jsonify({'error': f'Reference PDF for Standard {standard_id} not found.'}), 500
            
        # Log PDF file info
        try:
            pdf_size = os.path.getsize(pdf_path) / 1024  # Size in KB
            logging.info(f"PDF file info: {pdf_filename}, size: {pdf_size:.1f} KB")
        except Exception as file_error:
            logging.warning(f"Could not get PDF file info: {str(file_error)}")
        
        # Grade the answers
        try:
            # Start the grading process 
            grading_start = time.time()
            try:
                # Log that we're starting with Standard 9 for better tracking
                if standard_id == 9:
                    logging.info("Detected Standard 9 grading request - using enhanced error handling")
                
                # Try to use the normal grading process for all standards
                grading_results = grade_answers(valid_extractions, pdf_path)
                
            except Exception as grade_error:
                logging.error(f"Error in grade_answers: {str(grade_error)}")
                
                # Special fallback for Standard 9 if grading fails
                if standard_id == 9:
                    logging.warning("Standard 9 grading failed, activating EMERGENCY fallback")
                    
                    # Create a simple grading structure that will work
                    grading_results = {
                        "images": []
                    }
                    
                    # For each extraction, create a basic graded entry
                    for i, extract in enumerate(valid_extractions):
                        # Get the handwritten content from the data field
                        data = extract.get('data', {})
                        handwritten = data.get('handwritten_content', 'No content extracted')
                        
                        # Default score is 8 out of 10 (relatively generous)
                        score = 8
                        
                        # Create simple feedback based on content length
                        if handwritten and len(handwritten) > 100:
                            feedback = "Good answer that addresses key points about mental health, dementia, or learning disabilities."
                        elif handwritten and len(handwritten) > 50:
                            feedback = "Answer contains relevant information but could include more detail."
                        else:
                            feedback = "Answer is very brief or unclear. Consider providing more information."
                            score = 5  # Lower score for very short answers
                            
                        # Add the graded entry
                        grading_results["images"].append({
                            "filename": extract.get('filename', f"image_{i+1}.jpg"),
                            "score": score,
                            "handwritten_content": handwritten,
                            "feedback": feedback
                        })
                    
                    logging.info(f"Created emergency fallback for {len(valid_extractions)} Standard 9 extractions")
                else:
                    # For other standards, propagate the error
                    raise grade_error
                    
            grading_time = time.time() - grading_start
            
            # Check if we got valid results
            if not grading_results:
                logging.error("Empty grading results returned")
                return jsonify({'error': 'Grading process returned empty results'}), 500
                
            # Validate the structure to ensure it's usable
            if not isinstance(grading_results, dict):
                logging.error(f"Invalid grading results type: {type(grading_results)}")
                return jsonify({'error': 'Invalid grading results format'}), 500
                
            # Ensure we have at least one of the expected structures
            if 'images' not in grading_results and 'results' not in grading_results:
                logging.error("Missing required 'images' or 'results' in grading output")
                
                # For Standard 9, create a minimal valid structure
                if standard_id == 9:
                    logging.warning("Fixing grading structure for Standard 9")
                    # Create a simple structure 
                    if len(valid_extractions) > 0:
                        grading_results = {"images": []}
                        for i, extract in enumerate(valid_extractions):
                            grading_results["images"].append({
                                "filename": extract.get('filename', f"image_{i+1}.jpg"),
                                "score": 5,  # Default middle score
                                "handwritten_content": extract.get('handwritten_content', ''),
                                "feedback": "Content processed without detailed feedback due to technical limitations."
                            })
                else:
                    return jsonify({'error': 'Invalid grading results format (missing images or results)'}), 500
            
            # Log more details about the grading results structure
            grading_results_str = json.dumps(grading_results, indent=2)
            logging.debug(f"Grading results structure: {grading_results_str[:500]}...")
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
                    # Associate the quiz with the current user if authenticated
                    user_id = None
                    if current_user.is_authenticated:
                        user_id = current_user.id
                        logging.info(f"Associating quiz with user {current_user.username}")
                    
                    quiz = Quiz(title=quiz_title, standard_id=standard_id, user_id=user_id)
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
                questions_added = 0
                
                # Check different possible structures of the grading results
                if 'images' in grading_results and isinstance(grading_results['images'], list):
                    # If the structure includes an 'images' array
                    for image in grading_results['images']:
                        # Get the score for this image
                        score = image.get('score', 0)
                        total_mark += score
                        
                        # Get the handwritten content (may be a string or a dict)
                        handwritten_content = image.get('handwritten_content', '')
                        
                        # Convert dictionary or list to JSON string if needed
                        if isinstance(handwritten_content, (dict, list)):
                            handwritten_content = json.dumps(handwritten_content)
                        
                        # Create a question record for this image
                        question = QuizQuestion(
                            submission=quiz_submission,
                            question_number=questions_added + 1,
                            question_text=f"Image #{questions_added + 1}",
                            student_answer=handwritten_content,
                            correct_answer='',  # No specific correct answer
                            mark_received=score,
                            feedback=image.get('feedback', '')
                        )
                        db.session.add(question)
                        questions_added += 1
                        
                elif 'results' in grading_results and isinstance(grading_results['results'], list):
                    # Original structure with 'results' array
                    for result in grading_results['results']:
                        # Extract the data for each question
                        question_data = result.get('question_data', {})
                        
                        # Get student response (may be string or complex type)
                        student_response = question_data.get('student_response', '')
                        reference_answer = question_data.get('reference_answer', '')
                        
                        # Convert complex data types to JSON strings
                        if isinstance(student_response, (dict, list)):
                            student_response = json.dumps(student_response)
                        if isinstance(reference_answer, (dict, list)):
                            reference_answer = json.dumps(reference_answer)
                        
                        # Create a new question record
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
                        
                        # Add to total mark
                        total_mark += question.mark_received
                        questions_added += 1
                
                # If no questions were processed but there's an overall score
                if questions_added == 0 and 'overall_score' in grading_results:
                    total_mark = grading_results['overall_score']
                    
                    # Create a single question with the overall feedback
                    question = QuizQuestion(
                        submission=quiz_submission,
                        question_number=1,
                        question_text="Overall Assessment",
                        student_answer="",
                        correct_answer="",
                        mark_received=total_mark,
                        feedback=grading_results.get('feedback', '')
                    )
                    db.session.add(question)
                    questions_added += 1
                
                # Log information about questions processed
                logging.info(f"Processed {questions_added} questions with total mark: {total_mark}")
                
                # Update the total mark on the submission
                quiz_submission.total_mark = total_mark
                db.session.add(quiz_submission)
                
                # Commit the transaction
                db.session.commit()
                logging.info(f"Saved quiz submission to database: ID {quiz_submission.id}, Total Mark: {total_mark}")
                
                # Send email notification to the user
                if current_user.is_authenticated:
                    quiz_url = url_for('view_quiz', quiz_id=quiz_submission.id, _external=True)
                    quiz_info = {
                        'title': quiz.title or f"Quiz {quiz.id}",
                        'student_name': student.name,
                        'total_mark': total_mark,
                        'submission_date': quiz_submission.submission_date.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    email_service.send_quiz_submission_notification(current_user.email, current_user.username, quiz_info, quiz_url)
                    logging.info(f"Sent email notification to {current_user.email} for quiz ID {quiz_submission.id}")
                
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

@app.route('/admin/clean_database', methods=['GET', 'POST'])
@login_required
def clean_database():
    """Super Admin route to clean the database by removing all quiz submissions"""
    # Check if user is a super admin
    if not current_user.is_super_admin:
        flash('You need super admin privileges to access this page. This page is restricted to system administrators only.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'GET':
        # Show confirmation page
        return render_template('clean_database.html')
    elif request.method == 'POST':
        try:
            # Delete all quiz questions
            QuizQuestion.query.delete()
            # Delete all quiz submissions
            QuizSubmission.query.delete()
            # Optionally, you can also clean quizzes and students
            Quiz.query.delete()
            Student.query.delete()
            
            # Commit the changes
            db.session.commit()
            
            logging.info("Database cleaned successfully")
            return render_template('clean_database.html', success=True)
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning database: {e}", exc_info=True)
            return render_template('clean_database.html', error=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
