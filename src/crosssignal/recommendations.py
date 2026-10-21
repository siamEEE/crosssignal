"""Recommendation sources.

The UI depends only on the RecommendationProvider protocol. Today the
only implementation is CuratedProvider, which serves hand-written demo
associations. These are NOT Qloo output; a QlooProvider implementing the
same protocol will replace it once API credentials are available.
"""

from collections.abc import Sequence
from typing import Protocol

from crosssignal.models import (
    ArtistPick,
    Interest,
    InvalidSelection,
    RecommendationSet,
)

DEMO_SOURCE = "demo-curated"


class RecommendationProvider(Protocol):
    source: str

    def interests(self) -> list[Interest]:
        """Interests the user can choose from, in display order."""
        ...

    def recommend(
        self, interest_ids: Sequence[str], max_artists: int
    ) -> RecommendationSet:
        """Artists for the selected interests, most relevant first.

        Raises InvalidSelection for ids it does not offer, and
        RecommendationError when the source itself fails. An empty
        RecommendationSet is a valid "nothing found" answer.
        """
        ...


# (id, name, category, vibe, artists). Hand-picked for the demo.
_CURATED: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("blade-runner-2049", "Blade Runner 2049", "Films",
     "Brooding trip-hop and neon-noir atmosphere",
     ("Massive Attack", "Portishead")),
    ("interstellar", "Interstellar", "Films",
     "Vast, cosmic synths and swelling organ",
     ("M83", "Hans Zimmer")),
    ("studio-ghibli", "Studio Ghibli", "Films",
     "Warm orchestral whimsy and lo-fi nostalgia",
     ("Joe Hisaishi", "Nujabes")),
    ("drive", "Drive", "Films",
     "Retro synthwave and late-night tension",
     ("Kavinsky", "Cliff Martinez")),
    ("lost-in-translation", "Lost in Translation", "Films",
     "Hazy dream-pop and jet-lagged melancholy",
     ("The Jesus and Mary Chain", "Kevin Shields")),
    ("cyberpunk-2077", "Cyberpunk 2077", "Games",
     "Aggressive darksynth and chrome-lit streets",
     ("Carpenter Brut", "Perturbator")),
    ("journey", "Journey", "Games",
     "Sweeping, meditative orchestral ambience",
     ("Austin Wintory", "Ólafur Arnalds")),
    ("hollow-knight", "Hollow Knight", "Games",
     "Melancholic strings for lonely, ruined worlds",
     ("Christopher Larkin", "Max Richter")),
    ("quiet-coffee-shops", "Quiet coffee shops", "Aesthetics",
     "Laid-back grooves and soft indie warmth",
     ("Khruangbin", "Men I Trust")),
    ("dark-academia", "Dark academia", "Aesthetics",
     "Neoclassical piano and candlelit strings",
     ("Max Richter", "Agnes Obel")),
    ("cottagecore", "Cottagecore", "Aesthetics",
     "Pastoral folk harmonies and open fields",
     ("Fleet Foxes", "Sufjan Stevens")),
    ("rainy-city-nights", "Rainy city nights", "Aesthetics",
     "Downtempo electronica for wet streets",
     ("Bonobo", "Tycho")),
]  # fmt: skip


class CuratedProvider:
    """Hand-curated demo associations between interests and artists."""

    source = DEMO_SOURCE

    def __init__(
        self,
        catalog: Sequence[tuple[str, str, str, str, tuple[str, ...]]] = _CURATED,
    ) -> None:
        self._interests = {
            interest_id: Interest(interest_id, name, category, vibe)
            for interest_id, name, category, vibe, _ in catalog
        }
        self._artists = {entry[0]: entry[4] for entry in catalog}

    def interests(self) -> list[Interest]:
        return list(self._interests.values())

    def recommend(
        self, interest_ids: Sequence[str], max_artists: int
    ) -> RecommendationSet:
        unknown = [i for i in interest_ids if i not in self._interests]
        if unknown:
            raise InvalidSelection(f"Unknown interest ids: {unknown}")
        selected = list(dict.fromkeys(interest_ids))

        # Round-robin so every selected interest is represented before
        # any interest contributes a second artist.
        order: list[str] = []
        depth = max((len(self._artists[i]) for i in selected), default=0)
        for level in range(depth):
            for interest_id in selected:
                artists = self._artists[interest_id]
                if level < len(artists) and artists[level] not in order:
                    order.append(artists[level])
        order = order[:max_artists]

        # Credit every selected interest that led to the artist.
        picks = tuple(
            ArtistPick(
                artist=artist,
                interests=tuple(
                    self._interests[i] for i in selected if artist in self._artists[i]
                ),
                source=self.source,
            )
            for artist in order
        )
        return RecommendationSet(picks)
