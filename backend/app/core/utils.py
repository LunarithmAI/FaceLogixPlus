"""
Core utility functions for FaceLogix Backend.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime.
    
    This replaces deprecated datetime.utcnow() which returns naive datetime.
    Python 3.12+ deprecates utcnow() in favor of timezone-aware alternatives.
    """
    return datetime.now(timezone.utc)
