"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codexed.models import (
    PluginInstallParams,
    PluginInstallResponse,
    PluginListParams,
    PluginListResponse,
    PluginReadParams,
    PluginReadResponse,
    PluginUninstallParams,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient

logger = logging.getLogger(__name__)


class CodexPlugin:
    def __init__(self, client: CodexClient):
        self._client = client

    async def install(
        self,
        plugin_name: str,
        marketplace_path: str | None = None,
        remote_marketplace_name: str | None = None,
    ) -> PluginInstallResponse:
        """Install a plugin on the app-server."""
        params = PluginInstallParams(
            marketplace_path=marketplace_path,
            plugin_name=plugin_name,
            remote_marketplace_name=remote_marketplace_name,
        )
        response = await self._client.dispatch.send_request("plugin/install", params)
        return PluginInstallResponse.model_validate(response)

    async def uninstall(self, plugin_id: str) -> None:
        """Uninstall a plugin from the app-server."""
        params = PluginUninstallParams(plugin_id=plugin_id)
        await self._client.dispatch.send_request("plugin/uninstall", params)

    async def list(self, cwds: list[str] | None = None) -> PluginListResponse:
        params = PluginListParams(cwds=cwds)
        response = await self._client.dispatch.send_request("plugin/list", params)
        return PluginListResponse.model_validate(response)

    async def read(
        self,
        plugin_name: str,
        marketplace_path: str | None = None,
        remote_marketplace_name: str | None = None,
    ) -> PluginReadResponse:
        params = PluginReadParams(
            marketplace_path=marketplace_path,
            plugin_name=plugin_name,
            remote_marketplace_name=remote_marketplace_name,
        )
        response = await self._client.dispatch.send_request("plugin/read", params)
        return PluginReadResponse.model_validate(response)


if __name__ == "__main__":
    import asyncio

    from codexed.client import CodexClient

    async def main():
        client = CodexClient()
        async with client:
            response = await client.plugins.list()
            print(response)

    asyncio.run(main())
