class ExtractionError(Exception):
    """Base exception for invoice extraction errors."""


class TransientExtractionError(ExtractionError):
    """Temporary service failure. Retrying may succeed."""

    def __init__(self, message: str, partial_data=None) -> None:
        super().__init__(message)
        self.partial_data = partial_data


class PermanentExtractionError(ExtractionError):
    """Invalid or unsupported invoice content. Do not retry."""