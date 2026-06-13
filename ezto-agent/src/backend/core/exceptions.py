"""Application-level exceptions."""


class AppError(Exception):
    """Base application error."""
    status_code: int = 500

    def __init__(self, message: str, detail: dict | None = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class BadRequestError(AppError):
    status_code = 400


class PolicyViolationError(AppError):
    status_code = 403
