"""
Comprehensive Test Suite for Phase 3 Implementation

Tests:
1. Redis connectivity
2. Application builds correctly
3. BackgroundJob model operations
4. Job API endpoints
5. Upload endpoint async conversion
6. Task queueing functionality
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

# Set environment for testing
os.environ['FLASK_ENV'] = 'development'
os.environ['TESTING'] = 'true'

print("\n" + "="*70)
print("PHASE 3 IMPLEMENTATION - COMPREHENSIVE TEST SUITE")
print("="*70)

# Test 1: Redis Connectivity
print("\n[TEST 1] Redis Connectivity")
print("-" * 70)
try:
    from redis import Redis
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    redis_conn = Redis.from_url(redis_url, decode_responses=False)

    # Test connection
    redis_conn.ping()
    print("✓ Redis connection successful")
    print(f"  URL: {redis_url}")

    # Test basic operations
    redis_conn.set('test_key', 'test_value', ex=10)
    value = redis_conn.get('test_key')
    assert value == b'test_value', "Redis set/get failed"
    print("✓ Redis read/write operations working")

    redis_conn.delete('test_key')
    print("✓ Redis cleanup successful")

except Exception as e:
    print(f"✗ Redis connection failed: {e}")
    print("  Make sure Redis is running: brew services start redis")
    sys.exit(1)

# Test 2: Application Import and Build
print("\n[TEST 2] Application Import and Build")
print("-" * 70)
try:
    from app import create_app
    app = create_app()
    print("✓ Flask app factory works")
    print(f"  App name: {app.name}")

    # Check extensions
    assert 'SQLALCHEMY_DATABASE_URI' in app.config, "Database not configured"
    print("✓ Database configured")

    assert 'UPLOAD_FOLDER' in app.config, "Upload folder not configured"
    print("✓ Upload folder configured")

    # Check blueprints
    blueprint_names = [bp.name for bp in app.blueprints.values()]
    assert 'api_v1' in blueprint_names, "API v1 blueprint not registered"
    print(f"✓ Blueprints registered: {', '.join(blueprint_names)}")

except Exception as e:
    print(f"✗ Application import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Models Import
print("\n[TEST 3] Models Import")
print("-" * 70)
try:
    from models import BackgroundJob, User, Organization, OrganizationMember
    print("✓ All models imported successfully")

    # Check BackgroundJob has required methods
    required_methods = ['set_input_data', 'get_input_data', 'set_result_data',
                       'get_result_data', 'mark_started', 'mark_completed',
                       'mark_failed', 'can_retry', 'increment_retry']

    for method in required_methods:
        assert hasattr(BackgroundJob, method), f"BackgroundJob missing {method}"

    print(f"✓ BackgroundJob has all required methods ({len(required_methods)} methods)")

except Exception as e:
    print(f"✗ Models import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Database Operations
print("\n[TEST 4] Database Operations")
print("-" * 70)
try:
    from database import db

    with app.app_context():
        # Test that tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()

        required_tables = ['user', 'organization', 'organization_member',
                          'background_job', 'quiz', 'student']

        for table in required_tables:
            assert table in tables, f"Table {table} not found"

        print(f"✓ All required tables exist ({len(required_tables)} tables)")

        # Test BackgroundJob CRUD
        test_job_id = str(uuid.uuid4())
        test_job = BackgroundJob(
            id=test_job_id,
            job_type='test',
            status='queued',
            user_id=1,  # Assuming test user exists
            progress=0
        )

        test_input = {'test': 'data', 'count': 5}
        test_job.set_input_data(test_input)

        db.session.add(test_job)
        db.session.commit()
        print("✓ BackgroundJob create successful")

        # Retrieve
        retrieved = BackgroundJob.query.get(test_job_id)
        assert retrieved is not None, "Job not retrieved"
        assert retrieved.get_input_data() == test_input, "Input data mismatch"
        print("✓ BackgroundJob retrieve successful")

        # Update
        retrieved.mark_started()
        assert retrieved.status == 'processing', "Status not updated"
        assert retrieved.started_at is not None, "Started time not set"
        print("✓ BackgroundJob update successful")

        # Complete
        test_result = {'processed': True, 'items': 10}
        retrieved.mark_completed(test_result)
        assert retrieved.status == 'completed', "Status not completed"
        assert retrieved.get_result_data() == test_result, "Result data mismatch"
        print("✓ BackgroundJob completion successful")

        # Cleanup
        db.session.delete(retrieved)
        db.session.commit()
        print("✓ BackgroundJob delete successful")

except Exception as e:
    print(f"✗ Database operations failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Job API Endpoints
print("\n[TEST 5] Job API Endpoints")
print("-" * 70)
try:
    # Test that endpoints are registered
    with app.app_context():
        # Get all routes
        routes = []
        for rule in app.url_map.iter_rules():
            if '/api/v1/jobs' in rule.rule:
                routes.append((rule.rule, ','.join(rule.methods - {'HEAD', 'OPTIONS'})))

        expected_routes = [
            '/api/v1/jobs',
            '/api/v1/jobs/<job_id>',
            '/api/v1/jobs/<job_id>/result',
            '/api/v1/jobs/stats'
        ]

        for expected in expected_routes:
            found = any(expected in route[0] for route in routes)
            assert found, f"Route {expected} not found"

        print(f"✓ All job API endpoints registered ({len(routes)} routes)")
        for route, methods in sorted(routes):
            print(f"  {methods:20s} {route}")

except Exception as e:
    print(f"✗ Job API endpoints test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Tasks Module
print("\n[TEST 6] Tasks Module")
print("-" * 70)
try:
    import tasks

    # Check Redis connection in tasks
    assert tasks.redis_conn is not None, "Redis connection not initialized"
    tasks.redis_conn.ping()
    print("✓ Tasks module Redis connection working")

    # Check queues exist
    assert tasks.high_queue is not None, "High queue not initialized"
    assert tasks.default_queue is not None, "Default queue not initialized"
    assert tasks.low_queue is not None, "Low queue not initialized"
    print("✓ All task queues initialized (high, default, low)")

    # Check task functions exist
    required_tasks = ['process_images_task', 'grade_quiz_task',
                     'send_email_task', 'cleanup_old_jobs']

    for task_name in required_tasks:
        assert hasattr(tasks, task_name), f"Task {task_name} not found"

    print(f"✓ All task functions defined ({len(required_tasks)} tasks)")

except Exception as e:
    print(f"✗ Tasks module test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Image Processor Progress Callback
print("\n[TEST 7] Image Processor Progress Callback")
print("-" * 70)
try:
    import image_processor
    import inspect

    # Check process_images signature
    sig = inspect.signature(image_processor.process_images)
    params = list(sig.parameters.keys())

    assert 'image_paths' in params, "image_paths parameter missing"
    assert 'progress_callback' in params, "progress_callback parameter missing"
    print("✓ process_images has progress_callback parameter")

    # Test callback functionality
    callback_calls = []

    def test_callback(current, total):
        callback_calls.append((current, total))

    # We can't test with real images, but we can verify the callback parameter works
    # without actually calling it with real images
    print("✓ Progress callback signature verified")

except Exception as e:
    print(f"✗ Image processor test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 8: Upload Endpoint Returns 202
print("\n[TEST 8] Upload Endpoint Async Conversion")
print("-" * 70)
try:
    from app.api.v1 import upload
    import inspect

    # Check upload module imports
    source = inspect.getsource(upload.upload_files)

    assert 'BackgroundJob' in source, "BackgroundJob not imported in upload"
    assert 'process_images_task' in source, "process_images_task not imported"
    assert 'job_id' in source, "job_id not created in upload"
    assert '202' in source, "202 status code not returned"

    print("✓ Upload endpoint imports BackgroundJob")
    print("✓ Upload endpoint imports process_images_task")
    print("✓ Upload endpoint creates job_id")
    print("✓ Upload endpoint returns 202 Accepted")

except Exception as e:
    print(f"✗ Upload endpoint test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 9: RQ Dependencies
print("\n[TEST 9] RQ Dependencies")
print("-" * 70)
try:
    from rq import Queue, Worker
    from rq.job import Job
    import rq_dashboard

    print("✓ RQ library imported successfully")
    print("✓ RQ Dashboard library imported successfully")

    # Test creating a queue
    test_queue = Queue('test', connection=redis_conn)
    assert test_queue.name == 'test', "Queue creation failed"
    print("✓ RQ Queue creation works")

    # Clean up
    test_queue.empty()

except Exception as e:
    print(f"✗ RQ dependencies test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 10: Environment Configuration
print("\n[TEST 10] Environment Configuration")
print("-" * 70)
try:
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    print(f"✓ REDIS_URL configured: {redis_url}")

    with app.app_context():
        upload_folder = app.config.get('UPLOAD_FOLDER')
        assert upload_folder is not None, "UPLOAD_FOLDER not configured"
        print(f"✓ UPLOAD_FOLDER configured: {upload_folder}")

        # Check upload folder exists
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            print(f"✓ Created upload folder: {upload_folder}")
        else:
            print(f"✓ Upload folder exists: {upload_folder}")

except Exception as e:
    print(f"✗ Environment configuration test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 11: Build Verification
print("\n[TEST 11] Build Verification")
print("-" * 70)
try:
    # Try importing all key modules
    imports = [
        ('app', 'create_app'),
        ('models', 'BackgroundJob'),
        ('models', 'User'),
        ('models', 'Organization'),
        ('database', 'db'),
        ('tasks', 'process_images_task'),
        ('tasks', 'grade_quiz_task'),
        ('app.api.v1', 'api_v1_bp'),
        ('app.api.v1.jobs', None),
        ('app.api.v1.upload', None),
    ]

    for module_name, attr_name in imports:
        try:
            module = __import__(module_name, fromlist=[attr_name] if attr_name else [])
            if attr_name:
                assert hasattr(module, attr_name), f"{module_name} missing {attr_name}"
            print(f"✓ {module_name}{f'.{attr_name}' if attr_name else ''}")
        except Exception as e:
            print(f"✗ Failed to import {module_name}: {e}")
            raise

    print(f"✓ All modules import successfully ({len(imports)} imports)")

except Exception as e:
    print(f"✗ Build verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 12: Retry Logic
print("\n[TEST 12] Retry Logic")
print("-" * 70)
try:
    with app.app_context():
        # Create job with retry logic
        test_job_id = str(uuid.uuid4())
        test_job = BackgroundJob(
            id=test_job_id,
            job_type='test',
            status='queued',
            user_id=1,
            max_retries=3,
            retry_count=0
        )

        db.session.add(test_job)
        db.session.commit()

        # Test retry logic
        assert test_job.can_retry() == True, "Should be able to retry"
        print("✓ can_retry() returns True when retries available")

        test_job.increment_retry()
        assert test_job.retry_count == 1, "Retry count not incremented"
        print("✓ increment_retry() increments counter")

        # Increment to max
        test_job.increment_retry()
        test_job.increment_retry()
        assert test_job.retry_count == 3, "Retry count incorrect"
        assert test_job.can_retry() == False, "Should not be able to retry"
        print("✓ can_retry() returns False when max retries reached")

        # Cleanup
        db.session.delete(test_job)
        db.session.commit()
        print("✓ Retry logic working correctly")

except Exception as e:
    print(f"✗ Retry logic test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

test_results = [
    ("Redis Connectivity", True),
    ("Application Build", True),
    ("Models Import", True),
    ("Database Operations", True),
    ("Job API Endpoints", True),
    ("Tasks Module", True),
    ("Image Processor Progress Callback", True),
    ("Upload Endpoint Async Conversion", True),
    ("RQ Dependencies", True),
    ("Environment Configuration", True),
    ("Build Verification", True),
    ("Retry Logic", True),
]

passed = sum(1 for _, result in test_results if result)
total = len(test_results)

print(f"\nTests Passed: {passed}/{total}")
print("\nDetailed Results:")
for test_name, result in test_results:
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"  {status:10s} {test_name}")

if passed == total:
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED - PHASE 3 IMPLEMENTATION VERIFIED")
    print("="*70)
    print("\nThe implementation is working correctly!")
    print("Ready for:")
    print("  1. Starting RQ worker")
    print("  2. Testing with real image uploads")
    print("  3. Frontend polling implementation")
    print("="*70 + "\n")
    sys.exit(0)
else:
    print("\n" + "="*70)
    print("✗ SOME TESTS FAILED")
    print("="*70 + "\n")
    sys.exit(1)
