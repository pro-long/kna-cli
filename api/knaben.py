"""
Knaben API v2 async client.
Docs: https://knaben.org/api/v2/
Base: https://api.knaben.org
"""

import httpx

BASE_URL = "https://api.knaben.org"

HEADERS = {
    "User-Agent": "KnaCLI/1.0 (Termux; Android)",
    "Accept": "application/json",
}


class KnabenClient:
    """
    Async HTTP client for the Knaben API v2.

    Endpoints used:
        GET /v2/search  — keyword search
        GET /v2/browse  — browse without keyword
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=HEADERS,
            timeout=15.0,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        category: str = "",
        tracker: str = "",
        sort: str = "seeders",
        direction: str = "desc",
        size: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Search torrents by keyword.

        Returns a dict with keys:
            hits  : list of torrent objects
            total : { "value": int, "relation": str }
        """
        params: dict = {
            "q": query,
            "o": sort,
            "d": direction,
            "s": size,
            "f": offset,
        }
        if category:
            params["c"] = category
        if tracker:
            params["t"] = tracker

        resp = await self._client.get("/v2/search", params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Browse
    # ------------------------------------------------------------------

    async def browse(
        self,
        category: str = "",
        sort: str = "date",
        direction: str = "desc",
        size: int = 50,
        offset: int = 0,
    ) -> dict:
        """Browse latest torrents without a search query."""
        params: dict = {
            "o": sort,
            "d": direction,
            "s": size,
            "f": offset,
        }
        if category:
            params["c"] = category

        resp = await self._client.get("/v2/browse", params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
