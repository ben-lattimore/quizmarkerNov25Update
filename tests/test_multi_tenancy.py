"""
Multi-Tenancy Tests

Tests for organization-based data isolation, permissions, and plan limits.
Ensures that users can only access data from their own organizations and that
plan limits are properly enforced.
"""

import pytest
import json
from datetime import datetime, timedelta
from app import create_app
from database import db
from models import (
    User, Organization, OrganizationMember, Quiz, Student,
    QuizSubmission, QuizQuestion, APIUsageLog
)


@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def setup_organizations(app):
    """
    Set up test data with two organizations and users.

    Returns:
        dict: Contains org1, org2, user1, user2, super_admin
    """
    with app.app_context():
        # Create two organizations
        org1 = Organization(
            name="Organization 1",
            plan="free",
            max_quizzes_per_month=10,
            active=True,
            created_at=datetime.utcnow()
        )
        org2 = Organization(
            name="Organization 2",
            plan="pro",
            max_quizzes_per_month=100,
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(org1)
        db.session.add(org2)
        db.session.flush()

        # Create users
        user1 = User(
            username="user1",
            email="user1@test.com",
            is_admin=False,
            is_super_admin=False,
            default_organization_id=org1.id
        )
        user1.set_password("password123")

        user2 = User(
            username="user2",
            email="user2@test.com",
            is_admin=False,
            is_super_admin=False,
            default_organization_id=org2.id
        )
        user2.set_password("password123")

        super_admin = User(
            username="superadmin",
            email="admin@test.com",
            is_admin=True,
            is_super_admin=True
        )
        super_admin.set_password("admin123")

        db.session.add(user1)
        db.session.add(user2)
        db.session.add(super_admin)
        db.session.flush()

        # Create organization memberships
        member1 = OrganizationMember(
            organization_id=org1.id,
            user_id=user1.id,
            role='owner',
            joined_at=datetime.utcnow()
        )
        member2 = OrganizationMember(
            organization_id=org2.id,
            user_id=user2.id,
            role='owner',
            joined_at=datetime.utcnow()
        )
        db.session.add(member1)
        db.session.add(member2)

        # Create students for each org
        student1 = Student(name="Student 1", organization_id=org1.id)
        student2 = Student(name="Student 2", organization_id=org2.id)
        db.session.add(student1)
        db.session.add(student2)

        # Create quizzes for each org
        quiz1 = Quiz(
            title="Quiz 1",
            standard_id=1,
            user_id=user1.id,
            organization_id=org1.id,
            created_at=datetime.utcnow()
        )
        quiz2 = Quiz(
            title="Quiz 2",
            standard_id=2,
            user_id=user2.id,
            organization_id=org2.id,
            created_at=datetime.utcnow()
        )
        db.session.add(quiz1)
        db.session.add(quiz2)
        db.session.flush()

        # Create quiz submissions
        submission1 = QuizSubmission(
            quiz_id=quiz1.id,
            student_id=student1.id,
            submission_date=datetime.utcnow(),
            total_mark=8.5
        )
        submission2 = QuizSubmission(
            quiz_id=quiz2.id,
            student_id=student2.id,
            submission_date=datetime.utcnow(),
            total_mark=9.0
        )
        db.session.add(submission1)
        db.session.add(submission2)

        db.session.commit()

        return {
            'org1': org1,
            'org2': org2,
            'user1': user1,
            'user2': user2,
            'super_admin': super_admin,
            'student1': student1,
            'student2': student2,
            'quiz1': quiz1,
            'quiz2': quiz2,
            'submission1': submission1,
            'submission2': submission2
        }


# ============================================================================
# Data Isolation Tests
# ============================================================================

def test_quiz_data_isolation(client, app, setup_organizations):
    """Test that users can only see quizzes from their organization"""
    data = setup_organizations

    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Get quizzes - should only see org1 quizzes
        response = client.get('/api/v1/quizzes')
        assert response.status_code == 200
        result = response.get_json()

        assert result['success'] is True
        quizzes = result['data']['quizzes']

        # User1 should only see 1 quiz (from org1)
        assert len(quizzes) == 1
        assert quizzes[0]['quiz_title'] == 'Quiz 1'


def test_quiz_detail_access_denied_cross_org(client, app, setup_organizations):
    """Test that users cannot view quiz details from another organization"""
    data = setup_organizations

    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Try to access quiz from org2 (submission2)
        submission2_id = data['submission2'].id
        response = client.get(f'/api/v1/quizzes/{submission2_id}')

        # Should get 403 Forbidden
        assert response.status_code == 403
        result = response.get_json()
        assert result['success'] is False
        assert 'permission' in result['error'].lower()


def test_quiz_delete_access_denied_cross_org(client, app, setup_organizations):
    """Test that users cannot delete quizzes from another organization"""
    data = setup_organizations

    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Try to delete quiz from org2
        submission2_id = data['submission2'].id
        response = client.delete(f'/api/v1/quizzes/{submission2_id}')

        # Should get 403 Forbidden
        assert response.status_code == 403
        result = response.get_json()
        assert result['success'] is False


def test_super_admin_sees_all_quizzes(client, app, setup_organizations):
    """Test that super admin can see quizzes from all organizations"""
    data = setup_organizations

    with app.app_context():
        # Login as super admin
        client.post('/api/v1/auth/login', json={
            'username': 'superadmin',
            'password': 'admin123'
        })

        # Get quizzes - should see all
        response = client.get('/api/v1/quizzes')
        assert response.status_code == 200
        result = response.get_json()

        quizzes = result['data']['quizzes']

        # Super admin should see all 2 quizzes
        assert len(quizzes) == 2


# ============================================================================
# Organization Permission Tests
# ============================================================================

def test_create_organization(client, app, setup_organizations):
    """Test creating a new organization"""
    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Create new organization
        response = client.post('/api/v1/organizations', json={
            'name': 'New Organization',
            'plan': 'pro'
        })

        assert response.status_code == 201
        result = response.get_json()
        assert result['success'] is True
        assert result['organization']['name'] == 'New Organization'
        assert result['organization']['plan'] == 'pro'
        assert result['organization']['member_count'] == 1


def test_organization_member_permissions(client, app, setup_organizations):
    """Test that only admins can add members"""
    data = setup_organizations

    with app.app_context():
        # Create a regular member user
        org1 = data['org1']
        member_user = User(
            username="member",
            email="member@test.com",
            is_admin=False,
            default_organization_id=org1.id
        )
        member_user.set_password("password123")
        db.session.add(member_user)

        membership = OrganizationMember(
            organization_id=org1.id,
            user_id=member_user.id,
            role='member',  # Regular member, not admin
            joined_at=datetime.utcnow()
        )
        db.session.add(membership)
        db.session.commit()

        # Login as member
        client.post('/api/v1/auth/login', json={
            'username': 'member',
            'password': 'password123'
        })

        # Try to add another member (should fail - need admin)
        response = client.post(f'/api/v1/organizations/{org1.id}/members', json={
            'email': 'newuser@test.com',
            'role': 'member'
        })

        # Should get 403 - not an admin
        assert response.status_code == 403


def test_organization_owner_only_operations(client, app, setup_organizations):
    """Test that only owners can delete organizations"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']

        # Create an admin (not owner)
        admin_user = User(
            username="admin",
            email="admin_user@test.com",
            is_admin=False,
            default_organization_id=org1.id
        )
        admin_user.set_password("password123")
        db.session.add(admin_user)

        membership = OrganizationMember(
            organization_id=org1.id,
            user_id=admin_user.id,
            role='admin',  # Admin, not owner
            joined_at=datetime.utcnow()
        )
        db.session.add(membership)
        db.session.commit()

        # Login as admin
        client.post('/api/v1/auth/login', json={
            'username': 'admin',
            'password': 'password123'
        })

        # Try to delete organization (should fail - need owner)
        response = client.delete(f'/api/v1/organizations/{org1.id}')

        # Should get 403 - not owner
        assert response.status_code == 403


# ============================================================================
# Plan Limit Tests
# ============================================================================

def test_plan_limit_enforcement_free_plan(client, app, setup_organizations):
    """Test that free plan limit (10 quizzes/month) is enforced"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']
        user1 = data['user1']

        # Create 9 more quizzes to reach the limit of 10
        for i in range(9):
            quiz = Quiz(
                title=f"Quiz {i+2}",
                standard_id=1,
                user_id=user1.id,
                organization_id=org1.id,
                created_at=datetime.utcnow()
            )
            db.session.add(quiz)
        db.session.commit()

        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Try to grade (create) another quiz - should fail
        response = client.post('/api/v1/grade', json={
            'data': [
                {
                    'filename': 'test.jpg',
                    'data': {
                        'handwritten_content': 'Test answer'
                    }
                }
            ],
            'standard_id': 1,
            'student_name': 'Test Student',
            'quiz_title': 'Quiz 11'
        })

        # Should get 403 - plan limit exceeded
        assert response.status_code == 403
        result = response.get_json()
        assert result['code'] == 'PLAN_LIMIT_EXCEEDED'
        assert 'details' in result
        assert result['details']['plan'] == 'free'
        assert result['details']['quiz_limit'] == 10


def test_plan_limit_not_enforced_for_pro(client, app, setup_organizations):
    """Test that pro plan has higher limit (100 quizzes/month)"""
    data = setup_organizations

    with app.app_context():
        org2 = data['org2']

        # Check that org2 (pro plan) can create more quizzes
        can_create, error = org2.can_create_quiz()

        assert can_create is True
        assert error is None
        assert org2.max_quizzes_per_month == 100


def test_inactive_organization_blocks_grading(client, app, setup_organizations):
    """Test that inactive organizations cannot grade quizzes"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']

        # Deactivate org1
        org1.active = False
        db.session.commit()

        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Try to grade - should fail
        response = client.post('/api/v1/grade', json={
            'data': [
                {
                    'filename': 'test.jpg',
                    'data': {
                        'handwritten_content': 'Test answer'
                    }
                }
            ],
            'standard_id': 1,
            'student_name': 'Test Student',
            'quiz_title': 'New Quiz'
        })

        # Should get 403 - organization inactive
        assert response.status_code == 403
        result = response.get_json()
        assert 'inactive' in result['error'].lower()


# ============================================================================
# Usage Tracking Tests
# ============================================================================

def test_api_usage_logging(client, app, setup_organizations):
    """Test that API usage is logged"""
    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Make an API call
        response = client.get('/api/v1/quizzes')
        assert response.status_code == 200

        # Check that usage was logged
        usage_logs = APIUsageLog.query.all()

        # Should have at least 1 log entry for the quizzes endpoint
        quiz_logs = [log for log in usage_logs if '/api/v1/quizzes' in log.endpoint]
        assert len(quiz_logs) >= 1

        # Verify log details
        log = quiz_logs[0]
        assert log.method == 'GET'
        assert log.status_code == 200
        assert log.user_id is not None
        assert log.organization_id is not None


def test_organization_usage_stats(client, app, setup_organizations):
    """Test that organization usage stats are retrievable"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']
        user1 = data['user1']

        # Create some usage logs
        for i in range(5):
            log = APIUsageLog(
                organization_id=org1.id,
                user_id=user1.id,
                endpoint='/api/v1/grade',
                method='POST',
                status_code=200,
                timestamp=datetime.utcnow(),
                openai_tokens_used=1000 + i * 100
            )
            db.session.add(log)
        db.session.commit()

        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Get usage stats
        response = client.get(f'/api/v1/organizations/{org1.id}/usage')
        assert response.status_code == 200

        result = response.get_json()
        assert result['success'] is True
        assert 'usage' in result

        usage = result['usage']
        assert usage['organization_name'] == 'Organization 1'
        assert usage['total_api_calls'] >= 5
        assert usage['total_openai_tokens'] >= 5000  # Sum of tokens


# ============================================================================
# Student Isolation Tests
# ============================================================================

def test_student_scoped_to_organization(client, app, setup_organizations):
    """Test that students are scoped to their organization"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']
        org2 = data['org2']

        # Students should be in their respective orgs
        student1 = data['student1']
        student2 = data['student2']

        assert student1.organization_id == org1.id
        assert student2.organization_id == org2.id

        # Querying students by org should return only that org's students
        org1_students = Student.query.filter_by(organization_id=org1.id).all()
        assert len(org1_students) == 1
        assert org1_students[0].name == 'Student 1'


# ============================================================================
# Organization List and Details Tests
# ============================================================================

def test_list_user_organizations(client, app, setup_organizations):
    """Test listing user's organizations"""
    with app.app_context():
        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Get organizations
        response = client.get('/api/v1/organizations')
        assert response.status_code == 200

        result = response.get_json()
        assert result['success'] is True
        assert len(result['organizations']) == 1
        assert result['organizations'][0]['name'] == 'Organization 1'


def test_get_organization_details(client, app, setup_organizations):
    """Test getting organization details"""
    data = setup_organizations

    with app.app_context():
        org1 = data['org1']

        # Login as user1
        client.post('/api/v1/auth/login', json={
            'username': 'user1',
            'password': 'password123'
        })

        # Get organization details
        response = client.get(f'/api/v1/organizations/{org1.id}')
        assert response.status_code == 200

        result = response.get_json()
        assert result['success'] is True
        assert result['organization']['name'] == 'Organization 1'
        assert result['organization']['your_role'] == 'owner'
        assert 'quiz_count' in result['organization']
        assert 'member_count' in result['organization']


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
