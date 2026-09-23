import unittest
from unittest.mock import MagicMock, Mock, patch

from provider_retry import ProviderFailure, stream_with_provider_recovery
from providers import ProviderAPIError, stream_gemini_response


class ProviderRetryTests(unittest.TestCase):
    def run_request(self, stream, keys=None):
        calls = []
        delays = []
        logger = Mock()
        keys = keys or {"gemini": "gemini-key", "openrouter": "router-key"}

        def called_stream(key, provider, prompt, history):
            calls.append(provider)
            return stream(key, provider, prompt, history)

        result = stream_with_provider_recovery(
            "gemini",
            "prompt",
            [],
            called_stream,
            keys.get,
            logger,
            sleep=delays.append,
        )
        return result, calls, delays, logger

    def test_gemini_503_retries_twice_then_succeeds(self):
        attempts = 0

        def stream(key, provider, prompt, history):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ProviderAPIError("gemini", 503, "UNAVAILABLE")
            return iter(["Hallo."])

        result, calls, delays, logger = self.run_request(stream)
        self.assertEqual("".join(result), "Hallo.")
        self.assertEqual(calls, ["gemini"] * 3)
        self.assertEqual(delays, [0.35, 0.7])
        self.assertEqual(logger.info.call_count, 2)

    def test_openrouter_is_tried_once_after_gemini_exhausts(self):
        def stream(key, provider, prompt, history):
            if provider == "gemini":
                raise ProviderAPIError("gemini", 503, "UNAVAILABLE")
            return iter(["Guten Tag."])

        result, calls, delays, logger = self.run_request(stream)
        self.assertEqual("".join(result), "Guten Tag.")
        self.assertEqual(calls, ["gemini", "gemini", "gemini", "openrouter"])
        self.assertEqual(delays, [0.35, 0.7])
        self.assertEqual(logger.warning.call_count, 3)

    def test_all_attempts_fail_without_exposing_provider_error(self):
        def stream(key, provider, prompt, history):
            raise ProviderAPIError(provider, 503, "secret technical detail")

        result, calls, _, _ = self.run_request(stream)
        with self.assertRaises(ProviderFailure) as raised:
            list(result)
        self.assertNotIn("secret technical detail", str(raised.exception))
        self.assertEqual(calls, ["gemini"] * 3 + ["openrouter"])

    def test_no_fallback_without_openrouter_key(self):
        def stream(key, provider, prompt, history):
            raise ProviderAPIError("gemini", 503, "UNAVAILABLE")

        result, calls, _, _ = self.run_request(
            stream, keys={"gemini": "gemini-key"}
        )
        with self.assertRaises(ProviderFailure):
            list(result)
        self.assertEqual(calls, ["gemini"] * 3)

    def test_unavailable_status_retries_even_without_503(self):
        attempts = 0

        def stream(key, provider, prompt, history):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ProviderAPIError("gemini", 500, '{"status":"UNAVAILABLE"}')
            return iter(["Hallo."])

        result, calls, delays, _ = self.run_request(stream)
        self.assertEqual("".join(result), "Hallo.")
        self.assertEqual(calls, ["gemini", "gemini"])
        self.assertEqual(delays, [0.35])

    def test_partial_stream_is_not_replayed(self):
        def stream(key, provider, prompt, history):
            yield "Hallo"
            raise ProviderAPIError("gemini", 503, "UNAVAILABLE")

        result, calls, delays, _ = self.run_request(stream)
        self.assertEqual(next(result), "Hallo")
        with self.assertRaises(ProviderFailure):
            list(result)
        self.assertEqual(calls, ["gemini"])
        self.assertEqual(delays, [])

    def test_gemini_streamed_unavailable_error_is_detected(self):
        response = Mock(status_code=200)
        response.iter_lines.return_value = iter(
            ['data: {"error":{"code":503,"status":"UNAVAILABLE"}}']
        )
        context = MagicMock()
        context.__enter__.return_value = response
        with patch("providers.httpx.stream", return_value=context):
            with self.assertRaises(ProviderAPIError) as raised:
                list(stream_gemini_response("key", "prompt", []))
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
