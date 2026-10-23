"""FastAPI boundary tests with synthetic Qloo/catalog fakes (no network)."""

import pytest
from fakes import FakeCatalog, FakeQloo, artist, song, tag, title
from fastapi.testclient import TestClient

from crosssignal.api import CachedQloo, Services, TTLCache, create_app
from crosssignal.engine import Engine
from crosssignal.models import ProviderErrorKind, RecommendationError

MOVIE = "urn:entity:movie"
FILM = {"id": "m1", "kind": "entity", "name": "Neon Film", "category": "screen",
        "qloo_type": MOVIE}  # fmt: skip


def make_client(qloo=None, catalog=None):
    qloo = qloo or FakeQloo(
        searches={"Neon Film": [title("m1", "Neon Film", MOVIE, 2017)],
                  "Drive": [title("d1", "Drive", MOVIE, 2011, 0.9),
                            title("d2", "Drive", MOVIE, 1997, 0.8)]},
        tags={"rainy": [tag("urn:tag:ambience:qloo:rainy", "Rainy")]},
        insights={"m1": [artist(f"a{i}", f"Band {i}", "metal") for i in range(4)]},
    )  # fmt: skip
    catalog = catalog or FakeCatalog(
        {f"Band {i}": [song(f"Band {i}", f"Song {i}{k}") for k in range(3)]
         for i in range(4)}
    )  # fmt: skip
    return TestClient(create_app(Services(qloo, Engine(qloo, catalog, workers=2))))


def unconfigured():
    return TestClient(create_app(Services(None, None, "QLOO_API_KEY is not set")))


def test_health_reports_configuration_without_values():
    assert make_client().get("/api/health").json()["qloo_configured"] is True
    body = unconfigured().get("/api/health").json()
    assert body["qloo_configured"] is False
    assert body["config_problem"] == "QLOO_API_KEY is not set"


