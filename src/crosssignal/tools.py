"""Function-calling tools over CrossSignal's existing capabilities.

Groundwork for a Gemini (or other LLM) agent. There is no agent loop and
no LLM SDK here yet. Each tool wraps a function the app already uses, so
a model can only do what the app can do:

    list_interests     -> RecommendationProvider.interests()
    recommend_artists  -> RecommendationProvider.recommend()
    find_tracks        -> catalog.search_tracks()

Declarations use the JSON-schema subset Gemini documents for function
parameters (type, properties, items, required, enum, description). An
SDK integration wraps them in its own tool type.

Every result names its `source` (e.g. "demo-curated" or "qloo") so a
model cannot present demo data as Qloo output, and every failure comes
back as {"error": {"kind", "message"}} instead of raising.
"""

from collections.abc import Callable, Mapping
from typing import Any

from crosssignal.catalog import CatalogError, search_tracks
from crosssignal.discovery import MAX_ARTISTS, MAX_INTERESTS
from crosssignal.models import InvalidSelection, RecommendationError, Track
from crosssignal.recommendations import RecommendationProvider

TrackSearch = Callable[[str], list[Track]]

DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "list_interests",
        "description": "List the films, games and aesthetics a user can choose "
        "from, with their ids.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "recommend_artists",
        "description": "Recommend music artists for 1 to 5 interest ids from "
        "list_interests. Returns each artist with the interests that led to it, "
        "and the interests the source could not use.",
        "parameters": {
            "type": "object",
            "properties": {
                "interest_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"1 to {MAX_INTERESTS} ids from list_interests.",
                },
                "max_artists": {
                    "type": "integer",
                    "description": f"Maximum artists to return, 1 to {MAX_ARTISTS}.",
                },
            },
            "required": ["interest_ids"],
        },
    },
    {
        "name": "find_tracks",
        "description": "Find up to three songs by an exact artist name in the "
        "Apple iTunes catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "artist": {"type": "string", "description": "Exact artist name."},
            },
            "required": ["artist"],
        },
    },
]


def _error(kind: str, message: str) -> dict:
    return {"error": {"kind": kind, "message": message}}


class ToolBox:
    def __init__(
        self,
        provider: RecommendationProvider,
        track_search: TrackSearch = search_tracks,
    ) -> None:
        self._provider = provider
        self._track_search = track_search
        self._handlers: dict[str, Callable[[Mapping[str, Any]], dict]] = {
            "list_interests": self._list_interests,
            "recommend_artists": self._recommend_artists,
            "find_tracks": self._find_tracks,
        }

    def call(self, name: str, args: Mapping[str, Any] | None) -> dict:
        """Run one tool call. Always returns a JSON-serializable dict."""
        handler = self._handlers.get(name)
        if handler is None:
            return _error("unknown_tool", f"No tool named {name!r}.")
        if args is not None and not isinstance(args, Mapping):
            return _error("invalid_arguments", "Arguments must be an object.")
        return handler(args or {})

    def _list_interests(self, args: Mapping[str, Any]) -> dict:
        return {
            "source": self._provider.source,
            "interests": [
                {"id": i.id, "name": i.name, "category": i.category}
                for i in self._provider.interests()
            ],
        }

    def _recommend_artists(self, args: Mapping[str, Any]) -> dict:
        ids = args.get("interest_ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            return _error(
                "invalid_arguments", "interest_ids must be a list of strings."
            )
        if not 1 <= len(ids) <= MAX_INTERESTS:
            return _error(
                "invalid_arguments", f"Give 1 to {MAX_INTERESTS} interest ids."
            )
        limit = args.get("max_artists", MAX_ARTISTS)
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_ARTISTS
        ):
            return _error(
                "invalid_arguments", f"max_artists must be 1 to {MAX_ARTISTS}."
            )
        try:
            result = self._provider.recommend(ids, limit)
        except InvalidSelection as exc:
            return _error("invalid_arguments", str(exc))
        except RecommendationError as exc:
            return _error(f"provider_{exc.kind}", "The recommendation source failed.")
        return {
            "source": self._provider.source,
            "artists": [
                {
                    "artist": p.artist,
                    "because": [i.name for i in p.interests],
                    "score": p.score,
                    "score_kind": p.score_kind,
                }
                for p in result.picks
            ],
            "unresolved_interests": [i.name for i in result.unresolved],
        }

    def _find_tracks(self, args: Mapping[str, Any]) -> dict:
        artist = args.get("artist")
        if not isinstance(artist, str) or not artist.strip():
            return _error("invalid_arguments", "artist must be a non-empty string.")
        try:
            tracks = self._track_search(artist.strip())
        except CatalogError:
            return _error(
                "catalog_unavailable", "The music catalog could not be reached."
            )
        return {
            "source": "itunes",
            "tracks": [
                {"title": t.title, "artist": t.artist, "album": t.album,
                 "year": t.year, "url": t.url}
                for t in tracks
            ],
        }  # fmt: skip
