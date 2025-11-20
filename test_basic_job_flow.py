"""
Test basic job creation and retrieval functionality

This test verifies that:
1. BackgroundJob model works correctly
2. Jobs can be created in the database
3. Jobs can be retrieved and updated
4. Job status transitions work properly
"""

import os
import uuid
from datetime import datetime

# Ensure we're using the right environment
os.environ['FLASK_ENV'] = 'development'

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use importlib to explicitly load app.py (not the app package)
import importlib.util
spec = importlib.util.spec_from_file_location("app_module", "/Users/benjaminlattimore/JSProjects/QuizMarker/app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
app = app_module.app

from database import db
from models import BackgroundJob, User, Organization, OrganizationMember


def test_basic_job_flow():
    """Test basic job creation, updates, and retrieval"""

    print("\n" + "="*60)
    print("Testing Basic Job Flow")
    print("="*60)

    with app.app_context():
        # 1. Find or create a test user
        print("\n1. Getting test user...")
        test_user = User.query.filter_by(username='testuser').first()

        if not test_user:
            print("   Creating test user...")
            test_user = User(username='testuser', email='test@example.com')
            test_user.set_password('testpassword')

            # Create organization for user
            org = Organization(name='Test Organization', plan='free')
            db.session.add(org)
            db.session.flush()

            test_user.default_organization_id = org.id
            db.session.add(test_user)
            db.session.commit()  # Commit user first to get user.id

            # Add user as organization owner
            membership = OrganizationMember(
                organization_id=org.id,
                user_id=test_user.id,
                role='owner'
            )
            db.session.add(membership)
            db.session.commit()
            print(f"   ✓ Created test user with ID {test_user.id}")
        else:
            print(f"   ✓ Found existing test user with ID {test_user.id}")

        # 2. Create a new job
        print("\n2. Creating background job...")
        job_id = str(uuid.uuid4())
        job = BackgroundJob(
            id=job_id,
            job_type='upload',
            status='queued',
            user_id=test_user.id,
            organization_id=test_user.default_organization_id,
            progress=0
        )

        # Set input data
        test_input = {
            'image_paths': ['/tmp/test1.jpg', '/tmp/test2.jpg'],
            'total_images': 2
        }
        job.set_input_data(test_input)

        db.session.add(job)
        db.session.commit()
        print(f"   ✓ Created job with ID: {job_id}")
        print(f"   - Status: {job.status}")
        print(f"   - Progress: {job.progress}%")

        # 3. Retrieve the job
        print("\n3. Retrieving job from database...")
        retrieved_job = BackgroundJob.query.get(job_id)
        assert retrieved_job is not None, "Job not found in database!"
        print(f"   ✓ Retrieved job: {retrieved_job.id}")

        # Verify input data
        input_data = retrieved_job.get_input_data()
        assert input_data == test_input, "Input data doesn't match!"
        print(f"   ✓ Input data matches: {input_data}")

        # 4. Update job to processing
        print("\n4. Marking job as started...")
        retrieved_job.mark_started()
        assert retrieved_job.status == 'processing', "Status not updated!"
        assert retrieved_job.started_at is not None, "Started timestamp not set!"
        print(f"   ✓ Job status: {retrieved_job.status}")
        print(f"   ✓ Started at: {retrieved_job.started_at}")

        # 5. Update progress
        print("\n5. Updating job progress...")
        retrieved_job.update_progress(50, "Processing image 1 of 2")
        refreshed_job = BackgroundJob.query.get(job_id)
        assert refreshed_job.progress == 50, "Progress not updated!"
        assert refreshed_job.current_step == "Processing image 1 of 2", "Step not updated!"
        print(f"   ✓ Progress: {refreshed_job.progress}%")
        print(f"   ✓ Current step: {refreshed_job.current_step}")

        # 6. Complete the job
        print("\n6. Marking job as completed...")
        test_result = {
            'processed_images': 2,
            'extracted_data': [
                {'text': 'Sample text from image 1'},
                {'text': 'Sample text from image 2'}
            ]
        }
        refreshed_job.mark_completed(test_result)

        completed_job = BackgroundJob.query.get(job_id)
        assert completed_job.status == 'completed', "Status not set to completed!"
        assert completed_job.progress == 100, "Progress not set to 100!"
        assert completed_job.completed_at is not None, "Completed timestamp not set!"
        print(f"   ✓ Job status: {completed_job.status}")
        print(f"   ✓ Progress: {completed_job.progress}%")
        print(f"   ✓ Completed at: {completed_job.completed_at}")

        # Verify result data
        result_data = completed_job.get_result_data()
        assert result_data == test_result, "Result data doesn't match!"
        print(f"   ✓ Result data: {result_data['processed_images']} images processed")

        # 7. Test retry logic
        print("\n7. Testing retry logic...")
        retry_job = BackgroundJob(
            id=str(uuid.uuid4()),
            job_type='grading',
            status='queued',
            user_id=test_user.id,
            organization_id=test_user.default_organization_id,
            max_retries=3
        )
        db.session.add(retry_job)
        db.session.commit()

        assert retry_job.can_retry() == True, "Should be able to retry!"
        print(f"   ✓ Can retry: {retry_job.can_retry()}")

        retry_job.increment_retry()
        assert retry_job.retry_count == 1, "Retry count not incremented!"
        print(f"   ✓ Retry count incremented: {retry_job.retry_count}")

        # Increment to max retries
        retry_job.increment_retry()
        retry_job.increment_retry()
        assert retry_job.can_retry() == False, "Should not be able to retry!"
        print(f"   ✓ Max retries reached: cannot retry anymore")

        # 8. Test failure
        print("\n8. Testing job failure...")
        failed_job = BackgroundJob(
            id=str(uuid.uuid4()),
            job_type='upload',
            status='processing',
            user_id=test_user.id,
            organization_id=test_user.default_organization_id
        )
        db.session.add(failed_job)
        db.session.commit()

        failed_job.mark_failed("Test error message")
        assert failed_job.status == 'failed', "Status not set to failed!"
        assert failed_job.error_message == "Test error message", "Error message not set!"
        print(f"   ✓ Job marked as failed")
        print(f"   ✓ Error message: {failed_job.error_message}")

        # 9. Query jobs by user
        print("\n9. Querying all jobs for user...")
        user_jobs = BackgroundJob.query.filter_by(user_id=test_user.id).all()
        print(f"   ✓ Found {len(user_jobs)} jobs for user")
        for uj in user_jobs:
            print(f"     - {uj.job_type}: {uj.status} ({uj.progress}%)")

        # Cleanup test jobs
        print("\n10. Cleaning up test jobs...")
        for job in user_jobs:
            db.session.delete(job)
        db.session.commit()
        print(f"   ✓ Deleted {len(user_jobs)} test jobs")

        print("\n" + "="*60)
        print("✓ All tests passed successfully!")
        print("="*60 + "\n")


if __name__ == '__main__':
    try:
        test_basic_job_flow()
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
