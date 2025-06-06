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
      "command": "uv",
      "args": [
        "run",
        "pyrightmcp",
        "serve",
        "--allowed-dir",
        "/path/to/your/python/project"  // <-- Set this to your project root directory
      ]
    }
  }
}
```

You can then use the `pyright` tools from within your Claude chat session.
