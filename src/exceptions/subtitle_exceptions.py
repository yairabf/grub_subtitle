"""
Custom exception hierarchy for Hebrew Subtitle Service.
Provides specific exception types with context and metadata.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

class SubtitleProcessingError(Exception):
    """Base exception for subtitle processing errors."""
    
    def __init__(self, message: str, error_type: str = "general", 
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the subtitle processing error.
        
        Args:
            message: Error message
            error_type: Type of error (e.g., 'api', 'translation', 'validation')
            file_path: Path to the file being processed
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.file_path = file_path
        self.context = context or {}
        self.timestamp = datetime.utcnow()
        self.error_id = self._generate_error_id()
    
    def _generate_error_id(self) -> str:
        """Generate a unique error ID."""
        import uuid
        return f"err_{self.timestamp.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            'error_id': self.error_id,
            'error_type': self.error_type,
            'message': self.message,
            'file_path': self.file_path,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'exception_class': self.__class__.__name__
        }
    
    def __str__(self) -> str:
        """String representation of the error."""
        base_msg = f"[{self.error_type.upper()}] {self.message}"
        if self.file_path:
            base_msg += f" (File: {self.file_path})"
        if self.error_id:
            base_msg += f" (ID: {self.error_id})"
        return base_msg

class APIRateLimitError(SubtitleProcessingError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, api_name: str, retry_after: Optional[int] = None, 
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize API rate limit error.
        
        Args:
            api_name: Name of the API (e.g., 'opensubtitles', 'openai')
            retry_after: Seconds to wait before retrying
            file_path: Path to the file being processed
            context: Additional context information
        """
        message = f"API rate limit exceeded for {api_name}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        
        super().__init__(message, "api_rate_limit", file_path, context)
        self.api_name = api_name
        self.retry_after = retry_after

class APIConnectionError(SubtitleProcessingError):
    """Raised when API connection fails."""
    
    def __init__(self, api_name: str, endpoint: str, status_code: Optional[int] = None,
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize API connection error.
        
        Args:
            api_name: Name of the API
            endpoint: API endpoint that failed
            status_code: HTTP status code if available
            file_path: Path to the file being processed
            context: Additional context information
        """
        message = f"API connection failed for {api_name} at {endpoint}"
        if status_code:
            message += f" (Status: {status_code})"
        
        super().__init__(message, "api_connection", file_path, context)
        self.api_name = api_name
        self.endpoint = endpoint
        self.status_code = status_code

class TranslationError(SubtitleProcessingError):
    """Raised when translation fails."""
    
    def __init__(self, reason: str, chunk_number: Optional[int] = None,
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize translation error.
        
        Args:
            reason: Reason for translation failure
            chunk_number: Number of the chunk that failed
            file_path: Path to the file being processed
            context: Additional context information
        """
        message = f"Translation failed: {reason}"
        if chunk_number is not None:
            message += f" (Chunk {chunk_number})"
        
        super().__init__(message, "translation", file_path, context)
        self.reason = reason
        self.chunk_number = chunk_number

class ValidationError(SubtitleProcessingError):
    """Raised when subtitle validation fails."""
    
    def __init__(self, validation_type: str, details: str, errors: Optional[List[str]] = None,
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error.
        
        Args:
            validation_type: Type of validation that failed
            details: Detailed error message
            errors: List of specific validation errors
            file_path: Path to the file being processed
            context: Additional context information
        """
        message = f"Validation failed ({validation_type}): {details}"
        
        super().__init__(message, "validation", file_path, context)
        self.validation_type = validation_type
        self.details = details
        self.errors = errors or []

class ConfigurationError(SubtitleProcessingError):
    """Raised when there's an error with configuration."""
    
    def __init__(self, config_key: str, reason: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration error.
        
        Args:
            config_key: Configuration key that caused the error
            reason: Reason for the configuration error
            context: Additional context information
        """
        message = f"Configuration error for '{config_key}': {reason}"
        
        super().__init__(message, "configuration", None, context)
        self.config_key = config_key
        self.reason = reason

class FileProcessingError(SubtitleProcessingError):
    """Raised when file processing fails."""
    
    def __init__(self, operation: str, reason: str, file_path: str,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize file processing error.
        
        Args:
            operation: Operation that failed (e.g., 'read', 'write', 'parse')
            reason: Reason for the failure
            file_path: Path to the file being processed
            context: Additional context information
        """
        message = f"File processing failed ({operation}): {reason}"
        
        super().__init__(message, "file_processing", file_path, context)
        self.operation = operation
        self.reason = reason

class RetryableError(SubtitleProcessingError):
    """Base class for errors that can be retried."""
    
    def __init__(self, message: str, error_type: str, max_retries: int = 3,
                 retry_delay: float = 1.0, file_path: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize retryable error.
        
        Args:
            message: Error message
            error_type: Type of error
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            file_path: Path to the file being processed
            context: Additional context information
        """
        super().__init__(message, error_type, file_path, context)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_count = 0
    
    def should_retry(self) -> bool:
        """Check if the error should be retried."""
        return self.retry_count < self.max_retries
    
    def increment_retry_count(self):
        """Increment the retry count."""
        self.retry_count += 1
    
    def get_next_retry_delay(self) -> float:
        """Get the delay for the next retry (exponential backoff)."""
        return self.retry_delay * (2 ** self.retry_count)

class NonRetryableError(SubtitleProcessingError):
    """Base class for errors that should not be retried."""
    
    def __init__(self, message: str, error_type: str, file_path: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize non-retryable error.
        
        Args:
            message: Error message
            error_type: Type of error
            file_path: Path to the file being processed
            context: Additional context information
        """
        super().__init__(message, error_type, file_path, context)

# Make API errors retryable
APIRateLimitError.__bases__ = (RetryableError,)
APIConnectionError.__bases__ = (RetryableError,)

# Make validation and configuration errors non-retryable
ValidationError.__bases__ = (NonRetryableError,)
ConfigurationError.__bases__ = (NonRetryableError,) 