def test_multi_era_api_and_legacy_compatibility():
    client = make_client()
    body = {"signals": [FILM], "preferences": {"eras": ["1980s", "2000s", "2010s"]}}
    response = client.post("/api/discover", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["preferences"]["eras"] == ["1980s", "2000s", "2010s"]
    assert result["artists"] and result["artists"][0]["era"]["in_era"] == 3
    legacy = client.post("/api/discover", json={"signals": [FILM], "preferences": {"era": "2010s"}})
    assert legacy.json()["preferences"]["eras"] == ["2010s"]
    assert legacy.json()["preferences"]["era"] == "2010s"
    cleared = client.post("/api/discover", json={"signals": [FILM], "preferences": {"era": "2010s", "eras": []}})
    assert cleared.json()["preferences"]["eras"] == []
    invalid = client.post("/api/discover", json={"signals": [FILM], "preferences": {"eras": ["1890s"]}})
    assert invalid.status_code == 422


def test_reroll_exclusions_are_bounded_and_respected():
    client = make_client()
    first = client.post("/api/discover", json={"signals": [FILM]}).json()
    ids = [a["id"] for a in first["artists"]]
    next_result = client.post("/api/discover", json={"signals": [FILM], "page": 2, "exclude_artists": ids}).json()
    assert next_result["page"] == 2
    assert next_result["artists"] == []
    assert next_result["status"] == "empty"
    too_many = client.post("/api/discover", json={"signals": [FILM], "exclude_artists": ["x"] * 161})
    assert too_many.status_code == 422


def test_request_limits_reject_large_bodies_and_keep_valid_json_working():
    client = make_client()
    assert client.post("/api/discover", json={"signals": [FILM]}).status_code == 200
    response = client.post("/api/interpret", content=b"x" * 32769)
    assert response.status_code == 413
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"


def test_expensive_endpoints_have_a_shared_process_budget():
    client = make_client()
    for _ in range(60):
        assert client.get("/api/search", params={"q": "Drive"}).status_code == 200
    assert client.post("/api/interpret", json={"text": "Drive"}).status_code == 429
    assert client.get("/api/health").status_code == 200


def test_cross_origin_work_is_rejected_before_provider_calls():
    client = make_client()
    assert client.post("/api/discover", json={"signals": [FILM]},
                       headers={"Origin": "https://other.example"}).status_code == 403
    assert client.post("/api/discover", json={"signals": [FILM]},
                       headers={"Origin": "http://testserver"}).status_code == 200


def test_static_reference_endpoints():
    client = make_client()
    categories = {c["id"]: c["kind"] for c in client.get("/api/categories").json()}
    assert categories["aesthetics"] == "tag" and categories["books"] == "entity"
    options = client.get("/api/genres").json()
    assert {"metal", "rock", "pop"} <= {g["id"] for g in options["genres"]}
    assert options["eras"][-1] == "recent"
    assert options["limits"] == {"signals": 5, "liked": 3}
    assert all(c["items"] for c in client.get("/api/featured").json())


def test_search_returns_resolution_status_and_candidates():
    body = (
        make_client()
        .get("/api/search", params={"q": "Drive", "category": "screen"})
        .json()
    )
    assert body["match"] == "ambiguous"
    assert [(c["id"], c["year"]) for c in body["candidates"]] == [
        ("d1", 2011),
        ("d2", 1997),
    ]
    tags = make_client().get(
        "/api/search", params={"q": "rainy", "category": "aesthetics"}
    )
    assert tags.json()["candidates"][0]["kind"] == "tag"


def test_live_endpoints_say_clearly_when_qloo_is_not_configured():
    client = unconfigured()
    response = client.get("/api/search", params={"q": "Drive"})
    assert response.status_code == 503
    assert response.json()["error"]["kind"] == "not_configured"
    assert client.post("/api/discover", json={"signals": [FILM]}).status_code == 503
    # Reference data still works for the UI shell.
    assert client.get("/api/genres").status_code == 200


def test_discover_returns_grounded_artist_cards():
    response = make_client().post("/api/discover", json={
        "signals": [FILM], "preferences": {"preferred": ["metal"]},
    })  # fmt: skip
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    first = body["artists"][0]
    assert first["genre"]["fit"] == "preferred" and first["genre"]["support"] == "both"
    assert first["genre"]["matched"] == [{"id": "metal", "label": "Metal"}]
    assert first["evidence"][0] == {
        "signal_id": "m1", "signal_name": "Neon Film", "category": "screen",
        "rank": 1, "affinity": 0.9, "explained_share": None,
    }  # fmt: skip
    assert first["tracks"][0]["preview_url"].startswith("https://")
    assert body["tally"]["qloo_candidates"] == 4


def test_invalid_requests_are_422_with_a_message():
    client = make_client()
    mood = {"id": "urn:tag:ambience:qloo:rainy", "kind": "tag", "name": "Rainy",
            "category": "aesthetics", "qloo_type": "urn:tag:ambience:qloo"}  # fmt: skip
    response = client.post("/api/discover", json={"signals": [mood]})
    assert response.status_code == 422
    assert "at least one title" in response.json()["error"]["message"]
    bad_genre = {"signals": [FILM], "preferences": {"preferred": ["yacht-rock"]}}
    assert client.post("/api/discover", json=bad_genre).status_code == 422
    too_many = {"signals": [FILM] * 6}
    assert client.post("/api/discover", json=too_many).status_code == 422


@pytest.mark.parametrize(
    ("kind", "status"),
    [(ProviderErrorKind.RATE_LIMIT, 429), (ProviderErrorKind.TIMEOUT, 504),
     (ProviderErrorKind.AUTH, 502), (ProviderErrorKind.UNAVAILABLE, 502)],
)  # fmt: skip
def test_upstream_errors_map_to_status_and_hide_details(kind, status):
    secret = "sk-should-never-leak"
    qloo = FakeQloo(error=RecommendationError(kind, f"Qloo: details {secret}"))
    response = make_client(qloo=qloo).post("/api/discover", json={"signals": [FILM]})
    assert response.status_code == status
    assert response.json()["error"]["kind"] == kind
    assert secret not in response.text


def test_interpret_resolves_each_phrase_but_confirms_nothing():
    body = make_client().post("/api/interpret", json={
        "text": "I love Drive and rainy vibes, mostly metal, no country",
    }).json()  # fmt: skip
    assert body["interpreter"] == "deterministic"
    assert body["music"]["preferred"] == ["metal"]
    assert body["music"]["avoided"] == ["country"]
    drive, rainy = body["mentions"]
    assert drive["resolution"]["match"] == "ambiguous"  # the user must choose
    assert rainy["phrase"] == "rainy"
    assert rainy["tag_candidates"][0]["name"] == "Rainy"


def test_cache_reuses_successes_and_never_caches_failures():
    calls = []

    class Flaky:
        def search(self, query, types, take=5):
            calls.append(query)
            if len(calls) == 1:
                raise RecommendationError(ProviderErrorKind.TIMEOUT, "slow")
            return [title("x", query, MOVIE)]

    cached = CachedQloo(Flaky())
    with pytest.raises(RecommendationError):
        cached.search("Drive", [MOVIE])
    assert cached.search("Drive", [MOVIE])[0].name == "Drive"
    assert cached.search("Drive", [MOVIE])[0].name == "Drive"
    assert len(calls) == 2


def test_ttl_cache_expires_and_is_bounded():
    cache = TTLCache(ttl=0, max_items=2)
    values = iter(range(10))
    assert cache.get_or_set("a", lambda: next(values)) == 0
    assert cache.get_or_set("a", lambda: next(values)) == 1  # expired at once
    bounded = TTLCache(ttl=60, max_items=2)
    for key in "abc":
        bounded.get_or_set(key, lambda: 1)
    assert len(bounded._items) == 2
