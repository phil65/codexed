"""MCP server configs reach Codex with their tool approval mode."""

from __future__ import annotations

from codexed.helpers import merge_config
from codexed.models import HttpMcpServer, StdioMcpServer


def test_approval_mode_in_the_command_line_config() -> None:
    http = HttpMcpServer(url="http://127.0.0.1:1/mcp", default_tools_approval_mode="approve")
    stdio = StdioMcpServer(command="srv", default_tools_approval_mode="writes")
    assert http.to_config_toml("a") == (
        'mcp_servers.a={url = "http://127.0.0.1:1/mcp", default_tools_approval_mode = "approve"}'
    )
    assert 'default_tools_approval_mode = "writes"' in stdio.to_config_toml("b")
    assert "default_tools_approval_mode" not in HttpMcpServer(url="u").to_config_toml("c")


def test_approval_mode_in_a_threads_config() -> None:
    server = HttpMcpServer(url="u", default_tools_approval_mode="approve")
    config = merge_config(None, None, None, {"a": server})
    assert config is not None
    assert config["mcp_servers"]["a"] == {
        "url": "u",
        "enabled": True,
        "default_tools_approval_mode": "approve",
    }
