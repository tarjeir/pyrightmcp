from pathlib import Path
import logging
import os

import typer
from fastmcp import FastMCP, Context

from pyrightmcp import model as m
from pyrightmcp.pyright_service import setup_and_run_pyright

try:
    from pyrightmcp.lsp_client import LSPClient
    LSP_AVAILABLE = True
except ImportError:
    LSP_AVAILABLE = False

# Enable debug logging if environment variable is set
log_level = os.getenv("PYRIGHTMCP_LOG_LEVEL", "INFO").upper()
log_file = os.getenv("PYRIGHTMCP_LOG_FILE", "/tmp/pyrightmcp.log")

# Configure logging with both file and console handlers
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
    
logger = logging.getLogger(__name__)

mcp = FastMCP("Pyright Language Server MCP")

app = typer.Typer(help="FastMCP server for running pyright language server")

allowed_paths: list | None = None


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
async def organize_imports(project_dir: str, file_path: str, ctx: Context) -> str:
    """
    Organize imports in a Python file using pyright LSP code actions.
    
    This tool uses the Language Server Protocol to intelligently organize imports
    in a Python file, including:
    - Sorting imports alphabetically
    - Grouping standard library, third-party, and local imports
    - Removing unused imports
    - Formatting import statements consistently
    
    Requires LSP integration to be available (install with: uv sync --extra lsp)
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file to organize imports for.
        
    Returns:
        str: Success message or error description.
    """
    if not LSP_AVAILABLE:
        return "Error: LSP integration not available. Install with: uv sync --extra lsp"
        
    project_path = Path(project_dir).resolve()
    target_file = Path(file_path).resolve()
    
    if allowed_paths is None:
        return "The pyright mcp is not configured correctly"

    if not any(
        project_path == allowed or project_path.is_relative_to(allowed)
        for allowed in allowed_paths
    ):
        return f"Error: Project directory {project_path} is not in allowed directories"
        
    if not target_file.exists():
        return f"Error: File {target_file} does not exist"
        
    if not target_file.is_relative_to(project_path):
        return f"Error: File {target_file} is not within project {project_path}"

    await ctx.info(f"Organizing imports in {target_file}...")
    
    lsp_client = LSPClient(project_path)
    try:
        if not await lsp_client.start():
            return "Error: Failed to start LSP server"
            
        result = await lsp_client.organize_imports(target_file)
        
        match result:
            case m.PyrightError(message=error_msg):
                await ctx.error(f"Organize imports failed: {error_msg}")
                return f"Error: {error_msg}"
            case m.PyrightResult() as pyright_result:
                await ctx.info("Imports organized successfully")
                return pyright_result.output
                
    finally:
        await lsp_client.stop()


@mcp.tool
async def get_code_actions(project_dir: str, file_path: str, line: int, column: int, ctx: Context) -> str:
    """
    Get available code actions (quick fixes) for a specific position in a Python file.
    
    This tool uses the Language Server Protocol to retrieve code actions available
    at a specific line and column, including:
    - Quick fixes for type errors
    - Refactoring suggestions
    - Import suggestions
    - Code style improvements
    
    Requires LSP integration to be available (install with: uv sync --extra lsp)
    
    Args:
        project_dir (str): The absolute path to the root project directory.
        file_path (str): The absolute path to the Python file.
        line (int): Line number (0-based).
        column (int): Column number (0-based).
        
    Returns:
        str: JSON list of available code actions or error message.
    """
    if not LSP_AVAILABLE:
        return "Error: LSP integration not available. Install with: uv sync --extra lsp"
        
    project_path = Path(project_dir).resolve()
    target_file = Path(file_path).resolve()
    
    if allowed_paths is None:
        return "The pyright mcp is not configured correctly"

    if not any(
        project_path == allowed or project_path.is_relative_to(allowed)
        for allowed in allowed_paths
    ):
        return f"Error: Project directory {project_path} is not in allowed directories"
        
    if not target_file.exists():
        return f"Error: File {target_file} does not exist"
        
    if not target_file.is_relative_to(project_path):
        return f"Error: File {target_file} is not within project {project_path}"

    await ctx.info(f"Getting code actions for {target_file}:{line}:{column}...")
    
    lsp_client = LSPClient(project_path)
    try:
        if not await lsp_client.start():
            return "Error: Failed to start LSP server"
            
        await lsp_client.open_document(target_file)
        actions = await lsp_client.get_code_actions(target_file, line, column, line, column)
        
        if not actions:
            return "No code actions available at this position"
            
        # Format actions for display
        action_descriptions = []
        for i, action in enumerate(actions):
            title = action.get("title", "Unknown action")
            kind = action.get("kind", "unknown")
            action_descriptions.append(f"{i+1}. {title} (kind: {kind})")
            
        return f"Available code actions:\n" + "\n".join(action_descriptions)
        
    except Exception as e:
        await ctx.error(f"Failed to get code actions: {e}")
        return f"Error: {e}"
        
    finally:
        await lsp_client.stop()


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

