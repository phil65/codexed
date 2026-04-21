"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codexed.models import (
    MarketplaceAddParams,
    MarketplaceAddResponse,
    MarketplaceRemoveParams,
    MarketplaceRemoveResponse,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient

logger = logging.getLogger(__name__)


class CodexMarketPlace:
    def __init__(self, client: CodexClient):
        self._client = client

    async def add(
        self,
        source: str,
        ref_name: str | None = None,
        sparse_paths: list[str] | None = None,
    ) -> MarketplaceAddResponse:
        """Add a marketplace to the app-server."""
        params = MarketplaceAddParams(ref_name=ref_name, source=source, sparse_paths=sparse_paths)
        response = await self._client.dispatch.send_request("marketplace/add", params)
        return MarketplaceAddResponse.model_validate(response)

    async def remove(self, ref_name: str):
        """Remove a marketplace from the app-server."""
        params = MarketplaceRemoveParams(marketplace_name=ref_name)
        response = await self._client.dispatch.send_request("marketplace/remove", params)
        return MarketplaceRemoveResponse.model_validate(response)


if __name__ == "__main__":
    import asyncio

    from codexed.client import CodexClient

    async def main():
        client = CodexClient()
        async with client:
            _test = await client.marketplace.add("test")

    asyncio.run(main())
