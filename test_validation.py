"""
Test script to verify Marshmallow validation works correctly
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_validation():
    """Test that Marshmallow validation schemas work correctly"""
    print("Testing Marshmallow validation...")

    try:
        from app.schemas import RegisterSchema, LoginSchema, GradeQuizSchema
        from marshmallow import ValidationError

        # Test 1: Valid registration data
        schema = RegisterSchema()
        valid_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        schema.context = {'password': valid_data['password']}
        result = schema.load(valid_data)
        assert result['username'] == 'testuser'
        print("✓ Valid registration data accepted")

        # Test 2: Invalid email
        try:
            invalid_data = valid_data.copy()
            invalid_data['email'] = 'not-an-email'
            schema.load(invalid_data)
            assert False, "Should have raised ValidationError for invalid email"
        except ValidationError as e:
            assert 'email' in e.messages
            print("✓ Invalid email rejected")

        # Test 3: Short password
        try:
            invalid_data = valid_data.copy()
            invalid_data['password'] = 'short'
            invalid_data['confirm_password'] = 'short'
            schema.context = {'password': invalid_data['password']}
            schema.load(invalid_data)
            assert False, "Should have raised ValidationError for short password"
        except ValidationError as e:
            assert 'password' in e.messages
            print("✓ Short password rejected")

        # Test 4: Password mismatch
        try:
            invalid_data = valid_data.copy()
            invalid_data['confirm_password'] = 'different'
            schema.context = {'password': invalid_data['password']}
            schema.load(invalid_data)
            assert False, "Should have raised ValidationError for password mismatch"
        except ValidationError as e:
            assert 'confirm_password' in e.messages
            print("✓ Password mismatch detected")

        # Test 5: Invalid username characters
        try:
            invalid_data = valid_data.copy()
            invalid_data['username'] = 'user@name!'
            schema.context = {'password': valid_data['password']}
            schema.load(invalid_data)
            assert False, "Should have raised ValidationError for invalid username"
        except ValidationError as e:
            assert 'username' in e.messages
            print("✓ Invalid username characters rejected")

        # Test 6: Valid login data
        login_schema = LoginSchema()
        login_data = {
            'username': 'testuser',
            'password': 'password123'
        }
        result = login_schema.load(login_data)
        assert result['username'] == 'testuser'
        assert result['remember'] == False  # Default value
        print("✓ Valid login data accepted")

        # Test 7: Login with remember=true
        login_data['remember'] = True
        result = login_schema.load(login_data)
        assert result['remember'] == True
        print("✓ Login with remember flag works")

        # Test 8: Valid grading data
        grade_schema = GradeQuizSchema()
        grade_data = {
            'data': [
                {
                    'filename': 'test.jpg',
                    'data': {'handwritten_content': 'Some text'}
                }
            ],
            'standard_id': 5,
            'student_name': 'John Doe'
        }
        result = grade_schema.load(grade_data)
        assert result['standard_id'] == 5
        assert len(result['data']) == 1
        print("✓ Valid grading data accepted")

        # Test 9: Invalid standard_id (out of range)
        try:
            invalid_data = grade_data.copy()
            invalid_data['standard_id'] = 99  # Out of range (1-20)
            grade_schema.load(invalid_data)
            assert False, "Should have raised ValidationError for invalid standard_id"
        except ValidationError as e:
            assert 'standard_id' in e.messages
            print("✓ Out-of-range standard_id rejected")

        # Test 10: Empty data array
        try:
            invalid_data = grade_data.copy()
            invalid_data['data'] = []
            grade_schema.load(invalid_data)
            assert False, "Should have raised ValidationError for empty data array"
        except ValidationError as e:
            assert 'data' in e.messages
            print("✓ Empty data array rejected")

        print("\n✅ All validation tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_validation()
    sys.exit(0 if success else 1)
