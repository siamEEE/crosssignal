"""Check whether recommended artists resolve to real catalog tracks.

Three modes keep runs honest about what was measured:
- LiveProbe: queries the iTunes Search API (free, no key).
- SnapshotProbe: replays a snapshot previously recorded by LiveProbe,
  so runs are deterministic and offline. Artists absent from the
  snapshot are UNMEASURED, never assumed found or missing.
- NullProbe: availability is not measured at all.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from crosssignal.catalog import CatalogError, normalize_name, search_tracks
from crosssignal.models import Track


class Availability(StrEnum):
    FOUND = "found"  # at least one exact-credit track
    NOT_FOUND = "not_found"  # catalog answered, no exact match
    ERROR = "error"  # catalog request failed
    UNMEASURED = "unmeasured"  # not probed (no snapshot entry / disabled)


@dataclass(frozen=True)
class ArtistAvailability:
    artist: str
    status: Availability
    track_count: int = 0
    genres: tuple[str, ...] = ()


class CatalogProbe(Protocol):
    mode: str

    def probe(self, artist: str) -> ArtistAvailability: ...


def availability_from_tracks(artist: str, tracks: list[Track]) -> ArtistAvailability:
    genres = tuple(dict.fromkeys(t.genre for t in tracks if t.genre))
    status = Availability.FOUND if tracks else Availability.NOT_FOUND
    return ArtistAvailability(artist, status, len(tracks), genres)


class LiveProbe:
    mode = "live"

    def __init__(self, search: Callable[[str], list[Track]] = search_tracks) -> None:
        self._search = search
        self.recorded: dict[str, ArtistAvailability] = {}

    def probe(self, artist: str) -> ArtistAvailability:
        key = normalize_name(artist)
        if key in self.recorded:
            return self.recorded[key]
        try:
            result = availability_from_tracks(artist, list(self._search(artist)))
        except CatalogError:
            # Failures are not recorded: a snapshot holds only real answers.
            return ArtistAvailability(artist, Availability.ERROR)
        self.recorded[key] = result
        return result

    def save_snapshot(self, path: Path) -> None:
        entries = sorted(
            (asdict(a) for a in self.recorded.values()), key=lambda a: a["artist"]
        )
        payload = {
            "source": "iTunes Search API via crosssignal.catalog.search_tracks",
            "entries": entries,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


class SnapshotProbe:
    mode = "snapshot"

    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._entries = {
            normalize_name(e["artist"]): ArtistAvailability(
                e["artist"],
                Availability(e["status"]),
                int(e["track_count"]),
                tuple(e["genres"]),
            )
            for e in raw["entries"]
        }

    def probe(self, artist: str) -> ArtistAvailability:
        found = self._entries.get(normalize_name(artist))
        return found or ArtistAvailability(artist, Availability.UNMEASURED)


class NullProbe:
    mode = "none"

    def probe(self, artist: str) -> ArtistAvailability:
        return ArtistAvailability(artist, Availability.UNMEASURED)
