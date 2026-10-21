"""Choose the recommendation provider from configuration."""

from crosssignal.config import Settings
from crosssignal.qloo import QlooClient, QlooProvider
from crosssignal.recommendations import CuratedProvider, RecommendationProvider


def build_provider(settings: Settings) -> RecommendationProvider:
    """Curated demo data by default; Qloo when configured to use it.

    Qloo uses the same picker interests as the demo, so the UI offers the
    same choices whichever source answers.
    """
    curated = CuratedProvider()
    if settings.provider == "qloo":
        return QlooProvider(QlooClient(settings.qloo), curated.interests())
    return curated
