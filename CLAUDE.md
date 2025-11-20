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

# Test Phase 3 background jobs
python test_phase3_implementation.py
python test_basic_job_flow.py
```

### Background Workers (Phase 3)
```bash
# Start Redis server (required for background jobs)
redis-cli ping  # Check if running
brew services start redis  # Mac
sudo systemctl start redis  # Linux

# Run RQ worker (processes background jobs)
./venv/bin/rq worker --url redis://localhost:6379/0

# Run worker with specific queues
./venv/bin/rq worker high default low --url redis://localhost:6379/0

# Run worker in burst mode (for testing - exits when queue empty)
./venv/bin/rq worker --url redis://localhost:6379/0 --burst

# Job cleanup (removes old jobs from database)
python run_job_cleanup.py

# Scheduled job cleanup (runs continuously every hour)
python run_job_cleanup.py --schedule --interval 3600
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
- Models: `User`, `Student`, `Quiz`, `QuizSubmission`, `QuizQuestion`, `Organization`, `OrganizationMember`, `BackgroundJob`, `APIUsageLog`
- Relationships: Users → Quizzes → Submissions → Questions
- Multi-tenancy: Organizations → Members, Quizzes, Students
- Background Jobs: Track async task status and results

### Key Workflows

**Quiz Upload & Grading Flow** (Phase 3 - Async):
1. User uploads images via `/api/v1/upload` endpoint
2. Endpoint returns 202 Accepted with `job_id` immediately (<1 second)
3. Files saved temporarily with unique filenames to `/tmp/image_uploads`
4. Background worker picks up `process_images_task` from queue
5. `process_images()` extracts text from each image using GPT-4.1-mini vision
6. Frontend polls `/api/v1/jobs/{job_id}` for progress updates
7. User selects standard and submits to `/api/v1/grade` endpoint
8. Endpoint returns 202 Accepted with new `job_id` for grading
9. Background worker picks up `grade_quiz_task` from queue
10. Reference PDF loaded from `attached_assets/Standard-{id}.pdf`
11. Grading attempts combined approach first, falls back to individual grading
12. Results stored in database (Student, Quiz, QuizSubmission, QuizQuestion)
13. Email notification queued as background task
14. Temporary files cleaned up
15. Job marked as completed, frontend displays results

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
- `REDIS_URL` - Redis connection string for background jobs (default: `redis://localhost:6379/0`)
- `SENDGRID_API_KEY` - Email service (optional but needed for password reset and quiz notifications)

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
- Import models: `from models import User, Student, Quiz, QuizSubmission, QuizQuestion, Organization, OrganizationMember, APIUsageLog`
- Use relationships to avoid N+1 queries
- Always handle exceptions with rollback
- Check permissions before allowing access to data

## Multi-Tenancy Patterns (Phase 2)

QuizMarker now implements organization-based multi-tenancy for B2B/SaaS functionality. **CRITICAL**: All data access must enforce organization-level isolation to prevent data leakage between organizations.

### Organization Data Model

**Core Entities**:
- `Organization`: The tenant/company entity (free/pro/enterprise plans)
- `OrganizationMember`: Maps users to organizations with roles (owner/admin/member)
- `APIUsageLog`: Tracks API usage for billing and analytics

**Organization Fields on Existing Models**:
- `User.default_organization_id` - User's primary organization
- `Quiz.organization_id` - Which organization owns this quiz (NOT NULL)
- `Student.organization_id` - Which organization owns this student (NOT NULL)

### Data Isolation Pattern

**ALWAYS filter queries by organization_id** to prevent cross-organization data access:

```python
from app.utils import get_user_organization_ids, filter_by_organization

# Get user's accessible organization IDs
user_org_ids = get_user_organization_ids(current_user)

# Filter queries by organization
if current_user.is_super_admin:
    # Super admins see everything
    quizzes = Quiz.query.all()
else:
    # Regular users only see their organizations' data
    quizzes = Quiz.query.filter(Quiz.organization_id.in_(user_org_ids)).all()

    # Or use the helper function
    quizzes = filter_by_organization(Quiz.query, Quiz).all()
```

