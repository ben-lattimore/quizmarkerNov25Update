# Database Schema Documentation

This document provides a comprehensive reference for the QuizMarker database schema.

## Overview

The QuizMarker application uses a relational database (PostgreSQL in production, SQLite fallback for development) managed through SQLAlchemy ORM.

**ORM**: SQLAlchemy 2.0.40+
**Migrations**: Manual (using `db.create_all()`) - **Note**: Phase 2 will introduce Alembic for proper migrations

## Entity Relationship Diagram

```
┌─────────────────┐
│      User       │
│  (Markers)      │
└────────┬────────┘
         │
         │ 1:N (marked_quizzes)
         │
         ▼
┌─────────────────┐         ┌──────────────────┐
│      Quiz       │         │     Student      │
│   (Metadata)    │         │   (Quiz Takers)  │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │ 1:N                       │ 1:N
         │ (submissions)             │ (quiz_submissions)
         │                           │
         └──────────┬────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  QuizSubmission     │
         │  (Graded Quizzes)   │
         └──────────┬──────────┘
                    │
                    │ 1:N (questions)
                    │ CASCADE DELETE
                    ▼
         ┌─────────────────────┐
         │   QuizQuestion      │
         │ (Individual Q&A)    │
         └─────────────────────┘
```

---

## Table Definitions

### 1. User Table

**Purpose**: Stores teacher/marker accounts for authentication and authorization

**Table Name**: `user`

| Column Name      | Data Type      | Constraints                | Description                                    |
|------------------|----------------|----------------------------|------------------------------------------------|
| `id`             | Integer        | PRIMARY KEY, AUTO_INCREMENT | Unique user identifier                         |
| `username`       | String(64)     | UNIQUE, NOT NULL           | Unique username for login                      |
| `email`          | String(120)    | UNIQUE, NOT NULL           | Unique email address                           |
| `password_hash`  | String(256)    | NOT NULL                   | Hashed password (pbkdf2:sha256)                |
| `is_admin`       | Boolean        | DEFAULT FALSE              | Admin privileges flag                          |
| `is_super_admin` | Boolean        | DEFAULT FALSE              | Super admin privileges flag                    |
| `created_at`     | DateTime       | DEFAULT utcnow()           | Account creation timestamp                     |

**Indexes**:
- Primary Key: `id`
- Unique Index: `username`
- Unique Index: `email`

**Relationships**:
- `marked_quizzes` → One-to-Many with `Quiz` (via `user_id`)

**Methods**:
- `set_password(password)` - Hash and store password
- `check_password(password)` - Verify password against hash
- `__repr__()` - String representation: `<User username>`

**Mixins**:
- `UserMixin` (Flask-Login) - Provides authentication helper methods

**Notes**:
- First registered user automatically becomes admin
- Password hashing uses Werkzeug `generate_password_hash()`
- Super admins can clean database via admin panel

---

### 2. Student Table

**Purpose**: Stores student information (quiz takers)

**Table Name**: `student`

| Column Name | Data Type    | Constraints                | Description                |
|-------------|--------------|----------------------------|----------------------------|
| `id`        | Integer      | PRIMARY KEY, AUTO_INCREMENT | Unique student identifier  |
| `name`      | String(100)  | NOT NULL                   | Student's full name        |

**Indexes**:
- Primary Key: `id`

**Relationships**:
- `quiz_submissions` → One-to-Many with `QuizSubmission` (via `student_id`)

**Methods**:
- `__repr__()` - String representation: `<Student name>`

**Notes**:
- Currently minimal - designed for future expansion
- Can add fields like: email, cohort, enrollment_date, etc.
- Student name is captured during quiz grading

---

### 3. Quiz Table

**Purpose**: Stores quiz metadata and ownership

**Table Name**: `quiz`

| Column Name   | Data Type    | Constraints                | Description                                |
|---------------|--------------|----------------------------|--------------------------------------------|
| `id`          | Integer      | PRIMARY KEY, AUTO_INCREMENT | Unique quiz identifier                     |
| `title`       | String(200)  | NULLABLE                   | Quiz title (optional)                      |
| `standard_id` | Integer      | NOT NULL                   | Care Certificate standard number (1-15)    |
| `created_at`  | DateTime     | DEFAULT utcnow()           | Quiz creation timestamp                    |
| `user_id`     | Integer      | FOREIGN KEY (user.id), NULLABLE | Marker who created this quiz         |

**Indexes**:
- Primary Key: `id`
- Foreign Key: `user_id` → `user.id`

