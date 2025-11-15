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