**NEVER** query without organization filtering unless you're a super admin endpoint:

```python
# ❌ BAD - Can see all students across all organizations
students = Student.query.all()

# ✅ GOOD - Only see students from user's organizations
students = Student.query.filter(Student.organization_id.in_(user_org_ids)).all()
```

### Permission Decorators

Use permission decorators for route-level organization access control:

```python
from app.utils import (
    require_organization_access,  # Any member
    require_organization_admin,   # Admin or owner only
    require_organization_owner    # Owner only
)

@api_v1_bp.route('/organizations/<int:organization_id>/members', methods=['GET'])
@login_required
@require_organization_access  # Any member can view members
def list_members(organization_id):
    organization = g.current_organization  # Set by decorator
    # ... implementation

@api_v1_bp.route('/organizations/<int:organization_id>/members', methods=['POST'])
@login_required
@require_organization_admin  # Only admins can add members
def add_member(organization_id):
    organization = g.current_organization
    # ... implementation

@api_v1_bp.route('/organizations/<int:organization_id>', methods=['DELETE'])
@login_required
@require_organization_owner  # Only owner can delete
def delete_organization(organization_id):
    organization = g.current_organization
    # ... implementation
```

### Plan Limits and Usage Tracking

**Enforce plan limits before creating quizzes**:

```python
from models import Organization

# Check if organization can create quiz
if not current_user.is_super_admin:
    organization = Organization.query.get(current_user.default_organization_id)
    can_create, error_message = organization.can_create_quiz()

    if not can_create:
        return jsonify({
            'success': False,
            'error': error_message,
            'code': 'PLAN_LIMIT_EXCEEDED',
            'details': {
                'plan': organization.plan,
                'quiz_limit': organization.max_quizzes_per_month,
                'quizzes_this_month': organization.get_quiz_count_this_month()
            }
        }), 403
```

**Track API usage for billing**:

```python
from app.utils import track_openai_tokens

# In endpoints that use OpenAI API
tokens_used = response.usage.total_tokens  # From OpenAI response
track_openai_tokens(tokens_used)  # Automatically logged by middleware
```

### Creating Organization-Scoped Data

**When creating quizzes, students, or submissions**, always associate with organization:

```python
# For regular users - use their default organization
organization_id = current_user.default_organization_id if not current_user.is_super_admin else None

# Create student scoped to organization
student = Student.query.filter_by(
    name=student_name,
    organization_id=organization_id
).first()

if not student:
    student = Student(
        name=student_name,
        organization_id=organization_id  # CRITICAL: Always set this
    )
    db.session.add(student)

# Create quiz scoped to organization
quiz = Quiz(
    title=quiz_title,
    standard_id=standard_id,
    user_id=current_user.id,
    organization_id=organization_id  # CRITICAL: Always set this
)
db.session.add(quiz)
```

### Common Organization Helpers

```python
from app.utils import (
    get_user_organizations,           # Get all orgs user belongs to
    get_user_organization_ids,        # Get org IDs as list
    get_organization_role,            # Get user's role in org
    user_can_access_organization,     # Check if user has access
    user_is_organization_admin,       # Check if user is admin/owner
    user_is_organization_owner,       # Check if user is owner
    ensure_organization_access        # Verify access or 403
)

# Example: Check user's role before allowing action
role = get_organization_role(current_user, organization_id)
if role not in ['admin', 'owner']:
    return jsonify({'error': 'Permission denied'}), 403

# Example: Verify access
if not user_can_access_organization(current_user, organization_id):
    return jsonify({'error': 'Access denied'}), 403
```

### Security Checklist

When adding new endpoints or features:

- [ ] Does this endpoint filter queries by `organization_id`?
- [ ] Does this endpoint check organization membership before returning data?
- [ ] Are super admins exempt from organization filtering (if appropriate)?
- [ ] Does creating data set the correct `organization_id`?
- [ ] Are plan limits checked before allowing resource creation?
- [ ] Is API usage tracked for billing purposes?
- [ ] Are permission decorators applied correctly?