**Relationships**:
- `marker` → Many-to-One with `User` (via `user_id`)
- `submissions` → One-to-Many with `QuizSubmission` (via `quiz_id`)

**Methods**:
- `__repr__()` - String representation: `<Quiz title (Standard X)>`

**Notes**:
- One Quiz can have multiple submissions (different students)
- `title` is optional - defaults to "Quiz for Standard X"
- `standard_id` corresponds to PDF file: `attached_assets/Standard-{id}.pdf`

---

### 4. QuizSubmission Table

**Purpose**: Stores individual student quiz submissions and grading results

**Table Name**: `quiz_submission`

| Column Name          | Data Type | Constraints                           | Description                                    |
|----------------------|-----------|---------------------------------------|------------------------------------------------|
| `id`                 | Integer   | PRIMARY KEY, AUTO_INCREMENT           | Unique submission identifier                   |
| `quiz_id`            | Integer   | FOREIGN KEY (quiz.id), NOT NULL       | Reference to parent quiz                       |
| `student_id`         | Integer   | FOREIGN KEY (student.id), NOT NULL    | Reference to student who took quiz             |
| `total_mark`         | Float     | NULLABLE                              | Total marks received across all questions      |
| `submission_date`    | DateTime  | DEFAULT utcnow()                      | When quiz was submitted/graded                 |
| `raw_extracted_data` | Text      | NULLABLE                              | JSON string of extracted OCR data              |

**Indexes**:
- Primary Key: `id`
- Foreign Key: `quiz_id` → `quiz.id`
- Foreign Key: `student_id` → `student.id`

**Relationships**:
- `quiz` → Many-to-One with `Quiz` (via `quiz_id`)
- `student` → Many-to-One with `Student` (via `student_id`)
- `questions` → One-to-Many with `QuizQuestion` (via `quiz_submission_id`)
  - **CASCADE DELETE**: Deleting a submission deletes all associated questions

**Methods**:
- `set_raw_data(data)` - Convert Python dict to JSON string for storage
- `get_raw_data()` - Convert stored JSON string back to Python dict
- `__repr__()` - String representation: `<QuizSubmission id by Student student_id>`

**Notes**:
- `raw_extracted_data` stores original OCR output before grading
- `total_mark` is calculated sum of all `mark_received` from questions
- Cascade delete ensures orphaned questions don't remain

---

### 5. QuizQuestion Table

**Purpose**: Stores individual questions, answers, marks, and feedback

**Table Name**: `quiz_question`

| Column Name          | Data Type | Constraints                                   | Description                           |
|----------------------|-----------|-----------------------------------------------|---------------------------------------|
| `id`                 | Integer   | PRIMARY KEY, AUTO_INCREMENT                   | Unique question identifier            |
| `quiz_submission_id` | Integer   | FOREIGN KEY (quiz_submission.id), NOT NULL    | Reference to parent submission        |
| `question_number`    | Integer   | NULLABLE                                      | Question number (1, 2, 3, ...)        |
| `question_text`      | Text      | NULLABLE                                      | The actual question text              |
| `student_answer`     | Text      | NULLABLE                                      | Student's handwritten answer (OCR)    |
| `correct_answer`     | Text      | NULLABLE                                      | Model answer from reference material  |
| `mark_received`      | Float     | NULLABLE                                      | Marks awarded (out of 10 typically)   |
| `feedback`           | Text      | NULLABLE                                      | AI-generated feedback on answer       |

**Indexes**:
- Primary Key: `id`
- Foreign Key: `quiz_submission_id` → `quiz_submission.id` (CASCADE DELETE)

**Relationships**:
- `submission` → Many-to-One with `QuizSubmission` (via `quiz_submission_id`)

**Methods**:
- `__repr__()` - String representation: `<QuizQuestion question_number from Submission quiz_submission_id>`

**Notes**:
- Each question typically worth 10 marks
- Feedback provided by GPT-4.1-mini grading model
- `student_answer` extracted via GPT-4.1-mini vision model
- `correct_answer` sourced from reference PDF

---

## Relationships Summary

### One-to-Many Relationships

1. **User → Quiz** (`marked_quizzes`)
   - A user (marker) can create/own multiple quizzes
   - Accessed via: `user.marked_quizzes`
   - Reverse access: `quiz.marker`

2. **Quiz → QuizSubmission** (`submissions`)
   - A quiz can have multiple student submissions
   - Accessed via: `quiz.submissions`
   - Reverse access: `submission.quiz`

3. **Student → QuizSubmission** (`quiz_submissions`)
   - A student can submit multiple quizzes
   - Accessed via: `student.quiz_submissions`
   - Reverse access: `submission.student`

