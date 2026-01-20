"""
Structured logging configuration for the EKS API application.
Provides consistent, contextual logging for debugging and observability.
"""
import logging
import sys
import time
import uuid
from typing import Optional, Any
from contextlib import contextmanager

# Global request ID for tracing
_request_id: Optional[str] = None


def set_request_id(request_id: str) -> None:
    """Set the current request ID for logging context."""
    global _request_id
    _request_id = request_id


def get_request_id() -> str:
    """Get the current request ID or generate a new one."""
    global _request_id
    if _request_id is None:
        _request_id = str(uuid.uuid4())[:12]
    return _request_id


def clear_request_id() -> None:
    """Clear the current request ID."""
    global _request_id
    _request_id = None


class StructuredFormatter(logging.Formatter):
    """
    Structured logging formatter with request ID and contextual information.
    Format: timestamp | level | module | message [request_id]
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structure and request ID."""
        request_id = get_request_id()
        
        # Basic structure
        timestamp = self.formatTime(record, self.datefmt or '%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = record.levelname
        module = record.name.split('.')[-1]  # Last component of module name
        message = record.getMessage()
        
        # Build formatted message
        formatted = f"{timestamp} | {level:8s} | {module:20s} | {message}"
        
        # Add request ID if available
        if request_id:
            formatted += f" [{request_id}]"
        
        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Create and configure a structured logger with console output.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False  # Don't propagate to root logger
    
    # Create console handler with structured formatting
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


@contextmanager
def log_operation(logger: logging.Logger, operation: str, **context: Any):
    """
    Context manager for logging operation entry/exit with timing.
    
    Usage:
        with log_operation(logger, "create_job", job_name="test"):
            # operation code
            pass
    """
    context_str = " ".join(f"{k}={v}" for k, v in context.items())
    logger.info(f"START {operation} {context_str}")
    
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        logger.info(f"END {operation} success=true duration_ms={duration*1000:.1f}")
    except Exception as e:
        duration = time.time() - start_time
        logger.exception(f"END {operation} success=false duration_ms={duration*1000:.1f} error={str(e)}")
        raise
