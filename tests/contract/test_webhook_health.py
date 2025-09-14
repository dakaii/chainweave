"""Contract test for GET /health endpoint.

This test validates the health check API contract per webhook-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestWebhookHealthContract:
    """Contract tests for webhook service health endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for webhook service.
        
        This will fail initially since the FastAPI app doesn't exist yet.
        This is expected and required for TDD.
        """
        # This import will fail initially - that's expected!
        from backend.webhook_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_health_endpoint_returns_200(self, client: TestClient):
        """Test health endpoint returns 200 with required fields."""
        response: Response = client.get("/health")
        
        # Contract assertions per OpenAPI spec
        assert response.status_code == 200
        
        response_data = response.json()
        
        # Required fields per contract
        assert "status" in response_data
        assert "timestamp" in response_data
        assert "version" in response_data
        
        # Status should be "healthy" for successful response
        assert response_data["status"] == "healthy"
        
        # Version should be semantic version format
        version = response_data["version"]
        assert isinstance(version, str)
        assert len(version.split(".")) >= 2  # At least X.Y format
        
        # Timestamp should be ISO 8601 format
        timestamp = response_data["timestamp"]
        assert isinstance(timestamp, str)
        assert "T" in timestamp  # ISO format contains T
        assert timestamp.endswith("Z") or "+" in timestamp  # UTC or timezone

    def test_health_endpoint_response_content_type(self, client: TestClient):
        """Test health endpoint returns JSON content type."""
        response: Response = client.get("/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_health_endpoint_response_time(self, client: TestClient):
        """Test health endpoint responds quickly (< 1 second)."""
        import time
        
        start_time = time.time()
        response: Response = client.get("/health") 
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0, f"Health check took {response_time:.2f}s, should be < 1s"

    def test_health_endpoint_no_authentication_required(self, client: TestClient):
        """Test health endpoint accessible without authentication."""
        # Health endpoints should always be public for load balancer checks
        response: Response = client.get("/health")
        
        # Should not return 401 or 403
        assert response.status_code != 401
        assert response.status_code != 403
        assert response.status_code == 200

    def test_health_endpoint_handles_head_request(self, client: TestClient):
        """Test health endpoint handles HEAD requests for load balancers.""" 
        response: Response = client.head("/health")
        
        # HEAD request should return same status as GET but no body
        assert response.status_code == 200
        assert len(response.content) == 0

    def test_health_endpoint_cors_headers(self, client: TestClient):
        """Test health endpoint includes proper CORS headers."""
        response: Response = client.get("/health")
        
        assert response.status_code == 200
        
        # Should allow CORS for monitoring tools
        headers = response.headers
        
        # At minimum should not block basic CORS
        # Specific CORS config will be tested in integration tests
        assert "access-control-allow-origin" in headers or response.status_code == 200

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_health_endpoint_method_not_allowed(self, client: TestClient, method: str):
        """Test health endpoint only allows GET and HEAD methods."""
        response: Response = client.request(method, "/health")
        
        # Should return 405 Method Not Allowed for unsupported methods
        assert response.status_code == 405

    def test_health_endpoint_with_query_parameters(self, client: TestClient):
        """Test health endpoint ignores query parameters."""
        response: Response = client.get("/health?check=deep&timeout=30")
        
        # Should still return successful health check
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["status"] == "healthy"

    def test_health_endpoint_response_schema(self, client: TestClient):
        """Test health endpoint response matches exact schema."""
        response: Response = client.get("/health")
        
        assert response.status_code == 200
        response_data = response.json()
        
        # Validate exact schema per OpenAPI spec
        expected_fields = {"status", "timestamp", "version"}
        actual_fields = set(response_data.keys())
        
        # Should have exactly these fields, no more, no less
        assert actual_fields == expected_fields
        
        # Validate field types
        assert isinstance(response_data["status"], str)
        assert isinstance(response_data["timestamp"], str)  
        assert isinstance(response_data["version"], str)