"""
Periodic Job Cleanup Script

This script can be run manually or set up as a cron job to automatically
clean up old completed/failed jobs from the database.

Usage:
    python run_job_cleanup.py              # Run once
    python run_job_cleanup.py --schedule   # Run continuously every hour
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta

# Set up environment
os.environ.setdefault('FLASK_ENV', 'production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_old_jobs():
    """
    Clean up old completed/failed jobs from the database

    Deletes jobs that:
    - Have status 'completed' or 'failed'
    - Are older than 24 hours (completed_at < now - 24h)
    """
    try:
        from app import create_app
        from models import BackgroundJob
        from database import db

        app = create_app()

        with app.app_context():
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            logger.info(f"Looking for jobs older than {cutoff_time}")

            # Find old jobs
            old_jobs = BackgroundJob.query.filter(
                BackgroundJob.status.in_(['completed', 'failed']),
                BackgroundJob.completed_at < cutoff_time
            ).all()

            count = len(old_jobs)

            if count == 0:
                logger.info("No old jobs to clean up")
                return 0

            logger.info(f"Found {count} old jobs to delete")

            # Delete jobs
            for job in old_jobs:
                logger.debug(f"Deleting job {job.id} (type={job.job_type}, status={job.status})")
                db.session.delete(job)

            db.session.commit()

            logger.info(f"Successfully deleted {count} old jobs")
            return count

    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return -1


def main():
    parser = argparse.ArgumentParser(description='Clean up old background jobs')
    parser.add_argument('--schedule', action='store_true',
                       help='Run continuously every hour instead of once')
    parser.add_argument('--interval', type=int, default=3600,
                       help='Interval in seconds between cleanups (default: 3600 = 1 hour)')

    args = parser.parse_args()

    if args.schedule:
        logger.info(f"Starting scheduled cleanup (every {args.interval} seconds)")
        try:
            while True:
                logger.info("Running cleanup...")
                count = cleanup_old_jobs()

                if count >= 0:
                    logger.info(f"Cleanup complete. Next run in {args.interval} seconds")
                else:
                    logger.error("Cleanup failed")

                time.sleep(args.interval)

        except KeyboardInterrupt:
            logger.info("Cleanup scheduler stopped by user")
            sys.exit(0)
    else:
        logger.info("Running one-time cleanup...")
        count = cleanup_old_jobs()

        if count >= 0:
            logger.info("Cleanup complete")
            sys.exit(0)
        else:
            logger.error("Cleanup failed")
            sys.exit(1)


if __name__ == '__main__':
    main()
