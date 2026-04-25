"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codexed.models.v2_protocol import (
    DeviceKeyCreateParams,
    DeviceKeyCreateResponse,
    DeviceKeyPublicParams,
    DeviceKeyPublicResponse,
    DeviceKeySignParams,
    DeviceKeySignResponse,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models.v2_protocol import DeviceKeyProtectionPolicy, DeviceKeySignPayload

logger = logging.getLogger(__name__)


class CodexDevice:
    def __init__(self, client: CodexClient):
        self._client = client

    async def create_key(
        self,
        account_user_id: str,
        client_id: str,
        protection_policy: DeviceKeyProtectionPolicy | None = None,
    ) -> DeviceKeyCreateResponse:
        """Add a marketplace to the app-server."""
        params = DeviceKeyCreateParams(
            account_user_id=account_user_id,
            client_id=client_id,
            protection_policy=protection_policy,
        )
        response = await self._client.dispatch.send_request("device/key/create", params)
        return DeviceKeyCreateResponse.model_validate(response)

    async def public_key(self, key_id: str) -> DeviceKeyPublicResponse:
        """Get the public key for a device key."""
        params = DeviceKeyPublicParams(key_id=key_id)
        response = await self._client.dispatch.send_request("device/key/public", params=params)
        return DeviceKeyPublicResponse.model_validate(response)

    async def sign_key(self, key_id: str, payload: DeviceKeySignPayload) -> DeviceKeySignResponse:
        """Sign a key using the device key."""
        params = DeviceKeySignParams(key_id=key_id, payload=payload)
        response = await self._client.dispatch.send_request("device/key/sign", params=params)
        return DeviceKeySignResponse.model_validate(response)


if __name__ == "__main__":
    import asyncio

    from codexed.client import CodexClient

    async def main():
        client = CodexClient()
        async with client:
            _test = await client.marketplace.add("test")

    asyncio.run(main())
