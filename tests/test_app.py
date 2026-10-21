"""Headless UI tests using Streamlit's built-in AppTest (no browser, no network)."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from crosssignal import catalog, factory
from crosssignal.catalog import CatalogError
from crosssignal.discovery import MAX_ARTISTS
from crosssignal.models import (
    ArtistPick,
    Evidence,
    ProviderErrorKind,
    RecommendationError,
    RecommendationSet,
    Track,
)
from crosssignal.recommendations import CuratedProvider

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fake_track(artist: str, title: str | None = None, artwork: bool = False) -> Track:
    art = "https://is1-ssl.mzstatic.com/a/{0}x{0}bb.jpg" if artwork else None
    return Track(
        title=title or f"{artist} song",
        artist=artist,
        album="Album",
        year="2020",
        url="https://music.apple.com/us/album/x",
        artwork_small=art and art.format(200),
        artwork_large=art and art.format(600),
    )


@pytest.fixture
def calls(monkeypatch):
    """Patch the catalog; run with the default (curated) configuration.

    Artists in `calls.fail` raise, artists in `calls.empty` have no match,
    `calls.tracks` overrides what an artist returns, others get one track.
    """
    st.cache_data.clear()
    st.cache_resource.clear()
    for name in ("CROSSSIGNAL_PROVIDER", "QLOO_API_KEY", "QLOO_API_URL"):
        monkeypatch.delenv(name, raising=False)

    class Calls(list):
        def __init__(self) -> None:
            super().__init__()
            self.fail: set[str] = set()
            self.empty: set[str] = set()
            self.tracks: dict[str, list[Track]] = {}

    record = Calls()

    def fake_search(artist, aliases=(), **kwargs):
        record.append(artist)
        if artist in record.fail:
            raise CatalogError("offline")
        if artist in record.empty:
            return []
        return record.tracks.get(artist, [fake_track(artist)])

    monkeypatch.setattr(catalog, "search_tracks", fake_search)
    yield record
    st.cache_data.clear()
    st.cache_resource.clear()


def app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=10).run()


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label.startswith(label))


def markdown_text(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def select(at: AppTest, **picks: list[str]) -> AppTest:
    for category, ids in picks.items():
        at.session_state[f"pick_{category}"] = ids
    return at.run()


def test_landing_renders_with_demo_disclaimer(calls):
    at = app()
    assert not at.exception
    assert any("not Qloo recommendations" in i.value for i in at.info)
    assert button(at, "Discover").disabled
    assert calls == []


def test_discovery_persists_across_reruns(calls):
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()

    assert not at.exception
    assert calls == ["Massive Attack", "Portishead"]
    assert at.success[0].value.startswith("Found tracks for all 2 artists")
    assert "Massive Attack" in markdown_text(at)

    at.run()  # unrelated rerun: results must remain
    assert "Massive Attack" in markdown_text(at)
    assert len(calls) == 2  # served from cache, no new requests


def test_changing_selection_keeps_results_and_flags_stale(calls):
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()
    at = select(at, games=["journey"])

    assert "Massive Attack" in markdown_text(at)
    assert any("selection has changed" in i.value for i in at.info)


def test_reset_clears_selection_and_results(calls):
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()
    button(at, "Reset").click().run()

    assert at.session_state["pick_films"] == []
    assert at.session_state["discovery"] is None
    assert "Kavinsky" not in markdown_text(at)
    assert button(at, "Discover").disabled


def test_partial_failure_shows_warning_and_retry(calls):
    calls.fail = {"Portishead"}
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()

    assert "Found tracks for 1 of 2 artists" in at.warning[0].value
    assert "Massive Attack" in markdown_text(at)

    calls.fail = set()
    button(at, "Retry").click().run()
    assert at.success[0].value.startswith("Found tracks for all 2 artists")
    # Only the failed artist is re-requested; the success was cached.
    assert calls == ["Massive Attack", "Portishead", "Portishead"]


def test_total_failure_shows_error(calls):
    calls.fail = {"Massive Attack", "Portishead"}
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()

    assert "couldn't be reached" in at.error[0].value
    assert button(at, "Retry")


def test_more_than_five_interests_disables_discover(calls):
    at = select(
        app(),
        films=["blade-runner-2049", "interstellar", "drive"],
        games=["journey", "hollow-knight", "cyberpunk-2077"],
    )
    assert button(at, "Discover").disabled
    assert any("Remove 1 interest" in w.value for w in at.warning)


def test_multiple_interests_across_categories(calls):
    at = select(app(), films=["drive"], aesthetics=["dark-academia"])
    button(at, "Discover").click().run()

    assert not at.exception
    assert calls == ["Kavinsky", "Max Richter", "Cliff Martinez", "Agnes Obel"]


def test_five_interests_fill_the_artist_limit_and_credit_every_pick(calls):
    picked = {
        "films": ["blade-runner-2049", "interstellar"],
        "games": ["journey", "hollow-knight"],
        "aesthetics": ["dark-academia"],
    }
    at = select(app(), **picked)
    assert not button(at, "Discover").disabled
    button(at, "Discover").click().run()

    assert not at.exception
    assert len(calls) == MAX_ARTISTS
    text = markdown_text(at)
    because = [m.value for m in at.markdown if m.value.startswith("Because")]
    assert len(because) == MAX_ARTISTS
    for name in ["Blade Runner 2049", "Interstellar", "Journey", "Hollow Knight",
                 "Dark academia"]:  # fmt: skip
        assert f"**{name}**" in text
    # Max Richter is shared by two picks: one card, both credited.
    assert calls.count("Max Richter") == 1
    assert "Because you picked **Hollow Knight** and **Dark academia**" in text


def test_artwork_and_untrusted_titles_render_safely(calls):
    calls.tracks["Kavinsky"] = [
        fake_track("Kavinsky", "**Nightcall** :red[x] $5", artwork=True),
        fake_track("Kavinsky & Lovefoxxx", "Nightcall (Remix)", artwork=True),
    ]
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()

    assert not at.exception
    text = markdown_text(at)
    assert r"\*\*Nightcall\*\* \:red\[x\] \$5" in text
    # A collaboration credit is shown; the sole credit is not repeated.
    captions = [c.value for c in at.caption]
    assert "Kavinsky & Lovefoxxx · Album · 2020" in captions
    assert "Album · 2020" in captions


def test_all_empty_shows_no_match_info_without_retry(calls):
    calls.empty = {"Massive Attack", "Portishead"}
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()

    assert any("No exact catalog matches" in i.value for i in at.info)
    assert not [b for b in at.button if b.label.startswith("Retry")]


def test_success_offers_no_retry(calls):
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()
    assert not [b for b in at.button if b.label.startswith("Retry")]


def test_retry_after_selection_change_reuses_original_interests(calls):
    calls.fail = {"Portishead"}
    at = select(app(), films=["blade-runner-2049"])
    button(at, "Discover").click().run()
    at = select(at, films=["drive"])
    calls.fail = set()
    button(at, "Retry").click().run()

    assert at.session_state["discovery"].interest_ids == ("blade-runner-2049",)
    assert calls == ["Massive Attack", "Portishead", "Portishead"]
    assert any("selection has changed" in i.value for i in at.info)


def test_rediscovering_same_selection_uses_cache(calls):
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()
    button(at, "Discover").click().run()

    assert not at.exception
    assert calls == ["Kavinsky", "Cliff Martinez"]


def test_reset_while_results_are_stale(calls):
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()
    at = select(at, games=["journey"])
    button(at, "Reset").click().run()

    assert at.session_state["pick_games"] == []
    assert at.session_state["discovery"] is None
    assert button(at, "Reset").disabled


# --- non-demo provider states (stub provider, our models only) ------------


class StubQloo:
    """Answers like a Qloo-backed provider would, using the curated picker."""

    source = "qloo"

    def __init__(self, answer=None, error=None):
        self._interests = {i.id: i for i in CuratedProvider().interests()}
        self.answer, self.error = answer, error
        self.calls = 0

    def interests(self):
        return list(self._interests.values())

    def recommend(self, interest_ids, max_artists):
        self.calls += 1
        if self.error:
            raise self.error
        return self.answer(self._interests, interest_ids)


def use_provider(monkeypatch, stub):
    monkeypatch.setattr(factory, "build_provider", lambda settings: stub)
    return stub


def qloo_answer(interests, ids):
    drive = interests["drive"]
    evidence = Evidence(drive, "m1", "Drive", rank=2, affinity=0.91)
    return RecommendationSet(
        (ArtistPick("Kavinsky", (drive,), "qloo", score=0.91,
                    score_kind="qloo_affinity", external_id="e1",
                    evidence=(evidence,)),),
        (interests["dark-academia"],),
    )  # fmt: skip


def test_qloo_results_are_labelled_with_real_score_and_unresolved(calls, monkeypatch):
    use_provider(monkeypatch, StubQloo(qloo_answer))
    at = select(app(), films=["drive"], aesthetics=["dark-academia"])
    assert any("Live Qloo recommendations" in i.value for i in at.info)
    button(at, "Discover").click().run()

    assert not at.exception
    assert "Kavinsky" in markdown_text(at)
    captions = [c.value for c in at.caption]
    assert "Qloo's #2 artist for the film *Drive* · affinity 0.91" in captions
    # The hand-written demo vibe is not presented as Qloo's reasoning.
    vibe = next(i.vibe for i in CuratedProvider().interests() if i.id == "drive")
    assert not any(vibe in c for c in captions)
    assert any("No exact match" in i.value and "Dark academia" in i.value
               for i in at.info)  # fmt: skip
    assert not any("not Qloo recommendations" in i.value for i in at.info)


def test_retryable_provider_error_offers_retry(calls, monkeypatch):
    error = RecommendationError(ProviderErrorKind.RATE_LIMIT, "Qloo: 429")
    stub = use_provider(monkeypatch, StubQloo(qloo_answer, error))
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()

    assert "rate limiting" in at.error[0].value
    assert calls == []  # no catalog lookups after a provider failure
    stub.error = None
    button(at, "Retry").click().run()
    assert "Kavinsky" in markdown_text(at)
    assert stub.calls == 2


def test_auth_error_is_not_retryable_and_hides_details(calls, monkeypatch):
    error = RecommendationError(
        ProviderErrorKind.AUTH, "Qloo: authentication rejected (401)"
    )
    use_provider(monkeypatch, StubQloo(error=error))
    at = select(app(), films=["drive"])
    button(at, "Discover").click().run()

    assert "rejected its API key" in at.error[0].value
    assert "401" not in at.error[0].value
    assert not [b for b in at.button if b.label == "Retry"]


def test_no_recommendations_is_distinct_from_catalog_miss(calls, monkeypatch):
    def nothing(interests, ids):
        return RecommendationSet((), tuple(interests[i] for i in ids))

    use_provider(monkeypatch, StubQloo(nothing))
    at = select(app(), aesthetics=["cottagecore"])
    button(at, "Discover").click().run()

    assert any("No artists came back" in i.value for i in at.info)
    assert not any("No exact catalog matches" in i.value for i in at.info)
    assert calls == []


def test_bad_config_falls_back_to_demo_without_showing_secrets(calls, monkeypatch):
    monkeypatch.setenv("CROSSSIGNAL_PROVIDER", "qloo")
    monkeypatch.setenv("QLOO_API_KEY", "sk-should-never-render")
    monkeypatch.setenv("QLOO_API_URL", "http://insecure.example")
    at = app()

    assert not at.exception
    assert any("QLOO_API_URL must start with https://" in w.value for w in at.warning)
    assert any("not Qloo recommendations" in i.value for i in at.info)
    elements = [*at.warning, *at.info, *at.markdown, *at.caption]
    rendered = " ".join(str(e.value) for e in elements)
    assert "sk-should-never-render" not in rendered
