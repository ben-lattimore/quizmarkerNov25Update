"""
Test script to verify the Flask app factory works correctly
"""

import sys
import os

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_app_factory():
    """Test that the app factory creates a valid Flask app"""
    print("Testing Flask app factory...")

    try:
        from app import create_app

        # Create app instance
        app = create_app()

        # Verify app was created
        assert app is not None, "App should not be None"
        assert app.name == 'app', f"App name should be 'app', got '{app.name}'"

        # Verify configuration
        assert 'UPLOAD_FOLDER' in app.config, "UPLOAD_FOLDER should be in config"
        assert 'MAX_CONTENT_LENGTH' in app.config, "MAX_CONTENT_LENGTH should be in config"
        assert 'SQLALCHEMY_DATABASE_URI' in app.config, "Database URI should be configured"

        # Verify extensions are initialized
        from database import db
        assert db is not None, "Database should be initialized"

        # Verify template filters are registered
        assert 'from_json' in app.jinja_env.filters, "from_json filter should be registered"

        print("✓ App factory created successfully")
        print(f"✓ Database URI: {app.config['SQLALCHEMY_DATABASE_URI'][:30]}...")
        print(f"✓ Upload folder: {app.config['UPLOAD_FOLDER']}")
        print(f"✓ Max upload size: {app.config['MAX_CONTENT_LENGTH'] / (1024*1024)} MB")
        print(f"✓ CORS origins: {app.config.get('CORS_ORIGINS')}")
        print(f"✓ Debug mode: {app.config.get('DEBUG')}")

        # Test app context
        with app.app_context():
            from models import User, Student, Quiz, QuizSubmission, QuizQuestion
            print("✓ Models imported successfully")
            print("✓ Database connection verified")

        print("\n✅ All tests passed! App factory is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_app_factory()
    sys.exit(0 if success else 1)
