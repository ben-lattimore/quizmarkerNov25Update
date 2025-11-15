# API Endpoints Documentation

This document provides a comprehensive reference for all HTTP endpoints in the QuizMarker application.

## Base URL
- **Local Development**: `http://localhost:5000`
- **Production**: TBD (will be Railway deployment URL)

## Authentication

The application uses Flask-Login for session-based authentication. Protected routes require an authenticated user session.

## Endpoints Overview

### Public Endpoints
- `GET /` - Home page
- `GET/POST /register` - User registration
- `GET/POST /login` - User login
- `GET/POST /forgot-password` - Request password reset
- `GET/POST /reset-password` - Reset password with token
- `GET /standards` - Get available quiz standards (JSON)

### Protected Endpoints (Require Login)
- `GET /logout` - User logout
- `GET /quizzes` - List all quiz submissions
- `GET /quiz/<id>` - View specific quiz details
- `POST /upload` - Upload and process quiz images
- `POST /grade` - Grade quiz answers against reference material

### Admin Endpoints (Require Super Admin)
- `GET/POST /admin/clean_database` - Clean database (super admin only)

---

## Detailed Endpoint Documentation

### Public Endpoints

#### GET/POST /register
**Purpose**: Register a new teacher/marker account

**Methods**: `GET`, `POST`

**Authentication**: None (public)

**GET Response**:
- Returns HTML registration form
- If already authenticated, redirects to home page

**POST Request**:
```
Content-Type: application/x-www-form-urlencoded

username=string
email=string
password=string
confirm_password=string
```

**POST Response**:
- Success: Redirect to login page with success message
- Failure: Re-render form with error message

**Validation**:
- Username must be unique
- Email must be unique and valid format
- Password and confirm_password must match
- First registered user becomes admin automatically

**Notes**:
- Password is hashed using Werkzeug security
- Flash messages used for user feedback

---

#### GET/POST /login
**Purpose**: Authenticate teacher/marker users

**Methods**: `GET`, `POST`

**Authentication**: None (public)

**GET Response**:
- Returns HTML login form
- If already authenticated, redirects to home page

**POST Request**:
```
Content-Type: application/x-www-form-urlencoded

username=string  (can be username or email)
password=string
remember=boolean (optional)
```

**POST Response**:
- Success: Redirect to home page
- Failure: Re-render form with error message

**Notes**:
- Accepts either username or email for login
- "Remember me" functionality via Flask-Login
- Session-based authentication

---

#### GET /logout
**Purpose**: End current user session

**Methods**: `GET`

**Authentication**: Required (`@login_required`)

**Response**:
- Redirect to login page

---

#### GET/POST /forgot-password
**Purpose**: Request password reset email

**Methods**: `GET`, `POST`

**Authentication**: None (public)

**GET Response**:
- Returns HTML form for email input
- If authenticated, redirects to home page

**POST Request**:
```
Content-Type: application/x-www-form-urlencoded

email=string
```

**POST Response**:
- Always shows success message (security best practice)
- If email exists: Sends reset email via SendGrid
- If email doesn't exist: Silent failure, shows same success message

**Email Content**:
- Contains reset link: `/reset-password?token=<token>`
- Token is time-limited

**Notes**:
- Requires `SENDGRID_API_KEY` environment variable
- Uses `password_reset.py` module for token generation

---

#### GET/POST /reset-password
**Purpose**: Reset password using emailed token

**Methods**: `GET`, `POST`

**Authentication**: None (public, token-based)

**GET Parameters**:
```
?token=string (required)
```

**GET Response**:
- Returns HTML form for new password input
- If token invalid/expired: Redirect to forgot-password with error
- If authenticated: Redirects to home page

**POST Request**:
```
Content-Type: application/x-www-form-urlencoded

token=string (from URL or form)
password=string
confirm_password=string
```

**POST Response**:
- Success: Redirect to login with success message
- Failure: Re-render form with error message

**Validation**:
- Token must be valid and not expired
- Password and confirm_password must match

---

#### GET /standards
**Purpose**: Get list of available Care Certificate standards

**Methods**: `GET`

**Authentication**: None (public)

**Response**:
```json
{
  "standards": [
    {"id": "1", "name": "Standard 1"},
    {"id": "2", "name": "Standard 2"},
    ...
    {"id": "15", "name": "Standard 15"}
  ]
}
```

**Content-Type**: `application/json`

**Notes**:
- Scans `attached_assets/` directory for `Standard-{number}.pdf` files
- Returns only standards with existing PDF files
- Used to dynamically populate standard selector in UI

---

### Protected Endpoints

#### GET /
**Purpose**: Application home page / quiz upload interface

**Methods**: `GET`

**Authentication**: None (but shows different UI based on auth status)

