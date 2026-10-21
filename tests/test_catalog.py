import httpx
import pytest

from crosssignal.catalog import (
    CatalogError,
    credited_artists,
    match_rank,
    normalize_name,
    parse_tracks,
    search_tracks,
)


def song(artist: str, title: str = "Song", **overrides) -> dict:
    item = {
        "kind": "song",
        "artistName": artist,
        "trackName": title,
        "collectionName": "Album",
        "releaseDate": "1998-04-20T07:00:00Z",
        "trackViewUrl": "https://music.apple.com/us/album/x?i=1",
        "artworkUrl100": "https://is1-ssl.mzstatic.com/a/100x100bb.jpg",
        "primaryGenreName": "Electronic",
    }
    item.update(overrides)
    return item


def client_returning(response: httpx.Response) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda request: response))


# --- name matching -------------------------------------------------------


def test_normalize_ignores_case_accents_and_spacing():
    assert normalize_name("  Ólafur   ARNALDS ") == "olafur arnalds"


def test_credited_artists_splits_collaborations():
    assert credited_artists("Portishead, Nick Ingman & Orchestra") == [
        "Portishead",
        "Nick Ingman",
        "Orchestra",
    ]
    assert credited_artists("Kavinsky feat. Lovefoxxx") == ["Kavinsky", "Lovefoxxx"]


@pytest.mark.parametrize(
    "credit", ["Kavinsky (feat. Lovefoxxx)", "Kavinsky [feat. Lovefoxxx]"]
)
def test_bracketed_feature_credit_matches_main_artist(credit):
    assert credited_artists(credit) == ["Kavinsky", "Lovefoxxx"]
    assert match_rank(credit, ["Kavinsky"]) == 1


@pytest.mark.parametrize(
    "credit",
    ["M83 Tribute Band", "The M83 Experience", "M83x", "Tribute to M83"],
)
def test_substrings_do_not_match(credit):
    assert match_rank(credit, ["M83"]) is None


def test_exact_and_collaboration_ranks():
    assert match_rank("m83", ["M83"]) == 0
    assert match_rank("Khruangbin & Leon Bridges", ["Khruangbin"]) == 1
    assert match_rank("Leon Bridges", ["Khruangbin"]) is None


def test_alias_matches_exactly():
    assert match_rank("久石譲", ["Joe Hisaishi", "久石譲"]) == 0


# --- payload validation --------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [None, [], "results", 42, {}, {"results": None}, {"results": {"a": 1}}],
)
def test_unexpected_payload_shapes_raise_catalog_error(payload):
    with pytest.raises(CatalogError):
        parse_tracks(payload, "M83")


def test_malformed_items_are_skipped_not_fatal():
    payload = {
        "results": [
            None,
            "not a dict",
            song("M83", trackName=None),
            song("M83", trackName=123),
            song("M83", trackName="   "),
            song("M83", artistName=["M83"]),
            song("M83", trackViewUrl=None),
            song("M83", trackViewUrl="javascript:alert(1)"),
            song("M83", kind="music-video"),
            song(
                "M83",
                "Midnight City",
                collectionName=7,
                releaseDate=1,
                artworkUrl100={"bad": True},
                primaryGenreName=["bad"],
            ),
        ]
    }
    [track] = parse_tracks(payload, "M83")
    assert track.title == "Midnight City"
    assert track.album is None
    assert track.year is None
    assert track.artwork_small is None and track.artwork_large is None
    assert track.genre is None


def test_unrelated_and_substring_artists_are_rejected():
    payload = {
        "results": [
            song("M83 Tribute Band", "Fake City"),
            song("Nicki Minaj", "Unrelated"),
            song("M83", "Midnight City"),
        ]
    }
    assert [t.title for t in parse_tracks(payload, "M83")] == ["Midnight City"]


def test_sole_credit_first_duplicates_removed_and_limit_applied():
    payload = {
        "results": [
            song("Khruangbin & Leon Bridges", "Texas Sun"),
            song("Khruangbin", "Maria También"),
            song("Khruangbin", "maria también"),
            song("Khruangbin", "White Gloves"),
            song("Khruangbin", "So We Won't Forget"),
        ]
    }
    titles = [t.title for t in parse_tracks(payload, "Khruangbin", limit=3)]
    assert titles == ["Maria También", "White Gloves", "So We Won't Forget"]


def test_track_fields_and_artwork_sizes():
    [track] = parse_tracks({"results": [song("Portishead", "Roads")]}, "Portishead")
    assert track.year == "1998"
    assert track.album == "Album"
    assert track.genre == "Electronic"
    assert track.artwork_small.endswith("/200x200bb.jpg")
    assert track.artwork_large.endswith("/600x600bb.jpg")


def test_no_matches_returns_empty_list():
    assert parse_tracks({"results": []}, "M83") == []


# --- HTTP layer ----------------------------------------------------------


def test_search_tracks_sends_expected_query():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": [song("M83", "Wait")]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tracks = search_tracks("M83", client=client)

    assert [t.title for t in tracks] == ["Wait"]
    assert seen["term"] == "M83"
    assert seen["attribute"] == "artistTerm"
    assert seen["entity"] == "song"


def test_invalid_json_raises_catalog_error():
    client = client_returning(httpx.Response(200, content=b"<html>oops</html>"))
    with pytest.raises(CatalogError, match="invalid JSON"):
        search_tracks("M83", client=client)


def test_http_status_error_raises_catalog_error():
    client = client_returning(httpx.Response(503))
    with pytest.raises(CatalogError):
        search_tracks("M83", client=client)


def test_network_error_raises_catalog_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(CatalogError):
        search_tracks("M83", client=client)


def test_valid_json_with_wrong_shape_raises_catalog_error():
    client = client_returning(httpx.Response(200, json=["unexpected"]))
    with pytest.raises(CatalogError):
        search_tracks("M83", client=client)
