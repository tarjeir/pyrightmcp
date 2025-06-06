from pathlib import Path
from typing import Union

import typer
from fastmcp import FastMCP, Context

from pyrightmcp import model as m
from pyrightmcp.pyright_service import setup_and_run_pyright

mcp = FastMCP("Pyright Language Server MCP")

app = typer.Typer(help="FastMCP server for running pyright language server")

allowed_paths: list | None = None


@mcp.tool
async def run_pyright(project_dir: str, target_dir: str, ctx: Context) -> str:
    """
    Run pyright language server on a specific directory within a project.

    Args:
        project_dir (str): The root project directory path.
        target_dir (str): The target directory to analyze (relative to project_dir).

    Returns:
        str: The pyright analysis output.
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

    Returns:
        list[str]: List of allowed project directories.
    """

    return [str(p) for p in allowed_paths] if allowed_paths is not None else []


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

    typer.echo(f"Starting pyright MCP server with allowed directories: {allowed_dirs}")
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