**Response**:
- If authenticated: Returns quiz upload interface
- If not authenticated: Returns login prompt with CTA buttons

**Template**: `index.html`

---

#### GET /quizzes
**Purpose**: List all quiz submissions for current user

**Methods**: `GET`

**Authentication**: Required (`@login_required`)

**Response**:
- Returns HTML page with table of all quiz submissions
- Shows: Quiz title, student name, standard, total mark, date

**Query**:
```python
Quiz.query.filter_by(user_id=current_user.id)
           .order_by(Quiz.id.desc())
```

**Template**: `quizzes.html`

**Notes**:
- Only shows quizzes marked by the current user
- Ordered by most recent first (descending ID)

---

#### GET /quiz/<quiz_id>
**Purpose**: View detailed results for a specific quiz submission

**Methods**: `GET`

**Authentication**: Required (`@login_required`)

**URL Parameters**:
- `quiz_id` (integer) - The quiz submission ID

**Response**:
- Success: Returns detailed quiz view with all questions, answers, marks, and feedback
- Not found: 404 error
- Access denied: Flash error and redirect to quizzes page

**Authorization**:
- User must be the marker who created the quiz
- OR user must be a super admin

**Template**: `quiz_detail.html`

**Data Provided**:
- Quiz metadata (title, student, standard, total mark, date)
- All questions with:
  - Question number and text
  - Student's answer
  - Model answer
  - Marks received
  - Detailed feedback

---

#### POST /upload
**Purpose**: Upload quiz images and extract text using AI vision model

**Methods**: `POST`

**Authentication**: Required (`@login_required`)

**Request**:
```
Content-Type: multipart/form-data

files[]: File[] (images: JPG, PNG, GIF, WEBP, PDF)
```

**File Constraints**:
- Max size: 16MB per file
- Allowed extensions: png, jpg, jpeg, gif, webp, pdf
- Multiple files supported

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "filename": "quiz-001.jpg",
      "data": {
        "questions": [
          {
            "question_number": 1,
            "question_text": "What is duty of care?",
            "answer": "Student's handwritten response..."
          },
          ...
        ]
      }
    },
    ...
  ]
}
```

**Error Response**:
```json
{
  "error": "Error message describing what went wrong"
}
```

**Processing Flow**:
1. Files saved temporarily to `/tmp/image_uploads/` with UUID prefixes
2. Each image processed sequentially using GPT-4.1-mini vision model
3. Text extracted and structured into question/answer pairs
4. Temporary files cleaned up after processing
5. Results returned as JSON

**Notes**:
- Uses `image_processor.process_images()` function
- 2-second delay between API calls to avoid rate limits
- Automatic retry logic for API failures (3 attempts)
- 90-second timeout per API call

---

#### POST /grade
**Purpose**: Grade extracted quiz answers against Care Certificate reference material

**Methods**: `POST`

**Authentication**: Required (`@login_required`)

**Request**:
```json
{
  "results": [
    {
      "filename": "quiz-001.jpg",
      "data": {
        "questions": [
          {
            "question_number": 1,
            "question_text": "What is duty of care?",
            "answer": "Student's answer..."
          }
        ]
      }
    }
  ],
  "standard_id": "3",
  "student_name": "John Doe",
  "quiz_title": "Standard 3 Quiz - Week 1" (optional)
}
```

**Response**:
```json
{
  "success": true,
  "quiz_id": 42,
  "message": "Quiz graded successfully",
  "results": [
    {
      "question_number": 1,
      "question_text": "What is duty of care?",
      "student_answer": "Student's handwritten response",
      "correct_answer": "Model answer from reference material",
      "mark_received": 8,
      "max_marks": 10,
      "feedback": "Detailed feedback on the answer..."
    },
    ...
  ],
  "total_marks": 72,
  "max_total_marks": 100
}
```

**Error Response**:
```json
{
  "error": "Error message"
}
```

**Processing Flow**:
1. Load reference PDF from `attached_assets/Standard-{id}.pdf`
2. Extract reference text using PyPDF2
3. Combine all questions into single document
4. Grade using GPT-4.1-mini:
   - **Combined approach** (preferred): Grade all questions in single API call
   - **Individual approach** (fallback): Grade each question separately
5. Create database records:
   - Student record (if new)
   - Quiz record
   - QuizSubmission record
   - QuizQuestion records (one per question)
6. Send email notification to user (via SendGrid)
7. Return grading results

**Special Handling - Standard 9**:
- Has reliability issues with OpenAI API
- Uses shorter prompts and reduced token limits (2500 vs 4000)
- Has hardcoded fallback reference content
- Emergency fallback grading with default scores (5-8 out of 10)
- Can force fallback mode via URL parameter: `?force_fallback=true`

**Validation**:
- `results` array must not be empty
- `standard_id` must be provided and valid (1-15)
- `student_name` must be provided
- PDF file must exist for the standard

**Notes**:
- Uses `image_processor.grade_answers()` function
- Automatic retry logic for API failures
- Email notification requires `SENDGRID_API_KEY`
- Creates permanent database records

---

### Admin Endpoints

#### GET/POST /admin/clean_database
**Purpose**: Remove all quiz data from database (DESTRUCTIVE)

**Methods**: `GET`, `POST`

**Authentication**: Required + Super Admin Only

**Authorization Check**:
```python
if not current_user.is_super_admin:
    flash('Access denied', 'danger')
    return redirect(url_for('index'))