### Testing Multi-Tenancy

Always test data isolation:

```python
# Create two organizations with different users
org1 = Organization(name="Org 1", plan="free")
org2 = Organization(name="Org 2", plan="pro")

user1 = User(username="user1", default_organization_id=org1.id)
user2 = User(username="user2", default_organization_id=org2.id)

# Create data in each org
quiz1 = Quiz(title="Quiz 1", organization_id=org1.id)
quiz2 = Quiz(title="Quiz 2", organization_id=org2.id)

# Verify user1 cannot see quiz2
# Verify user2 cannot see quiz1
# Verify super admin can see both
```

## Background Jobs and Async Processing (Phase 3)

QuizMarker uses Redis Queue (RQ) for asynchronous background processing of expensive AI operations. This architecture prevents API timeouts, enables non-blocking user experiences, and allows horizontal scaling of worker processes.

### Architecture Overview

**Components**:
- **Redis**: Message broker and job queue (stores job data, manages queues)
- **RQ Worker**: Background worker process that executes tasks from Redis queues
- **BackgroundJob Model**: Database record tracking job status, progress, and results
- **tasks.py**: Task definitions decorated with `@job` for background execution
- **Job API**: 5 endpoints for job management (`/api/v1/jobs/...`)

**Three Priority Queues**:
- **high**: Time-sensitive operations (not currently used, reserved for future features)
- **default**: Standard processing (upload, grading) - most tasks run here
- **low**: Background maintenance (email notifications, cleanup tasks)

**Workflow**:
1. API endpoint receives request (e.g., `/api/v1/upload` or `/api/v1/grade`)
2. Endpoint creates `BackgroundJob` record in database with status `queued`
3. Endpoint queues task in Redis (e.g., `process_images_task.delay()`)
4. Endpoint returns 202 Accepted with `job_id` immediately (<1 second)
5. RQ Worker picks up task from Redis queue
6. Task executes, updating job progress in database periodically
7. Frontend polls `/api/v1/jobs/{job_id}` every 2 seconds for updates
8. Job completes, results stored in database, status set to `completed`
9. Frontend retrieves results and displays to user

**Performance Impact**:
- API response time: 30-60s → <1s (99%+ improvement)
- No more timeout errors or blocking operations
- User can continue working while jobs process in background

### Database Model

**BackgroundJob** (`models.py`):
```python
class BackgroundJob(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # UUID
    job_type = db.Column(db.String(50), nullable=False)  # 'upload', 'grading', 'email'
    status = db.Column(db.String(20), nullable=False)  # 'queued', 'processing', 'completed', 'failed'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'))

    # Progress tracking
    progress = db.Column(db.Integer, default=0)  # 0-100
    current_step = db.Column(db.String(200))  # Human-readable status

    # Data storage (JSON strings)
    input_data = db.Column(db.Text)  # Job inputs
    result_data = db.Column(db.Text)  # Job outputs
    error_message = db.Column(db.Text)  # Error details if failed

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # Auto-cleanup timestamp

    # Retry logic
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
```

### Creating Background Tasks

**Task Definition Pattern** (`tasks.py`):
```python
from rq.decorators import job
from tasks import redis_conn, update_job_progress

@job('default', connection=redis_conn, timeout=600)
def my_background_task(job_id, param1, param2):
    """
    Background task description

    Args:
        job_id: UUID of the BackgroundJob record
        param1, param2: Task-specific parameters

    Returns:
        dict: Task results to be stored in BackgroundJob.result_data
    """
    from app import create_app
    from models import BackgroundJob

    app = create_app()

    with app.app_context():
        # Get job record
        job = BackgroundJob.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Mark job as started
        job.mark_started()
        update_job_progress(job_id, 10, "Starting task")

        try:
            # Do work
            result = do_work(param1, param2)

            # Update progress periodically
            update_job_progress(job_id, 50, "Halfway done")

            # More work
            final_result = finalize_work(result)

            # Mark completed
            update_job_progress(job_id, 100, "Complete")
            job.mark_completed(final_result)

            return final_result

        except Exception as e:
            # Handle retry logic
            if job.can_retry():
                job.increment_retry()
                # Re-queue the task
                my_background_task.delay(job_id, param1, param2)
            else:
                # Max retries reached
                job.mark_failed(str(e))
            raise
```

