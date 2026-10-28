"""Bounded Gemini function-calling host for the existing Qloo Culture Radio engine.

Uses the Gemini REST API through httpx, already a project dependency. Gemini
chooses tools; CrossSignal executes only the declared, validated operations.
No fabricated artist/track results and no API credential in browser responses.
"""

import os
from collections.abc import Callable
from typing import Any

import httpx

from crosssignal import culture, genres
from crosssignal.engine import Engine, Feedback, Signal
from crosssignal.ranking import DISCOVERY_MODES, ERAS, Preferences

MODEL = "gemini-3.8-flash"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_MODEL_TURNS = 5
MAX_TOOLS = 7

TOOLS = [
    {
        "name": "find_interest",
        "description": "Search Qloo for a film, TV series, game, book, creator, brand, place or aesthetic named by the listener. Only a single exact match is added to their profile; ambiguous matches require their choice.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Actual title or cultural name to look up"},
                "category": {"type": "STRING", "description": "Optional: screen, games, books, people, podcasts, brands, places, aesthetics"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "set_music_preferences",
        "description": "Set musical preferences to guide Qloo. Use only genre IDs and era IDs from the system instruction. Fields omitted are kept unchanged. The arrays provided replace the corresponding previous arrays.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "preferred": {"type": "ARRAY", "items": {"type": "STRING"}},
                "open_to": {"type": "ARRAY", "items": {"type": "STRING"}},
                "avoided": {"type": "ARRAY", "items": {"type": "STRING"}},
                "eras": {"type": "ARRAY", "items": {"type": "STRING"}},
                "discovery": {"type": "STRING", "enum": ["familiar", "balanced", "adventurous"]},
            },
        },
    },
    {
        "name": "tune_radio",
        "description": "Run the real Qloo Insights artist discovery and Apple iTunes track verification. Call this after finding interests and applying music preferences, unless the user only asked a question. Use a later page when they request another mix.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"page": {"type": "INTEGER", "description": "Qloo result page 1 through 20"}},
        },
    },
]


class AgentUnavailable(Exception):
    """A failed Gemini model request; no demo results should be substituted."""


def _genre_map() -> dict[str, str]:
    return {g.id: g.label for g in genres.GENRES}


