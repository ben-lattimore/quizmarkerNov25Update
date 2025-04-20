from app import db
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with quizzes - a user can mark multiple quizzes
    marked_quizzes = db.relationship('Quiz', backref='marker', lazy=True)
    
    def set_password(self, password):
        """Set password hash from plain text password"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check if password matches stored hash"""
        return check_password_hash(self.password_hash, password)
        
    def __repr__(self):
        return f'<User {self.username}>'

class Student(db.Model):
    """Model for storing student information"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
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