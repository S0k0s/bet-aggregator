from abc import ABC, abstractmethod
import httpx
from bs4 import BeautifulSoup
from app.models.schemas import SourcePick


class BaseCollector(ABC):
    name: str
    base_url: str
    timeout: int = 15

    async def get_html(self, url: str) -> BeautifulSoup:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; BetAggregatorBot/1.0)"}
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")

    @abstractmethod
    async def fetch_picks(self) -> list[SourcePick]:
        raise NotImplementedError
