"""Exceptions for aioindiallsky library."""


class IndiAllSkyError(Exception):
    """Base exception for aioindiallsky."""
    pass


class IndiAllSkyConnectionError(IndiAllSkyError):
    """Raised when connecting to indi-allsky fails."""
    pass


class IndiAllSkyTimeoutError(IndiAllSkyConnectionError):
    """Raised when a request to indi-allsky times out."""
    pass


class IndiAllSkyAuthError(IndiAllSkyError):
    """Raised when authentication fails."""
    pass


class IndiAllSkyCommandError(IndiAllSkyError):
    """Raised when sending a command fails."""
    pass
