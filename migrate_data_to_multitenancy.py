"""
Data migration script to assign organizations to existing users.

This script:
1. Creates an Organization for each existing User
2. Sets the user as owner (creates OrganizationMember)
3. Sets user.default_organization_id
4. Updates all quizzes owned by the user with organization_id
5. Updates all students from those quizzes with organization_id

Run this script once after adding organization_id columns to the database.
"""

import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from database import db
from models import User, Organization, OrganizationMember, Quiz, Student, QuizSubmission
from app import create_app

def migrate_data():
    """Migrate existing data to multi-tenancy structure."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("DATA MIGRATION: Multi-Tenancy")
        print("=" * 60)
        print()

        # Get all users
        users = User.query.all()
        print(f"Found {len(users)} users to migrate")
        print()

        if not users:
            print("No users found. Nothing to migrate.")
            return

        migrated_count = 0
        skipped_count = 0

        for user in users:
            print(f"Processing user: {user.username} (ID: {user.id})")

            # Check if user already has a default organization
            if user.default_organization_id is not None:
                print(f"  ⚠️  User already has default_organization_id={user.default_organization_id}, skipping")
                skipped_count += 1
                continue

            try:
                # Create organization for this user
                org_name = f"{user.username}'s Organization"
                organization = Organization(
                    name=org_name,
                    plan='free',  # Start with free plan
                    max_quizzes_per_month=10,  # Free plan limit
                    active=True,
                    created_at=user.created_at or datetime.utcnow()
                )
                db.session.add(organization)
                db.session.flush()  # Get the organization ID

                print(f"  ✓ Created organization: {org_name} (ID: {organization.id})")

                # Create organization membership (set user as owner)
                membership = OrganizationMember(
                    organization_id=organization.id,
                    user_id=user.id,
                    role='owner',
                    joined_at=user.created_at or datetime.utcnow()
                )
                db.session.add(membership)
                print(f"  ✓ Set user as organization owner")

                # Set user's default organization
                user.default_organization_id = organization.id
                print(f"  ✓ Set default_organization_id for user")

                # Update all quizzes owned by this user
                quizzes = Quiz.query.filter_by(user_id=user.id).all()
                quiz_count = 0
                student_ids = set()

                for quiz in quizzes:
                    quiz.organization_id = organization.id
                    quiz_count += 1

                    # Collect student IDs from submissions
                    for submission in quiz.submissions:
                        student_ids.add(submission.student_id)

                print(f"  ✓ Updated {quiz_count} quizzes with organization_id")

                # Update all students associated with this user's quizzes
                student_count = 0
                for student_id in student_ids:
                    student = Student.query.get(student_id)
                    if student and student.organization_id is None:
                        student.organization_id = organization.id
                        student_count += 1

                print(f"  ✓ Updated {student_count} students with organization_id")

                # Commit changes for this user
                db.session.commit()
                print(f"  ✅ Migration completed for {user.username}")
                print()

                migrated_count += 1

            except Exception as e:
                db.session.rollback()
                print(f"  ❌ Error migrating user {user.username}: {str(e)}")
                print()
                continue

        print("=" * 60)
        print(f"MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Total users: {len(users)}")
        print(f"Successfully migrated: {migrated_count}")
        print(f"Skipped (already migrated): {skipped_count}")
        print(f"Errors: {len(users) - migrated_count - skipped_count}")
        print()

        if migrated_count > 0:
            print("✅ Data migration completed successfully!")
        else:
            print("⚠️  No users were migrated. All users may already have organizations.")

if __name__ == '__main__':
    print()
    print("This script will migrate existing users to the multi-tenancy structure.")
    print("Each user will get their own organization and all their data will be associated with it.")
    print()

    # Ask for confirmation
    response = input("Do you want to proceed with the migration? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        print()
        migrate_data()
    else:
        print("\nMigration cancelled.")
        sys.exit(0)