4. **QuizSubmission → QuizQuestion** (`questions`)
   - A submission contains multiple questions
   - Accessed via: `submission.questions`
   - Reverse access: `question.submission`
   - **CASCADE DELETE**: Deleting submission deletes all questions

### Foreign Key Constraints

```sql
quiz.user_id → user.id
quiz_submission.quiz_id → quiz.id
quiz_submission.student_id → student.id
quiz_question.quiz_submission_id → quiz_submission.id (ON DELETE CASCADE)
```

---

## Cascade Delete Behavior

**QuizSubmission → QuizQuestion**:
- When a `QuizSubmission` is deleted, all associated `QuizQuestion` records are automatically deleted
- Defined in models.py line 67: `cascade='all, delete-orphan'`

**Other Relationships**:
- No other cascade deletes currently implemented
- Deleting a User does NOT delete their quizzes (user_id becomes NULL)
- Deleting a Quiz does NOT automatically delete submissions (manual cleanup required)
- Deleting a Student does NOT automatically delete their submissions (manual cleanup required)

---

## Data Flow

### Quiz Creation and Grading Flow

1. **User uploads images** → `/upload` endpoint
   ```
   User exists in database → authenticated session
   ```

2. **Images processed** → OCR extracts text
   ```
   No database interaction yet
   ```

3. **Grade quiz** → `/grade` endpoint

   a. **Create/Find Student**:
   ```python
   student = Student.query.filter_by(name=student_name).first()
   if not student:
       student = Student(name=student_name)
       db.session.add(student)
   ```

   b. **Create Quiz**:
   ```python
   quiz = Quiz(
       title=quiz_title,
       standard_id=standard_id,
       user_id=current_user.id
   )
   db.session.add(quiz)
   ```

   c. **Create QuizSubmission**:
   ```python
   submission = QuizSubmission(
       quiz_id=quiz.id,
       student_id=student.id,
       total_mark=total_marks
   )
   submission.set_raw_data(raw_results)
   db.session.add(submission)
   ```

   d. **Create QuizQuestions**:
   ```python
   for question_data in grading_results:
       question = QuizQuestion(
           quiz_submission_id=submission.id,
           question_number=question_data['question_number'],
           question_text=question_data['question_text'],
           student_answer=question_data['student_answer'],
           correct_answer=question_data['correct_answer'],
           mark_received=question_data['mark_received'],
           feedback=question_data['feedback']
       )
       db.session.add(question)
   ```

   e. **Commit Transaction**:
   ```python
   db.session.commit()
   ```

---

## Database Initialization

### Current Implementation (Manual)

```python
# From app.py lines 19-22
with app.app_context():
    db.create_all()
```