```

**GET Response**:
- Returns HTML confirmation form
- Shows warning about data deletion

**POST Response**:
- Deletes all quiz submissions and related data
- Cascade deletes QuizQuestion records
- Redirects to quizzes page with success message

**Database Operations**:
```sql
DELETE FROM quiz_question WHERE quiz_submission_id IN (...);
DELETE FROM quiz_submission;
DELETE FROM student;  (if no other references)
DELETE FROM quiz;
```

**Warning**:
- This is a DESTRUCTIVE operation
- Cannot be undone
- Should only be used for testing/development

**Template**: `clean_database.html`

---

## Error Handling

### HTTP Status Codes
- `200` - Success
- `302` - Redirect (after POST operations)
- `400` - Bad Request (missing parameters, validation errors)
- `404` - Not Found (quiz doesn't exist)
- `500` - Server Error (unhandled exceptions)

### Error Response Format
```json
{
  "error": "Human-readable error message"
}
```

### Flash Message Categories
- `success` - Green alert (Bootstrap success class)
- `info` - Blue alert (Bootstrap info class)
- `warning` - Yellow alert (Bootstrap warning class)
- `danger` - Red alert (Bootstrap danger class)

---

## Security Considerations

### Authentication
- Session-based authentication via Flask-Login
- Password hashing using Werkzeug (pbkdf2:sha256)
- CSRF protection on all forms (Flask-WTF)

### File Upload Security
- Filename sanitization using `secure_filename()`
- File extension validation (whitelist)
- File size limits (16MB max)
- UUID prefixes to prevent filename conflicts
- Temporary file cleanup in try/finally blocks

### Authorization
- Route-level protection with `@login_required` decorator
- Resource-level checks (users can only access their own quizzes)
- Admin-only routes check `is_super_admin` flag

### API Keys
- OpenAI API key stored in environment variables
- SendGrid API key stored in environment variables
- Session secret from environment variables

---

## Rate Limiting

**Current Implementation**: None (manual delays only)

**Future Phase 7**: Will implement proper rate limiting
- 100 requests per hour per user
- 10 uploads per hour per user

**OpenAI API**:
- Sequential processing (not parallel)
- 2-second delay between image processing calls
- 3 retry attempts with exponential backoff
- 90-second timeout per request

---

## Database Schema

See `DATABASE_SCHEMA.md` for detailed database documentation.

**Key Models**:
- `User` - Teacher/marker accounts
- `Student` - Quiz takers
- `Quiz` - Quiz metadata
- `QuizSubmission` - Individual student quiz submissions
- `QuizQuestion` - Individual questions and grading results

---

## Future API Changes (Planned)

### Phase 2 - Backend Restructuring
- Move to FastAPI or Flask Blueprints
- RESTful endpoint naming
- API versioning (/api/v1/)
- Request/response schemas with Pydantic

### Phase 3 - Background Jobs
- Async quiz grading via job queue
- WebSocket updates for real-time progress
- Polling endpoints for job status

### Phase 4 - File Storage
- Replace local storage with S3
- Presigned URLs for file uploads
- CDN integration for file delivery

---

## Testing Endpoints

### Using cURL

**Register User**:
```bash
curl -X POST http://localhost:5000/register \
  -d "username=testuser&email=test@example.com&password=password123&confirm_password=password123"
```

**Login**:
```bash
curl -X POST http://localhost:5000/login \
  -d "username=testuser&password=password123" \
  -c cookies.txt
```

**Get Standards**:
```bash
curl http://localhost:5000/standards
```

**Upload File**:
```bash
curl -X POST http://localhost:5000/upload \
  -b cookies.txt \
  -F "files[]=@quiz.jpg"
```

**Grade Quiz**:
```bash
curl -X POST http://localhost:5000/grade \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "standard_id": "3",
    "student_name": "John Doe",
    "quiz_title": "Test Quiz",
    "results": [...]
  }'
```

---

## Version History

- **v1.0** (Current) - Initial monolithic Flask application
- **Phase 2** (Planned) - RESTful restructuring
- **Phase 3** (Planned) - Async processing

---

*Last Updated: November 15, 2025 - Phase 1 Migration*
