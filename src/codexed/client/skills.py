"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codexed.models import (
    SkillsConfigWriteParams,
    SkillsListParams,
    SkillsListResponse,
    SkillsRemoteExportParams,
    SkillsRemoteExportResponse,
    SkillsRemoteListParams,
    SkillsRemoteListResponse,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models import (
        HazelnutScope,
        ProductSurface,
        RemoteSkillSummary,
        SkillMetadata,
    )

logger = logging.getLogger(__name__)


class CodexSkills:
    def __init__(self, client: CodexClient):
        self._client = client

    async def list_skills(
        self,
        *,
        cwds: list[str] | None = None,
        force_reload: bool | None = None,
    ) -> list[SkillMetadata]:
        """List available skills.

        Args:
            cwds: Optional working directories to scope skills
            force_reload: Force reload of skills cache

        Returns:
            List of skills with metadata
        """
        params = SkillsListParams(cwds=cwds, force_reload=force_reload)
        result = await self._client.dispatch.send_request("skills/list", params)
        response = SkillsListResponse.model_validate(result)
        if response.data:
            return response.data[0].skills
        return []

    async def config_write(self, path: str, *, enabled: bool) -> None:
        """Write skills configuration.

        Args:
            path: Path to the skill
            enabled: Whether the skill is enabled
        """
        params = SkillsConfigWriteParams(path=path, enabled=enabled)
        await self._client.dispatch.send_request("skills/config/write", params)

    async def remote_list(
        self,
        *,
        hazelnut_scope: HazelnutScope = "example",
        product_surface: ProductSurface = "codex",
        enabled: bool = False,
    ) -> list[RemoteSkillSummary]:
        """List remote skills.

        Args:
            hazelnut_scope: Scope filter (example/workspace-shared/all-shared/personal)
            product_surface: Product surface filter (chatgpt/codex/api/atlas)
            enabled: Whether to filter by enabled status

        Returns:
            List of remote skill summaries
        """
        params = SkillsRemoteListParams(
            hazelnut_scope=hazelnut_scope,
            product_surface=product_surface,
            enabled=enabled,
        )
        result = await self._client.dispatch.send_request("skills/remote/list", params)
        response = SkillsRemoteListResponse.model_validate(result)
        return response.data

    async def remote_export(self, hazelnut_id: str) -> SkillsRemoteExportResponse:
        """Export a skill to remote storage.

        Args:
            hazelnut_id: ID of the remote skill to export

        Returns:
            SkillsRemoteExportResponse with id and local path
        """
        params = SkillsRemoteExportParams(hazelnut_id=hazelnut_id)
        result = await self._client.dispatch.send_request("skills/remote/export", params)
        return SkillsRemoteExportResponse.model_validate(result)
