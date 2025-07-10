"""Test hover functionality to verify LSP integration."""
import pytest
from pathlib import Path
from pyrightmcp.lsp_client import LSPClient


@pytest.mark.asyncio
async def test_hover_on_function_definition(mcp_client, test_project_path):
    """Test hover on function definition using MCP tool."""
    file_path = str(test_project_path / "sample.py")
    
    # Test hover on function name 'calculate_area' at line 5, column 4
    result = await mcp_client.call_tool("get_hover", {
        "project_dir": str(test_project_path),
        "file_path": file_path,
        "line": 5,
        "column": 4
    })
    
    print(f"Hover result for function definition: {result}")
    assert isinstance(result, list)
    assert len(result) > 0
    result_text = result[0].text
    assert "calculate_area" in result_text


@pytest.mark.asyncio
async def test_lsp_client_direct_hover():
    """Test LSPClient hover directly to debug issues."""
    test_file = Path("/tmp/direct_hover_test.py")
    test_content = '''
def simple_function(x: int) -> str:
    """Convert integer to string."""
    return str(x)

value = simple_function(42)
'''
    test_file.write_text(test_content)
    
    project_path = test_file.parent
    client = LSPClient(project_path)
    
    try:
        await client.start()
        
        # Test hover on the function definition
        hover_result = await client.get_hover(str(test_file), 1, 4)
        print(f"Direct LSP hover result: {hover_result}")
        
        if hover_result:
            print(f"Hover contents type: {type(hover_result.contents)}")
            print(f"Hover contents: {hover_result.contents}")
        else:
            print("No hover result returned")
        
        # Test hover on function call
        hover_result_call = await client.get_hover(str(test_file), 5, 8)
        print(f"Direct LSP hover result for call: {hover_result_call}")
        
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_hover_with_debug_info():
    """Test hover with detailed debug information."""
    test_file = Path("/tmp/debug_hover_test.py")
    test_content = '''
import os
from typing import List

def process_files(files: List[str]) -> None:
    """Process a list of files."""
    for file in files:
        if os.path.exists(file):
            print(f"Processing {file}")

# Test call
process_files(["test.txt"])
'''
    test_file.write_text(test_content)
    
    project_path = test_file.parent
    client = LSPClient(project_path)
    
    try:
        await client.start()
        
        # Test multiple positions
        positions = [
            (1, 7),   # 'os' import
            (2, 14),  # 'List' type
            (4, 4),   # function name
            (4, 20),  # parameter type
            (7, 12),  # os.path.exists
            (11, 0),  # function call
        ]
        
        for line, col in positions:
            hover_result = await client.get_hover(str(test_file), line, col)
            print(f"Position ({line}, {col}): {hover_result}")
            
    finally:
        await client.stop()


if __name__ == "__main__":
    import asyncio
    
    print("Running direct hover tests...")
    asyncio.run(test_lsp_client_direct_hover())
    print("\nRunning debug hover tests...")
    asyncio.run(test_hover_with_debug_info())