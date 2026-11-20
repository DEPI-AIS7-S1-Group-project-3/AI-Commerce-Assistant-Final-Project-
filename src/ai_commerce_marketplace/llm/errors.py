"""LLM errors. ``fallback_ok`` tells the fallback chain whether another provider may help."""


class LLMError(Exception):
    code = "llm_error"
    fallback_ok = True

    def __init__(self, message: str, *, provider: str | None = None, status: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status = status


class RateLimitError(LLMError):
    code = "rate_limited"


class ProviderUnavailable(LLMError):
    """Timeout, network error or 5xx."""

    code = "unavailable"


class AuthenticationError(LLMError):
    """Bad or missing key for this provider. Another provider may still work."""

    code = "auth_failed"


class BadResponseError(LLMError):
    """The provider answered, but not with something we can use."""

    code = "bad_response"


class InvalidRequestError(LLMError):
    """Our request is wrong. Retrying elsewhere would hide a bug, so the chain stops."""

    code = "invalid_request"
    fallback_ok = False


class NotConfiguredError(LLMError):
    code = "not_configured"
    fallback_ok = False


class AllProvidersFailed(LLMError):
    code = "all_providers_failed"
    fallback_ok = False
