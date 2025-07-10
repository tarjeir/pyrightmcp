from pathlib import Path
import asyncio

import typer
from fastmcp import FastMCP, Context

from pyrightmcp import model as m
from pyrightmcp.pyright_service import setup_and_run_pyright
from pyrightmcp.lsp_client import LSPClient, LSPClientError

mcp = FastMCP("Pyright Language Server MCP")

app = typer.Typer(help="FastMCP server for running pyright language server")

allowed_paths: list | None = None
lsp_clients: dict[str, LSPClient] = {}  # Cache LSP clients by project path


async def get_lsp_client(project_path: Path) -> LSPClient:
    """Get or create an LSP client for the given project path."""
    if allowed_paths is None:
        raise LSPClientError("The pyright mcp is not configured correctly")

    if not any(
        project_path == allowed or project_path.is_relative_to(allowed)
        for allowed in allowed_paths
    ):
        raise LSPClientError(f"Project directory {project_path} is not in allowed directories")

    project_key = str(project_path)
    
    if project_key not in lsp_clients:
        client = LSPClient(project_path)
        await client.start()
        lsp_clients[project_key] = client
    
    return lsp_clients[project_key]


@mcp.tool
async def run_pyright(project_dir: str, target_dir: str, ctx: Context) -> str:
    """
    Run pyright type checker and static analysis on a specific directory within a Python project.
    
    This tool performs comprehensive Python static analysis including:
    - Type checking and type inference validation
    - Detection of unused variables, imports, and functions (with --warnings flag)
    - Identification of unreachable code
    - Missing import detection
    - Configuration compliance checking
    
    The tool automatically handles project setup:
    - Checks for virtual environment existence
    - Installs pyright if not present using uv
    - Runs analysis with proper PYTHONPATH configuration

    Args:
        project_dir (str): The absolute path to the root project directory containing pyproject.toml, setup.py, or Python package structure.
        target_dir (str): The target directory path to analyze, relative to project_dir (use "." for entire project).

    Returns:
        str: Complete pyright analysis output including errors, warnings, and summary statistics.
    """
    project_path = Path(project_dir).resolve()
    target_path = Path(project_dir) / target_dir
    target_path = target_path.resolve()

    if allowed_paths is None:
        return "The pyright mcp is not configured correctly"

    if not any(
        project_path == allowed or project_path.is_relative_to(allowed)
        for allowed in allowed_paths
    ):
        return f"Error: Project directory {project_path} is not in allowed directories"

    await ctx.info(f"Running pyright on {target_path}...")

    result = setup_and_run_pyright(project_path=project_path, target_dir=target_path)

    match result:
        case m.PyrightError(message=error_msg):
            await ctx.error(f"Pyright failed: {error_msg}")
            return f"Error: {error_msg}"
        case m.PyrightResult() as pyright_result:
            await ctx.info(
                f"Pyright completed with exit code {pyright_result.exit_code}"
            )
            return pyright_result.output


@mcp.tool
async def list_allowed_directories() -> list[str]:
    """
    List the directories where pyright can be run.
    
    This tool returns all project directories that have been configured as allowed
    for pyright analysis. These directories are set when starting the MCP server
    using the --allowed-dir flag or through interactive prompts.
    
    Security note: Only projects within these allowed directories can be analyzed
    to prevent unauthorized access to filesystem locations.

    Returns:
        list[str]: List of absolute paths to allowed project directories.
    """

    return [str(p) for p in allowed_paths] if allowed_paths is not None else []


