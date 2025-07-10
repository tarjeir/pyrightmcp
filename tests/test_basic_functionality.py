"""Test basic pyrightmcp functionality and server setup."""

import pytest


@pytest.mark.asyncio
async def test_server_startup(mcp_server):
    """Test that MCP server can be created successfully."""
    assert mcp_server is not None
    assert mcp_server.name == "Pyright Language Server MCP"


@pytest.mark.asyncio
async def test_client_connection(mcp_client):
    """Test that MCP client can connect to server."""
    assert mcp_client is not None


@pytest.mark.asyncio
async def test_list_tools(mcp_client):
    """Test that all expected tools are registered."""
    tools = await mcp_client.list_tools()
    
    tool_names = [tool.name for tool in tools]
    
    # Check that our main tools are registered
    expected_tools = [
        "run_pyright",
        "list_allowed_directories", 
        "get_definition",
        "get_references",
        "get_hover",
        "get_diagnostics",
        "rename_symbol",
        "get_code_actions",
        "organize_imports",
        "edit_file"
    ]
    
    for tool_name in expected_tools:
        assert tool_name in tool_names, f"Tool {tool_name} not found in registered tools"


@pytest.mark.asyncio
async def test_tool_has_description(mcp_client):
    """Test that tools have proper descriptions."""
    tools = await mcp_client.list_tools()
    
    for tool in tools:
        assert tool.description, f"Tool {tool.name} has no description"
        assert len(tool.description) > 10, f"Tool {tool.name} has too short description"