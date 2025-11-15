from database import db
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin, db.Model):
    """Model for storing user (marker/teacher) authentication information"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    default_organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)

    # Relationship with quizzes - a user can mark multiple quizzes
    marked_quizzes = db.relationship('Quiz', backref='marker', lazy=True)

    # Relationship with default organization
    default_organization = db.relationship('Organization', foreign_keys=[default_organization_id], backref='users')
    
    def set_password(self, password):
        """Set password hash from plain text password"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check if password matches stored hash"""
        return check_password_hash(self.password_hash, password)

    def get_organizations(self):
        """Get all organizations this user is a member of"""
        return [membership.organization for membership in self.organization_memberships]

    def get_organization_role(self, organization_id):
        """Get user's role in a specific organization"""
        membership = OrganizationMember.query.filter_by(
            user_id=self.id,
            organization_id=organization_id
        ).first()
        return membership.role if membership else None

    def is_organization_owner(self, organization_id):
        """Check if user is owner of the organization"""
        role = self.get_organization_role(organization_id)
        return role == 'owner'

    def is_organization_admin(self, organization_id):
        """Check if user is admin or owner of the organization"""
        role = self.get_organization_role(organization_id)
        return role in ['owner', 'admin']

    def can_access_organization(self, organization_id):
        """Check if user has access to the organization"""
        return self.get_organization_role(organization_id) is not None

    def __repr__(self):
        return f'<User {self.username}>'

class Organization(db.Model):
    """Model for storing organization (tenant) information for multi-tenancy"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(50), default='free')  # 'free', 'pro', 'enterprise'
    max_quizzes_per_month = db.Column(db.Integer, default=10)  # Based on plan
    active = db.Column(db.Boolean, default=True)  # Subscription status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    members = db.relationship('OrganizationMember', backref='organization', lazy=True, cascade='all, delete-orphan')
    quizzes = db.relationship('Quiz', backref='organization', lazy=True)
    students = db.relationship('Student', backref='organization', lazy=True)
    usage_logs = db.relationship('APIUsageLog', backref='organization', lazy=True)

    def __repr__(self):
        return f'<Organization {self.name} ({self.plan})>'

    def get_members(self):
        """Get all members of this organization"""
        return self.members

    def get_member_role(self, user_id):
        """Get the role of a specific user in this organization"""
        member = OrganizationMember.query.filter_by(
            organization_id=self.id,
            user_id=user_id
        ).first()
        return member.role if member else None

    def add_member(self, user_id, role='member'):
        """Add a new member to this organization"""
        existing = OrganizationMember.query.filter_by(
            organization_id=self.id,
            user_id=user_id
        ).first()
        if existing:
            return existing

        new_member = OrganizationMember(
            organization_id=self.id,
            user_id=user_id,
            role=role
        )
        db.session.add(new_member)
        return new_member

    def remove_member(self, user_id):
        """Remove a member from this organization"""
        member = OrganizationMember.query.filter_by(
            organization_id=self.id,
            user_id=user_id
        ).first()
        if member:
            db.session.delete(member)
            return True
        return False

    def get_quiz_count_this_month(self):
        """Get the count of quizzes created this month for plan limit enforcement"""
        from datetime import datetime
        from sqlalchemy import extract

        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year

        count = Quiz.query.filter(
            Quiz.organization_id == self.id,
            extract('month', Quiz.created_at) == current_month,
            extract('year', Quiz.created_at) == current_year
        ).count()

        return count

    def can_create_quiz(self):
        """Check if organization can create a new quiz based on plan limits"""
        if not self.active:
            return False, "Organization subscription is inactive"

        current_count = self.get_quiz_count_this_month()
        if current_count >= self.max_quizzes_per_month:
            return False, f"Monthly quiz limit reached ({self.max_quizzes_per_month} quizzes)"

        return True, None

class OrganizationMember(db.Model):
    """Model for storing organization membership and roles"""
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(50), default='member')  # 'owner', 'admin', 'member'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Ensure unique membership (user can only be in an org once)
    __table_args__ = (db.UniqueConstraint('organization_id', 'user_id', name='unique_org_member'),)

    # Relationship to user
    user = db.relationship('User', backref='organization_memberships', lazy=True)

    def __repr__(self):
        return f'<OrganizationMember user={self.user_id} org={self.organization_id} role={self.role}>'

    def is_owner(self):
        """Check if member is organization owner"""
        return self.role == 'owner'

    def is_admin(self):
        """Check if member is admin or owner"""
        return self.role in ['owner', 'admin']

    def can_manage_members(self):
        """Check if member can add/remove other members"""
        return self.is_admin()

    def can_delete_organization(self):
        """Only owners can delete organizations"""
        return self.is_owner()

class APIUsageLog(db.Model):
    """Model for logging API usage per organization for billing and analytics"""
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)  # e.g., '/api/v1/grade'
    method = db.Column(db.String(10), nullable=False)  # GET, POST, PUT, DELETE
    status_code = db.Column(db.Integer)  # HTTP response code
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    openai_tokens_used = db.Column(db.Integer, default=0)  # Track OpenAI API usage for billing

    # Relationship to user
    user = db.relationship('User', backref='api_usage_logs', lazy=True)

    def __repr__(self):
        return f'<APIUsageLog {self.method} {self.endpoint} org={self.organization_id}>'

    @staticmethod
    def log_request(organization_id, user_id, endpoint, method, status_code, openai_tokens=0):
        """Helper method to log an API request"""
        log_entry = APIUsageLog(
            organization_id=organization_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            openai_tokens_used=openai_tokens
        )
        db.session.add(log_entry)
        return log_entry

    @staticmethod
    def get_organization_usage(organization_id, start_date=None, end_date=None):
        """Get usage statistics for an organization within a date range"""
        query = APIUsageLog.query.filter_by(organization_id=organization_id)

        if start_date:
            query = query.filter(APIUsageLog.timestamp >= start_date)
        if end_date:
            query = query.filter(APIUsageLog.timestamp <= end_date)

        return query.all()

    @staticmethod
    def get_total_tokens_used(organization_id, start_date=None, end_date=None):
        """Get total OpenAI tokens used by an organization"""
        from sqlalchemy import func

        query = db.session.query(func.sum(APIUsageLog.openai_tokens_used)).filter(
            APIUsageLog.organization_id == organization_id
        )

        if start_date:
            query = query.filter(APIUsageLog.timestamp >= start_date)
        if end_date:
            query = query.filter(APIUsageLog.timestamp <= end_date)

        result = query.scalar()
        return result or 0

class Student(db.Model):
    """Model for storing student information"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    # Additional student information can be added here as needed

    # Relationship to quiz submissions
    quiz_submissions = db.relationship('QuizSubmission', backref='student', lazy=True)
    
    def __repr__(self):
        return f'<Student {self.name}>'

