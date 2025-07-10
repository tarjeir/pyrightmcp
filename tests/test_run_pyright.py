"""Test run_pyright functionality."""

import pytest


@pytest.mark.asyncio
async def test_run_pyright_success(mcp_client, test_project_path):
    """Test successful pyright execution on test workspace."""
    result = await mcp_client.call_tool("run_pyright", {
        "project_dir": str(test_project_path),
        "target_dir": "."
    })
    
    # Should return TextContent with pyright output
    assert isinstance(result, list)
    assert len(result) > 0
    result_text = result[0].text
    
    # Should contain some pyright output (success or error messages)
    assert result_text is not None
    assert len(result_text) > 0


@pytest.mark.asyncio
async def test_run_pyright_specific_file(mcp_client, test_project_path):
    """Test running pyright on a specific file."""
    result = await mcp_client.call_tool("run_pyright", {
        "project_dir": str(test_project_path),
        "target_dir": "sample.py"
    })
    
    assert isinstance(result, list)
    assert len(result) > 0
    result_text = result[0].text
    assert result_text is not None


@pytest.mark.asyncio
async def test_run_pyright_invalid_directory(mcp_client):
    """Test error handling for invalid directory."""
    result = await mcp_client.call_tool("run_pyright", {
        "project_dir": "/nonexistent/directory",
        "target_dir": "."
    })
    
    assert isinstance(result, list)
    assert len(result) > 0
    result_text = result[0].text
    
    # Should contain error message about directory not being allowed
    assert "Error:" in result_text
    assert "not in allowed directories" in result_text


@pytest.mark.asyncio 
async def test_run_pyright_missing_params(mcp_client):
    """Test error handling for missing parameters."""
    # This should handle missing parameters gracefully
    try:
        result = await mcp_client.call_tool("run_pyright", {})
        # If it doesn't raise an exception, it should return an error message
        assert isinstance(result, list)
        result_text = result[0].text if result else ""
        assert "Error:" in result_text
    except Exception:
        # It's also acceptable for this to raise an exception
        pass