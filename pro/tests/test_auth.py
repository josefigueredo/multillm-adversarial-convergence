import pytest

from backend.shared import ApiKeyMismatch, require_api_key


def test_valid_key_passes():
    require_api_key("secret", "secret")  # no exception


def test_missing_key_rejected():
    with pytest.raises(ApiKeyMismatch):
        require_api_key(None, "secret")


def test_wrong_key_rejected():
    with pytest.raises(ApiKeyMismatch):
        require_api_key("nope", "secret")


def test_empty_server_key_always_rejects():
    with pytest.raises(ApiKeyMismatch):
        require_api_key("anything", "")
