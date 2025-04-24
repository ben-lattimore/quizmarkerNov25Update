#!/usr/bin/env python3
"""
Script to add is_super_admin column and set a specific user as super admin
"""

import sys
import os
import logging
from database import db
from app import app
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def add_super_admin_column():
    """Add is_super_admin column to the user table if it doesn't exist"""
    with app.app_context():
        # Always start with a fresh session for DDL operations
        db.session.close()
        
        # First check if column exists using raw connection
        conn = db.engine.connect()
        try:
            # Create a transaction to check if the column exists
            conn.execute(text('SELECT is_super_admin FROM "user" LIMIT 1'))
            conn.close()
            logging.info("Column is_super_admin already exists")
            return True
        except Exception:
            conn.close()  # Close the connection with error
            
            # Try to add the column with a new connection
            new_conn = db.engine.connect()
            try:
                # Add column using raw SQL
                new_conn.execute(text('ALTER TABLE "user" ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE'))
                new_conn.commit()
                logging.info("Successfully added is_super_admin column to user table")
                new_conn.close()
                return True
            except Exception as e:
                if not new_conn.closed:
                    new_conn.close()
                logging.error(f"Failed to add column: {e}")
                return False

def set_super_admin(email):
    """Set the specified user as a super admin"""
    with app.app_context():
        # Always start with a fresh connection
        conn = db.engine.connect()
        try:
            # Update the user record directly with SQL
            result = conn.execute(
                text('UPDATE "user" SET is_super_admin = TRUE, is_admin = TRUE WHERE email = :email'),
                {"email": email}
            )
            conn.commit()
            
            rowcount = result.rowcount
            conn.close()
            
            if rowcount > 0:
                logging.info(f"Successfully set {email} as a super admin")
                return True
            else:
                logging.error(f"User with email {email} not found")
                return False
        except Exception as e:
            if not conn.closed:
                conn.close()
            logging.error(f"Failed to set super admin: {e}")
            return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python add_super_admin.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    
    if add_super_admin_column():
        logging.info("Column added or already exists")
    else:
        logging.error("Failed to add column to database")
        sys.exit(1)
    
    logging.info(f"Setting super admin privileges for user: {email}")
    if set_super_admin(email):
        logging.info("Operation completed successfully")
    else:
        logging.error("Operation failed")
        sys.exit(1)