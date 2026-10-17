
import httpx
import streamlit as st

st.set_page_config(
    page_title="CrossSignal",
    page_icon="🎧",
    layout="wide",
)

# Temporary curated associations.
# Real Qloo recommendations will replace these.
CULTURAL_WORLDS = {
    "Blade Runner 2049": ["Massive Attack", "Portishead"],
    "Interstellar": ["M83", "Hans Zimmer"],
    "Studio Ghibli": ["Joe Hisaishi", "Nujabes"],
    "Cyberpunk 2077": ["Carpenter Brut", "Perturbator"],
    "Quiet coffee shops": ["Khruangbin", "Men I Trust"],
    "Dark academia": ["Max Richter", "Agnes Obel"],
}


@st.cache_data(ttl=3600)
def find_tracks(artist: str) -> list[dict]:
    response = httpx.get(
        "https://itunes.apple.com/search",
        params={
            "term": artist,
            "media": "music",
            "entity": "song",
            "attribute": "artistTerm",
            "country": "US",
            "limit": 40,
        },
        timeout=15,
    )
    response.raise_for_status()

    results = response.json().get("results", [])

    # Reject tracks from unrelated artists.
    matches = [
        item
        for item in results
        if artist.casefold()
        in item.get("artistName", "").casefold()
    ]

    return matches[:3]


st.title("🎧 CrossSignal")
st.markdown("### Discover music from everything else you love.")
st.write(
    "Choose films, games, or aesthetics you enjoy. "
    "We'll discover a possible soundtrack for your world."
)

choices = st.multiselect(
    "What are you into?",
    options=list(CULTURAL_WORLDS),
    default=["Blade Runner 2049"],
    max_selections=3,
)

st.caption(
    "V0: artist associations are manually curated. "
    "Tracks and links are retrieved from a live catalog."
)

if st.button("Discover my soundtrack", type="primary"):
    if not choices:
        st.warning("Choose at least one interest.")
    else:
        artists = list(
            dict.fromkeys(
                artist
                for choice in choices
                for artist in CULTURAL_WORLDS[choice]
            )
        )[:6]

        st.success(f"Exploring {len(artists)} artists!")

        for artist in artists:
            with st.container(border=True):
                st.subheader(artist)

                try:
                    tracks = find_tracks(artist)

                    if not tracks:
                        st.info("No matching tracks found.")
                        continue

                    for track in tracks:
                        image_col, detail_col = st.columns([1, 5])

                        with image_col:
                            artwork = track.get("artworkUrl100")
                            if artwork:
                                st.image(artwork, width=90)

                        with detail_col:
                            st.markdown(
                                f"**{track.get('trackName', 'Unknown')}**"
                            )
                            st.caption(
                                track.get("collectionName", "Unknown album")
                            )

                            url = track.get("trackViewUrl")
                            if url:
                                st.link_button(
                                    "Listen / view track",
                                    url,
                                )

                except httpx.HTTPError:
                    st.error(
                        "Music catalog unavailable. Please retry."
                    )

st.divider()
st.caption(
    "CrossSignal — V0 prototype. "
    "Qloo cultural intelligence and agent orchestration "
    "are coming next."
)
