class ExtractionError(Exception):
    """Base exception for invoice extraction errors."""


class TransientExtractionError(ExtractionError):
    """Temporary service failure. Retrying may succeed."""


class PermanentExtractionError(ExtractionError):
    """Invalid or unsupported invoice content. Do not retry."""