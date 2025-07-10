"""LSP client for communicating with pyright-langserver."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import subprocess
import logging

from pyrightmcp import model as m

logger = logging.getLogger(__name__)


class LSPError(Exception):
    """LSP communication error."""
    pass


class LSPClient:
    """JSON-RPC client for pyright-langserver communication."""
    
    def __init__(self, project_path: Path, request_timeout: float = 30.0):
        self.project_path = project_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.initialized = False
        self.server_capabilities: Dict[str, Any] = {}
        self._read_task: Optional[asyncio.Task] = None
        self.request_timeout = request_timeout
        self._shutdown_event = asyncio.Event()
        self._startup_timeout = 30.0
        
    async def start(self) -> bool:
        """Start the pyright-langserver process."""
        try:
            # Use asyncio subprocess for proper async handling
            self.process = await asyncio.create_subprocess_exec(
                "uv", "run", "pyright-langserver", "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_path
            )
            
            # Start background task to read responses and track it
            self._read_task = asyncio.create_task(self._read_responses())
            
            # Initialize the LSP server with timeout
            try:
                await asyncio.wait_for(self._initialize(), timeout=self._startup_timeout)
                return True
            except asyncio.TimeoutError:
                logger.error(f"LSP server initialization timed out after {self._startup_timeout}s")
                await self.stop()
                return False
            
        except Exception as e:
            logger.error(f"Failed to start LSP server: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """Stop the LSP server."""
        # Set shutdown flag to prevent new requests
        self._shutdown_event.set()
        
        # Cancel all pending requests
        for request_id, future in list(self.pending_requests.items()):
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        # Cancel background read task first
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await asyncio.wait_for(self._read_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.error(f"Error cancelling read task: {e}")
        
        if self.process:
            try:
                # Try graceful shutdown first
                if self.initialized:
                    try:
                        # Temporarily clear shutdown flag to send exit notification
                        self._shutdown_event.clear()
                        await asyncio.wait_for(
                            self._send_notification("exit", {}), 
                            timeout=2.0
                        )
                        self._shutdown_event.set()
                    except (asyncio.TimeoutError, LSPError):
                        pass  # Continue with forceful shutdown
                    
                # Terminate the process
                self.process.terminate()
                
                try:
                    # Wait for process to terminate gracefully
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Force kill if it doesn't terminate
                    logger.warning("LSP server didn't terminate gracefully, forcing kill")
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.error("LSP server didn't respond to kill signal")
                    
            except Exception as e:
                logger.error(f"Error stopping LSP server: {e}")
            finally:
                self.process = None
                self.initialized = False
                self._read_task = None
    
    def _get_next_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Send a JSON-RPC request and wait for response."""
        if not self.process or not self.process.stdin:
            raise LSPError("LSP server not running")
        
        if self._shutdown_event.is_set():
            raise LSPError("LSP client is shutting down")
            
        request_id = self._get_next_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        logger.debug(f"Sending LSP request: {method} (id: {request_id})")
        logger.debug(f"Request params: {params}")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        # Send request
        try:
            await self._send_message(request)
            
            # Wait for response with configurable timeout
            response = await asyncio.wait_for(future, timeout=self.request_timeout)
            
            logger.debug(f"LSP response for {method} (id: {request_id}): {response}")
            
            if "error" in response:
                error_info = response["error"]
                error_msg = f"LSP error {error_info.get('code', 'unknown')}: {error_info.get('message', 'unknown error')}"
                logger.error(f"LSP error for {method}: {error_msg}")
                raise LSPError(error_msg)
                
            return response.get("result")
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise LSPError(f"Request {method} timed out after {self.request_timeout}s")
        except LSPError:
            self.pending_requests.pop(request_id, None)
            raise
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise LSPError(f"Request {method} failed: {e}")
    
    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        await self._send_message(notification)
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send a JSON-RPC message with proper headers."""
        if not self.process or not self.process.stdin:
            raise LSPError("LSP server not running")
            
        content = json.dumps(message, separators=(',', ':'))
        content_bytes = content.encode('utf-8')
        headers = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        
        full_message = headers.encode('utf-8') + content_bytes
        
        self.process.stdin.write(full_message)
        await self.process.stdin.drain()
    
    async def _read_responses(self):
        """Background task to read and process LSP responses."""
        if not self.process or not self.process.stdout:
            return
            
        try:
            while (self.process and 
                   self.process.returncode is None and 
                   not self._shutdown_event.is_set()):
                try:
                    # Read headers with timeout
                    headers = {}
                    while True:
                        try:
                            line_bytes = await asyncio.wait_for(
                                self.process.stdout.readline(), 
                                timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            # Check if we should continue or shutdown
                            if self._shutdown_event.is_set():
                                break
                            continue
                            
                        if not line_bytes:
                            return  # EOF
                        
                        line = line_bytes.decode('utf-8').strip()
                        if not line:
                            break  # Empty line signals end of headers
                            
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key.strip()] = value.strip()
                    
                    if self._shutdown_event.is_set():
                        break
                    
                    # Read content
                    content_length = int(headers.get('Content-Length', 0))
                    if content_length > 0:
                        try:
                            content_bytes = await asyncio.wait_for(
                                self.process.stdout.readexactly(content_length),
                                timeout=5.0
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Timeout reading LSP message content")
                            break
                            
                        content = content_bytes.decode('utf-8')
                        
                        try:
                            message = json.loads(content)
                            await self._handle_message(message)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse LSP message: {e}")
                            logger.debug(f"Raw content: {content}")
                
                except asyncio.IncompleteReadError:
                    # EOF reached
                    break
                except Exception as e:
                    if not self._shutdown_event.is_set():
                        logger.error(f"Error reading LSP message: {e}")
                    break
                        
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            logger.debug("LSP response reader cancelled")
        except Exception as e:
            logger.error(f"Error in LSP response reader: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming LSP message."""
        if "id" in message and message["id"] in self.pending_requests:
            # Response to our request
            future = self.pending_requests.pop(message["id"])
            future.set_result(message)
        elif "method" in message:
            # Notification from server
            logger.debug(f"LSP notification: {message['method']}")
    
    async def _initialize(self):
        """Initialize the LSP server."""
        init_params = {
            "processId": None,
            "rootUri": f"file://{self.project_path}",
            "capabilities": {
                "textDocument": {
                    "codeAction": {
                        "dynamicRegistration": True,
                        "codeActionLiteralSupport": {
                            "codeActionKind": {
                                "valueSet": [
                                    "quickfix",
                                    "refactor",
                                    "source.organizeImports"
                                ]
                            }
                        }
                    }
                }
            },
            "workspaceFolders": [{
                "uri": f"file://{self.project_path}",
                "name": self.project_path.name
            }]
        }
        
        result = await self._send_request("initialize", init_params)
        self.server_capabilities = result.get("capabilities", {})
        
        # Send initialized notification
        await self._send_notification("initialized", {})
        self.initialized = True
        
        logger.info("LSP server initialized successfully")
    
    async def open_document(self, file_path: Path) -> bool:
        """Open a document in the LSP server."""
        if not self.initialized:
            raise LSPError("LSP server not initialized")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            params = {
                "textDocument": {
                    "uri": f"file://{file_path}",
                    "languageId": "python",
                    "version": 1,
                    "text": content
                }
            }
            
            await self._send_notification("textDocument/didOpen", params)
            return True
            
        except Exception as e:
            logger.error(f"Failed to open document {file_path}: {e}")
            return False
    
    async def get_code_actions(
        self, 
        file_path: Path, 
        start_line: int = 0, 
        start_char: int = 0,
        end_line: int = 0, 
        end_char: int = 0,
        only: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get code actions for a range in a document."""
        if not self.initialized:
            raise LSPError("LSP server not initialized")
            
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "range": {
                "start": {"line": start_line, "character": start_char},
                "end": {"line": end_line, "character": end_char}
            },
            "context": {
                "diagnostics": [],
                "only": only or []
            }
        }
        
        logger.debug(f"Requesting code actions for {file_path} at {start_line}:{start_char}-{end_line}:{end_char}")
        logger.debug(f"Code action request params: {params}")
        
        result = await self._send_request("textDocument/codeAction", params)
        
        logger.debug(f"Code actions response: {result}")
        logger.info(f"Found {len(result or [])} code actions for {file_path}")
        
        return result or []
    
    async def organize_imports(self, file_path: Path) -> Union[m.PyrightResult, m.PyrightError]:
        """Organize imports in a Python file using LSP executeCommand."""
        try:
            logger.info(f"Starting organize imports for {file_path}")
            
            # Ensure document is open
            await self.open_document(file_path)
            
            # Try executeCommand approach first
            logger.debug("Trying executeCommand approach for organize imports")
            try:
                result = await self._send_request("workspace/executeCommand", {
                    "command": "pyright.organizeImports",
                    "arguments": [f"file://{file_path}"]
                })
                
                logger.debug(f"executeCommand organize imports result: {result}")
                
                if result is not None:
                    logger.info(f"Successfully organized imports for {file_path} using executeCommand")
                    return m.PyrightResult(
                        output="Imports organized successfully using executeCommand",
                        exit_code=0,
                        directory=file_path.parent
                    )
                    
            except Exception as e:
                logger.warning(f"executeCommand approach failed: {e}, falling back to codeAction")
            
            # Fallback to code action approach
            logger.debug("Falling back to codeAction approach")
            
            # Get document content to determine range
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.splitlines()
            end_line = len(lines) - 1 if lines else 0
            end_character = len(lines[-1]) if lines else 0
            
            # Send organize imports code action request directly
            logger.debug("Sending organize imports code action request")
            result = await self._send_request("textDocument/codeAction", {
                "textDocument": {"uri": f"file://{file_path}"},
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": end_line, "character": end_character}
                },
                "context": {
                    "diagnostics": [],
                    "only": ["source.organizeImports"]
                }
            })
            
            logger.debug(f"Organize imports response: {result}")
            
            if not result or not isinstance(result, list) or len(result) == 0:
                logger.warning(f"No organize imports action available for {file_path}. The result was {result}")
                return m.PyrightResult(
                    output="No organize imports action available",
                    exit_code=0,
                    directory=file_path.parent
                )
            
            # Apply the first organize imports action
            action = result[0]
            logger.debug(f"Applying organize imports action: {action}")
            
            if "edit" in action:
                await self._apply_workspace_edit(action["edit"])
                logger.info(f"Successfully organized imports for {file_path}")
                return m.PyrightResult(
                    output="Imports organized successfully",
                    exit_code=0,
                    directory=file_path.parent
                )
            
            logger.error(f"No workspace edit in organize imports action: {action}")
            return m.PyrightError(message="No workspace edit in organize imports action")
            
        except Exception as e:
            return m.PyrightError(message=f"Failed to organize imports: {e}")
    
    async def _apply_workspace_edit(self, edit: Dict[str, Any]):
        """Apply a workspace edit to files."""
        changes = edit.get("changes", {})
        
        for uri, edits in changes.items():
            if uri.startswith("file://"):
                file_path = Path(uri[7:])  # Remove file:// prefix
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Apply edits in reverse order to maintain positions
                    lines = content.splitlines(keepends=True)
                    
                    for edit_item in reversed(sorted(edits, key=lambda e: (e["range"]["start"]["line"], e["range"]["start"]["character"]))):
                        start_line = edit_item["range"]["start"]["line"]
                        start_char = edit_item["range"]["start"]["character"]
                        end_line = edit_item["range"]["end"]["line"]
                        end_char = edit_item["range"]["end"]["character"]
                        new_text = edit_item["newText"]
                        
                        # Apply the edit
                        if start_line == end_line:
                            # Single line edit
                            line = lines[start_line]
                            lines[start_line] = line[:start_char] + new_text + line[end_char:]
                        else:
                            # Multi-line edit
                            start_line_content = lines[start_line][:start_char]
                            end_line_content = lines[end_line][end_char:]
                            
                            # Replace the range with new text
                            new_lines = (start_line_content + new_text + end_line_content).splitlines(keepends=True)
                            lines[start_line:end_line + 1] = new_lines
                    
                    # Write the modified content back
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                        
                except Exception as e:
                    logger.error(f"Failed to apply edit to {file_path}: {e}")
                    raise
