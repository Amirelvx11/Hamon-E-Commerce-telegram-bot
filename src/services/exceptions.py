"""Custom exceptions for the APIService layer."""
from typing import Any

class APIServiceError(Exception):
    def __init__(self, message: str = "An unspecified API service error occurred."):
        self.message = message
        super().__init__(self.message)

class APIAuthenticationError(APIServiceError):
    def __init__(self, message: str = "API authentication failed."):
        super().__init__(message)

class APIResponseError(APIServiceError):
    def __init__(self, status_code: int, error_detail: str | dict | None = None, retryable: bool = False):
        super().__init__(f"API returned error {status_code}: {error_detail}")
        self.status_code = status_code
        self.error_detail = error_detail
        self.retryable = retryable

    def __str__(self):
        return f"[{self.status_code}] {self.error_detail}"

class APIValidationError(APIServiceError):
    def __init__(self, model_name: str, validation_errors: Any):
        self.model_name = model_name
        self.validation_errors = validation_errors
        message = f"Failed to validate API response against {model_name} model. Errors: {validation_errors}"
        super().__init__(message)

class APINetworkError(APIServiceError):
    def __init__(self, original_exception: Exception):
        self.original_exception = original_exception
        message = f"A network error occurred during API request: {original_exception}"
        super().__init__(message)
        
class ConfigurationError(Exception):
    """Raised when a required application configuration is missing or invalid."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"ConfigurationError: {self.message}"

# base alias for global typing and external catching    
API_ERRORS = (APIResponseError, APIValidationError, APINetworkError, APIAuthenticationError)
