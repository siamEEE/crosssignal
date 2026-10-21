"""Explicitly invoked live check of the Qloo hackathon API.

    uv run --env-file .env python -m crosssignal.qloo_smoke
    uv run --env-file .env python -m crosssignal.qloo_smoke \\
        --query "Hollow Knight" --type urn:entity:video_game

Makes two calls: GET /search for one title, then GET /v2/insights for
artists with that entity as the signal and feature.explainability=true.
Prints status codes, field names and value *types*, plus entity names and
ids. It never prints the API key or raw response bodies.
"""

import argparse

import httpx

from crosssignal.config import load_settings
from crosssignal.qloo import ARTIST_TYPE, CATEGORY_TYPES


def shape(value: object, depth: int = 0, max_depth: int = 3) -> str:
    """Field names and value types only, never the values themselves."""
    if isinstance(value, dict):
        if depth >= max_depth:
            return "{...}"
        inner = ", ".join(
            f"{k}: {shape(v, depth + 1, max_depth)}" for k, v in value.items()
        )
        return "{" + inner + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        return f"[{len(value)} x {shape(value[0], depth + 1, max_depth)}]"
    return type(value).__name__


def _error_hint(response: httpx.Response, secret: str) -> str:
    """The API's own short error message, with the key redacted just in case."""
    try:
        body = response.json()
    except ValueError:
        return "(non-JSON body)"
    if not isinstance(body, dict):
        return shape(body)
    text = next((str(body[k]) for k in ("message", "error", "reason") if k in body), "")
    return text.replace(secret, "***")[:160] or shape(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m crosssignal.qloo_smoke")
    parser.add_argument("--query", default="Interstellar")
    parser.add_argument("--type", default=CATEGORY_TYPES["Films"])
    parser.add_argument("--take", type=int, default=5)
    args = parser.parse_args(argv)

    settings = load_settings().qloo
    if not settings.configured:
        print("QLOO_API_KEY is not set. Nothing was sent.")
        return 2
    secret = settings.api_key.reveal()
    print(f"Host: {settings.base_url}  (key: set, value hidden)")
    headers = {"X-Api-Key": secret, "Accept": "application/json"}

    with httpx.Client(timeout=settings.timeout, headers=headers) as http:
        search = http.get(
            f"{settings.base_url}/search",
            params={"query": args.query, "types": args.type, "take": args.take},
        )
        print(
            f"\nGET /search query={args.query!r} types={args.type} -> {search.status_code}"
        )
        if not search.is_success:
            print(f"Stopping: {_error_hint(search, secret)}")
            return 1
        payload = search.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        top = (
            {k: v for k, v in payload.items() if k != "results"}
            if isinstance(payload, dict)
            else payload
        )
        print(f"top-level (excluding results): {shape(top)}")
        if not isinstance(results, list) or not results:
            print("No search results; cannot test insights.")
            return 1
        print(f"result count: {len(results)}")
        print(f"first result shape: {shape(results[0], max_depth=2)}")
        for item in results:
            if isinstance(item, dict):
                print(f"  - {item.get('name')!r} id={item.get('entity_id')} "
                      f"types={item.get('types')} subtype={item.get('subtype')}")  # fmt: skip
        first = results[0]

        insights = http.get(
            f"{settings.base_url}/v2/insights",
            params={
                "filter.type": ARTIST_TYPE,
                "signal.interests.entities": first.get("entity_id"),
                "feature.explainability": "true",
                "take": args.take,
            },
        )
        print(
            f"\nGET /v2/insights (signal: {first.get('name')!r}) -> {insights.status_code}"
        )
        if not insights.is_success:
            print(f"Stopping: {_error_hint(insights, secret)}")
            return 1
        body = insights.json()
        if not isinstance(body, dict):
            print(f"Body is not an object: {shape(body)}")
            return 1
        results_obj = body.get("results")
        entities = (
            results_obj.get("entities") if isinstance(results_obj, dict) else None
        )
        print(f"top-level keys: {sorted(body)}")
        if isinstance(results_obj, dict):
            print(f"results keys: {sorted(results_obj)}")
            for key, value in results_obj.items():
                if key != "entities":
                    print(f"results.{key}: {shape(value)}")
        if "query" in body:
            print(f"top-level query: {shape(body['query'], max_depth=4)}")
        if not isinstance(entities, list) or not entities:
            print("No artist entities returned.")
            return 1
        print(f"entity count: {len(entities)}")
        print(f"first entity keys: {sorted(entities[0])}")
        for entity in entities:
            query = entity.get("query") if isinstance(entity, dict) else None
            print(f"  - {entity.get('name')!r} id={entity.get('entity_id')} "
                  f"type={entity.get('type')} subtype={entity.get('subtype')}")  # fmt: skip
            print(f"    query: {shape(query, max_depth=4)}")
            if isinstance(query, dict):
                affinity = query.get("affinity")
                print(f"    query.affinity type={type(affinity).__name__} "
                      f"in [0,1]: {isinstance(affinity, float) and 0 <= affinity <= 1}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
