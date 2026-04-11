from http import HTTPStatus

from backend.core.errors import RateLimitError, SecurityError


def test_app_error_to_dict():
    err = RateLimitError("provider throttled", details={"provider": "mock"})

    assert err.http_status == HTTPStatus.TOO_MANY_REQUESTS
    assert err.to_dict() == {
        "code": "APP-2001",
        "message": "provider throttled",
        "details": {"provider": "mock"},
    }


def test_security_error_code():
    err = SecurityError("invalid signature")

    assert err.code == "APP-4001"
    assert err.http_status == HTTPStatus.UNAUTHORIZED
