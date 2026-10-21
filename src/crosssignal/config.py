"""Configuration from environment variables.

    CROSSSIGNAL_PROVIDER  "curated" (default) or "qloo"
    QLOO_API_KEY          Qloo key; never logged, printed or rendered
    QLOO_API_URL          base URL (default https://hackathon.api.qloo.com,
                          the only host hackathon keys work on). Override
                          only if your key was issued for another host.
    QLOO_TIMEOUT_SECONDS  per-request timeout (default 10)

The key is wrapped in Secret so an accidental print, f-string, log line
or Streamlit render shows a mask instead of the value.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_QLOO_URL = "https://hackathon.api.qloo.com"
DEFAULT_TIMEOUT = 10.0
PROVIDERS = ("curated", "qloo")


class ConfigError(ValueError):
    """Configuration is present but unusable. Messages never include secrets."""


class Secret:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """The raw value. Call only where it is sent to the API."""
        return self._value

    def __repr__(self) -> str:
        return "Secret('********')"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True)
class QlooSettings:
    api_key: Secret | None
    base_url: str = DEFAULT_QLOO_URL
    timeout: float = DEFAULT_TIMEOUT

    @property
    def configured(self) -> bool:
        return self.api_key is not None


@dataclass(frozen=True)
class Settings:
    provider: str
    qloo: QlooSettings


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env

    provider = env.get("CROSSSIGNAL_PROVIDER", "curated").strip().lower() or "curated"
    if provider not in PROVIDERS:
        raise ConfigError(f"CROSSSIGNAL_PROVIDER must be one of {PROVIDERS}")

    key = env.get("QLOO_API_KEY", "").strip()
    base_url = env.get("QLOO_API_URL", "").strip().rstrip("/") or DEFAULT_QLOO_URL
    if not base_url.startswith("https://"):
        raise ConfigError("QLOO_API_URL must start with https://")

    raw_timeout = env.get("QLOO_TIMEOUT_SECONDS", "").strip()
    try:
        timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT
    except ValueError as exc:
        raise ConfigError("QLOO_TIMEOUT_SECONDS must be a number") from exc
    if not 0 < timeout <= 60:
        raise ConfigError("QLOO_TIMEOUT_SECONDS must be between 0 and 60")

    qloo = QlooSettings(Secret(key) if key else None, base_url, timeout)
    if provider == "qloo" and not qloo.configured:
        raise ConfigError("CROSSSIGNAL_PROVIDER=qloo requires QLOO_API_KEY")
    return Settings(provider, qloo)
