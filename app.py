"""CrossSignal Streamlit UI.

Presentation only. Recommendations come from a RecommendationProvider
chosen by configuration (see crosssignal.config) and tracks from the
catalog module. Nothing here reads provider-specific JSON; it works only
with crosssignal.models.
"""

import streamlit as st

from crosssignal.catalog import normalize_name, search_tracks
from crosssignal.config import ConfigError, load_settings
from crosssignal.discovery import MAX_INTERESTS, discover
from crosssignal.factory import build_provider
from crosssignal.models import (
    ArtistPick,
    ArtistResult,
    Discovery,
    LookupStatus,
    Outcome,
    ProviderErrorKind,
    Track,
)
from crosssignal.recommendations import (
    DEMO_SOURCE,
    CuratedProvider,
    RecommendationProvider,
)
from crosssignal.text import escape_markdown, join_names, markdown_link

st.set_page_config(
    page_title="CrossSignal — Your world has a soundtrack",
    page_icon="🎧",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def get_provider() -> tuple[RecommendationProvider, str | None]:
    """The configured provider, plus a config problem to show, if any.

    One instance per server process, so the Qloo provider's lookup cache
    is shared across reruns. Config messages never contain secret values.
    """
    try:
        return build_provider(load_settings()), None
    except ConfigError as exc:
        return CuratedProvider(), f"{exc}. Showing demo data instead."


PROVIDER, CONFIG_PROBLEM = get_provider()
IS_DEMO = PROVIDER.source == DEMO_SOURCE
INTERESTS = {interest.id: interest for interest in PROVIDER.interests()}
CATEGORIES = ("Films", "Games", "Aesthetics")
CATEGORY_ICONS = {
    "Films": ":material/movie:",
    "Games": ":material/sports_esports:",
    "Aesthetics": ":material/palette:",
}

CSS = """
<style>
.cs-hero { padding: 1.5rem 0 0.5rem; }
.cs-eyebrow {
  margin: 0; color: #9C9CB8; font-size: 0.78rem;
  letter-spacing: 0.18em; text-transform: uppercase;
}
.cs-title {
  margin: 0.2rem 0 0; padding: 0; font-size: clamp(2.6rem, 8vw, 4.75rem);
  font-weight: 800; letter-spacing: -0.035em; line-height: 1.05;
  background: linear-gradient(90deg, #C4B5FD, #F0ABFC 55%, #67E8F9);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.cs-tagline {
  margin: 0.4rem 0 0.9rem; font-size: clamp(1.2rem, 3.4vw, 1.7rem);
  font-weight: 600;
}
.cs-lede { max-width: 42rem; color: #B9B9CC; font-size: 1.05rem; line-height: 1.6; }
[data-testid="stImage"] img { border-radius: 0.6rem; }
</style>
"""


# --- data access ---------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner=False)
def cached_tracks(artist: str, aliases: tuple[str, ...]) -> list[Track]:
    # Exceptions are not cached, so a retry re-requests only failed artists.
    return search_tracks(artist, aliases)


def lookup(pick: ArtistPick) -> list[Track]:
    return cached_tracks(pick.artist, pick.aliases)


# --- state ---------------------------------------------------------------
# pick_<category>: list of interest ids, owned by each st.pills widget.
# discovery:       the last submitted Discovery, rendered on every rerun.
# pending:         interest ids queued by Discover/Retry, consumed once.


def pill_key(category: str) -> str:
    return f"pick_{category.lower()}"


def selected_ids() -> list[str]:
    return [
        interest_id
        for category in CATEGORIES
        for interest_id in st.session_state.get(pill_key(category)) or []
    ]


def queue_discovery(interest_ids: list[str] | tuple[str, ...]) -> None:
    st.session_state.pending = tuple(interest_ids)


def reset() -> None:
    for category in CATEGORIES:
        st.session_state[pill_key(category)] = []
    st.session_state.discovery = None
    st.session_state.pending = None


st.session_state.setdefault("discovery", None)
st.session_state.setdefault("pending", None)


# --- rendering -----------------------------------------------------------


def render_hero() -> None:
    st.html(CSS)
    st.html(
        """
        <div class="cs-hero">
          <p class="cs-eyebrow">Cross-domain music discovery</p>
          <h1 class="cs-title">CrossSignal</h1>
          <p class="cs-tagline">Your world has a soundtrack.</p>
          <p class="cs-lede">The films you rewatch, the games you get lost in and
          the aesthetics you live in all carry a sound. Pick a few, and
          CrossSignal turns those signals into artists and tracks to explore.</p>
        </div>
        """
    )
    steps = st.columns(3)
    for column, (icon, title, body) in zip(
        steps,
        [
            (":material/touch_app:", "Pick your worlds",
             "Up to five films, games or aesthetics."),
            (":material/graphic_eq:", "Find the signal",
             "Each choice maps to artists that share its mood."),
            (":material/headphones:", "Hear the soundtrack",
             "Real tracks and artwork from the Apple catalog."),
        ],
        strict=True,
    ):  # fmt: skip
        with column:
            st.markdown(f"{icon} **{title}**")
            st.caption(body)

    if CONFIG_PROBLEM:
        st.warning(
            f"Configuration problem: {CONFIG_PROBLEM}", icon=":material/settings:"
        )
    if IS_DEMO:
        st.info(
            "**Demo data.** The links between interests and artists are "
            "hand-curated for this prototype. They are not Qloo recommendations. "
            "Tracks, artwork and links are fetched live from the Apple iTunes catalog.",
            icon=":material/science:",
        )
    else:
        st.info(
            "**Live Qloo recommendations.** Artists come from Qloo's taste graph "
            "for each interest Qloo recognises. Tracks, artwork and links are "
            "fetched live from the Apple iTunes catalog.",
            icon=":material/hub:",
        )


def render_picker() -> list[str]:
    st.subheader("Choose your worlds")
    st.caption(f"Select up to {MAX_INTERESTS} across any category.")
    for category in CATEGORIES:
        st.pills(
            f"{CATEGORY_ICONS[category]} {category}",
            options=[i.id for i in INTERESTS.values() if i.category == category],
            selection_mode="multi",
            format_func=lambda interest_id: INTERESTS[interest_id].name,
            key=pill_key(category),
        )
    return selected_ids()


def render_signal(ids: list[str]) -> None:
    too_many = len(ids) > MAX_INTERESTS
    with st.container(border=True):
        st.markdown(f"**Your signal** · {len(ids)}/{MAX_INTERESTS} selected")
        if ids:
            with st.container(horizontal=True, gap="small"):
                for interest_id in ids:
                    st.badge(INTERESTS[interest_id].name, color="violet")
        else:
            st.caption("Nothing selected yet. Pick at least one world above.")

        if too_many:
            extra = len(ids) - MAX_INTERESTS
            st.warning(
                f"Remove {extra} interest{'s' if extra > 1 else ''} to continue.",
                icon=":material/block:",
            )

        with st.container(horizontal=True, gap="small"):
            st.button(
                "Discover my soundtrack",
                type="primary",
                icon=":material/auto_awesome:",
                disabled=not ids or too_many,
                on_click=queue_discovery,
                args=(ids,),
            )
            st.button(
                "Reset",
                icon=":material/restart_alt:",
                disabled=not ids and st.session_state.discovery is None,
                on_click=reset,
            )


def run_pending() -> None:
    ids = st.session_state.pending
    if not ids:
        return
    st.session_state.pending = None
    progress = st.progress(0.0, text="Tuning in to your signal…")

    def on_progress(done: int, total: int, pick: ArtistPick) -> None:
        progress.progress(
            done / total, text=f"Checked {done} of {total} artists · {pick.artist}"
        )

    try:
        st.session_state.discovery = discover(ids, PROVIDER, lookup, on_progress)
    finally:
        progress.empty()


PROVIDER_MESSAGES = {
    ProviderErrorKind.AUTH: "The recommendation service rejected its API key.",
    ProviderErrorKind.RATE_LIMIT: "The recommendation service is rate limiting "
    "requests. Wait a moment, then retry.",
    ProviderErrorKind.TIMEOUT: "The recommendation service took too long to respond.",
    ProviderErrorKind.UNAVAILABLE: "The recommendation service couldn't be reached.",
    ProviderErrorKind.MALFORMED: "The recommendation service sent a response "
    "CrossSignal couldn't read.",
    ProviderErrorKind.BAD_REQUEST: "The recommendation service rejected the request.",
    ProviderErrorKind.NOT_CONFIGURED: "The recommendation service isn't configured.",
}
RETRYABLE = {
    ProviderErrorKind.RATE_LIMIT,
    ProviderErrorKind.TIMEOUT,
    ProviderErrorKind.UNAVAILABLE,
}


def render_unresolved(discovery: Discovery) -> None:
    if discovery.unresolved:
        names = join_names([escape_markdown(i.name) for i in discovery.unresolved])
        st.info(
            f"No exact match in the recommendation source for {names}, "
            "so they did not shape these results.",
            icon=":material/link_off:",
        )


def render_provider_problem(discovery: Discovery) -> bool:
    """Show provider-level outcomes. True if there are no cards to render."""
    if discovery.outcome is Outcome.PROVIDER_ERROR:
        kind = discovery.provider_error
        st.error(PROVIDER_MESSAGES[kind], icon=":material/cloud_off:")
        if kind in RETRYABLE:
            st.button(
                "Retry",
                icon=":material/refresh:",
                on_click=queue_discovery,
                args=(discovery.interest_ids,),
            )
        return True
    if discovery.outcome is Outcome.NO_RECOMMENDATIONS:
        st.info(
            "No artists came back for these worlds. Try different ones.",
            icon=":material/search_off:",
        )
        return True
    return False


def render_outcome(discovery: Discovery) -> None:
    total = len(discovery.results)
    found = discovery.count(LookupStatus.OK)
    errors = discovery.count(LookupStatus.ERROR)
    empty = discovery.count(LookupStatus.EMPTY)
    outcome = discovery.outcome

    if outcome is Outcome.SUCCESS:
        st.success(f"Found tracks for all {total} artists.", icon=":material/check:")
    elif outcome is Outcome.PARTIAL:
        details = []
        if errors:
            details.append(f"{errors} couldn't be reached")
        if empty:
            details.append(f"{empty} had no exact catalog match")
        st.warning(
            f"Found tracks for {found} of {total} artists ({', '.join(details)}).",
            icon=":material/error:",
        )
    elif outcome is Outcome.FAILURE:
        st.error(
            "The music catalog couldn't be reached. Check your connection and retry.",
            icon=":material/wifi_off:",
        )
    else:
        st.info(
            "No exact catalog matches for these artists. Try different worlds.",
            icon=":material/search_off:",
        )

    if errors:
        st.button(
            f"Retry {errors} failed lookup{'s' if errors > 1 else ''}",
            icon=":material/refresh:",
            on_click=queue_discovery,
            args=(discovery.interest_ids,),
        )


def render_track(track: Track, artist: str) -> None:
    with st.container(horizontal=True, vertical_alignment="center", wrap=False):
        if track.artwork_small:
            st.image(
                track.artwork_small,
                width=56,
                alt=f"Artwork for {track.album or track.title}",
            )
        with st.container(gap=None):
            st.markdown(f"**{markdown_link(track.title, track.url)}**")
            meta = [part for part in (track.album, track.year) if part]
            if normalize_name(track.artist) != normalize_name(artist):
                meta.insert(0, track.artist)
            if meta:
                st.caption(" · ".join(escape_markdown(part) for part in meta))


CATEGORY_NOUNS = {"Films": "film", "Games": "game"}
AFFINITY_HELP = (
    "Qloo's affinity ranks how strongly an artist is associated with a "
    "title's audience. It is not a probability that you will like the artist."
)


def render_evidence(pick: ArtistPick) -> None:
    """What Qloo actually returned: the matched title and the artist's rank."""
    for evidence in pick.evidence:
        line = (
            f"Qloo's #{evidence.rank} artist for the "
            f"{CATEGORY_NOUNS.get(evidence.interest.category, 'title')} "
            f"*{escape_markdown(evidence.signal_name)}*"
        )
        if evidence.affinity is not None:
            line += f" · affinity {evidence.affinity:.2f}"
        st.caption(line, help=AFFINITY_HELP if evidence.affinity is not None else None)


def render_card(result: ArtistResult) -> None:
    pick = result.pick
    with st.container(border=True):
        cover = next((t.artwork_large for t in result.tracks if t.artwork_large), None)
        if cover:
            st.image(cover, width="stretch", alt=f"Album artwork for {pick.artist}")

        st.markdown(f"### {escape_markdown(pick.artist)}")
        because = join_names([f"**{escape_markdown(i.name)}**" for i in pick.interests])
        st.markdown(f"Because you picked {because}")
        if pick.source == DEMO_SOURCE:
            st.caption(" · ".join(escape_markdown(i.vibe) for i in pick.interests))
            st.badge("Demo-curated link", icon=":material/science:", color="gray")
        else:
            render_evidence(pick)
            st.badge("Qloo insight", icon=":material/hub:", color="blue")

        if result.status is LookupStatus.ERROR:
            st.warning("Couldn't reach the catalog for this artist.")
        elif result.status is LookupStatus.EMPTY:
            st.info("No exact catalog match for this artist.")
        else:
            for track in result.tracks:
                render_track(track, pick.artist)
            st.caption("Titles open on Apple Music.")


def render_results(discovery: Discovery | None, ids: list[str]) -> None:
    if discovery is None:
        return

    st.divider()
    st.subheader("Your soundtrack")
    names = join_names([INTERESTS[i].name for i in discovery.interest_ids])
    total = len(discovery.results)
    st.caption(
        f"{total} artist{'s' if total != 1 else ''} from {escape_markdown(names)}"
    )
    if set(ids) != set(discovery.interest_ids):
        st.info(
            "Your selection has changed. Discover again to update these results.",
            icon=":material/sync:",
        )

    render_unresolved(discovery)
    if render_provider_problem(discovery):
        return
    render_outcome(discovery)
    if discovery.outcome is Outcome.FAILURE:
        return

    columns_per_row = 2
    results = discovery.results
    for start in range(0, len(results), columns_per_row):
        row = st.columns(columns_per_row, gap="medium")
        for column, result in zip(row, results[start : start + columns_per_row]):
            with column:
                render_card(result)


def render_footer() -> None:
    st.divider()
    source = (
        "Interest-to-artist associations are demo-curated, not generated by Qloo."
        if IS_DEMO
        else "Interest-to-artist associations from the Qloo Insights API."
    )
    st.caption(
        f"CrossSignal prototype. {source} Music data and artwork via the "
        "Apple iTunes Search API; titles link to Apple Music."
    )


render_hero()
selection = render_picker()
render_signal(selection)
run_pending()
render_results(st.session_state.discovery, selection)
render_footer()