@mcp.tool
async def get_definition(project_dir: str, file_path: str, line: int, column: int, ctx: Context) -> str:
    """
    Get the definition of a symbol at a specific position in a file.
    
    This tool uses the Language Server Protocol to find where a symbol (function, class, variable, etc.)
    is defined in the codebase.
    
    IMPORTANT: Target the exact symbol name, not the body content. Point to class names, 
    function names, variable names - not decorators, docstrings, or implementation details.
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        line (int): Line number (0-based indexing, where first line is 0).
        column (int): Column number (0-based indexing, where first column is 0).
        
    Returns:
        str: Information about the symbol definition including file path and location.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Get definition
        locations = await client.get_definition(file_path, line, column)
        
        if not locations:
            return "No definition found"
        
        result = "Definitions found:\n"
        for location in locations:
            uri = location.uri
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove file:// prefix
            else:
                file_path = uri
            
            result += f"- {file_path}:{location.range.start.line + 1}:{location.range.start.character + 1}\n"
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def get_references(project_dir: str, file_path: str, line: int, column: int, ctx: Context) -> str:
    """
    Find all references to a symbol at a specific position in a file.
    
    This tool uses the Language Server Protocol to find all places where a symbol is used
    throughout the codebase.
    
    IMPORTANT: Target the exact symbol name, not the body content. Point to class names, 
    function names, variable names - not decorators, docstrings, or implementation details.
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        line (int): Line number (0-based indexing, where first line is 0).
        column (int): Column number (0-based indexing, where first column is 0).
        
    Returns:
        str: List of all references to the symbol including file paths and locations.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Get references
        locations = await client.get_references(file_path, line, column)
        
        if not locations:
            return "No references found"
        
        result = f"Found {len(locations)} references:\n"
        for location in locations:
            uri = location.uri
            if uri.startswith("file://"):
                file_path = uri[7:]  # Remove file:// prefix
            else:
                file_path = uri
            
            result += f"- {file_path}:{location.range.start.line + 1}:{location.range.start.character + 1}\n"
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def get_hover(project_dir: str, file_path: str, line: int, column: int, ctx: Context) -> str:
    """
    Get hover information for a symbol at a specific position in a file.
    
    This tool uses the Language Server Protocol to get documentation, type information,
    and other details about a symbol when hovering over it.
    
    IMPORTANT: Target the exact symbol name, not the body content. Point to class names, 
    function names, variable names - not decorators, docstrings, or implementation details.
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        line (int): Line number (0-based indexing, where first line is 0).
        column (int): Column number (0-based indexing, where first column is 0).
        
    Returns:
        str: Hover information including type hints and documentation.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Get hover info (document will be opened automatically)
        hover = await client.get_hover(file_path, line, column)
        
        if not hover:
            return "No hover information available"
        
        # Handle different hover content formats
        contents = hover.contents
        if isinstance(contents, dict):
            # LSP hover contents can be MarkupContent with kind and value
            if 'value' in contents:
                return contents.get('value', '')
            elif 'text' in contents:
                return contents.get('text', '')
            else:
                return str(contents)
        elif isinstance(contents, list):
            # Contents can be a list of strings or MarkupContent objects
            result = []
            for item in contents:
                if isinstance(item, dict):
                    if 'value' in item:
                        result.append(item.get('value', ''))
                    elif 'text' in item:
                        result.append(item.get('text', ''))
                    else:
                        result.append(str(item))
                else:
                    result.append(str(item))
            return "\n".join(result)
        else:
            return str(contents)
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def get_diagnostics(project_dir: str, file_path: str, ctx: Context) -> str:
    """
    Get diagnostic information (errors, warnings, etc.) for a specific file.
    
    This tool uses the Language Server Protocol to get real-time diagnostics
    from the pyright language server.
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        
    Returns:
        str: Diagnostic information including errors and warnings.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Wait a moment for diagnostics to be published
        await asyncio.sleep(0.5)
        
        # Get diagnostics
        diagnostics = await client.get_diagnostics(file_path)
        
        if not diagnostics:
            return "No diagnostics found"
        
        result = f"Found {len(diagnostics)} diagnostics:\n"
        for diagnostic in diagnostics:
            severity = diagnostic.severity.name.lower() if diagnostic.severity else "unknown"
            line = diagnostic.range.start.line + 1
            char = diagnostic.range.start.character + 1
            
            result += f"- {severity.upper()} at line {line}, column {char}: {diagnostic.message}\n"
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def rename_symbol(project_dir: str, file_path: str, line: int, column: int, new_name: str, ctx: Context) -> str:
    """
    Rename a symbol at a specific position and update all references throughout the codebase.
    
    This tool uses the Language Server Protocol to safely rename variables, functions, classes,
    and other symbols while updating all references.
    
    CRITICAL: Must target the exact symbol name. Use get_references first to verify what 
    will be renamed. Point to class names, function names, variable names - not decorators, 
    docstrings, or implementation details.
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        line (int): Line number (0-based indexing, where first line is 0).
        column (int): Column number (0-based indexing, where first column is 0).
        new_name (str): The new name for the symbol.
        
    Returns:
        str: Information about the rename operation and files that were modified.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Get workspace edit for rename
        workspace_edit = await client.rename_symbol(file_path, line, column, new_name)
        
        if not workspace_edit or not workspace_edit.changes:
            return "No rename changes available"
        
        result = f"Rename operation would modify {len(workspace_edit.changes)} files:\n"
        for file_uri, edits in workspace_edit.changes.items():
            if file_uri.startswith("file://"):
                file_path = file_uri[7:]  # Remove file:// prefix
            else:
                file_path = file_uri
            
            result += f"- {file_path}: {len(edits)} changes\n"
        
        result += "\nNote: This is a preview. The actual rename operation would need to be applied separately."
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def get_code_actions(project_dir: str, file_path: str, start_line: int, start_char: int, end_line: int, end_char: int, ctx: Context) -> str:
    """
    Get available code actions (quick fixes) for a specific range in a file.
    
    This tool uses the Language Server Protocol to get code actions such as:
    - Quick fixes for errors
    - Refactoring suggestions
    - Import organization
    - Code style improvements
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        start_line (int): Start line number (0-based indexing, where first line is 0).
        start_char (int): Start column number (0-based indexing, where first column is 0).
        end_line (int): End line number (0-based indexing, where first line is 0).
        end_char (int): End column number (0-based indexing, where first column is 0).
        
    Returns:
        str: List of available code actions.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Get code actions
        actions = await client.get_code_actions(file_path, start_line, start_char, end_line, end_char)
        
        if not actions:
            return "No code actions available"
        
        result = f"Found {len(actions)} code actions:\n"
        for i, action in enumerate(actions, 1):
            result += f"{i}. {action.title}"
            if action.kind:
                result += f" ({action.kind})"
            result += "\n"
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def organize_imports(project_dir: str, file_path: str, ctx: Context) -> str:
    """
    Organize imports in a Python file using pyright LSP code actions.
    
    This tool uses the Language Server Protocol to intelligently organize imports
    in a Python file, including:
    - Sorting imports alphabetically
    - Grouping standard library, third-party, and local imports
    - Removing unused imports
    - Formatting import statements consistently
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file to organize imports for.
        
    Returns:
        str: Success message or error description.
    """
    try:
        project_path = Path(project_dir).resolve()
        client = await get_lsp_client(project_path)
        
        # Ensure the file is opened in the LSP server
        await client.did_open(file_path)
        
        # Get code actions for the entire file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        actions = await client.get_code_actions(file_path, 0, 0, len(lines) - 1, len(lines[-1]) if lines else 0)
        
        # Look for organize imports actions
        organize_actions = [action for action in actions if action.kind and 'organizeImports' in action.kind]
        
        if not organize_actions:
            return "No organize imports actions available"
        
        result = f"Found {len(organize_actions)} import organization actions:\n"
        for i, action in enumerate(organize_actions, 1):
            result += f"{i}. {action.title}\n"
        
        result += "\nNote: This is a preview. The actual organization would need to be applied separately."
        
        return result.strip()
        
    except LSPClientError as e:
        await ctx.error(f"LSP client error: {e}")
        return f"Error: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        return f"Error: {e}"


