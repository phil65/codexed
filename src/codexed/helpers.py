from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codexed.models.tool_config import tools_to_config_dict


if TYPE_CHECKING:
    from collections.abc import Mapping

    from codexed.models import McpServerConfig, ToolConfig


def kebab_to_camel(s: str) -> str:
    """Convert kebab-case to camelCase."""
    parts = s.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def merge_config(
    config: dict[str, Any] | None,
    tools: list[ToolConfig] | None,
    code_mode: bool | None,
    mcp_servers: Mapping[str, McpServerConfig] | None = None,
    mcp_elicitation_for_approvals: bool = False,
) -> dict[str, Any] | None:
    """Merge tools, code_mode, and mcp_servers into a config dict."""
    merged = dict(config) if config else {}
    if code_mode is not None:
        merged.setdefault("features", {})["code_mode"] = code_mode
    merged.setdefault("features", {})["codex_hooks"] = True
    merged.setdefault("features", {})["realtime_conversation"] = True
    if mcp_elicitation_for_approvals:
        merged.setdefault("features", {})["tool_call_mcp_elicitation"] = True
    if tools is not None:
        tool_config = tools_to_config_dict(tools)
        for key, value in tool_config.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                merged[key] = {**value, **merged[key]}
    if mcp_servers:
        servers = merged.setdefault("mcp_servers", {})
        for name, srv in mcp_servers.items():
            servers.setdefault(name, srv.model_dump(exclude_none=True))
    return merged or None