**Key Patterns**:
- Always accept `job_id` as first parameter
- Create Flask app context with `create_app()` and `with app.app_context()`
- Call `job.mark_started()` at beginning
- Update progress frequently with `update_job_progress(job_id, percent, message)`
- Call `job.mark_completed(result)` on success
- Handle retries with `job.can_retry()` and `job.increment_retry()`
- Call `job.mark_failed(error)` on final failure

### Queueing Jobs from API Endpoints

**Endpoint Pattern**:
```python
from models import BackgroundJob
from tasks import my_background_task
import uuid
from datetime import datetime, timedelta

@api_v1_bp.route('/my-endpoint', methods=['POST'])
@login_required
@limiter.limit("15 per hour")
def my_endpoint():
    # 1. Validate input
    data = request.json
    if not data or 'required_field' not in data:
        return jsonify({'success': False, 'error': 'Missing required field'}), 400

    # 2. Check organization plan limits (if applicable)
    if not current_user.is_super_admin:
        organization = Organization.query.get(current_user.default_organization_id)
        can_create, error_message = organization.can_create_quiz()
        if not can_create:
            return jsonify({
                'success': False,
                'error': error_message,
                'code': 'PLAN_LIMIT_EXCEEDED'
            }), 403

    # 3. Create background job record
    job_id = str(uuid.uuid4())
    organization_id = None if current_user.is_super_admin else current_user.default_organization_id

    job = BackgroundJob(
        id=job_id,
        job_type='my_task',
        status='queued',
        user_id=current_user.id,
        organization_id=organization_id,
        progress=0,
        current_step='Queued for processing',
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    # Store input data (for debugging/auditing)
    job.set_input_data({
        'param1': data['param1'],
        'param2': data['param2']
    })

    db.session.add(job)
    db.session.commit()

    # 4. Queue the task in Redis
    try:
        my_background_task.delay(job_id, data['param1'], data['param2'])
    except Exception as e:
        job.mark_failed(f"Failed to queue: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to queue job'}), 500

    # 5. Return 202 Accepted with job info
    return jsonify({
        'success': True,
        'job_id': job_id,
        'status': 'queued',
        'message': 'Task queued successfully',
        'data': {
            'job_status_url': f'/api/v1/jobs/{job_id}',
            'estimated_time': '30-60 seconds'
        }
    }), 202
```

**Critical Steps**:
1. Validate input and check permissions/limits
2. Create `BackgroundJob` record with unique UUID
3. Store input data with `job.set_input_data()`
4. Commit job to database BEFORE queuing
5. Queue task with `.delay()` method
6. Return 202 Accepted (not 200 OK) with `job_id`
7. Always include `job_status_url` for frontend polling

### Progress Tracking Pattern

**Update Progress Directly**:
```python
from tasks import update_job_progress

# Simple progress update
update_job_progress(job_id, 50, "Processing item 5 of 10")
```

**Progress Callback for Existing Functions**:
```python
# Create callback function
def my_progress_callback(current, total):
    progress = int(10 + (current / total) * 80)  # Scale to 10%-90%
    step = f"Processing item {current} of {total}"
    update_job_progress(job_id, progress, step)

# Pass to existing functions that support callbacks
results = process_images(
    image_paths,
    progress_callback=my_progress_callback
)
```

**Progress Ranges**:
- 0-5%: Initial setup
- 5-95%: Main processing (scale based on items)
- 95-100%: Finalization and cleanup

### Retry Logic Pattern

Tasks automatically retry on failure up to `max_retries` (default: 3):

```python
try:
    # Task work
    result = do_work()
    job.mark_completed(result)
except Exception as e:
    with app.app_context():
        job = BackgroundJob.query.get(job_id)
        if job.can_retry():
            # Increment retry count
            job.increment_retry()
            # Re-queue the task (will be picked up again)
            my_background_task.delay(job_id, param1, param2)
        else:
            # Max retries reached, mark as failed
            job.mark_failed(f"Failed after {job.retry_count} retries: {str(e)}")
    raise
```

