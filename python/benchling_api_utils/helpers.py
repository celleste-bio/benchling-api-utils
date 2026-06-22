"""
Endpoint helpers built on BenchlingClient.

These cover the most common operations across automation apps. They are plain
functions (not methods on the client) so the core HTTP layer stays separate and
these can be extended, overridden, or ignored per-app without touching client.py.

Import style::

    from benchling_api_utils import helpers
    entity = helpers.get_entity_by_id(client, entity_id)

    # or selectively:
    from benchling_api_utils.helpers import bulk_update_custom_entities
"""
from __future__ import annotations

from typing import Any

from .client import BenchlingClient


# ------------------------------------------------------------------
# Entity routing
# ------------------------------------------------------------------

def get_entity_by_id(client: BenchlingClient, entity_id: str) -> dict[str, Any]:
    """
    Fetch any entity by ID, routing to the correct endpoint by prefix.

    Handles the mxt_* gap: the Benchling SDK and custom-entities endpoint do not
    support mixture IDs — this function calls /mixtures/{id} automatically.
    """
    if entity_id.startswith("mxt_"):
        return get_mixture(client, entity_id)
    return get_custom_entity(client, entity_id)


# ------------------------------------------------------------------
# Custom entities
# ------------------------------------------------------------------

def get_custom_entity(client: BenchlingClient, entity_id: str) -> dict[str, Any]:
    return client.get(f"custom-entities/{entity_id}")


def list_custom_entities(
    client: BenchlingClient,
    *,
    schema_id: str | None = None,
    page_size: int = 50,
    max_results: int | None = None,
    extra_params: dict | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = dict(extra_params or {})
    if schema_id:
        params["schemaId"] = schema_id
    return client.paginate(
        "custom-entities",
        "customEntities",
        params=params,
        page_size=page_size,
        max_results=max_results,
    )


def bulk_update_custom_entities(
    client: BenchlingClient,
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Update multiple custom entities in one request.

    Each item in updates must have an "id" and a "fields" dict.
    Returns the bulk-update response body.
    """
    return client.post("custom-entities:bulk-update", json={"customEntities": updates})


# ------------------------------------------------------------------
# Mixtures  (mxt_* prefix — not covered by the Python SDK)
# ------------------------------------------------------------------

def get_mixture(client: BenchlingClient, entity_id: str) -> dict[str, Any]:
    """Fetch a mixture entity. The SDK does not support mxt_* IDs."""
    return client.get(f"mixtures/{entity_id}")


def list_mixtures(
    client: BenchlingClient,
    *,
    schema_id: str | None = None,
    page_size: int = 50,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if schema_id:
        params["schemaId"] = schema_id
    return client.paginate(
        "mixtures",
        "mixtures",
        params=params,
        page_size=page_size,
        max_results=max_results,
    )


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

def list_entity_schemas(client: BenchlingClient) -> list[dict[str, Any]]:
    return client.paginate("entity-schemas", "entitySchemas")


def get_schema_id_by_name(client: BenchlingClient, name: str) -> str | None:
    """Return the ID of the first schema matching name, or None."""
    for schema in list_entity_schemas(client):
        if schema.get("name") == name:
            return schema.get("id")
    return None


# ------------------------------------------------------------------
# Dropdowns
# ------------------------------------------------------------------

def list_dropdowns(client: BenchlingClient) -> list[dict[str, Any]]:
    return client.paginate("dropdowns", "dropdowns")


def get_dropdown(client: BenchlingClient, dropdown_id: str) -> dict[str, Any]:
    return client.get(f"dropdowns/{dropdown_id}")


def get_dropdown_by_name(client: BenchlingClient, name: str) -> dict[str, Any] | None:
    """Return the first dropdown matching name, or None."""
    for dropdown in list_dropdowns(client):
        if dropdown.get("name") == name:
            return dropdown
    return None


def get_dropdown_option_id(dropdown: dict[str, Any], option_name: str) -> str | None:
    """
    Find an option ID within a fetched dropdown dict.

    dropdown is the response body from get_dropdown() or get_dropdown_by_name().
    """
    for option in dropdown.get("options", []):
        if option.get("name") == option_name:
            return option.get("id")
    return None


# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------

def get_user(client: BenchlingClient, user_id: str) -> dict[str, Any]:
    return client.get(f"users/{user_id}")


def list_users_by_handle(
    client: BenchlingClient,
    handles: list[str],
) -> list[dict[str, Any]]:
    return client.paginate("users", "users", params={"handles": ",".join(handles)})


# ------------------------------------------------------------------
# Entries (ELN)
# ------------------------------------------------------------------

def get_entry(client: BenchlingClient, entry_id: str) -> dict[str, Any]:
    return client.get(f"entries/{entry_id}")


def create_entry(client: BenchlingClient, payload: dict[str, Any]) -> dict[str, Any]:
    return client.post("entries", json=payload)


def update_entry(
    client: BenchlingClient,
    entry_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return client.patch(f"entries/{entry_id}", json=payload)


# ------------------------------------------------------------------
# Projects
# ------------------------------------------------------------------

def list_projects(client: BenchlingClient) -> list[dict[str, Any]]:
    return client.paginate("projects", "projects")


def get_project_id_by_name(client: BenchlingClient, name: str) -> str | None:
    """Return the ID of the first project matching name, or None."""
    for project in list_projects(client):
        if project.get("name") == name:
            return project.get("id")
    return None
