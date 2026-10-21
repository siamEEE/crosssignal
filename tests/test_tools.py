import json

import pytest

from crosssignal.catalog import CatalogError
from crosssignal.models import ProviderErrorKind, RecommendationError, Track
from crosssignal.recommendations import CuratedProvider
from crosssignal.tools import DECLARATIONS, ToolBox

ALLOWED_SCHEMA_KEYS = {"type", "properties", "items", "required", "enum", "description"}


def track(artist: str) -> Track:
    return Track(
        "Nightcall", artist, "OutRun", "2013", "https://music.apple.com/x", None, None
    )


def toolbox(**kwargs) -> ToolBox:
    return ToolBox(kwargs.pop("provider", CuratedProvider()),
                   kwargs.pop("search", lambda artist: [track(artist)]))  # fmt: skip


def schema_keys(schema: dict) -> set[str]:
    keys = set(schema)
    for child in schema.get("properties", {}).values():
        keys |= schema_keys(child)
    if "items" in schema:
        keys |= schema_keys(schema["items"])
    return keys


def test_declarations_match_handlers_and_use_documented_schema_subset():
    names = [d["name"] for d in DECLARATIONS]
    assert names == ["list_interests", "recommend_artists", "find_tracks"]
    for declaration in DECLARATIONS:
        assert declaration["description"]
        assert schema_keys(declaration["parameters"]) <= ALLOWED_SCHEMA_KEYS
        json.dumps(declaration)  # serializable
    tools = toolbox()
    for name in names:
        assert "unknown_tool" not in json.dumps(tools.call(name, {}))


def test_list_interests_names_its_source():
    result = toolbox().call("list_interests", {})
    assert result["source"] == "demo-curated"
    assert {"id": "drive", "name": "Drive", "category": "Films"} in result["interests"]


def test_recommend_artists_returns_explanations_and_no_invented_scores():
    result = toolbox().call(
        "recommend_artists", {"interest_ids": ["drive"], "max_artists": 2}
    )
    assert result["source"] == "demo-curated"
    assert result["artists"][0] == {
        "artist": "Kavinsky", "because": ["Drive"], "score": None, "score_kind": None,
    }  # fmt: skip
    assert result["unresolved_interests"] == []
    json.dumps(result)


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"interest_ids": "drive"},
        {"interest_ids": []},
        {"interest_ids": ["a", "b", "c", "d", "e", "f"]},
        {"interest_ids": ["drive"], "max_artists": 0},
        {"interest_ids": ["drive"], "max_artists": True},
        {"interest_ids": ["not-an-interest"]},
    ],
)
def test_recommend_artists_rejects_bad_arguments(args):
    assert (
        toolbox().call("recommend_artists", args)["error"]["kind"]
        == "invalid_arguments"
    )


def test_provider_failure_is_reported_as_data():
    class Failing(CuratedProvider):
        source = "qloo"

        def recommend(self, interest_ids, max_artists):
            raise RecommendationError(ProviderErrorKind.TIMEOUT, "Qloo: timed out")

    result = toolbox(provider=Failing()).call(
        "recommend_artists", {"interest_ids": ["drive"]}
    )
    assert result == {
        "error": {
            "kind": "provider_timeout",
            "message": "The recommendation source failed.",
        }
    }


def test_find_tracks_and_catalog_failure():
    assert (
        toolbox().call("find_tracks", {"artist": " Kavinsky "})["tracks"][0]["artist"]
        == "Kavinsky"
    )

    def offline(artist):
        raise CatalogError("offline")

    failed = toolbox(search=offline).call("find_tracks", {"artist": "Kavinsky"})
    assert failed["error"]["kind"] == "catalog_unavailable"
    assert (
        toolbox().call("find_tracks", {"artist": ""})["error"]["kind"]
        == "invalid_arguments"
    )


def test_unknown_tool_and_non_object_args():
    assert toolbox().call("delete_everything", {})["error"]["kind"] == "unknown_tool"
    assert (
        toolbox().call("find_tracks", ["Kavinsky"])["error"]["kind"]
        == "invalid_arguments"
    )
