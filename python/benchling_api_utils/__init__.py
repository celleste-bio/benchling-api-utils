"""
benchling-api-utils
~~~~~~~~~~~~~~~~~~~

Thin wrapper for the Benchling REST API.

Core components::

    from benchling_api_utils import BenchlingClient, OAuthTokenProvider, BenchlingApiError

    client = BenchlingClient.from_credentials(domain, client_id, client_secret)

Endpoint helpers::

    from benchling_api_utils import helpers

    entity = helpers.get_entity_by_id(client, entity_id)
    schemas = helpers.list_entity_schemas(client)
"""

from .auth import OAuthTokenProvider
from .client import BenchlingClient
from .errors import BenchlingApiError
from . import helpers

__all__ = [
    "BenchlingClient",
    "BenchlingApiError",
    "OAuthTokenProvider",
    "helpers",
]
