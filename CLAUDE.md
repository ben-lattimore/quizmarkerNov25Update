# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuizMarker is a Flask-based web application that uses AI (OpenAI GPT-4.1-mini) to automatically grade handwritten quiz answers against reference PDFs for The Care Certificate standards. The system extracts text from uploaded images using vision models, compares answers against reference material, and provides scores and feedback.

## Core Commands

### Development
```bash
# Run development server (loads .env automatically via python-dotenv)
python main.py

# Run with Gunicorn (production-style)
gunicorn --bind 0.0.0.0:5001 --reuse-port --reload main:app

# Note: Ensure .env file exists with required variables (see .env.example)
# The app now uses python-dotenv to automatically load environment variables
```

### Database Management
```bash
# Create a super admin user
python set_super_admin.py

# Add a super admin (alternative method)
python add_super_admin.py
```

### Testing
```bash
# Test OpenAI GPT-4.1-mini model
python test_gpt41_mini.py

# Test PDF extraction functionality
python test_pdf_extraction.py
```

## Architecture

### Application Structure

**Entry Point**: `main.py` → imports and runs the Flask app from `app.py`
- Uses `python-dotenv` to automatically load environment variables from `.env` file
- Ensures environment variables are available before importing app modules

**Frontend** (`static/js/main.js`):
- Drag-and-drop file upload support
- Stores selected files in memory for both drag-drop and browse button workflows
- Sequential image processing to avoid API timeouts
- Real-time progress tracking during upload and grading

**Core Flask App** (`app.py`):
- Main application with all routes and request handling
- Authentication using Flask-Login
- File upload handling (supports images and PDFs up to 16MB)
- Quiz grading orchestration
- Database operations and user management

**Image Processing Pipeline** (`image_processor.py`):
- **Text Extraction**: `extract_text_from_image()` uses GPT-4.1-mini vision to extract structured text from images
- **Batch Processing**: `process_images()` handles multiple images sequentially with delays to prevent API rate limits
- **Grading Strategies**:
  - **Combined approach** (preferred): `grade_combined_document()` grades all answers in a single API call for efficiency
  - **Fallback approach**: Individual grading per answer if combined approach fails
  - **Standard 9 special handling**: Has hardcoded fallback content and emergency grading logic due to API reliability issues

**Database Layer** (`database.py` + `models.py`):
- SQLAlchemy ORM with PostgreSQL (or SQLite fallback)
- Models: `User`, `Student`, `Quiz`, `QuizSubmission`, `QuizQuestion`
- Relationships: Users → Quizzes → Submissions → Questions

### Key Workflows

**Quiz Upload & Grading Flow**:
1. User uploads images via `/upload` endpoint
2. Files saved temporarily with unique filenames to `/tmp/image_uploads`
3. `process_images()` extracts text from each image using GPT-4.1-mini vision
4. User selects standard and submits to `/grade` endpoint
5. Reference PDF loaded from `attached_assets/Standard-{id}.pdf`
6. Grading attempts combined approach first, falls back to individual grading
7. Results stored in database (Student, Quiz, QuizSubmission, QuizQuestion)
8. Email notification sent to user
9. Temporary files cleaned up

**Authentication Flow**:
- Registration: Creates user, first user becomes admin
- Login: Flask-Login session management
- Password reset: Token-based via email (SendGrid)
- Admin routes: Check `current_user.is_admin` or `current_user.is_super_admin`

### OpenAI API Configuration

**Model**: `gpt-4.1-mini` (changed from gpt-4o per user request)

**Timeouts & Retries**:
- Timeout: 90 seconds for API calls
- Max retries: 2 (3 total attempts)
- Retry delay: 3 seconds with exponential backoff
- HTTP/2 enabled for better performance
- Custom httpx client with connection pooling

**Rate Limiting Strategy**:
- Sequential processing of images (not parallel)
- 2-second delay between image processing API calls
- Special handling for Standard 9 with reduced token limits

### Critical Implementation Details

**Standard 9 Special Handling**:
Standard 9 (Mental Health, Dementia, Learning Disabilities) has experienced OpenAI API reliability issues. The code includes:
- Hardcoded fallback content for reference material
- Emergency fallback grading with default scores (5-8 out of 10)
- Reduced max_tokens (2500 vs 4000) to prevent timeouts
- Shorter system prompts
- Manual fallback mode via URL parameter `force_fallback=true`

**File Upload Security**:
- Allowed extensions: png, jpg, jpeg, gif, webp, pdf
- Max file size: 16MB
- Files sanitized with `secure_filename()`
- Unique filenames using UUID to prevent conflicts
- Automatic cleanup after processing

**Database Sessions**:
- Use `db.session.add()` and `db.session.commit()` for writes
- Always wrap in try/except with `db.session.rollback()` on errors
- Complex queries use joined queries for efficiency
- JSON data stored as text strings with helper methods (`set_raw_data()`, `get_raw_data()`)

## Environment Variables

Required:
- `OPENAI_API_KEY` - OpenAI API access
- `DATABASE_URL` - PostgreSQL connection string
- `SESSION_SECRET` - Flask session secret
- `SENDGRID_API_KEY` - Email service (optional but needed for password reset)

## Reference Materials

Reference PDFs are stored in `attached_assets/` directory with naming convention: `Standard-{number}.pdf`

The `/standards` endpoint dynamically discovers available standards from this directory.

## Common Patterns

**Adding a new route with authentication**:
```python
@app.route('/new-route')
@login_required
def new_route():
    # Check permissions if needed
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    # Route logic here
```

**Processing uploaded files**:
- Always use `secure_filename()` for filenames
- Add UUID prefix for uniqueness
- Track all saved files for cleanup
- Use try/finally to ensure cleanup happens

**Making OpenAI API calls**:
- Always wrap in retry logic for timeout errors
- Log attempt numbers and timing
- Use `response_format={"type": "json_object"}` for structured responses
- Validate JSON structure after parsing
- Consider combined approach for batch operations

**Database operations**:
- Import models: `from models import User, Student, Quiz, QuizSubmission, QuizQuestion`
- Use relationships to avoid N+1 queries
- Always handle exceptions with rollback
- Check permissions before allowing access to data
