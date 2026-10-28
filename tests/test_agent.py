"""Offline, provider-free checks of real Gemini-selected tool execution."""

from types import SimpleNamespace

import pytest

from crosssignal.agent import AgentUnavailable, run_agent
from crosssignal.engine import NO_FEEDBACK, Signal
from crosssignal.culture import Kind
from crosssignal.ranking import Preferences


def test_agent_invokes_qloo_discovery_tool_and_returns_real_result():
    calls = []
    responses = iter([
        {"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "tune_radio", "args": {"page": 2}}}
        ]}}]},
        {"candidates": [{"content": {"role": "model", "parts": [
            {"text": "Here are some more artists to try."}
        ]}}]},
    ])

    def generate(payload):
        calls.append(payload)
        return next(responses)

    class Engine:
        def discover(self, signals, prefs, feedback, page, exclude_artists):
            assert len(signals) == 1
            assert page == 2
            assert exclude_artists == ["already-seen"]
            return SimpleNamespace(
                status=SimpleNamespace(value="ok"),
                picks=[SimpleNamespace(candidate=SimpleNamespace(name="Sample Artist"))],
                tally=SimpleNamespace(lookups=1),
                notices=[],
            )

    result = run_agent(
        qloo=object(),
        engine=Engine(),
        message="Try another mix",
        signals=[Signal("urn:entity:movie:123", Kind.ENTITY, "Arrival", "screen", "urn:entity:movie")],
        prefs=Preferences(),
        feedback=NO_FEEDBACK,
        seen=["already-seen"],
        generate=generate,
    )
    assert len(calls) == 2
    assert result["result"] is not None
    assert result["page"] == 2
    assert "Qloo page 2" in result["trace"][0]
    assert "more artists" in result["reply"]


def test_agent_without_model_key_does_not_fabricate_results(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AgentUnavailable):
        run_agent(
            qloo=object(),
            engine=object(),
            message="Give me some songs",
            signals=[], prefs=Preferences(), feedback=NO_FEEDBACK,
        )
