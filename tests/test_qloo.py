"""Qloo client/provider tests against mocked HTTP.

Payloads are synthetic fixtures. Their *field names and nesting* match
what the live hackathon API returned on 2026-10-21; every id, name and
number in them is made up. No real Qloo response data is stored here.
"""

import httpx
import pytest

from crosssignal.config import QlooSettings, Secret
from crosssignal.models import (
    Interest,
    InvalidSelection,
    ProviderErrorKind,
    RecommendationError,
)
from crosssignal.qloo import (
    MAX_RETRIES,
    MAX_RETRY_AFTER,
    QlooClient,
    QlooEntity,
    QlooProvider,
    parse_entity,
    parse_insights,
    parse_search,
)

KEY = "test-key-not-real"
SETTINGS = QlooSettings(Secret(KEY), "https://qloo.example", 5.0)

DRIVE = Interest("drive", "Drive", "Films", "synth")
JOURNEY = Interest("journey", "Journey", "Games", "orchestral")
ACADEMIA = Interest("dark-academia", "Dark academia", "Aesthetics", "piano")


def entity(entity_id: str, name: str, *types: str, affinity=None) -> dict:
    """A search-style entity: `types` is a list."""
    item = {"entity_id": entity_id, "name": name, "types": list(types)}
    if affinity is not None:
        item["query"] = {"affinity": affinity}
    return item


def artist(entity_id: str, name: str, affinity=0.5, explained=None) -> dict:
    """An insights-style artist: `type` + `subtype`, affinity under `query`."""
    query = {"affinity": affinity, "measurements": {"audience_growth": 0}}
    if explained is not None:
        query["explainability"] = {
            "signal.interests.entities": [
                {"entity_id": signal, "score": share} for signal, share in explained
            ]
        }
    return {"entity_id": entity_id, "name": name, "type": "urn:entity",
            "subtype": "urn:entity:artist", "popularity": 0.5, "query": query}  # fmt: skip


def search_payload(*items: dict) -> dict:
    return {"results": list(items)}


def insights_payload(*items: dict) -> dict:
    return {"success": True, "results": {"entities": list(items)}}


def client_for(handler, sleeps: list | None = None) -> QlooClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    record = sleeps if sleeps is not None else []
    return QlooClient(SETTINGS, http, sleep=record.append)


def responding(status: int, **kwargs) -> QlooClient:
    return client_for(lambda request: httpx.Response(status, **kwargs))


# --- request shape -------------------------------------------------------


def test_search_and_insights_send_documented_parameters_and_header():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/search":
            return httpx.Response(200, json=search_payload(entity("m1", "Drive")))
        return httpx.Response(200, json=insights_payload(artist("a1", "Kavinsky")))

    client = client_for(handler)
    assert client.search("Drive", ["urn:entity:movie"])[0].entity_id == "m1"
    assert client.artist_insights(["m1", "m2"], take=80)[0].name == "Kavinsky"

    search, insights = seen
    assert search.headers["X-Api-Key"] == KEY
    assert search.url.params["query"] == "Drive"
    assert search.url.params["types"] == "urn:entity:movie"
    assert insights.url.path == "/v2/insights"
    assert insights.url.params["filter.type"] == "urn:entity:artist"
    assert insights.url.params["signal.interests.entities"] == "m1,m2"
    assert insights.url.params["take"] == "50"  # documented maximum
    assert insights.url.params["feature.explainability"] == "true"


def test_client_requires_configuration():
    with pytest.raises(RecommendationError) as info:
        QlooClient(QlooSettings(None))
    assert info.value.kind is ProviderErrorKind.NOT_CONFIGURED


def test_insights_needs_a_signal():
    with pytest.raises(ValueError):
        responding(200, json=insights_payload()).artist_insights([], take=5)


