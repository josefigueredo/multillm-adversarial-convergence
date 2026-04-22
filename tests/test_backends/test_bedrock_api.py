"""Tests for src.backends.bedrock_api — BedrockApiBackend."""

from unittest.mock import patch

from src.backends import StreamEvent
from src.backends.bedrock_api import BedrockApiBackend
from src.backends.types import CallOptions


class TestBedrockApiBackend:
    def setup_method(self):
        self.backend = BedrockApiBackend()

    def test_name(self):
        assert self.backend.name == "bedrock-api"

    def test_parse_payload(self):
        payload = {
            "output": {
                "message": {
                    "content": [
                        {"text": "hi"},
                    ]
                }
            },
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"}, clear=True)
    def test_check_available_with_region_and_boto3(self, _):
        assert self.backend.check_available() is True

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=False)
    @patch.dict("os.environ", {"AWS_REGION": "us-east-1"}, clear=True)
    def test_check_available_without_boto3(self, _):
        assert self.backend.check_available() is False

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_without_region(self, _):
        assert self.backend.check_available() is False

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch("src.backends.bedrock_api.BedrockApiBackend._client")
    def test_invoke_uses_converse_contract(self, mock_client, _):
        self.backend.provider_config = type(
            "Provider",
            (),
            {"region": "us-east-1", "aws_profile": "sandbox"},
        )()
        mock_client.return_value.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "hi"}],
                }
            },
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
        resp = self.backend.invoke("hello", CallOptions(model="anthropic.claude-3-5-sonnet-20240620-v1:0"), timeout=30)
        assert resp.text == "hi"
        mock_client.assert_called_once_with(region="us-east-1", profile="sandbox", timeout=30)
        mock_client.return_value.converse.assert_called_once()
        kwargs = mock_client.return_value.converse.call_args.kwargs
        assert kwargs["modelId"] == "anthropic.claude-3-5-sonnet-20240620-v1:0"
        assert kwargs["messages"][0]["content"][0]["text"] == "hello"

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch("src.backends.bedrock_api.BedrockApiBackend._client")
    def test_invoke_includes_system_prompt(self, mock_client, _):
        self.backend.provider_config = type(
            "Provider",
            (),
            {"region": "us-east-1", "aws_profile": "sandbox"},
        )()
        mock_client.return_value.converse.return_value = {
            "output": {"message": {"content": [{"text": "hi"}]}},
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
        self.backend.invoke(
            "hello",
            CallOptions(
                model="anthropic.claude-3-5-sonnet-20240620-v1:0",
                system_prompt="You are precise.",
            ),
            timeout=30,
        )
        kwargs = mock_client.return_value.converse.call_args.kwargs
        assert kwargs["system"][0]["text"] == "You are precise."

    def test_error_response_from_bedrock_throttling_exception(self):
        class FakeClientError(Exception):
            def __init__(self):
                self.response = {
                    "Error": {
                        "Code": "ThrottlingException",
                        "Message": "Rate exceeded",
                    }
                }
                super().__init__("Rate exceeded")

        resp = self.backend._error_response_from_exception(FakeClientError())
        assert resp.is_error is True
        assert resp.raw["error"]["category"] == "rate_limit"
        assert resp.raw["error"]["provider_code"] == "ThrottlingException"

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch("src.backends.bedrock_api.BedrockApiBackend._client")
    def test_invoke_stream_normalizes_bedrock_stream(self, mock_client, _):
        self.backend.provider_config = type(
            "Provider",
            (),
            {"region": "us-east-1", "aws_profile": "sandbox"},
        )()
        mock_client.return_value.converse_stream.return_value = {
            "stream": iter([
                {"messageStart": {"role": "assistant"}},
                {"contentBlockDelta": {"delta": {"text": "Hel"}}},
                {"contentBlockDelta": {"delta": {"text": "lo"}}},
                {
                    "metadata": {
                        "usage": {"inputTokens": 10, "outputTokens": 5},
                    }
                },
                {"messageStop": {"stopReason": "end_turn"}},
            ])
        }

        events = list(self.backend.invoke_stream(
            "hello",
            CallOptions(model="anthropic.claude-3-5-sonnet-20240620-v1:0", stream=True),
            timeout=30,
        ))

        assert events == [
            StreamEvent(type="start", raw={"messageStart": {"role": "assistant"}}),
            StreamEvent(type="text_delta", text="Hel", raw={"contentBlockDelta": {"delta": {"text": "Hel"}}}),
            StreamEvent(type="text_delta", text="lo", raw={"contentBlockDelta": {"delta": {"text": "lo"}}}),
            StreamEvent(
                type="completed",
                raw={
                    "response": {
                        "output": {"message": {"content": [{"text": "Hello"}]}},
                        "usage": {"inputTokens": 10, "outputTokens": 5},
                    }
                },
            ),
        ]

    @patch("src.backends.bedrock_api.BedrockApiBackend._has_boto3", return_value=True)
    @patch("src.backends.bedrock_api.BedrockApiBackend._client")
    def test_invoke_stream_maps_bedrock_error_event(self, mock_client, _):
        self.backend.provider_config = type(
            "Provider",
            (),
            {"region": "us-east-1", "aws_profile": "sandbox"},
        )()
        mock_client.return_value.converse_stream.return_value = {
            "stream": iter([
                {"internalServerException": {"message": "boom"}},
            ])
        }

        events = list(self.backend.invoke_stream(
            "hello",
            CallOptions(model="anthropic.claude-3-5-sonnet-20240620-v1:0", stream=True),
            timeout=30,
        ))

        assert events == [
            StreamEvent(type="error", raw={"internalServerException": {"message": "boom"}}),
        ]
