"""iTunes Search API lookup.

Docs: https://performance-partners.apple.com/search-api
No credentials are required. Every network, decoding, or shape problem
is reported as CatalogError so callers handle exactly one failure type.
"""

import re
import unicodedata
from collections.abc import Iterable

import httpx

from crosssignal.models import Track

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
TIMEOUT_SECONDS = 15
SEARCH_LIMIT = 40

# Separators iTunes uses between credited artists, e.g.
# "Portishead, Nick Ingman & Orchestra", "Kavinsky feat. X" or
# "Kavinsky (feat. X)". Brackets around a feature credit are separators too.
_CREDIT_SEPARATORS = re.compile(
    r"\s*(?:,|&|[()\[\]]|\bfeat\.|\bft\.|\bfeaturing\b)\s*",
    re.IGNORECASE,
)
_ARTWORK_SIZE = re.compile(r"/\d+x\d+bb\.")


class CatalogError(Exception):
    """The music catalog could not provide a usable response."""


def normalize_name(name: str) -> str:
    """Compare names case-, accent-, and whitespace-insensitively."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


# "(2007 Remaster)", "- Live", "[Radio Edit]" and similar version labels.
_VERSION_WORDS = (
    r"remaster(?:ed)?|live|remix|mix|edit|version|mono|stereo|demo|"
    r"deluxe|bonus|single|radio|instrumental|acoustic|re-recorded|reprise"
)
_VERSION_SUFFIX = re.compile(
    rf"\s*(?:[(\[][^)\]]*\b(?:{_VERSION_WORDS})\b[^)\]]*[)\]]"
    rf"|\s-\s[^-]*\b(?:{_VERSION_WORDS})\b.*)$",
    re.IGNORECASE,
)


def base_title(title: str) -> str:
    """A title without version labels, for spotting duplicate songs.

    "Where Is My Mind? (2007 Remaster)" and "Where Is My Mind? - Live"
    both become "where is my mind?".
    """
    previous = None
    while previous != title:
        previous, title = title, _VERSION_SUFFIX.sub("", title)
    return normalize_name(title)


def credited_artists(artist_name: str) -> list[str]:
    """Split a credit string into the individual artists it names."""
    return [part for part in _CREDIT_SEPARATORS.split(artist_name) if part]


def match_rank(artist_name: str, wanted: Iterable[str]) -> int | None:
    """Rank how well a track credit matches the wanted artist.

    0 means the artist is the sole credit, 1 means they are one of several
    credited artists, None means no exact match. Substrings never match:
    "M83 Tribute Band" is not "M83".
    """
    targets = {normalize_name(name) for name in wanted}
    if normalize_name(artist_name) in targets:
        return 0
    if any(normalize_name(part) in targets for part in credited_artists(artist_name)):
        return 1
    return None


def _https_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.startswith("https://"):
        return value
    return None


def _resize_artwork(url: str | None, size: int) -> str | None:
    if url is None:
        return None
    return _ARTWORK_SIZE.sub(f"/{size}x{size}bb.", url)


def _parse_track(item: object) -> Track | None:
    """Build a Track from one result, or None if required fields are bad."""
    if not isinstance(item, dict):
        return None
    if item.get("kind", "song") != "song":
        return None
    if item.get("isStreamable") is False:  # listed, but not playable
        return None

    title = item.get("trackName")
    artist = item.get("artistName")
    url = _https_or_none(item.get("trackViewUrl"))
    if not (isinstance(title, str) and title.strip()):
        return None
    if not (isinstance(artist, str) and artist.strip()) or url is None:
        return None

    album = item.get("collectionName")
    release = item.get("releaseDate")
    year = release[:4] if isinstance(release, str) and release[:4].isdigit() else None
    artwork = _https_or_none(item.get("artworkUrl100"))
    genre = item.get("primaryGenreName")

    return Track(
        title=title.strip(),
        artist=artist.strip(),
        album=album.strip() if isinstance(album, str) and album.strip() else None,
        year=year,
        url=url,
        artwork_small=_resize_artwork(artwork, 200),
        artwork_large=_resize_artwork(artwork, 600),
        genre=genre.strip() if isinstance(genre, str) and genre.strip() else None,
        preview_url=_https_or_none(item.get("previewUrl")),
    )


def parse_tracks(
    payload: object,
    artist: str,
    aliases: Iterable[str] = (),
    limit: int = 3,
) -> list[Track]:
    """Select up to `limit` distinct songs credited to `artist`.

    Raises CatalogError if the payload is not the documented shape.
    Individual malformed results are skipped.
    """
    if not isinstance(payload, dict):
        raise CatalogError("Catalog response was not a JSON object.")
    results = payload.get("results")
    if not isinstance(results, list):
        raise CatalogError("Catalog response had no results list.")

    wanted = [artist, *aliases]
    ranked: list[tuple[int, int, Track]] = []
    for position, item in enumerate(results):
        track = _parse_track(item)
        if track is None:
            continue
        rank = match_rank(track.artist, wanted)
        if rank is not None:
            ranked.append((rank, position, track))

    # Sole-credit tracks first, then collaborations, keeping catalog order.
    ranked.sort(key=lambda entry: (entry[0], entry[1]))

    seen_titles: set[str] = set()
    tracks: list[Track] = []
    for _, _, track in ranked:
        key = base_title(track.title)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        tracks.append(track)
        if len(tracks) == limit:
            break
    return tracks


def search_tracks(
    artist: str,
    aliases: Iterable[str] = (),
    *,
    client: httpx.Client | None = None,
    limit: int = 3,
) -> list[Track]:
    """Fetch songs by `artist` from the iTunes Search API."""
    params = {
        "term": artist,
        "media": "music",
        "entity": "song",
        "attribute": "artistTerm",
        "country": "US",
        "limit": SEARCH_LIMIT,
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = http.get(ITUNES_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise CatalogError(f"Catalog request failed: {exc}") from exc
    except ValueError as exc:
        raise CatalogError("Catalog returned invalid JSON.") from exc
    finally:
        if owns_client:
            http.close()

    return parse_tracks(payload, artist, aliases, limit)