# --- failures ------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, ProviderErrorKind.AUTH),
        (403, ProviderErrorKind.AUTH),
        (429, ProviderErrorKind.RATE_LIMIT),
        (400, ProviderErrorKind.BAD_REQUEST),
        (404, ProviderErrorKind.BAD_REQUEST),  # live: unknown path, not "no results"
        (500, ProviderErrorKind.UNAVAILABLE),
        (503, ProviderErrorKind.UNAVAILABLE),
    ],
)
def test_http_errors_map_to_kinds_without_leaking_the_key(status, kind):
    client = responding(status, json={"code": status, "message": f"echo {KEY}"})
    with pytest.raises(RecommendationError) as info:
        client.search("Drive", ["urn:entity:movie"])
    assert info.value.kind is kind
    assert KEY not in str(info.value)


def test_timeout_and_network_errors():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    for handler, kind in [(timeout, ProviderErrorKind.TIMEOUT),
                          (offline, ProviderErrorKind.UNAVAILABLE)]:  # fmt: skip
        with pytest.raises(RecommendationError) as info:
            client_for(handler).artist_insights(["m1"], take=5)
        assert info.value.kind is kind


def test_empty_results_are_empty_lists_not_errors():
    assert (
        responding(200, json=search_payload()).search("x", ["urn:entity:movie"]) == []
    )
    client = responding(200, json=insights_payload())
    assert client.artist_insights(["m1"], take=5) == []


def test_rate_limit_is_retried_with_bounded_backoff():
    responses = iter([httpx.Response(429, headers={"Retry-After": "2"}),
                      httpx.Response(503),
                      httpx.Response(200, json=search_payload(entity("m1", "Drive")))])  # fmt: skip
    sleeps = []
    client = client_for(lambda request: next(responses), sleeps)
    assert client.search("Drive", ["urn:entity:movie"])[0].entity_id == "m1"
    assert sleeps == [2.0, 1.5]  # Retry-After honoured, then backoff


def test_retries_give_up_and_retry_after_is_capped():
    requests, sleeps = [], []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "600"})

    with pytest.raises(RecommendationError) as info:
        client_for(handler, sleeps).search("Drive", ["urn:entity:movie"])
    assert info.value.kind is ProviderErrorKind.RATE_LIMIT
    assert len(requests) == MAX_RETRIES + 1
    assert sleeps == [MAX_RETRY_AFTER] * MAX_RETRIES


@pytest.mark.parametrize("status", [400, 401])
def test_auth_and_bad_requests_are_not_retried(status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, text="Unauthorized")

    with pytest.raises(RecommendationError):
        client_for(handler).search("Drive", ["urn:entity:movie"])
    assert len(requests) == 1


def test_timeout_then_success_is_retried():
    attempts = []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=insights_payload(artist("a1", "M83")))

    assert client_for(handler).artist_insights(["m1"], take=5)[0].name == "M83"
    assert len(attempts) == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"<html>proxy</html>"),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"success": True}),
        httpx.Response(200, json={"success": True, "results": {"entities": None}}),
        httpx.Response(200, json={"success": False, "results": {"entities": []}}),
    ],
)
def test_malformed_insights(response):
    with pytest.raises(RecommendationError) as info:
        client_for(lambda request: response).artist_insights(["m1"], take=5)
    assert info.value.kind is ProviderErrorKind.MALFORMED


def test_malformed_search():
    with pytest.raises(RecommendationError) as info:
        parse_search({"results": {"oops": 1}})
    assert info.value.kind is ProviderErrorKind.MALFORMED


# --- parsing -------------------------------------------------------------


def test_live_shaped_artist_parses_affinity_explainability_and_types():
    parsed = parse_entity(artist("a1", "Kavinsky", 0.93, [("m1", 1), ("m2", 0.4)]))
    assert parsed.affinity == 0.93
    assert parsed.explained_by == (("m1", 1.0), ("m2", 0.4))
    assert "urn:entity:artist" in parsed.types


def test_insights_drop_entities_that_are_not_artists():
    payload = insights_payload(
        artist("a1", "M83"),
        entity("p1", "A Podcast", "urn:entity:podcast"),
        {"entity_id": "x", "name": "Untyped"},
    )
    client = responding(200, json=payload)
    assert [e.name for e in client.artist_insights(["m1"], take=5)] == ["M83"]


