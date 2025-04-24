#!/usr/bin/env python3
"""
Script to set a user account as super admin
Usage: python set_super_admin.py <email>
"""

import sys
import os
import logging
from database import db
from models import User
from app import app

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def set_super_admin(email):
    """Set the specified user as a super admin"""
    with app.app_context():
        # Find the user by email
        user = User.query.filter_by(email=email).first()
        
        if not user:
            logging.error(f"User with email {email} not found in the database")
            return False
        
        # Set super admin privileges
        user.is_super_admin = True
        
        # Also ensure they have regular admin privileges
        user.is_admin = True
        
        # Commit the changes
        try:
            db.session.commit()
            logging.info(f"Successfully set {user.username} ({email}) as a super admin")
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to set super admin privileges: {e}")
            return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python set_super_admin.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    
    logging.info(f"Setting super admin privileges for user: {email}")
    if set_super_admin(email):
        logging.info("Operation completed successfully")
    else:
        logging.error("Operation failed")
        sys.exit(1)