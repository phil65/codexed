"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from codexed.models import (
    CancelLoginAccountParams,
    CancelLoginAccountResponse,
    GetAccountParams,
    GetAccountRateLimitsResponse,
    GetAccountResponse,
    LoginAccountParams,
    LoginAccountResponse,
    SendAddCreditsNudgeEmailParams,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models import AddCreditsNudgeCreditType, AuthMode, CancelLoginAccountStatus

logger = logging.getLogger(__name__)


class CodexAccount:
    def __init__(self, client: CodexClient):
        self._client = client

    async def read(self, *, refresh_token: bool = False) -> GetAccountResponse:
        """Read account information.

        Args:
            refresh_token: When true, trigger a proactive token refresh

        Returns:
            GetAccountResponse with account info
        """
        params = GetAccountParams(refresh_token=refresh_token)
        result = await self._client.dispatch.send_request("account/read", params)
        return GetAccountResponse.model_validate(result)

    async def login_start(
        self,
        login_type: AuthMode,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        chatgpt_account_id: str | None = None,
    ) -> LoginAccountResponse:
        """Start account login.

        Args:
            login_type: Login type (apiKey, chatgpt, chatgptAuthTokens)
            api_key: API key (for apiKey type)
            access_token: Access token (for chatgptAuthTokens type)
            chatgpt_account_id: ChatGPT account ID (for chatgptAuthTokens type)

        Returns:
            LoginAccountResponse with login details
        """
        dct = dict(
            type=login_type,
            api_key=api_key,
            access_token=access_token,
            chatgpt_account_id=chatgpt_account_id,
        )
        params = TypeAdapter[LoginAccountParams](LoginAccountParams).validate_python(dct)
        result = await self._client.dispatch.send_request("account/login/start", params)
        return TypeAdapter[LoginAccountResponse](LoginAccountResponse).validate_python(result)

    async def login_cancel(self, login_id: str) -> CancelLoginAccountStatus:
        """Cancel an in-progress account login."""
        params = CancelLoginAccountParams(login_id=login_id)
        result = await self._client.dispatch.send_request("account/login/cancel", params)
        response = CancelLoginAccountResponse.model_validate(result)
        return response.status

    async def logout(self) -> None:
        """Logout from the current account."""
        await self._client.dispatch.send_request("account/logout")

    async def rate_limits_read(self) -> GetAccountRateLimitsResponse:
        """Read account rate limits."""
        result = await self._client.dispatch.send_request("account/rateLimits/read")
        return GetAccountRateLimitsResponse.model_validate(result)

    async def send_add_credits_nudge_email(self, credit_type: AddCreditsNudgeCreditType) -> None:
        """Send an add credits nudge email."""
        params = SendAddCreditsNudgeEmailParams(credit_type=credit_type)
        await self._client.dispatch.send_request("account/sendAddCreditsNudgeEmail", params)


if __name__ == "__main__":
    import asyncio

    from codexed.client import CodexClient

    async def main():
        client = CodexClient()
        async with client:
            response = await client.account.read()
            print(response)

    asyncio.run(main())
