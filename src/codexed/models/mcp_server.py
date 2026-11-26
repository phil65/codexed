"""MCP server configuration models."""

from typing import Literal

from mcp.types import BlobResourceContents, TextResourceContents
from pydantic import BaseModel


ResourceContents = TextResourceContents | BlobResourceContents

type ToolApprovalMode = Literal["auto", "prompt", "writes", "approve"]
"""When Codex asks before calling a server's tools (``default_tools_approval_mode``).

- ``auto``: Codex's default; asks unless the tool is annotated read-only, or
  non-destructive and closed-world. Under approval policy ``never`` it rejects them.
- ``prompt``: always asks.
- ``writes``: asks unless the tool is annotated read-only.
- ``approve``: never asks.
"""


class StdioMcpServer(BaseModel):
    """MCP server running as a subprocess via stdio transport."""

    command: str
    args: list[str] = []
    env: dict[str, str] | None = None
    enabled: bool = True
    default_tools_approval_mode: ToolApprovalMode | None = None
    """When Codex asks before calling this server's tools (Codex's default: ``auto``)."""

    def to_config_toml(self, name: str) -> str:
        parts = [f'command = "{self.command}"']
        if self.args:
            args_str = ", ".join(f'"{arg}"' for arg in self.args)
            parts.append(f"args = [{args_str}]")
        if self.env:
            # env as inline table
            env_items = ", ".join(f'{k} = "{v}"' for k, v in self.env.items())
            parts.append(f"env = {{{env_items}}}")
        if not self.enabled:
            parts.append("enabled = false")
        if self.default_tools_approval_mode:
            parts.append(f'default_tools_approval_mode = "{self.default_tools_approval_mode}"')
        return f"mcp_servers.{name}={{{', '.join(parts)}}}"


class HttpMcpServer(BaseModel):
    """MCP server accessible via HTTP/SSE transport."""

    url: str
    bearer_token_env_var: str | None = None
    http_headers: dict[str, str] | None = None
    enabled: bool = True
    default_tools_approval_mode: ToolApprovalMode | None = None
    """When Codex asks before calling this server's tools (Codex's default: ``auto``)."""

    def to_config_toml(self, name: str) -> str:
        parts = [f'url = "{self.url}"']
        if self.bearer_token_env_var:
            parts.append(f'bearer_token_env_var = "{self.bearer_token_env_var}"')
        if self.http_headers:
            # headers as inline table
            headers_items = ", ".join(f'{k} = "{v}"' for k, v in self.http_headers.items())
            parts.append(f"http_headers = {{{headers_items}}}")
        if not self.enabled:
            parts.append("enabled = false")
        if self.default_tools_approval_mode:
            parts.append(f'default_tools_approval_mode = "{self.default_tools_approval_mode}"')
        return f"mcp_servers.{name}={{{', '.join(parts)}}}"


McpServerConfig = StdioMcpServer | HttpMcpServer
