"""Tests for endpoint helpers."""
from unittest.mock import MagicMock

from benchling_api_utils import helpers
from benchling_api_utils.client import BenchlingClient


def _client() -> MagicMock:
    return MagicMock(spec=BenchlingClient)


# ------------------------------------------------------------------
# Entity routing
# ------------------------------------------------------------------

def test_get_entity_by_id_routes_custom_entity():
    client = _client()
    client.get.return_value = {"id": "ent_1"}
    helpers.get_entity_by_id(client, "ent_1")
    client.get.assert_called_once_with("custom-entities/ent_1")


def test_get_entity_by_id_routes_mixture():
    client = _client()
    client.get.return_value = {"id": "mxt_1"}
    helpers.get_entity_by_id(client, "mxt_1")
    client.get.assert_called_once_with("mixtures/mxt_1")


# ------------------------------------------------------------------
# Custom entities
# ------------------------------------------------------------------

def test_get_custom_entity():
    client = _client()
    client.get.return_value = {"id": "ent_1", "name": "Sample A"}
    result = helpers.get_custom_entity(client, "ent_1")
    client.get.assert_called_once_with("custom-entities/ent_1")
    assert result["name"] == "Sample A"


def test_list_custom_entities_passes_schema_id():
    client = _client()
    client.paginate.return_value = []
    helpers.list_custom_entities(client, schema_id="sch_1", page_size=25, max_results=100)
    client.paginate.assert_called_once_with(
        "custom-entities", "customEntities",
        params={"schemaId": "sch_1"},
        page_size=25,
        max_results=100,
    )


def test_list_custom_entities_no_schema():
    client = _client()
    client.paginate.return_value = []
    helpers.list_custom_entities(client)
    call_params = client.paginate.call_args.kwargs["params"]
    assert "schemaId" not in call_params


def test_bulk_update_custom_entities():
    client = _client()
    updates = [{"id": "ent_1", "fields": {"status": {"value": "Active"}}}]
    helpers.bulk_update_custom_entities(client, updates)
    client.post.assert_called_once_with(
        "custom-entities:bulk-update",
        json={"customEntities": updates},
    )


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

def test_get_schema_id_by_name_found():
    client = _client()
    client.paginate.return_value = [
        {"id": "sch_1", "name": "Sample"},
        {"id": "sch_2", "name": "Cell Line"},
    ]
    result = helpers.get_schema_id_by_name(client, "Cell Line")
    assert result == "sch_2"


def test_get_schema_id_by_name_not_found():
    client = _client()
    client.paginate.return_value = [{"id": "sch_1", "name": "Sample"}]
    result = helpers.get_schema_id_by_name(client, "Unknown Schema")
    assert result is None


# ------------------------------------------------------------------
# Dropdowns
# ------------------------------------------------------------------

def test_get_dropdown_by_name_found():
    client = _client()
    client.paginate.return_value = [
        {"id": "dd_1", "name": "Exit Reason"},
        {"id": "dd_2", "name": "Media Type"},
    ]
    result = helpers.get_dropdown_by_name(client, "Exit Reason")
    assert result == {"id": "dd_1", "name": "Exit Reason"}


def test_get_dropdown_by_name_not_found():
    client = _client()
    client.paginate.return_value = []
    result = helpers.get_dropdown_by_name(client, "Missing")
    assert result is None


def test_get_dropdown_option_id_found():
    dropdown = {
        "options": [
            {"id": "opt_1", "name": "Contamination"},
            {"id": "opt_2", "name": "Passage limit"},
        ]
    }
    assert helpers.get_dropdown_option_id(dropdown, "Passage limit") == "opt_2"


def test_get_dropdown_option_id_not_found():
    dropdown = {"options": [{"id": "opt_1", "name": "Contamination"}]}
    assert helpers.get_dropdown_option_id(dropdown, "Unknown") is None


# ------------------------------------------------------------------
# Projects
# ------------------------------------------------------------------

def test_get_project_id_by_name_found():
    client = _client()
    client.paginate.return_value = [
        {"id": "src_1", "name": "Experiments"},
        {"id": "src_2", "name": "Archive"},
    ]
    assert helpers.get_project_id_by_name(client, "Archive") == "src_2"


def test_get_project_id_by_name_not_found():
    client = _client()
    client.paginate.return_value = []
    assert helpers.get_project_id_by_name(client, "Missing") is None


# ------------------------------------------------------------------
# Entries
# ------------------------------------------------------------------

def test_create_entry():
    client = _client()
    payload = {"name": "Run 42", "schemaId": "ens_1"}
    helpers.create_entry(client, payload)
    client.post.assert_called_once_with("entries", json=payload)


def test_update_entry():
    client = _client()
    helpers.update_entry(client, "etr_1", {"fields": {}})
    client.patch.assert_called_once_with("entries/etr_1", json={"fields": {}})