def agent_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def run_agent(
    qloo: Any,
    engine: Engine,
    message: str,
    signals: list[Signal],
    prefs: Preferences,
    feedback: Feedback,
    history: list[dict[str, str]] | None = None,
    seen: list[str] | None = None,
    default_page: int = 1,
    *,
    generate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute model-selected tools against real CrossSignal services.

    `generate` is injectable for offline tests; production calls Gemini HTTP.
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and generate is None:
        raise AgentUnavailable("The AI Radio Host isn't configured on this server.")

    genre_labels = _genre_map()
    system = (
        "You are CrossSignal's concise, grounded music-radio assistant. "
        "You operate tools; do not invent Qloo artists, entity IDs, tracks, matches or tool outcomes. "
        "When the listener names films, games, books or other cultural references, you MUST call find_interest for each title. This is how you get real Qloo IDs without making the listener use the manual picker. "
        "Only a unique exact Qloo match is added; for ambiguous names ask them to clarify. "
        "When the listener requests music recommendations, first resolve their cultural references and apply any music preferences, then call tune_radio yourself and present the results in the existing radio cards. Do not ask the listener to select anything manually unless Qloo returns ambiguous matches. If no cultural interest can be identified, ask for one. "
        "Call set_music_preferences for specified genres/eras/discovery; otherwise keep the existing choices. "
        "Be natural, not promotional. Say when a match cannot be verified. "
        "For a request to try again, tune a later page, keeping the user's existing choices. "
        "Genre IDs (use these exactly, not arbitrary text): "
        + ", ".join(f"{k}={v}" for k, v in genre_labels.items())
        + ". Era IDs: " + ", ".join(ERAS)
        + ". Always describe only the actions actually executed. Keep the final response to 1-3 sentences."
    )

    state_signals = list(dict.fromkeys(signals))[:5]
    state_prefs = {
        "preferred": list(prefs.preferred),
        "open_to": list(prefs.open_to),
        "avoided": list(prefs.avoided),
        "eras": list(prefs.eras),
        "discovery": prefs.discovery,
    }
    trace: list[str] = []
    result = None
    result_page = default_page
    tool_count = 0

    def find_interest(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()[:120]
        category = args.get("category")
        if not query:
            return {"error": "Name required"}
        if category not in culture.CATEGORY_BY_ID:
            category = None
        match = culture.resolve(qloo, query, category, 6)
        options = [{"name": c.name, "category": c.category, "year": c.year, "type": c.type_label}
                   for c in match.candidates[:4]]
        if match.match == culture.Match.EXACT and len(state_signals) < 5:
            c = match.candidates[0]
            if not any(s.id == c.id for s in state_signals):
                state_signals.append(Signal(c.id, c.kind, c.name, c.category, c.qloo_type))
            trace.append(f"Qloo confirmed: {c.name}")
            return {"match": "exact", "added": c.name, "options": options}
        trace.append(f"Qloo searched: {query} ({match.match.value})")
        return {"match": match.match.value, "added": None, "options": options,
                "note": "Ask the listener to clarify or select one in the main interface."}

    def set_music(args: dict[str, Any]) -> dict[str, Any]:
        valid = set(genre_labels)
        updated = dict(state_prefs)
        for field in ("preferred", "open_to", "avoided"):
            if field in args:
                value = args[field]
                if not isinstance(value, list) or any(v not in valid for v in value):
                    return {"error": f"Unknown {field} genre ID; use documented genre IDs"}
                updated[field] = list(dict.fromkeys(value))[:30]
        if "eras" in args:
            value = args["eras"]
            if not isinstance(value, list) or any(v not in ERAS for v in value):
                return {"error": "Unknown era ID"}
            updated["eras"] = list(dict.fromkeys(value))
        if "discovery" in args:
            if args["discovery"] not in DISCOVERY_MODES:
                return {"error": "Unknown discovery mode"}
            updated["discovery"] = args["discovery"]
        # Explicit avoid takes precedence; avoid overlaps that the engine rejects.
        updated["preferred"] = [g for g in updated["preferred"] if g not in updated["avoided"]]
        updated["open_to"] = [g for g in updated["open_to"] if g not in updated["avoided"] and g not in updated["preferred"]]
        state_prefs.update(updated)
        trace.append("Applied music preferences")
        return {"preferences": state_prefs}

    def tune(args: dict[str, Any]) -> dict[str, Any]:
        nonlocal result, result_page
        page = args.get("page", default_page)
        if not isinstance(page, int) or not 1 <= page <= 20:
            return {"error": "Page must be 1 through 20"}
        if not any(s.kind == culture.Kind.ENTITY for s in state_signals) and not feedback.liked:
            return {"error": "No confirmed cultural interests; find an exact match first"}
        p = Preferences(
            preferred=tuple(state_prefs["preferred"]),
            open_to=tuple(state_prefs["open_to"]),
            avoided=tuple(state_prefs["avoided"]),
            eras=tuple(state_prefs["eras"]),
            discovery=state_prefs["discovery"],
        )
        result = engine.discover(
            state_signals, p, feedback, page=page, exclude_artists=(seen or [])[:160]
        )
        result_page = page
        names = [artist.candidate.name for artist in result.picks]
        trace.append(f"Qloo page {page}; verified {len(names)} artists with Apple Music")
        return {"page": page, "status": result.status.value, "artists": names,
                "catalog_checks": result.tally.lookups,
                "notes": result.notices[:2]}

    def call_model(payload: dict[str, Any]) -> dict[str, Any]:
        if generate is not None:
            return generate(payload)
        model = os.getenv("CROSSSIGNAL_AGENT_MODEL", MODEL).strip() or MODEL
        try:
            with httpx.Client(timeout=24) as client:
                response = client.post(
                    f"{ENDPOINT}{model}:generateContent",
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                reason = "Gemini rejected the server API key. Check GEMINI_API_KEY on Render."
            elif status == 404:
                reason = f"Gemini model {model} is unavailable to this API project (404). Check its model access."
            elif status == 400:
                reason = "Gemini rejected the model request (400). Check the deployment/model configuration."
            elif status == 429:
                reason = "Gemini quota or rate limit reached (429). Try a model available on your AI Studio free tier."
            elif status in (500, 502, 503, 504):
                reason = f"Gemini is temporarily overloaded (HTTP {status}). Try again shortly."
            else:
                reason = f"Gemini API returned HTTP {status}."
            raise AgentUnavailable(reason) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AgentUnavailable("Couldn't reach the Gemini API. Try again shortly.") from exc

    contents: list[dict[str, Any]] = []
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        text = turn.get("content", "")
        if role in ("user", "model") and isinstance(text, str) and text.strip():
            contents.append({"role": role, "parts": [{"text": text[:900]}]})
    contents.append({
        "role": "user",
        "parts": [{"text": (
            f"Current confirmed interests: {[s.name for s in state_signals]}. "
            f"Current preferences: {state_prefs}. Current result page: {default_page}. "
            f"Listener's request: {message[:600]}"
        )}],
    })
    reply = ""
    for _ in range(MAX_MODEL_TURNS):
        response = call_model({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": TOOLS}],
            "generationConfig": {"maxOutputTokens": 2400, "thinkingConfig": {"thinkingLevel": "LOW"}},
        })
        candidates = response.get("candidates") or []
        if not candidates:
            raise AgentUnavailable("Gemini returned no usable response.")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        # Preserve model thought signatures by replaying all parts unchanged.
        calls = [p["functionCall"] for p in parts if isinstance(p, dict) and "functionCall" in p]
        if not calls:
            reply = " ".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            break
        contents.append({"role": "model", "parts": parts})
        function_responses: list[dict[str, Any]] = []
        for function_call in calls[:MAX_TOOLS - tool_count]:
            name = function_call.get("name")
            args = function_call.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            if name == "find_interest":
                output = find_interest(args)
            elif name == "set_music_preferences":
                output = set_music(args)
            elif name == "tune_radio":
                output = tune(args)
            else:
                output = {"error": "Unknown function"}
            function_response = {"name": name, "response": {"result": output}}
            # Gemini 3.x needs the exact function-call ID when provided.
            if function_call.get("id"):
                function_response["id"] = function_call["id"]
            function_responses.append({"functionResponse": function_response})
            tool_count += 1
        if function_responses:
            contents.append({"role": "user", "parts": function_responses})
        if tool_count >= MAX_TOOLS:
            break

    if not reply:
        reply = (
            f"Found {len(result.picks)} artists from Qloo and checked their tracks."
            if result is not None else
            "I've checked the available matches. You can adjust the request or try again."
        )
    return {
        "reply": reply[:1400], "trace": trace,
        "signals": state_signals, "preferences": state_prefs,
        "result": result, "page": result_page,
    }
