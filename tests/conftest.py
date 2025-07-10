"""Shared pytest fixtures for pyrightmcp testing."""

import pytest
import pytest_asyncio
from pathlib import Path

from pyrightmcp import main


@pytest.fixture
def test_project_path() -> Path:
    """Path to test workspace directory."""
    return Path(__file__).parent / "fixtures" / "test_workspace"


@pytest.fixture
def mcp_server():
    """FastMCP server instance for in-memory testing."""
    # Set up allowed paths to include test workspace
    test_workspace = Path(__file__).parent / "fixtures" / "test_workspace"
    main.allowed_paths = [test_workspace]
    
    return main.mcp


@pytest_asyncio.fixture
async def mcp_client(mcp_server):
    """FastMCP client connected to server via in-memory transport."""
    from fastmcp import Client
    
    async with Client(mcp_server) as client:
        yield client