- Creates all tables on application startup
- No migration tracking
- Idempotent (won't recreate existing tables)

### Future Implementation (Phase 2)

Will migrate to Alembic for proper database migrations:
```bash
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

## Indexing Strategy

### Current Indexes

**Automatic Indexes** (created by SQLAlchemy):
- Primary keys on all tables
- Unique constraints on `user.username` and `user.email`
- Foreign key indexes

### Recommended Future Indexes (Phase 2)

For performance optimization:

```sql
-- Speed up quiz listing queries
CREATE INDEX idx_quiz_user_created ON quiz(user_id, created_at DESC);

-- Speed up student quiz lookups
CREATE INDEX idx_submission_student ON quiz_submission(student_id);

-- Speed up quiz detail queries
CREATE INDEX idx_question_submission ON quiz_question(quiz_submission_id);

-- Speed up standard-based queries
CREATE INDEX idx_quiz_standard ON quiz(standard_id);
```

---

## Data Types and Constraints

### String Length Limits

| Field Type           | Max Length | Rationale                          |
|----------------------|------------|------------------------------------|
| Username             | 64 chars   | Standard username length           |
| Email                | 120 chars  | RFC 5321 max local@domain          |
| Password Hash        | 256 chars  | pbkdf2:sha256 hash length          |
| Student Name         | 100 chars  | Full names with suffixes           |
| Quiz Title           | 200 chars  | Descriptive quiz titles            |
| Question/Answer/Feedback | Text   | Unlimited (within DB limits)       |

### Nullable Fields

**Allowed to be NULL**:
- `quiz.title` - Defaults to "Quiz for Standard X"
- `quiz.user_id` - Quiz can exist without assigned marker
- `quiz_submission.total_mark` - Calculated field
- `quiz_submission.raw_extracted_data` - Optional OCR data
- All `quiz_question` text fields - Graceful degradation

**NOT NULL Requirements**:
- `user.username`, `user.email`, `user.password_hash` - Authentication requirements
- `student.name` - Must identify student
- `quiz.standard_id` - Must know which standard
- `quiz_submission.quiz_id`, `quiz_submission.student_id` - Referential integrity

---

## JSON Data Storage

### raw_extracted_data Format

Stored as JSON string in `quiz_submission.raw_extracted_data`:

```json
[
  {
    "filename": "quiz-001.jpg",
    "data": {
      "questions": [
        {
          "question_number": 1,
          "question_text": "What is duty of care?",
          "answer": "Student's handwritten answer extracted via OCR"
        },
        {
          "question_number": 2,
          "question_text": "Explain confidentiality",
          "answer": "Another student response..."
        }
      ]
    }
  }
]
```

**Helper Methods**:
- `submission.set_raw_data(dict)` - Converts to JSON and stores
- `submission.get_raw_data()` - Parses JSON and returns dict

---

## Sample Queries

### Common Query Patterns

**Get all quizzes for a user**:
```python
quizzes = Quiz.query.filter_by(user_id=current_user.id)\
                    .order_by(Quiz.created_at.desc())\
                    .all()
```

**Get quiz with all submissions**:
```python
quiz = Quiz.query.get_or_404(quiz_id)
submissions = quiz.submissions  # Lazy-loaded relationship
```

**Get submission with all questions**:
```python
submission = QuizSubmission.query.get_or_404(submission_id)
questions = submission.questions.order_by(QuizQuestion.question_number).all()
```

**Find student by name**:
```python
student = Student.query.filter_by(name=student_name).first()
```

**Get all submissions for a student**:
```python
student = Student.query.get(student_id)
submissions = student.quiz_submissions
```

---

## Database Cleanup Operations

### Super Admin Database Clean

From `/admin/clean_database` endpoint:

```python
# Delete all quiz questions (cascade would do this automatically)
QuizQuestion.query.delete()

# Delete all quiz submissions
QuizSubmission.query.delete()

# Delete all students (no foreign key constraints left)
Student.query.delete()

# Delete all quizzes
Quiz.query.delete()

# Commit the transaction
db.session.commit()
```

**Warning**: This is DESTRUCTIVE and cannot be undone!

---

## Transaction Management

### Standard Pattern

```python
try:
    # Create records
    db.session.add(new_record)
    db.session.commit()
except Exception as e:
    db.session.rollback()
    # Handle error
    raise
```

### Multi-Record Transaction

```python
try:
    # Create student
    student = Student(name=name)
    db.session.add(student)
    db.session.flush()  # Get student.id without committing

    # Create quiz with student_id
    quiz = Quiz(standard_id=1)
    db.session.add(quiz)
    db.session.flush()  # Get quiz.id

    # Create submission with both IDs
    submission = QuizSubmission(
        quiz_id=quiz.id,
        student_id=student.id
    )
    db.session.add(submission)

    # Commit all at once
    db.session.commit()
except Exception as e:
    db.session.rollback()
    raise
```

---

## Migration Path (Phase 2)

### Current State
- Manual schema creation via `db.create_all()`
- No migration history
- No rollback capability

### Phase 2 Plan
1. Initialize Alembic
2. Generate initial migration from current models
3. Tag as "baseline" migration
4. Future changes via Alembic revision files

### Alembic Setup
```bash
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

---

## Security Considerations

### Password Storage
- Never store plaintext passwords
- Use Werkzeug `generate_password_hash()` with default settings
- Hash format: `pbkdf2:sha256:salt$hash`

### SQL Injection Protection
- SQLAlchemy ORM handles parameterization
- Never use raw SQL with user input
- Query parameters automatically escaped

### Data Access Control
- Users can only view their own quizzes
- Super admins can access all data
- Route-level authorization checks

---

## Performance Considerations

### N+1 Query Problem

**Problem**:
```python
quizzes = Quiz.query.all()
for quiz in quizzes:
    print(quiz.marker.username)  # N+1 queries!
```

**Solution**:
```python
quizzes = Quiz.query.options(
    db.joinedload(Quiz.marker)
).all()
```

### Lazy Loading

**Current**: `lazy=True` on all relationships (load on access)

**Future Optimization**: Use `lazy='joined'` or explicit `joinedload()` for frequently accessed relationships

---

## Schema Version

**Current Version**: 1.0 (Pre-Alembic)
**Last Modified**: November 15, 2025 (Phase 1 - Documentation)
**Next Review**: Phase 2 - Backend Restructuring

---

*This schema documentation is maintained as part of the QuizMarker migration project.*