**When to Retry**:
- ✅ Transient API errors (timeouts, rate limits)
- ✅ Temporary network issues
- ✅ Database connection errors
- ❌ Validation errors (bad input data)
- ❌ Permission errors (user lacks access)
- ❌ Email sending (to prevent duplicate emails)

### Frontend Polling Pattern

**JavaScript polling for job status** (`static/js/main.js`):
```javascript
async function pollJobStatus(jobId, onProgress) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const maxAttempts = 180;  // 6 minutes (180 * 2 seconds)

        const pollInterval = setInterval(async () => {
            attempts++;

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                reject(new Error('Job timed out after 6 minutes'));
                return;
            }

            try {
                const response = await fetch(`/api/v1/jobs/${jobId}`);
                const data = await response.json();

                if (!data.success) {
                    clearInterval(pollInterval);
                    reject(new Error(data.error || 'Failed to get job status'));
                    return;
                }

                const job = data.data;

                if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    resolve(job.result);
                } else if (job.status === 'failed') {
                    clearInterval(pollInterval);
                    reject(new Error(job.error || 'Job failed'));
                } else {
                    // Update progress (status: 'queued' or 'processing')
                    if (onProgress) {
                        onProgress(job.progress, job.current_step);
                    }
                }
            } catch (error) {
                clearInterval(pollInterval);
                reject(error);
            }
        }, 2000);  // Poll every 2 seconds
    });
}

// Usage example
try {
    const result = await pollJobStatus(jobId, (progress, step) => {
        // Update progress bar
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${progress}%`;

        // Update status message
        statusMessage.textContent = step;
    });

    // Job completed successfully
    console.log('Job result:', result);
    displayResults(result);

} catch (error) {
    // Job failed or timed out
    console.error('Job error:', error);
    displayError(error.message);
}
```

**Polling Best Practices**:
- Poll every 2 seconds (not faster to avoid server load)
- Set reasonable timeout (6 minutes = 180 attempts)
- Handle all three states: queued, processing, completed/failed
- Update UI with progress and current step
- Clear interval on completion or error

### Job Management API

**5 Endpoints** (`/api/v1/jobs.py`):

1. **Get Job Status**: `GET /api/v1/jobs/<job_id>`
   - Returns job status, progress, current step, result (if completed)
   - Users can only view their own jobs (except super admins)
   - Example: `curl http://localhost:5001/api/v1/jobs/abc-123-def`

2. **List Jobs**: `GET /api/v1/jobs`
   - Query parameters: `status`, `job_type`, `page`, `per_page`
   - Filtered by organization (multi-tenancy)
   - Paginated results (default: 20 per page)
   - Example: `curl http://localhost:5001/api/v1/jobs?status=completed&page=1`

3. **Get Job Result**: `GET /api/v1/jobs/<job_id>/result`
   - Returns only the result data (no metadata)
   - Only works for completed jobs
   - Example: `curl http://localhost:5001/api/v1/jobs/abc-123-def/result`

4. **Job Statistics**: `GET /api/v1/jobs/stats`
   - Returns total jobs, jobs by status, average processing time
   - Filtered by organization
   - Example: `curl http://localhost:5001/api/v1/jobs/stats`

5. **Cancel Job**: `DELETE /api/v1/jobs/<job_id>`
   - Marks job as failed (cannot truly cancel if already processing)
   - Users can only cancel their own jobs
   - Example: `curl -X DELETE http://localhost:5001/api/v1/jobs/abc-123-def`

### Job Cleanup

**Automatic cleanup of old jobs** prevents database bloat:

```bash
# Run cleanup manually (deletes jobs older than 24 hours)
python run_job_cleanup.py

# Run continuously with custom interval
python run_job_cleanup.py --schedule --interval 3600  # Every hour

# Set up as cron job (Unix/Mac)
crontab -e
# Add: 0 * * * * cd /path/to/QuizMarker && python run_job_cleanup.py

# Set up as systemd service (Linux production)
# See PHASE3_COMPLETE.md for systemd configuration
```

