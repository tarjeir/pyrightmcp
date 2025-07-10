"""
LSP client for communicating with pyright-langserver.
Handles JSON-RPC 2.0 protocol over stdio.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import subprocess
from dataclasses import asdict

from pyrightmcp.lsp_types import (
    InitializeParams,
    InitializeResult,
    LSPRequest,
    LSPResponse,
    LSPNotification,
    TextDocumentIdentifier,
    TextDocumentPositionParams,
    ReferenceParams,
    RenameParams,
    CodeActionParams,
    PublishDiagnosticsParams,
    Diagnostic,
    DiagnosticSeverity,
    Hover,
    Location,
    WorkspaceEdit,
    CodeAction,
    create_text_document_identifier,
    create_text_document_position_params,
)

logger = logging.getLogger(__name__)


class LSPClientError(Exception):
    """Exception raised by LSP client operations."""
    pass


class LSPClient:
    """
    LSP client for communicating with pyright-langserver.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.process: Optional[subprocess.Popen] = None
        self.stdin_writer: Optional[asyncio.StreamWriter] = None
        self.stdout_reader: Optional[asyncio.StreamReader] = None
        self.stderr_reader: Optional[asyncio.StreamReader] = None
        self.request_id = 0
        self.pending_requests: Dict[Union[int, str], asyncio.Future] = {}
        self.diagnostics: Dict[str, List[Diagnostic]] = {}
        self.server_capabilities: Optional[Dict[str, Any]] = None
        self.initialized = False
        self.reader_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the pyright-langserver process and initialize the LSP connection."""
        if self.process is not None:
            raise LSPClientError("LSP client is already started")

        try:
            # Start pyright-langserver process
            self.process = await asyncio.create_subprocess_exec(
                "uv", "run", "pyright-langserver", "--stdio",
                cwd=self.project_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": str(self.project_path)},
            )

            if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
                raise LSPClientError("Failed to create subprocess pipes")

            self.stdin_writer = self.process.stdin
            self.stdout_reader = self.process.stdout
            self.stderr_reader = self.process.stderr

            # Start reading responses
            self.reader_task = asyncio.create_task(self._read_responses())

            # Initialize the LSP connection
            await self._initialize()

            logger.info("LSP client started and initialized")

        except Exception as e:
            await self.stop()
            raise LSPClientError(f"Failed to start LSP client: {e}")

    async def stop(self) -> None:
        """Stop the pyright-langserver process and clean up."""
        if not self.initialized:
            return

        try:
            # Send shutdown and exit requests
            await self._send_request("shutdown", {})
            await self._send_notification("exit", {})
        except Exception as e:
            logger.warning(f"Error during LSP shutdown: {e}")

        # Cancel reader task
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass

        # Terminate process
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            except Exception as e:
                logger.warning(f"Error terminating LSP process: {e}")

        # Reset state
        self.process = None
        self.stdin_writer = None
        self.stdout_reader = None
        self.stderr_reader = None
        self.initialized = False
        self.pending_requests.clear()

        logger.info("LSP client stopped")

    async def _initialize(self) -> None:
        """Initialize the LSP connection."""
        # Send initialize request
        init_params = InitializeParams(
            process_id=os.getpid(),
            root_path=str(self.project_path),
            root_uri=f"file://{self.project_path}",
            capabilities={
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": False,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "didSave": False,
                    },
                    "completion": {"dynamicRegistration": False},
                    "hover": {"dynamicRegistration": False},
                    "definition": {"dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                    "rename": {"dynamicRegistration": False},
                    "codeAction": {"dynamicRegistration": False},
                    "publishDiagnostics": {"dynamicRegistration": False},
                },
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": False,
                        "resourceOperations": [],
                        "failureHandling": "textOnlyTransactional",
                    },
                },
            },
        )

        result = await self._send_request("initialize", asdict(init_params))
        self.server_capabilities = result.get("capabilities", {})

        # Send initialized notification
        await self._send_notification("initialized", {})
        self.initialized = True

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Send an LSP request and wait for response."""
        if not self.stdin_writer:
            raise LSPClientError("LSP client not started")

        request_id = self.request_id
        self.request_id += 1

        request = LSPRequest(id=request_id, method=method, params=params)
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            await self._send_message(asdict(request))
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise LSPClientError(f"Timeout waiting for response to {method}")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise LSPClientError(f"Error sending request {method}: {e}")

    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send an LSP notification."""
        if not self.stdin_writer:
            raise LSPClientError("LSP client not started")

        notification = LSPNotification(method=method, params=params)
        await self._send_message(asdict(notification))

    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a JSON-RPC message."""
        if not self.stdin_writer:
            raise LSPClientError("LSP client not started")

        content = json.dumps(message)
        message_str = f"Content-Length: {len(content)}\r\n\r\n{content}"
        
        self.stdin_writer.write(message_str.encode())
        await self.stdin_writer.drain()

    async def _read_responses(self) -> None:
        """Read responses from the LSP server."""
        if not self.stdout_reader:
            return

        try:
            while True:
                # Read Content-Length header
                header_line = await self.stdout_reader.readline()
                if not header_line:
                    break

                header = header_line.decode().strip()
                if not header.startswith("Content-Length:"):
                    continue

                content_length = int(header.split(":")[1].strip())

                # Read empty line
                await self.stdout_reader.readline()

                # Read content
                content = await self.stdout_reader.read(content_length)
                if not content:
                    break

                try:
                    message = json.loads(content.decode())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading LSP responses: {e}")

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming LSP message."""
        if "id" in message:
            # Response
            request_id = message["id"]
            future = self.pending_requests.pop(request_id, None)
            if future:
                if "error" in message:
                    error = message["error"]
                    future.set_exception(LSPClientError(f"LSP error: {error}"))
                else:
                    future.set_result(message.get("result"))
        else:
            # Notification
            method = message.get("method")
            params = message.get("params", {})
            
            if method == "textDocument/publishDiagnostics":
                await self._handle_diagnostics(params)

    async def _handle_diagnostics(self, params: Dict[str, Any]) -> None:
        """Handle diagnostics notification."""
        uri = params.get("uri", "")
        diagnostics_data = params.get("diagnostics", [])
        
        diagnostics = []
        for diag_data in diagnostics_data:
            # Convert raw diagnostic data to Diagnostic object
            range_data = diag_data.get("range", {})
            start_pos = range_data.get("start", {})
            end_pos = range_data.get("end", {})
            
            diagnostic = Diagnostic(
                range=type('Range', (), {
                    'start': type('Position', (), {
                        'line': start_pos.get('line', 0),
                        'character': start_pos.get('character', 0)
                    })(),
                    'end': type('Position', (), {
                        'line': end_pos.get('line', 0),
                        'character': end_pos.get('character', 0)
                    })()
                })(),
                message=diag_data.get("message", ""),
                severity=DiagnosticSeverity(diag_data.get("severity", 1)),
                code=diag_data.get("code"),
                source=diag_data.get("source"),
            )
            diagnostics.append(diagnostic)
        
        self.diagnostics[uri] = diagnostics

    # High-level LSP methods

    async def get_definition(self, file_path: str, line: int, character: int) -> List[Location]:
        """Get definition of symbol at the given position."""
        params = asdict(create_text_document_position_params(file_path, line, character))
        result = await self._send_request("textDocument/definition", params)
        
        locations = []
        if isinstance(result, list):
            for loc_data in result:
                locations.append(Location(
                    uri=loc_data.get("uri", ""),
                    range=type('Range', (), {
                        'start': type('Position', (), loc_data.get("range", {}).get("start", {}))(),
                        'end': type('Position', (), loc_data.get("range", {}).get("end", {}))()
                    })()
                ))
        elif isinstance(result, dict):
            locations.append(Location(
                uri=result.get("uri", ""),
                range=type('Range', (), {
                    'start': type('Position', (), result.get("range", {}).get("start", {}))(),
                    'end': type('Position', (), result.get("range", {}).get("end", {}))()
                })()
            ))
        
        return locations

    async def get_references(self, file_path: str, line: int, character: int, include_declaration: bool = True) -> List[Location]:
        """Get references to symbol at the given position."""
        params = {
            "textDocument": asdict(create_text_document_identifier(file_path)),
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration}
        }
        result = await self._send_request("textDocument/references", params)
        
        locations = []
        if isinstance(result, list):
            for loc_data in result:
                locations.append(Location(
                    uri=loc_data.get("uri", ""),
                    range=type('Range', (), {
                        'start': type('Position', (), loc_data.get("range", {}).get("start", {}))(),
                        'end': type('Position', (), loc_data.get("range", {}).get("end", {}))()
                    })()
                ))
        
        return locations

    async def get_hover(self, file_path: str, line: int, character: int) -> Optional[Hover]:
        """Get hover information for symbol at the given position."""
        params = asdict(create_text_document_position_params(file_path, line, character))
        result = await self._send_request("textDocument/hover", params)
        
        if not result:
            return None
        
        contents = result.get("contents", "")
        if isinstance(contents, list):
            contents = "\n".join(str(c) for c in contents)
        
        return Hover(contents=contents)

    async def rename_symbol(self, file_path: str, line: int, character: int, new_name: str) -> Optional[WorkspaceEdit]:
        """Rename symbol at the given position."""
        params = {
            "textDocument": asdict(create_text_document_identifier(file_path)),
            "position": {"line": line, "character": character},
            "newName": new_name
        }
        result = await self._send_request("textDocument/rename", params)
        
        if not result:
            return None
        
        return WorkspaceEdit(changes=result.get("changes", {}))

    async def get_code_actions(self, file_path: str, start_line: int, start_char: int, end_line: int, end_char: int) -> List[CodeAction]:
        """Get code actions for the given range."""
        params = {
            "textDocument": asdict(create_text_document_identifier(file_path)),
            "range": {
                "start": {"line": start_line, "character": start_char},
                "end": {"line": end_line, "character": end_char}
            },
            "context": {"diagnostics": []}
        }
        result = await self._send_request("textDocument/codeAction", params)
        
        actions = []
        if isinstance(result, list):
            for action_data in result:
                actions.append(CodeAction(
                    title=action_data.get("title", ""),
                    kind=action_data.get("kind"),
                    edit=WorkspaceEdit(changes=action_data.get("edit", {}).get("changes", {})) if action_data.get("edit") else None
                ))
        
        return actions

    async def get_diagnostics(self, file_path: str) -> List[Diagnostic]:
        """Get diagnostics for the given file."""
        uri = f"file://{file_path}" if not file_path.startswith("file://") else file_path
        return self.diagnostics.get(uri, [])

    async def did_open(self, file_path: str, language_id: str = "python") -> None:
        """Notify server that a text document was opened."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        params = {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": language_id,
                "version": 1,
                "text": content
            }
        }
        await self._send_notification("textDocument/didOpen", params)

    async def did_close(self, file_path: str) -> None:
        """Notify server that a text document was closed."""
        params = {
            "textDocument": asdict(create_text_document_identifier(file_path))
        }
        await self._send_notification("textDocument/didClose", params)