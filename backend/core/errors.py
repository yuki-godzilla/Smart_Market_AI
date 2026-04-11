from http import HTTPStatus


class AppError(Exception):
    code = "APP-0000"
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationAppError(AppError):
    code = "APP-1001"
    http_status = HTTPStatus.BAD_REQUEST


class DataSourceError(AppError):
    code = "APP-2000"
    http_status = HTTPStatus.BAD_GATEWAY


class RateLimitError(DataSourceError):
    code = "APP-2001"
    http_status = HTTPStatus.TOO_MANY_REQUESTS


class BrokerError(AppError):
    code = "APP-3001"
    http_status = HTTPStatus.BAD_GATEWAY


class UnsupportedTifError(BrokerError):
    code = "APP-3101"
    http_status = HTTPStatus.BAD_REQUEST


class SecurityError(AppError):
    code = "APP-4001"
    http_status = HTTPStatus.UNAUTHORIZED


class SchemaMismatchError(AppError):
    code = "APP-5001"
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
