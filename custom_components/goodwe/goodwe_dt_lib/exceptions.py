class InverterError(Exception):
    """Base exception for inverter-related errors."""
    pass


class RequestFailedException(InverterError):
    """Exception raised when a request to the inverter fails."""

    def __init__(self, message: str = "", consecutive_failures_count: int = 0):
        super().__init__(message)
        self.consecutive_failures_count = consecutive_failures_count


class MaxRetriesException(InverterError):
    """Exception raised when maximum retry attempts have been exceeded."""
    pass


class RequestRejectedException(InverterError):
    """Exception raised when the inverter rejects a request."""
    pass


class PartialResponseException(InverterError):
    """Exception raised when a partial response is received."""

    def __init__(self, length: int, expected: int):
        super().__init__(f"Partial response: received {length} bytes, expected {expected}")
        self.length = length
        self.expected = expected
