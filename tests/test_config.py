import pytest

from crosssignal.config import (
    DEFAULT_QLOO_URL,
    ConfigError,
    Secret,
    load_settings,
)

KEY = "sk-test-value"


def test_defaults_to_curated_without_a_key():
    settings = load_settings({})
    assert settings.provider == "curated"
    assert not settings.qloo.configured
    assert settings.qloo.base_url == DEFAULT_QLOO_URL


def test_qloo_settings_and_secret_masking():
    settings = load_settings(
        {
            "CROSSSIGNAL_PROVIDER": "QLOO",
            "QLOO_API_KEY": f"  {KEY} ",
            "QLOO_API_URL": "https://staging.api.qloo.com/",
            "QLOO_TIMEOUT_SECONDS": "4.5",
        }
    )
    assert settings.provider == "qloo"
    assert settings.qloo.api_key.reveal() == KEY
    assert settings.qloo.base_url == "https://staging.api.qloo.com"
    assert settings.qloo.timeout == 4.5
    # The value never appears in any string form of the settings.
    for text in (repr(settings), str(settings), f"{settings.qloo.api_key}"):
        assert KEY not in text


def test_secret_equality_does_not_need_reveal():
    assert Secret("a") == Secret("a") and Secret("a") != Secret("b")


@pytest.mark.parametrize(
    "env",
    [
        {"CROSSSIGNAL_PROVIDER": "spotify"},
        {"CROSSSIGNAL_PROVIDER": "qloo"},  # no key
        {"QLOO_API_URL": "http://api.qloo.com"},
        {"QLOO_TIMEOUT_SECONDS": "soon"},
        {"QLOO_TIMEOUT_SECONDS": "0"},
    ],
)
def test_invalid_configuration_raises_without_echoing_values(env):
    with pytest.raises(ConfigError) as info:
        load_settings({**env, "QLOO_API_KEY": env.get("QLOO_API_KEY", "")})
    assert KEY not in str(info.value)


def test_default_host_is_the_hackathon_api():
    assert DEFAULT_QLOO_URL == "https://hackathon.api.qloo.com"