@mcp.tool
async def edit_file(file_path: str, edits: list[dict], ctx: Context) -> str:
    """
    Apply multiple text edits to a file based on line numbers.
    
    This tool allows making multiple line-based edits to a file in a single operation.
    Each edit specifies a line range to replace and the new text content.
    
    Args:
        file_path (str): The absolute path to the file to edit.
        edits (list[dict]): List of edit operations, each containing:
            - startLine (int): Start line to replace, inclusive, 1-indexed
            - endLine (int): End line to replace, inclusive, 1-indexed  
            - newText (str): Replacement text (empty string to delete lines)
            
    Returns:
        str: Success message with details of the edits applied.
    """
    try:
        file_path_obj = Path(file_path).resolve()
        
        # Check if file is in allowed directories
        if allowed_paths is None:
            return "Error: The pyright mcp is not configured correctly"

        if not any(
            file_path_obj.is_relative_to(allowed) for allowed in allowed_paths
        ):
            return f"Error: File {file_path_obj} is not in allowed directories"

        if not file_path_obj.exists():
            return f"Error: File {file_path_obj} does not exist"

        # Read the current file content
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Sort edits by line number in descending order to avoid index issues
        sorted_edits = sorted(edits, key=lambda x: x.get('startLine', 0), reverse=True)

        # Apply edits
        for edit in sorted_edits:
            start_line = edit.get('startLine', 1)
            end_line = edit.get('endLine', start_line)
            new_text = edit.get('newText', '')

            # Convert to 0-based indexing
            start_idx = start_line - 1
            end_idx = end_line - 1

            # Validate line numbers
            if start_idx < 0 or end_idx >= len(lines) or start_idx > end_idx:
                return f"Error: Invalid line range {start_line}-{end_line} for file with {len(lines)} lines"

            # Prepare new text with proper line ending
            if new_text and not new_text.endswith('\n'):
                new_text += '\n'

            # Replace the lines
            if new_text:
                lines[start_idx:end_idx + 1] = [new_text]
            else:
                # Delete lines if new_text is empty
                lines[start_idx:end_idx + 1] = []

        # Write the modified content back to the file
        with open(file_path_obj, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        await ctx.info(f"Applied {len(edits)} edits to {file_path_obj}")
        
        return f"Successfully applied {len(edits)} edits to {file_path_obj}"

    except Exception as e:
        await ctx.error(f"Error editing file: {e}")
        return f"Error: {e}"


@app.command()
def serve(
    allowed_dirs: list[str] = typer.Option(
        [],
        "--allowed-dir",
        "-d",
        help="Allowed project directories (can be specified multiple times)",
    ),
    transport: str = typer.Option(
        "stdio", help="Transport type (stdio, sse, streamable-http)"
    ),
    host: str = typer.Option("127.0.0.1", help="Host for HTTP transports"),
    port: int = typer.Option(8000, help="Port for HTTP transports"),
):
    """Start the pyright MCP server."""
    if not allowed_dirs:
        allowed_dirs = [typer.prompt("Enter a project directory")]

        while typer.confirm("Add another directory?", default=False):
            additional_dir = typer.prompt("Enter another project directory")
            allowed_dirs.append(additional_dir)

    global allowed_paths
    allowed_paths = [Path(d).resolve() for d in allowed_dirs]

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    elif transport == "streamable-http":
        mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")
    else:
        typer.echo(f"Unknown transport: {transport}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