def test_bad_entities_are_skipped_and_affinity_read_only_when_numeric():
    entities = parse_insights(
        insights_payload(
            {"name": "No id"},
            {"entity_id": "x", "name": "  "},
            "junk",
            entity("a1", "Kavinsky", affinity=0.91),
            entity("a2", "M83", affinity="high"),
            entity("a3", "Tycho", affinity=True),
        )
    )
    assert [(e.name, e.affinity) for e in entities] == [
        ("Kavinsky", 0.91), ("M83", None), ("Tycho", None),
    ]  # fmt: skip


def test_entity_types_from_types_type_and_subtype():
    item = {"entity_id": "m", "name": "Drive", "type": "urn:entity",
            "subtype": "urn:entity:movie"}  # fmt: skip
    assert parse_entity(item).types == ("urn:entity", "urn:entity:movie")


# --- provider ------------------------------------------------------------


class FakeClient:
    """Records calls; serves fixed search and insight results."""

    def __init__(self, search=None, artists=None, error=None):
        self.searches = search or {}
        self.artists = artists or {}
        self.error = error
        self.calls: list[tuple] = []

    def search(self, query, types, take=5):
        self.calls.append(("search", query, tuple(types)))
        if self.error:
            raise self.error
        return self.searches.get(query, [])

    def artist_insights(self, entity_ids, take):
        self.calls.append(("insights", tuple(entity_ids), take))
        return self.artists.get(entity_ids[0], [])[:take]


def provider(client) -> QlooProvider:
    return QlooProvider(client, [DRIVE, JOURNEY, ACADEMIA])


MOVIE, GAME = "urn:entity:movie", "urn:entity:videogame"


def test_resolution_prefers_the_most_popular_exact_match():
    client = FakeClient(
        search={"Drive": [QlooEntity("old", "Drive", (MOVIE,), popularity=0.6),
                          QlooEntity("x", "Drive Angry", (MOVIE,), popularity=0.99),
                          QlooEntity("m1", "Drive", (MOVIE,), popularity=0.98)]}
    )  # fmt: skip
    assert provider(client).resolve(DRIVE).entity_id == "m1"


def test_fuzzy_search_results_without_an_exact_name_are_unresolved():
    client = FakeClient(
        search={"Journey": [QlooEntity("g9", "Journey to the End", (GAME,))]}
    )
    assert provider(client).resolve(JOURNEY) is None


def test_resolution_requires_exact_name_and_matching_type():
    client = FakeClient(
        search={
            "Drive": [QlooEntity("x", "Drive My Car", (MOVIE,)),
                      QlooEntity("m1", "drive", (MOVIE,))],
            "Journey": [QlooEntity("band", "Journey", ("urn:entity:artist",))],
        }
    )  # fmt: skip
    p = provider(client)
    assert p.resolve(DRIVE).entity_id == "m1"
    assert p.resolve(JOURNEY) is None  # the band, not the game
    assert p.resolve(ACADEMIA) is None  # aesthetics have no Qloo type
    assert all(call[1] != "Dark academia" for call in client.calls)
    p.resolve(DRIVE)
    assert sum(c[0] == "search" for c in client.calls) == 2  # cached