**What gets cleaned up**:
- Jobs with status `completed` or `failed` older than 24 hours
- Keeps `queued` and `processing` jobs (might still be active)
- Configurable age threshold (default: 24 hours)

### Running the System

**Required Processes** (all must be running):

1. **Redis Server** (message broker):
   ```bash
   # Check if running
   redis-cli ping  # Should return "PONG"

   # Start Redis (Mac with Homebrew)
   brew services start redis

   # Start Redis (Linux)
   sudo systemctl start redis

   # Start Redis manually
   redis-server
   ```

2. **Flask Application** (web server):
   ```bash
   python main.py
   # Runs on http://localhost:5001
   ```

3. **RQ Worker** (background task processor):
   ```bash
   # Run worker with all queues
   ./venv/bin/rq worker high default low --url redis://localhost:6379/0

   # Or just default queue
   ./venv/bin/rq worker --url redis://localhost:6379/0

   # Run with burst mode (exits when queue empty - for testing)
   ./venv/bin/rq worker --url redis://localhost:6379/0 --burst
   ```

4. **Job Cleanup** (optional, but recommended for production):
   ```bash
   python run_job_cleanup.py --schedule --interval 3600
   ```

**Development Workflow**:
Open 3 terminal windows:
- Terminal 1: `python main.py` (Flask)
- Terminal 2: `./venv/bin/rq worker --url redis://localhost:6379/0` (Worker)
- Terminal 3: `redis-cli monitor` (Optional: watch Redis activity)

### Monitoring Jobs

**Via API**:
```bash
# Get specific job status
curl http://localhost:5001/api/v1/jobs/abc-123-def

# List all completed jobs
curl http://localhost:5001/api/v1/jobs?status=completed

# Get job statistics
curl http://localhost:5001/api/v1/jobs/stats

# Get result of completed job
curl http://localhost:5001/api/v1/jobs/abc-123-def/result
```

**Via Redis CLI**:
```bash
redis-cli

# Check queue lengths
> LLEN rq:queue:default
> LLEN rq:queue:high
> LLEN rq:queue:low

# Watch all Redis commands (real-time monitoring)
> MONITOR

# List all job IDs in queue
> LRANGE rq:queue:default 0 -1

# Get job data
> GET rq:job:abc-123-def
```

**Via RQ Dashboard** (optional web UI):
```bash
# Install RQ Dashboard
./venv/bin/pip install rq-dashboard

# Run dashboard
./venv/bin/rq-dashboard --url redis://localhost:6379/0

# Open browser to http://localhost:9181
```

### Common Job Patterns

**Check if job is complete**:
```python
from models import BackgroundJob

job = BackgroundJob.query.get(job_id)
if job.status == 'completed':
    result = job.get_result_data()  # Returns dict
    # Process result
elif job.status == 'failed':
    error = job.error_message
    # Handle error
elif job.status in ['queued', 'processing']:
    # Still running, check progress
    progress = job.progress  # 0-100
    step = job.current_step
```

**Filter jobs by organization** (multi-tenancy):
```python
# Get all jobs for an organization
jobs = BackgroundJob.query.filter_by(
    organization_id=organization_id,
    status='completed'
).order_by(BackgroundJob.created_at.desc()).all()

# Get active jobs for user
active_jobs = BackgroundJob.query.filter(
    BackgroundJob.user_id == current_user.id,
    BackgroundJob.status.in_(['queued', 'processing'])
).all()
```

**Get jobs by type**:
```python
# Get all upload jobs
upload_jobs = BackgroundJob.query.filter_by(
    job_type='upload',
    organization_id=organization_id
).all()

# Get failed grading jobs
failed_gradings = BackgroundJob.query.filter_by(
    job_type='grading',
    status='failed',
    organization_id=organization_id
).all()
```

