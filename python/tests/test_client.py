"""Tests for BenchlingClient: retry, rate limiting, pagination, error handling."""
from unittest.mock import MagicMock, call, patch

import pytest
import requests as req

from benchling_api_utils.auth import OAuthTokenProvider
from benchling_api_utils.client import BenchlingClient, RETRYABLE_STATUS_CODES
from benchling_api_utils.errors import ApiError


def _make_response(status_code, json_data=None, headers=None):
    resp = MagicMock(spec=req.Response)
    resp.status_code = status_code
    resp.content = b"body" if json_data is not None else b""
    resp.json.return_value = json_data or {}
    resp.text = str(json_data or "")
    resp.headers = headers or {}
    return resp


def _make_client(**kwargs) -> tuple[BenchlingClient, MagicMock]:
    provider = MagicMock(spec=OAuthTokenProvider)
    provider.get_token.return_value = "tok_test"
    defaults = {"max_retries": 3, "retry_backoff": 0.0}
    defaults.update(kwargs)
    client = BenchlingClient("tenant.benchling.com", provider, **defaults)
    return client, provider


# ------------------------------------------------------------------
# Basic request behaviour
# ------------------------------------------------------------------

def test_successful_get_returns_json():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(200, {"id": "ent_1"})):
        result = client.get("custom-entities/ent_1")
    assert result == {"id": "ent_1"}


def test_empty_204_returns_empty_dict():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(204)):
        result = client.post("some-endpoint", json={})
    assert result == {}


def test_bearer_token_sent_in_header():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(200, {})) as mock_req:
        client.get("some-endpoint")
    headers = mock_req.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok_test"


def test_4xx_non_retryable_raises_immediately():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(404)) as mock_req:
        with pytest.raises(ApiError) as exc_info:
            client.get("custom-entities/missing")
    assert exc_info.value.status_code == 404
    assert mock_req.call_count == 1  # no retries


# ------------------------------------------------------------------
# Retry logic
# ------------------------------------------------------------------

@pytest.mark.parametrize("status_code", sorted(RETRYABLE_STATUS_CODES))
def test_retries_on_retryable_status_codes(status_code):
    client, _ = _make_client(max_retries=3)
    responses = [
        _make_response(status_code),
        _make_response(status_code),
        _make_response(200, {"ok": True}),
    ]
    with patch("requests.request", side_effect=responses):
        with patch("time.sleep"):
            result = client.get("some-endpoint")
    assert result == {"ok": True}


def test_exhausts_retries_and_raises():
    client, _ = _make_client(max_retries=2)
    with patch("requests.request", return_value=_make_response(500)):
        with patch("time.sleep"):
            with pytest.raises(ApiError) as exc_info:
                client.get("some-endpoint")
    assert exc_info.value.status_code == 500


def test_401_invalidates_token_and_retries():
    client, provider = _make_client(max_retries=3)
    responses = [_make_response(401), _make_response(200, {"ok": True})]
    with patch("requests.request", side_effect=responses):
        result = client.get("some-endpoint")
    provider.invalidate.assert_called_once()
    assert result == {"ok": True}


def test_network_error_retried():
    client, _ = _make_client(max_retries=3)
    responses = [req.ConnectionError("refused"), _make_response(200, {"ok": True})]
    with patch("requests.request", side_effect=responses):
        with patch("time.sleep"):
            result = client.get("some-endpoint")
    assert result == {"ok": True}


def test_retry_after_header_respected():
    client, _ = _make_client(max_retries=2)
    responses = [
        _make_response(429, headers={"Retry-After": "0.01"}),
        _make_response(200, {"ok": True}),
    ]
    with patch("requests.request", side_effect=responses):
        with patch("time.sleep") as mock_sleep:
            client.get("some-endpoint")
    mock_sleep.assert_called_once_with(0.01)


def test_exponential_backoff_timing():
    client, _ = _make_client(max_retries=3, retry_backoff=1.0)
    responses = [_make_response(500), _make_response(500), _make_response(200, {})]
    with patch("requests.request", side_effect=responses):
        with patch("time.sleep") as mock_sleep:
            client.get("some-endpoint")
    # attempt 1 → sleep(1.0 * 2^0 = 1.0), attempt 2 → sleep(1.0 * 2^1 = 2.0)
    assert mock_sleep.call_args_list == [call(1.0), call(2.0)]


# ------------------------------------------------------------------
# Pagination
# ------------------------------------------------------------------

def test_paginate_collects_all_pages():
    client, _ = _make_client()
    pages = [
        {"items": [1, 2], "nextToken": "tok1"},
        {"items": [3, 4], "nextToken": "tok2"},
        {"items": [5]},
    ]
    with patch("requests.request", side_effect=[_make_response(200, p) for p in pages]):
        result = client.paginate("some-endpoint", "items")
    assert result == [1, 2, 3, 4, 5]


def test_paginate_stops_at_max_results():
    client, _ = _make_client()
    pages = [
        {"items": [1, 2, 3], "nextToken": "tok1"},
        {"items": [4, 5, 6]},
    ]
    with patch("requests.request", side_effect=[_make_response(200, p) for p in pages]) as mock_req:
        result = client.paginate("some-endpoint", "items", max_results=4)
    assert result == [1, 2, 3, 4]
    # second page was still fetched because we needed item 4 from it
    assert mock_req.call_count == 2


def test_paginate_sends_page_size_param():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(200, {"items": []})) as mock_req:
        client.paginate("some-endpoint", "items", page_size=25)
    params = mock_req.call_args.kwargs["params"]
    assert params["pageSize"] == 25


def test_iter_pages_yields_one_page_at_a_time():
    client, _ = _make_client()
    pages = [
        {"items": [1, 2], "nextToken": "tok1"},
        {"items": [3]},
    ]
    with patch("requests.request", side_effect=[_make_response(200, p) for p in pages]):
        result = list(client.iter_pages("some-endpoint", "items"))
    assert result == [[1, 2], [3]]


def test_paginate_handles_empty_result_set():
    client, _ = _make_client()
    with patch("requests.request", return_value=_make_response(200, {"items": []})):
        result = client.paginate("some-endpoint", "items")
    assert result == []


# ------------------------------------------------------------------
# Rate limiting
# ------------------------------------------------------------------

def test_rate_limit_delay_applied_between_requests():
    client, _ = _make_client(rate_limit_delay=0.05)
    pages = [
        {"items": [1], "nextToken": "tok1"},
        {"items": [2]},
    ]
    with patch("requests.request", side_effect=[_make_response(200, p) for p in pages]):
        with patch("time.sleep") as mock_sleep:
            client.paginate("some-endpoint", "items")
    assert mock_sleep.called