class Quiz(db.Model):
    """Model for storing quiz metadata"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    standard_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # The marker who created/owns this quiz
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Relationship to quiz submissions
    submissions = db.relationship('QuizSubmission', backref='quiz', lazy=True)
    
    def __repr__(self):
        return f'<Quiz {self.title} (Standard {self.standard_id})>'

class QuizSubmission(db.Model):
    """Model for storing quiz submission data"""
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    total_mark = db.Column(db.Float)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    raw_extracted_data = db.Column(db.Text)  # JSON string of extracted data
    uploaded_files = db.Column(db.Text, nullable=True)  # JSON string of S3 file keys/paths

    # Relationship to quiz questions
    questions = db.relationship('QuizQuestion', backref='submission', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<QuizSubmission {self.id} by Student {self.student_id}>'
    
    def set_raw_data(self, data):
        """Convert data to JSON string for storage"""
        self.raw_extracted_data = json.dumps(data)
    
    def get_raw_data(self):
        """Convert stored JSON string back to Python object"""
        if self.raw_extracted_data:
            return json.loads(self.raw_extracted_data)
        return None

    def set_uploaded_files(self, file_list):
        """Convert file list to JSON string for storage"""
        self.uploaded_files = json.dumps(file_list)

    def get_uploaded_files(self):
        """Convert stored JSON string back to Python list"""
        if self.uploaded_files:
            return json.loads(self.uploaded_files)
        return []

class QuizQuestion(db.Model):
    """Model for storing individual question data and grades"""
    id = db.Column(db.Integer, primary_key=True)
    quiz_submission_id = db.Column(db.Integer, db.ForeignKey('quiz_submission.id'), nullable=False)
    question_number = db.Column(db.Integer)
    question_text = db.Column(db.Text)
    student_answer = db.Column(db.Text)
    correct_answer = db.Column(db.Text)
    mark_received = db.Column(db.Float)
    feedback = db.Column(db.Text)
    
    def __repr__(self):
        return f'<QuizQuestion {self.question_number} from Submission {self.quiz_submission_id}>'