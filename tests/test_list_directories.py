"""Test list_allowed_directories functionality."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_list_allowed_directories_success(mcp_client, test_project_path):
    """Test that allowed directories are listed correctly."""
    result = await mcp_client.call_tool("list_allowed_directories", {})
    
    # The result should be a list containing TextContent objects
    assert isinstance(result, list)
    assert len(result) > 0
    
    # Extract the text from the TextContent object
    result_text = result[0].text
    assert str(test_project_path) in result_text


@pytest.mark.asyncio
async def test_list_allowed_directories_format(mcp_client):
    """Test that the response is properly formatted."""
    result = await mcp_client.call_tool("list_allowed_directories", {})
    
    # Should be a list
    assert isinstance(result, list)
    assert len(result) >= 1  # Should have at least one directory


@pytest.mark.asyncio
async def test_list_allowed_directories_no_params(mcp_client):
    """Test that the tool works without any parameters."""
    # This should not raise an exception
    result = await mcp_client.call_tool("list_allowed_directories", {})
    assert result is not None
    assert isinstance(result, list)