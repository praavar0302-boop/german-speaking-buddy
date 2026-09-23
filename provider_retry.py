"""Small, server-side recovery for temporary model-provider failures."""

from __future__ import annotations

import time

from providers import ProviderAPIError


class ProviderFailure(RuntimeError):
    """No usable provider response is available for this request."""


def _gemini_unavailable(error):
    if isinstance(error, ProviderAPIError):
        return error.provider == "gemini" and (
            error.status_code == 503 or "UNAVAILABLE" in error.detail.upper()
        )
    message = str(error).upper()
    return "GEMINI" in message and ("503" in message or "UNAVAILABLE" in message)


def stream_with_provider_recovery(
    provider,
    system_prompt,
    history,
    provider_stream,
    get_api_key,
    logger,
    *,
    sleep=None,
):
    """Retry Gemini before yielding text; then try configured OpenRouter once."""
    if sleep is None:
        sleep = time.sleep
    if provider != "gemini":
        try:
            yield from provider_stream(
                get_api_key(provider), provider, system_prompt, history
            )
        except Exception as error:
            logger.warning(
                "provider_failure provider=%s attempt=1 status=%s",
                provider,
                getattr(error, "status_code", "unknown"),
            )
            raise ProviderFailure("Provider request failed") from error
        return

    for attempt in range(1, 4):
        emitted = False
        try:
            for chunk in provider_stream(
                get_api_key("gemini"), "gemini", system_prompt, history
            ):
                emitted = True
                yield chunk
            return
        except Exception as error:
            temporary = _gemini_unavailable(error)
            logger.warning(
                "provider_failure provider=gemini attempt=%d status=%s temporary=%s "
                "partial_stream=%s",
                attempt,
                getattr(error, "status_code", "unknown"),
                temporary,
                emitted,
            )
            if not temporary or emitted:
                raise ProviderFailure("Provider request failed") from error
            if attempt < 3:
                delay = 0.35 * attempt
                logger.info(
                    "provider_retry provider=gemini next_attempt=%d delay=%.2fs",
                    attempt + 1,
                    delay,
                )
                sleep(delay)

    openrouter_key = get_api_key("openrouter")
    if not openrouter_key:
        raise ProviderFailure("No provider response is available")

    logger.info("provider_fallback provider=openrouter attempt=1")
    try:
        yield from provider_stream(
            openrouter_key, "openrouter", system_prompt, history
        )
    except Exception as error:
        logger.warning(
            "provider_failure provider=openrouter attempt=1 status=%s",
            getattr(error, "status_code", "unknown"),
        )
        raise ProviderFailure("No provider response is available") from error
