"""
Custom exceptions for validation service operations.
"""


class ValidationError(Exception):
    """Base exception for validation-related errors."""
    pass


class ValidationServiceError(Exception):
    """Exception for validation service operational errors."""
    pass


class ValidationFileError(ValidationError):
    """Exception for file-related validation errors."""
    pass


class ValidationContentError(ValidationError):
    """Exception for content-related validation errors."""
    pass


class ValidationCacheError(ValidationServiceError):
    """Exception for cache-related validation errors."""
    pass


class ValidationBatchError(ValidationServiceError):
    """Exception for batch validation errors."""
    pass 