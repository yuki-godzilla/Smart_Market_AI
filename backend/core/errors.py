from http import HTTPStatus


class AppError(Exception):
    """Base application error with an app-specific code and HTTP mapping."""

    code = "APP-0000"
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        """Create an application error with optional structured details."""

        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        """Serialize the error for API responses or structured logs."""

        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationAppError(AppError):
    """Input validation failed before service execution."""

    code = "APP-1001"
    http_status = HTTPStatus.BAD_REQUEST


class DataSourceError(AppError):
    """Market-data or external data source request failed."""

    code = "APP-2000"
    http_status = HTTPStatus.BAD_GATEWAY


class ComputationError(AppError):
    """Application could not compute a derived value from otherwise valid inputs."""

    code = "APP-2002"
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY


class RateLimitError(DataSourceError):
    """Data provider rejected or delayed a request due to rate limits."""

    code = "APP-2001"
    http_status = HTTPStatus.TOO_MANY_REQUESTS


class BrokerError(AppError):
    """Broker or execution provider request failed."""

    code = "APP-3001"
    http_status = HTTPStatus.BAD_GATEWAY


class UnsupportedTifError(BrokerError):
    """Requested time-in-force is unsupported by the broker or market."""

    code = "APP-3101"
    http_status = HTTPStatus.BAD_REQUEST


class SecurityError(AppError):
    """Security validation failed, such as HMAC or timestamp checks."""

    code = "APP-4001"
    http_status = HTTPStatus.UNAUTHORIZED


class SchemaMismatchError(AppError):
    """Received data did not match the expected contract."""

    code = "APP-5001"
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
