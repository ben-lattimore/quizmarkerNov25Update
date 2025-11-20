"""
Job status and management endpoints for async processing

Provides endpoints for:
- Getting job status
- Getting job results
- Listing user's jobs
- Canceling jobs (optional)
"""

from flask import jsonify, g
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.api.v1 import api_v1_bp
from models import BackgroundJob
from database import db


@api_v1_bp.route('/jobs/<job_id>', methods=['GET'])
@login_required
def get_job_status(job_id):
    """
    Get the status of a background job

    Returns:
        200: Job status with progress and results
        403: User doesn't have permission to view this job
        404: Job not found

    Response format:
        {
            "success": true,
            "data": {
                "job_id": "abc-123",
                "job_type": "upload",
                "status": "processing",
                "progress": 45,
                "current_step": "Processing image 2 of 5",
                "created_at": "2025-11-19T12:00:00",
                "started_at": "2025-11-19T12:00:05",
                "completed_at": null,
                "result": null,
                "error": null
            }
        }
    """
    # Get job from database
    job = BackgroundJob.query.get(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': 'Job not found',
            'code': 'JOB_NOT_FOUND'
        }), 404

    # Verify user has permission to view this job
    if job.user_id != current_user.id and not current_user.is_super_admin:
        return jsonify({
            'success': False,
            'error': 'You do not have permission to view this job',
            'code': 'PERMISSION_DENIED'
        }), 403

    # Build response data
    response_data = {
        'job_id': job.id,
        'job_type': job.job_type,
        'status': job.status,
        'progress': job.progress,
        'current_step': job.current_step,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'retry_count': job.retry_count,
        'result': job.get_result_data() if job.status == 'completed' else None,
        'error': job.error_message if job.status == 'failed' else None
    }

    return jsonify({
        'success': True,
        'data': response_data
    }), 200


@api_v1_bp.route('/jobs', methods=['GET'])
@login_required
def list_jobs():
    """
    List all jobs for the current user

    Query parameters:
        - status: Filter by status (queued, processing, completed, failed)
        - job_type: Filter by job type (upload, grading, email)
        - limit: Max number of jobs to return (default: 50, max: 100)
        - offset: Pagination offset (default: 0)

    Returns:
        200: List of jobs

    Response format:
        {
            "success": true,
            "data": {
                "jobs": [...],
                "total": 10,
                "limit": 50,
                "offset": 0
            }
        }
    """
    from flask import request

    # Get query parameters
    status_filter = request.args.get('status')
    job_type_filter = request.args.get('job_type')
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    # Build query
    query = BackgroundJob.query

    # Filter by user (unless super admin)
    if not current_user.is_super_admin:
        query = query.filter_by(user_id=current_user.id)

    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)

    if job_type_filter:
        query = query.filter_by(job_type=job_type_filter)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    jobs = query.order_by(BackgroundJob.created_at.desc()).limit(limit).offset(offset).all()

    # Build response
    jobs_data = []
    for job in jobs:
        jobs_data.append({
            'job_id': job.id,
            'job_type': job.job_type,
            'status': job.status,
            'progress': job.progress,
            'current_step': job.current_step,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'has_error': job.error_message is not None
        })

    return jsonify({
        'success': True,
        'data': {
            'jobs': jobs_data,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    }), 200


@api_v1_bp.route('/jobs/<job_id>/result', methods=['GET'])
@login_required
def get_job_result(job_id):
    """
    Get the result of a completed job

    Returns:
        200: Job result data
        403: Permission denied
        404: Job not found
        400: Job not completed yet

    Response format:
        {
            "success": true,
            "data": {
                "job_id": "abc-123",
                "status": "completed",
                "result": {...}  // Job-specific result data
            }
        }
    """
    # Get job from database
    job = BackgroundJob.query.get(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': 'Job not found',
            'code': 'JOB_NOT_FOUND'
        }), 404

    # Verify permission
    if job.user_id != current_user.id and not current_user.is_super_admin:
        return jsonify({
            'success': False,
            'error': 'You do not have permission to view this job',
            'code': 'PERMISSION_DENIED'
        }), 403

    # Check if job is completed
    if job.status != 'completed':
        return jsonify({
            'success': False,
            'error': f'Job is not completed yet (status: {job.status})',
            'code': 'JOB_NOT_COMPLETED',
            'data': {
                'status': job.status,
                'progress': job.progress
            }
        }), 400

    return jsonify({
        'success': True,
        'data': {
            'job_id': job.id,
            'status': job.status,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'result': job.get_result_data()
        }
    }), 200


@api_v1_bp.route('/jobs/stats', methods=['GET'])
@login_required
def get_job_stats():
    """
    Get statistics about user's jobs

    Returns:
        200: Job statistics

    Response format:
        {
            "success": true,
            "data": {
                "total_jobs": 100,
                "queued": 5,
                "processing": 2,
                "completed": 90,
                "failed": 3,
                "jobs_last_24h": 15,
                "avg_processing_time": 45.2  // seconds
            }
        }
    """
    from sqlalchemy import func, extract

    # Build base query
    query = BackgroundJob.query
    if not current_user.is_super_admin:
        query = query.filter_by(user_id=current_user.id)

    # Get counts by status
    total_jobs = query.count()
    queued = query.filter_by(status='queued').count()
    processing = query.filter_by(status='processing').count()
    completed = query.filter_by(status='completed').count()
    failed = query.filter_by(status='failed').count()

    # Get jobs in last 24 hours
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    jobs_last_24h = query.filter(BackgroundJob.created_at >= cutoff_time).count()

    # Calculate average processing time for completed jobs
    completed_jobs = query.filter_by(status='completed').filter(
        BackgroundJob.started_at.isnot(None),
        BackgroundJob.completed_at.isnot(None)
    ).all()

    avg_processing_time = 0
    if completed_jobs:
        total_time = sum(
            (job.completed_at - job.started_at).total_seconds()
            for job in completed_jobs
        )
        avg_processing_time = round(total_time / len(completed_jobs), 2)

    return jsonify({
        'success': True,
        'data': {
            'total_jobs': total_jobs,
            'queued': queued,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'jobs_last_24h': jobs_last_24h,
            'avg_processing_time': avg_processing_time
        }
    }), 200


@api_v1_bp.route('/jobs/<job_id>', methods=['DELETE'])
@login_required
def cancel_job(job_id):
    """
    Cancel a queued or processing job (optional feature)

    Note: This only marks the job as failed. If the job is already processing,
    it will continue until completion but the status will be marked as failed.

    Returns:
        200: Job canceled successfully
        403: Permission denied
        404: Job not found
        400: Job cannot be canceled (already completed/failed)
    """
    # Get job from database
    job = BackgroundJob.query.get(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': 'Job not found',
            'code': 'JOB_NOT_FOUND'
        }), 404

    # Verify permission
    if job.user_id != current_user.id and not current_user.is_super_admin:
        return jsonify({
            'success': False,
            'error': 'You do not have permission to cancel this job',
            'code': 'PERMISSION_DENIED'
        }), 403

    # Check if job can be canceled
    if job.status in ['completed', 'failed']:
        return jsonify({
            'success': False,
            'error': f'Job cannot be canceled (status: {job.status})',
            'code': 'JOB_CANNOT_BE_CANCELED'
        }), 400

    # Mark job as failed (canceled)
    job.mark_failed('Job canceled by user')

    return jsonify({
        'success': True,
        'message': 'Job canceled successfully',
        'data': {
            'job_id': job.id,
            'status': job.status
        }
    }), 200
