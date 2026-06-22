"""Tests for OAuthTokenProvider."""
from unittest.mock import MagicMock, patch

import pytest

from benchling_api_utils.auth import OAuthTokenProvider, _REFRESH_SKEW_SECONDS


def _mock_token_response(token="tok_test", expires_in=3600):
    resp = MagicMock()
    resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    resp.raise_for_status.return_value = None
    return resp


def make_provider():
    return OAuthTokenProvider("tenant.benchling.com", "client_id", "secret")


def test_fetches_token_on_first_call():
    with patch("requests.post", return_value=_mock_token_response("tok_1")) as mock_post:
        provider = make_provider()
        token = provider.get_token()
    assert token == "tok_1"
    mock_post.assert_called_once()


def test_caches_token_on_subsequent_calls():
    with patch("requests.post", return_value=_mock_token_response("tok_1")) as mock_post:
        provider = make_provider()
        t1 = provider.get_token()
        t2 = provider.get_token()
    assert t1 == t2 == "tok_1"
    assert mock_post.call_count == 1


def test_refreshes_when_token_expires():
    with patch("requests.post", side_effect=[
        _mock_token_response("tok_1", expires_in=0),
        _mock_token_response("tok_2"),
    ]) as mock_post:
        provider = make_provider()
        t1 = provider.get_token()
        t2 = provider.get_token()
    assert t1 == "tok_1"
    assert t2 == "tok_2"
    assert mock_post.call_count == 2


def test_invalidate_forces_refresh():
    with patch("requests.post", side_effect=[
        _mock_token_response("tok_1"),
        _mock_token_response("tok_2"),
    ]) as mock_post:
        provider = make_provider()
        provider.get_token()
        provider.invalidate()
        t2 = provider.get_token()
    assert t2 == "tok_2"
    assert mock_post.call_count == 2


def test_refresh_skew_triggers_early_refresh():
    """Token should be refreshed when less than REFRESH_SKEW_SECONDS remain."""
    with patch("requests.post", side_effect=[
        _mock_token_response("tok_1", expires_in=_REFRESH_SKEW_SECONDS - 1),
        _mock_token_response("tok_2"),
    ]) as mock_post:
        provider = make_provider()
        provider.get_token()
        t2 = provider.get_token()
    assert t2 == "tok_2"
    assert mock_post.call_count == 2


def test_raises_on_network_failure():
    import requests as req
    with patch("requests.post", side_effect=req.RequestException("timeout")):
        provider = make_provider()
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            provider.get_token()


def test_raises_when_access_token_missing():
    resp = MagicMock()
    resp.json.return_value = {"token_type": "Bearer"}  # no access_token
    resp.raise_for_status.return_value = None
    with patch("requests.post", return_value=resp):
        provider = make_provider()
        with pytest.raises(RuntimeError, match="missing access_token"):
            provider.get_token()
