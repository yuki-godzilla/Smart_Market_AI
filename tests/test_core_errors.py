from http import HTTPStatus

from backend.core.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    SchemaMismatchError,
    SecurityError,
)


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


def test_provider_unavailable_error_http_mapping():
    err = ProviderUnavailableError("provider unavailable", details={"provider": "yahoo"})

    assert err.http_status == HTTPStatus.SERVICE_UNAVAILABLE
    assert err.to_dict() == {
        "code": "APP-2003",
        "message": "provider unavailable",
        "details": {"provider": "yahoo"},
    }


def test_provider_timeout_error_http_mapping():
    err = ProviderTimeoutError("provider timed out", details={"timeout_seconds": 3})

    assert err.http_status == HTTPStatus.GATEWAY_TIMEOUT
    assert err.to_dict() == {
        "code": "APP-2004",
        "message": "provider timed out",
        "details": {"timeout_seconds": 3},
    }


def test_schema_mismatch_error_code():
    err = SchemaMismatchError("unexpected provider payload")

    assert err.code == "APP-5001"
    assert err.http_status == HTTPStatus.UNPROCESSABLE_ENTITY
