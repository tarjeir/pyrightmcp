# Pyright MCP Server

A FastMCP server that provides pyright language server functionality for Python projects.

## Features

- Automatically checks for and creates virtual environments
- Installs pyright if not present
- Runs pyright analysis on specified directories
- Configurable allowed project directories for security
- Multiple transport options (stdio, SSE, HTTP)

## Installation

You can install and run this project using either [uv](https://github.com/astral-sh/uv) or [pipx](https://pypa.github.io/pipx/).

### Using uv

```bash
uv sync
```

### Using pipx

First, ensure you have [pipx](https://pypa.github.io/pipx/) installed:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Then install the project in an isolated environment:

```bash
pipx install .
```

To run the server with pipx:

```bash
pipx run pyrightmcp serve
```

### Using pipx with a global classpath

If you want to run the server with `pipx` and analyze code using your global Python environment (not a project `.venv`), you can do so by pointing `--allowed-dir` to your global site-packages or a directory on your global `PYTHONPATH`.  
This is useful for system-wide or user-wide codebases.

```bash
pipx run pyrightmcp serve --allowed-dir /usr/local/lib/python3.12/site-packages
```

Or, to analyze code in a directory that is on your global `PYTHONPATH`:

```bash
pipx run pyrightmcp serve --allowed-dir /path/to/your/global/code
```

> **Note:** When using a global classpath, ensure that `pyright` is available in your global environment, or install it globally with:
> ```bash
> pipx inject pyrightmcp pyright
> ```

## Usage

### Interactive Mode

```bash
uv run pyrightmcp serve
```

This will prompt you to enter allowed project directories.

### Command Line

```bash
uv run pyrightmcp serve --allowed-dir /path/to/your/python/project1 --allowed-dir /path/to/your/python/project2
```
> **Note:** The path you provide to `--allowed-dir` should be the root directory of your Python project.

### Different Transports

```bash
# STDIO (default)
uv run pyrightmcp serve --transport stdio

# SSE
uv run pyrightmcp serve --transport sse --port 8000

# HTTP
uv run pyrightmcp serve --transport streamable-http --port 8000
```

## Available Tools

- `run_pyright`: Run pyright analysis on a specific directory within a project
- `list_allowed_directories`: List the directories where pyright can be run

## Example

```python
# Connect to the server and run pyright
from fastmcp import Client

async with Client("uv run pyrightmcp serve") as client:
    result = await client.call_tool("run_pyright", {
        "project_dir": "/path/to/my/project",
        "target_dir": "src"
    })
    print(result.text)
```

## Example MCP Claude Config

To use this server with [MCP Claude](https://github.com/paulgb/mcp-claude), add a config block like the following to your `~/.mcp/config.yaml`:

```yaml
servers:
  - name: pyright
    command: uv run pyrightmcp serve --allowed-dir /path/to/my/project
    transport: stdio
    tools:
      - run_pyright
      - list_allowed_directories
```

Or, if you use the JSON config format (`~/.mcp/config.json`):

```json
{
  "mcpServers": {
    "pyright": {
      "command": "pyrightmcp",
      "args": [
        "serve",
        "--allowed-dir",
        "/path/to/project"
      ]
    }
  }
}
```

> **Note:** This example configures MCP to run the `pyrightmcp` executable directly (as installed by pipx or globally), and sets `--allowed-dir` to your global site-packages directory.  
> You can also use any directory on your global `PYTHONPATH` as the allowed directory.

You can then use the `pyright` tools from within your Claude chat session.
