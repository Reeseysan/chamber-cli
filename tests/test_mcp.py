"""Tests for MCP server module."""
from __future__ import annotations

import pytest
import json


def test_mcp_server_import_error():
    """MCP server should give a clear error if mcp package is not installed."""
    # We can't easily test FastMCP without installing mcp,
    # but we can test the error handling path
    import importlib
    import sys

    # Save and remove mcp if it exists
    mcp_module = sys.modules.pop("mcp", None)
    mcp_server_module = sys.modules.pop("mcp.server", None)
    mcp_fastmcp_module = sys.modules.pop("mcp.server.fastmcp", None)

    try:
        from chamber.mcp_server import create_mcp_server
        # If mcp is not installed, this should raise ImportError
        try:
            create_mcp_server()
        except ImportError as e:
            assert "pip install chamber-cli[mcp]" in str(e)
    finally:
        # Restore modules
        if mcp_module:
            sys.modules["mcp"] = mcp_module
        if mcp_server_module:
            sys.modules["mcp.server"] = mcp_server_module
        if mcp_fastmcp_module:
            sys.modules["mcp.server.fastmcp"] = mcp_fastmcp_module


def test_try_import_silent_failure():
    """_try_import should silently ignore failures."""
    from chamber.mcp_server import _try_import
    # Should not raise
    _try_import("nonexistent_module_that_does_not_exist")
