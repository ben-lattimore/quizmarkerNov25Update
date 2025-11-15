"""
Test script to verify the API Blueprint structure works correctly
"""

import sys
import os

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_api_blueprint():
    """Test that the API blueprint is registered and routes work"""
    print("Testing API Blueprint structure...")

    try:
        from app import create_app

        # Create app instance
        app = create_app()

        # Create a test client
        with app.test_client() as client:
            # Test 1: API index endpoint
            response = client.get('/api/v1/')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.get_json()
            assert data['success'] == True, "API index should return success=True"
            assert 'endpoints' in data, "API index should list endpoints"
            print("✓ API index endpoint (/api/v1/) working")

            # Test 2: Health check endpoint
            response = client.get('/api/v1/health')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.get_json()
            assert data['status'] == 'healthy', "Health endpoint should return healthy status"
            print("✓ Health check endpoint (/api/v1/health) working")

            # Test 3: Standards endpoint
            response = client.get('/api/v1/standards')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.get_json()
            assert 'success' in data, "Standards endpoint should have success field"
            print("✓ Standards endpoint (/api/v1/standards) working")

            # Test 4: Auth endpoints exist (should require data, but route should exist)
            response = client.post('/api/v1/auth/register')
            # Should get 400 (no data) not 404 (not found)
            assert response.status_code in [400, 401], f"Register endpoint exists (got {response.status_code})"
            print("✓ Register endpoint (/api/v1/auth/register) exists")

            response = client.post('/api/v1/auth/login')
            assert response.status_code in [400, 401], f"Login endpoint exists (got {response.status_code})"
            print("✓ Login endpoint (/api/v1/auth/login) exists")

            # Test 5: Upload endpoint exists (should require auth)
            response = client.post('/api/v1/upload')
            # Should get 401 (unauthorized) not 404 (not found)
            assert response.status_code == 401, f"Upload endpoint requires auth (got {response.status_code})"
            print("✓ Upload endpoint (/api/v1/upload) requires auth")

            # Test 6: Grade endpoint exists (should require auth)
            response = client.post('/api/v1/grade')
            assert response.status_code == 401, f"Grade endpoint requires auth (got {response.status_code})"
            print("✓ Grade endpoint (/api/v1/grade) requires auth")

            # Test 7: Quizzes list endpoint exists (should require auth)
            response = client.get('/api/v1/quizzes')
            assert response.status_code == 401, f"Quizzes endpoint requires auth (got {response.status_code})"
            print("✓ Quizzes list endpoint (/api/v1/quizzes) requires auth")

        # Test 8: Verify blueprint is registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        assert 'api_v1' in blueprint_names, "API v1 blueprint should be registered"
        print("✓ API v1 blueprint is registered")

        # Test 9: List all API routes
        api_routes = []
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/api/v1'):
                api_routes.append(f"{rule.methods} {rule.rule}")

        print(f"\n📋 Found {len(api_routes)} API v1 routes:")
        for route in sorted(api_routes):
            print(f"   {route}")

        print("\n✅ All API blueprint tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_api_blueprint()
    sys.exit(0 if success else 1)
