"""Tests for src.backends.gemini_api — GeminiApiBackend."""

from unittest.mock import patch

from src.backends.gemini_api import GeminiApiBackend
from src.backends.types import CallOptions


class TestGeminiApiBackend:
    def setup_method(self):
        self.backend = GeminiApiBackend()

    def test_name(self):
        assert self.backend.name == "gemini-api"

    def test_build_request(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="gemini-2.5-pro"))
        assert url.startswith("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent")
        assert headers["Content-Type"] == "application/json"
        assert body["contents"][0]["parts"][0]["text"] == "hello"

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="gemini-2.5-pro", system_prompt="You are precise."),
        )
        assert body["system_instruction"]["parts"][0]["text"] == "You are precise."

    def test_parse_payload(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "hi"}],
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
            },
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_extract_error_details_for_unavailable(self):
        details = self.backend.extract_error_details(
            {
                "error": {
                    "code": 503,
                    "message": "The model is overloaded. Please try again later.",
                    "status": "UNAVAILABLE",
                }
            },
            503,
        )
        assert details["category"] == "server_error"
        assert details["provider_status"] == "UNAVAILABLE"

    @patch.dict("os.environ", {"GEMINI_API_KEY": "x"}, clear=True)
    def test_check_available_when_gemini_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "x"}, clear=True)
    def test_check_available_when_google_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_when_api_key_missing(self):
        assert self.backend.check_available() is False