**Check job age**:
```python
from datetime import datetime, timedelta

# Get jobs older than 24 hours
cutoff = datetime.utcnow() - timedelta(hours=24)
old_jobs = BackgroundJob.query.filter(
    BackgroundJob.completed_at < cutoff,
    BackgroundJob.status.in_(['completed', 'failed'])
).all()
```

### Security Considerations

**Job Access Control**:
- Users can only view their own jobs (enforced in API endpoints)
- Super admins can view all jobs across all organizations
- Organization members can only see jobs from their organization
- Job IDs are UUIDs (hard to guess, but still check ownership)

**Organization Isolation**:
- All jobs MUST set `organization_id` (except super admin jobs)
- Job queries must filter by `organization_id` to prevent data leakage
- Job results (quiz data, student names) are organization-scoped

**Plan Limits**:
- Check organization plan limits BEFORE creating job
- Prevent job creation if organization exceeds monthly quota
- Track API usage for billing (OpenAI tokens)

**Rate Limiting**:
- Upload endpoint: 20 requests per hour per user
- Grading endpoint: 15 requests per hour per user
- Job status endpoint: No rate limit (needed for polling)

**Automatic Cleanup**:
- Jobs expire after 24 hours (configurable)
- Prevents database bloat and reduces storage costs
- Removes sensitive data (student answers, grading results)

**Secure Data Storage**:
- Input/output data stored as JSON strings
- No sensitive credentials in job data
- File paths cleaned up after processing (temporary files deleted)

### Troubleshooting

**Jobs stuck in "queued" status**:
- **Problem**: Worker not running
- **Solution**: Start RQ worker: `./venv/bin/rq worker --url redis://localhost:6379/0`
- **Verify**: Check worker logs for errors

**"Failed to queue job" error**:
- **Problem**: Redis not running or not reachable
- **Solution**: Start Redis: `brew services start redis` (Mac) or `sudo systemctl start redis` (Linux)
- **Verify**: Run `redis-cli ping` (should return "PONG")

**Worker crashes or restarts**:
- **Problem**: Import errors, missing dependencies, or unhandled exceptions in task code
- **Solution**: Run worker with verbose logging: `./venv/bin/rq worker --url redis://localhost:6379/0 --verbose`
- **Check**: Worker logs for stack traces

**Jobs not found in database**:
- **Problem**: Database migration not run
- **Solution**: Run migration: `./venv/bin/alembic upgrade head`
- **Verify**: Check for `background_job` table: `psql -d quizmarker -c "\dt background_job"`

**Frontend not showing progress**:
- **Problem**: Polling not working or CORS issues
- **Solution**: Check browser console for errors
- **Verify**: Manually call API: `curl http://localhost:5001/api/v1/jobs/{job_id}`

**Jobs timing out**:
- **Problem**: Task taking longer than `timeout` parameter (default: 600s)
- **Solution**: Increase timeout in task decorator: `@job('default', timeout=1200)`
- **Note**: Upload tasks have 900s timeout, grading tasks have 1800s timeout

**Redis memory full**:
- **Problem**: Too many jobs in queue or completed jobs not cleaned up
- **Solution**: Run cleanup: `python run_job_cleanup.py`
- **Prevention**: Schedule automatic cleanup

**Worker not picking up jobs**:
- **Problem**: Worker listening to wrong queue or Redis URL
- **Solution**: Verify Redis URL matches in both app and worker
- **Check**: `redis-cli LLEN rq:queue:default` (should show queued jobs)

### Task Timeouts

Each task type has a configured timeout:

- **Upload tasks** (`process_images_task`): 900 seconds (15 minutes)
  - Handles large batches of images (up to 20 images)
  - 2-second delay between images + API call time

- **Grading tasks** (`grade_quiz_task`): 1800 seconds (30 minutes)
  - Handles complex grading with multiple API calls
  - Includes PDF loading, grading, database writes, email queuing

- **Email tasks** (`send_email_task`): 120 seconds (2 minutes)
  - Simple email send, no retry logic

If a task exceeds its timeout, RQ will kill it and mark as failed. Adjust timeouts if needed in `tasks.py`.
