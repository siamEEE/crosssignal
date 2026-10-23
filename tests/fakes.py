"""Synthetic stand-ins for Qloo and the catalog, shared by engine/API tests.

Ids, names, tags and numbers are made up. Field shapes follow what the
live APIs returned (see docs/QLOO_INTEGRATION.md); no real response data.
"""

from crosssignal.catalog import CatalogError
from crosssignal.models import Track
from crosssignal.qloo import ARTIST_TYPE, QlooEntity, QlooTag

TAG = "urn:tag:genre:music:"


def artist(entity_id, name, *tags, popularity=0.5, affinity=0.9):
    return QlooEntity(
        entity_id, name, ("urn:entity", ARTIST_TYPE), affinity, popularity,
        genre_tags=tuple((TAG + t, t.replace("_", " ").title()) for t in tags),
    )  # fmt: skip


def title(entity_id, name, qloo_type, year=None, popularity=0.5):
    return QlooEntity(entity_id, name, (qloo_type,), popularity=popularity, year=year)


def song(artist_name, title_text, *, year="2015", genre="Metal", album=None,
         url=None, preview=True):  # fmt: skip
    slug = f"{artist_name}-{title_text}".replace(" ", "-").lower()
    return Track(
        title=title_text,
        artist=artist_name,
        album=album or f"{title_text} LP",
        year=year,
        url=url or f"https://music.example/{slug}",
        artwork_small=None,
        artwork_large=None,
        genre=genre,
        preview_url=f"https://audio.example/{slug}.m4a" if preview else None,
    )


class FakeQloo:
    """Records calls. `insights[signal_id]` is the artist list per signal;
    with `genre_filtered[signal_id]` set, filtered queries return that."""

    def __init__(self, searches=None, tags=None, insights=None, genre_filtered=None,
                 error=None):  # fmt: skip
        self.searches = searches or {}
        self.tag_results = tags or {}
        self.insights = insights or {}
        self.genre_filtered = genre_filtered or {}
        self.error = error
        self.calls: list[tuple[str, tuple, dict]] = []

    def search(self, query, types, take=5):
        self.calls.append(("search", (query, tuple(types)), {"take": take}))
        if self.error:
            raise self.error
        # Qloo search is case-insensitive.
        found = next(
            (v for k, v in self.searches.items() if k.casefold() == query.casefold()),
            [],
        )
        return [e for e in found if set(e.types) & set(types)][:take]

    def tags(self, query, tag_types=(), take=10):
        self.calls.append(("tags", (query, tuple(tag_types)), {"take": take}))
        if self.error:
            raise self.error
        return [t for t in self.tag_results.get(query, [])
                if not tag_types or t.tag_type in tag_types][:take]  # fmt: skip

    def artist_insights(self, entity_ids, take, **kwargs):
        self.calls.append(("insights", tuple(entity_ids), {"take": take, **kwargs}))
        if self.error:
            raise self.error
        signal = entity_ids[0]
        source = self.insights
        if kwargs.get("filter_tags") and signal in self.genre_filtered:
            source = self.genre_filtered
        excluded = set(kwargs.get("exclude_entities") or ())
        return [a for a in source.get(signal, []) if a.entity_id not in excluded][:take]

    def insight_calls(self):
        return [c for c in self.calls if c[0] == "insights"]


class FakeCatalog:
    """Artist name -> tracks; names in `failing` raise CatalogError."""

    def __init__(self, tracks=None, failing=()):
        self.tracks = tracks or {}
        self.failing = set(failing)
        self.lookups: list[str] = []

    def __call__(self, name):
        self.lookups.append(name)
        if name in self.failing:
            raise CatalogError("offline")
        return self.tracks.get(name, [])


def tag(tag_id, name, tag_type="urn:tag:ambience:qloo"):
    return QlooTag(tag_id, name, tag_type)
