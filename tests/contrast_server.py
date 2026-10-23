"""Local browser fixture server. Synthetic data only; never a deployable app."""

import uvicorn
from fakes import FakeCatalog, FakeQloo, artist, song, title

from crosssignal.api import Services, create_app
from crosssignal.engine import Engine


class PagedFixture(FakeQloo):
    def artist_insights(self, entity_ids, take, **kwargs):
        page = kwargs.get("page", 1)
        self.insights[entity_ids[0]] = (
            [
                artist(f"test-artist-{i}", f"Synthetic browser fixture {i}", "metal")
                for i in range((page - 1) * 8, page * 8)
            ]
            if page <= 2
            else []
        )
        return super().artist_insights(entity_ids, take, **kwargs)


qloo = PagedFixture(
    searches={"Fixture Film": [title("test-film", "Fixture Film", "urn:entity:movie")]}
)
catalog = FakeCatalog(
    {
        f"Synthetic browser fixture {i}": [
            song(
                f"Synthetic browser fixture {i}",
                f"Fixture song {i}-{k}",
                year=str(year),
                url=f"https://music.apple.com/us/song/{900000000 + i * 10 + k}",
                preview=True,
            )
            for k, year in enumerate((1984, 2004, 2014))
        ]
        for i in range(16)
    }
)
if __name__ == "__main__":
    uvicorn.run(
        create_app(Services(qloo, Engine(qloo, catalog))), host="127.0.0.1", port=8012
    )
