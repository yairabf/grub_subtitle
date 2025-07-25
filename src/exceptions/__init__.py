"""
Custom exceptions for Hebrew Subtitle Service.
"""

from .subtitle_exceptions import (
    SubtitleProcessingError,
    APIRateLimitError,
    TranslationError,
    ValidationError,
    ConfigurationError,
    FileProcessingError
)

__all__ = [
    'SubtitleProcessingError',
    'APIRateLimitError', 
    'TranslationError',
    'ValidationError',
    'ConfigurationError',
    'FileProcessingError'
] 