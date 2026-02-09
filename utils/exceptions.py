"""Custom exceptions."""


class BotException(Exception):
    """Base exception for bot errors."""

    pass


class ParserError(BotException):
    """Exception raised when parsing fails."""

    pass


class DatabaseError(BotException):
    """Exception raised when database operation fails."""

    pass


class ValidationError(BotException):
    """Exception raised when validation fails."""

    pass


class UserNotFoundError(BotException):
    """Exception raised when user is not found."""

    pass


class FilterNotFoundError(BotException):
    """Exception raised when filter is not found."""

    pass