def test_recommend_round_robin_credits_and_scores():
    client = FakeClient(
        search={"Drive": [QlooEntity("m1", "Drive", (MOVIE,))],
                "Journey": [QlooEntity("g1", "Journey", (GAME,))]},
        artists={
            "m1": [QlooEntity("a1", "Kavinsky", (), 0.9),
                   QlooEntity("a2", "Shared", (), 0.8)],
            "g1": [QlooEntity("a3", "Austin Wintory", (), 0.7),
                   QlooEntity("a2", "Shared", (), 0.6)],
        },
    )  # fmt: skip
    result = provider(client).recommend(["drive", "journey", "dark-academia"], 8)

    assert [p.artist for p in result.picks] == ["Kavinsky", "Austin Wintory", "Shared"]
    assert result.unresolved == (ACADEMIA,)
    kavinsky, _, shared = result.picks
    assert (kavinsky.score, kavinsky.score_kind) == (0.9, "qloo_affinity")
    assert kavinsky.interests == (DRIVE,)
    assert kavinsky.external_id == "a1"
    assert shared.interests == (DRIVE, JOURNEY)
    assert shared.score is None  # two queries, two affinities: none shown
    assert all(p.source == "qloo" for p in result.picks)
    # Provenance: the Qloo entity each interest resolved to, and rank there.
    assert [(e.signal_id, e.rank, e.affinity) for e in kavinsky.evidence] == [
        ("m1", 1, 0.9)
    ]
    assert [(e.interest, e.signal_id, e.rank, e.affinity) for e in shared.evidence] == [
        (DRIVE, "m1", 2, 0.8), (JOURNEY, "g1", 2, 0.6),
    ]  # fmt: skip


def test_duplicate_artists_merge_by_entity_id_and_by_name():
    client = FakeClient(
        search={"Drive": [QlooEntity("m1", "Drive", (MOVIE,))],
                "Journey": [QlooEntity("g1", "Journey", (GAME,))]},
        artists={
            "m1": [QlooEntity("a1", "Ólafur Arnalds"),
                   QlooEntity("a1", "Olafur Arnalds (dup row)"),
                   QlooEntity("a2", "M83")],
            "g1": [QlooEntity("a9", "olafur arnalds"),
                   QlooEntity("a2", "M83")],
        },
    )  # fmt: skip
    result = provider(client).recommend(["drive", "journey"], 8)
    assert [p.artist for p in result.picks] == ["Ólafur Arnalds", "M83"]
    assert all(p.interests == (DRIVE, JOURNEY) for p in result.picks)
    assert [e.rank for e in result.picks[0].evidence] == [1, 1]


def test_explained_share_is_kept_for_the_signal_entity():
    client = FakeClient(
        search={"Drive": [QlooEntity("m1", "Drive", (MOVIE,))]},
        artists={"m1": [QlooEntity("a1", "Kavinsky", (), 0.9,
                                   explained_by=(("m1", 1.0),))]},
    )  # fmt: skip
    (pick,) = provider(client).recommend(["drive"], 8).picks
    assert pick.evidence[0].explained_share == 1.0


def test_resolved_interest_with_no_artists_gives_an_empty_answer():
    client = FakeClient(search={"Drive": [QlooEntity("m1", "Drive", (MOVIE,))]})
    result = provider(client).recommend(["drive"], 8)
    assert result.picks == () and result.unresolved == ()


def test_max_artists_limits_picks_and_take():
    artists = [QlooEntity(f"a{n}", f"Artist {n}") for n in range(10)]
    client = FakeClient(search={"Drive": [QlooEntity("m1", "Drive", (MOVIE,))]},
                        artists={"m1": artists})  # fmt: skip
    result = provider(client).recommend(["drive"], 3)
    assert len(result.picks) == 3
    assert ("insights", ("m1",), 3) in client.calls


def test_nothing_resolved_is_an_empty_answer_not_an_error():
    result = provider(FakeClient()).recommend(["drive", "dark-academia"], 8)
    assert result.picks == ()
    assert result.unresolved == (DRIVE, ACADEMIA)


def test_unknown_interest_is_invalid_input():
    with pytest.raises(InvalidSelection):
        provider(FakeClient()).recommend(["nope"], 8)


def test_provider_errors_propagate_and_are_not_cached():
    error = RecommendationError(ProviderErrorKind.RATE_LIMIT, "Qloo: 429")
    client = FakeClient(error=error)
    p = provider(client)
    with pytest.raises(RecommendationError):
        p.recommend(["drive"], 8)
    client.error = None
    assert p.recommend(["drive"], 8).unresolved == (DRIVE,)
