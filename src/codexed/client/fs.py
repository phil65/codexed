"""Codex app-server client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from codexed.models import (
    FsCopyParams,
    FsCreateDirectoryParams,
    FsGetMetadataParams,
    FsGetMetadataResponse,
    FsReadDirectoryParams,
    FsReadDirectoryResponse,
    FsReadFileParams,
    FsReadFileResponse,
    FsRemoveParams,
    FsUnwatchParams,
    FsWatchParams,
    FsWatchResponse,
    FsWriteFileParams,
)


if TYPE_CHECKING:
    from codexed.client import CodexClient
    from codexed.models import FsReadDirectoryEntry

logger = logging.getLogger(__name__)


class CodexFS:
    def __init__(self, client: CodexClient):
        self._client = client

    async def read_file(self, path: str) -> FsReadFileResponse:
        """Read a file from the host filesystem.

        Args:
            path: Absolute path to read.

        Returns:
            FsReadFileResponse with base64-encoded file contents.
        """
        params = FsReadFileParams(path=path)
        result = await self._client.dispatch.send_request("fs/readFile", params)
        return FsReadFileResponse.model_validate(result)

    async def write_file(self, path: str, data_base64: str) -> None:
        """Write a file on the host filesystem.

        Args:
            path: Absolute path to write.
            data_base64: File contents encoded as base64.
        """
        params = FsWriteFileParams(path=path, data_base64=data_base64)
        await self._client.dispatch.send_request("fs/writeFile", params)

    async def create_directory(self, path: str, *, recursive: bool | None = None) -> None:
        """Create a directory on the host filesystem.

        Args:
            path: Absolute directory path to create.
            recursive: Whether to create parent directories. Defaults to True server-side.
        """
        params = FsCreateDirectoryParams(path=path, recursive=recursive)
        await self._client.dispatch.send_request("fs/createDirectory", params)

    async def get_metadata(self, path: str) -> FsGetMetadataResponse:
        """Get metadata for an absolute path.

        Args:
            path: Absolute path to inspect.

        Returns:
            FsGetMetadataResponse with isDirectory, isFile, and timestamps.
        """
        params = FsGetMetadataParams(path=path)
        result = await self._client.dispatch.send_request("fs/getMetadata", params)
        return FsGetMetadataResponse.model_validate(result)

    async def read_directory(
        self,
        path: str,
        *,
        recursive: bool = False,
    ) -> list[FsReadDirectoryEntry]:
        """List child entries for a directory.

        Args:
            path: Absolute directory path to read.
            recursive: If True, recursively list all descendant entries.

        Returns:
            List of directory entries with fileName, isDirectory, isFile.
        """
        params = FsReadDirectoryParams(path=path)
        result = await self._client.dispatch.send_request("fs/readDirectory", params)
        entries = FsReadDirectoryResponse.model_validate(result).entries
        if not recursive:
            return entries
        all_entries = list(entries)
        for entry in entries:
            if entry.is_directory:
                sub_path = f"{path.rstrip('/')}/{entry.file_name}"
                sub_entries = await self.read_directory(sub_path, recursive=True)
                all_entries.extend(sub_entries)
        return all_entries

    async def remove(
        self,
        path: str,
        *,
        recursive: bool | None = None,
        force: bool | None = None,
    ) -> None:
        """Remove a file or directory from the host filesystem.

        Args:
            path: Absolute path to remove.
            recursive: Whether to recurse into directories. Defaults to True server-side.
            force: Whether to ignore missing paths. Defaults to True server-side.
        """
        params = FsRemoveParams(path=path, recursive=recursive, force=force)
        await self._client.dispatch.send_request("fs/remove", params)

    async def copy(self, source: str, destination: str, *, recursive: bool = False) -> None:
        """Copy a file or directory tree on the host filesystem.

        Args:
            source: Absolute source path.
            destination: Absolute destination path.
            recursive: Required for directory copies; ignored for file copies.
        """
        params = FsCopyParams(source_path=source, destination_path=destination, recursive=recursive)
        await self._client.dispatch.send_request("fs/copy", params)

    async def watch(self, path: str, watch_id: str) -> FsWatchResponse:
        """Start filesystem watch notifications for an absolute path.

        Args:
            path: Absolute file or directory path to watch.
            watch_id: Watch identifier to associate with the path.

        Returns:
            FsWatchResponse with watch_id and canonicalized path.
        """
        params = FsWatchParams(path=path, watch_id=watch_id)
        result = await self._client.dispatch.send_request("fs/watch", params)
        return FsWatchResponse.model_validate(result)

    async def unwatch(self, watch_id: str) -> None:
        """Stop filesystem watch notifications for a prior watch.

        Args:
            watch_id: Watch identifier returned by fs_watch.
        """
        params = FsUnwatchParams(watch_id=watch_id)
        await self._client.dispatch.send_request("fs/unwatch", params)
