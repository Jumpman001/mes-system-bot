"""
Custom exception hierarchy for the MES system.
Provides a clear categorization of errors (Database, Validation, Business Logic).
"""

class MesBotError(Exception):
    """Base exception for the MES bot application."""
    def __init__(self, message: str = "Произошла ошибка в работе бота."):
        self.message = message
        super().__init__(self.message)

class DatabaseError(MesBotError):
    """Raised when a database operation fails unexpectedly."""
    def __init__(self, message: str = "Ошибка базы данных."):
        super().__init__(message)

class ValidationError(MesBotError):
    """Raised when user input or operations violate business rules."""
    pass

class BusinessLogicError(MesBotError):
    """Raised when a business logic invariant is violated (e.g., state transition)."""
    pass
