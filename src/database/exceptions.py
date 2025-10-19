"""
Custom exception hierarchy for DynamoDB operations.

This module defines domain-specific exceptions used by the database module
to handle various failure scenarios in a granular, testable way.
"""


class DynamoDBException(Exception):
    """
    Base exception for all DynamoDB-related errors.

    Used for recoverable and unrecoverable errors from DynamoDB operations.
    """

    pass


class NotFoundError(DynamoDBException):
    """
    Raised when a requested item is not found in DynamoDB.

    Note: Repository methods return None for missing items by default (AC-4a),
    so this exception is rarely raised unless explicitly used in calling code.
    """

    pass


class ThrottlingError(DynamoDBException):
    """
    Raised when DynamoDB returns throttling errors after retry exhaustion.

    This indicates the database is overloaded and requests are being throttled.
    Callers should implement backoff and retry logic at a higher level.
    """

    pass


class NetworkError(DynamoDBException):
    """
    Raised when network-level failures occur (connection timeout, DNS failure, etc.).

    This is unrecoverable at the repository level and indicates infrastructure issues.
    """

    pass


class PermissionError(DynamoDBException):
    """
    Raised when IAM permissions are insufficient for the operation.

    Indicates a configuration/security issue that must be fixed by an administrator.
    """

    pass
