import pytest
from nexarch import NexarchSDK
from fastapi import FastAPI


def test_sdk_initialization():
    """Test basic SDK initialization"""
    sdk = NexarchSDK(
        api_key="test_key",
        environment="test",
        service_name="test_service"
    )
    assert sdk.api_key == "test_key"
    assert sdk.environment == "test"
    assert sdk.service_name == "test_service"


def test_sdk_with_fastapi():
    """Test SDK integration with FastAPI"""
    app = FastAPI()
    sdk = NexarchSDK(
        api_key="test_key",
        environment="test",
        project_name="test-project",
    )
    sdk.init(app)
    
    # Check middleware is added
    assert len(app.user_middleware) > 0
    
    # No internal telemetry router should be injected anymore
    routes = [route.path for route in app.routes]
    assert "/__nexarch/health" not in routes

    assert sdk.project_name == "test-project"


def test_sampling_rate_validation():
    """Test sampling rate is clamped to valid range"""
    sdk1 = NexarchSDK(api_key="test", sampling_rate=1.5)
    assert sdk1.sampling_rate == 1.0
    
    sdk2 = NexarchSDK(api_key="test", sampling_rate=-0.5)
    assert sdk2.sampling_rate == 0.0
    
    sdk3 = NexarchSDK(api_key="test", sampling_rate=0.5)
    assert sdk3.sampling_rate == 0.5
