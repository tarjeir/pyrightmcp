"""
LSP protocol types and dataclasses for communication with language servers.
Based on the Language Server Protocol specification.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum


@dataclass
class Position:
    """Position in a text document expressed as zero-based line and character offset."""
    line: int
    character: int


@dataclass
class Range:
    """A range in a text document expressed as (zero-based) start and end positions."""
    start: Position
    end: Position


@dataclass
class Location:
    """Represents a location inside a resource, such as a line inside a text file."""
    uri: str
    range: Range


@dataclass
class TextDocumentIdentifier:
    """A literal to identify a text document in the client."""
    uri: str


@dataclass
class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    """An identifier to denote a specific version of a text document."""
    version: int


@dataclass
class TextDocumentItem:
    """An item to transfer a text document from the client to the server."""
    uri: str
    language_id: str
    version: int
    text: str


@dataclass
class TextDocumentPositionParams:
    """A parameter literal used in requests to pass a text document and a position inside that document."""
    text_document: TextDocumentIdentifier
    position: Position


@dataclass
class ReferenceParams(TextDocumentPositionParams):
    """Parameters for a textDocument/references request."""
    context: Dict[str, Any]


@dataclass
class RenameParams(TextDocumentPositionParams):
    """Parameters for a textDocument/rename request."""
    new_name: str


@dataclass
class CodeActionParams:
    """Parameters for a textDocument/codeAction request."""
    text_document: TextDocumentIdentifier
    range: Range
    context: Dict[str, Any]


class DiagnosticSeverity(Enum):
    """The diagnostic's severity."""
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass
class Diagnostic:
    """Represents a diagnostic, such as a compiler error or warning."""
    range: Range
    message: str
    severity: Optional[DiagnosticSeverity] = None
    code: Optional[Union[int, str]] = None
    source: Optional[str] = None


@dataclass
class PublishDiagnosticsParams:
    """Parameters for a textDocument/publishDiagnostics notification."""
    uri: str
    diagnostics: List[Diagnostic]


@dataclass
class Hover:
    """The result of a hover request."""
    contents: Union[str, List[str]]
    range: Optional[Range] = None


@dataclass
class WorkspaceEdit:
    """A workspace edit represents changes to many resources managed in the workspace."""
    changes: Optional[Dict[str, List[Dict[str, Any]]]] = None


@dataclass
class TextEdit:
    """A textual edit applicable to a text document."""
    range: Range
    new_text: str


@dataclass
class CodeAction:
    """A code action represents a change that can be performed in code."""
    title: str
    kind: Optional[str] = None
    diagnostics: Optional[List[Diagnostic]] = None
    edit: Optional[WorkspaceEdit] = None
    command: Optional[Dict[str, Any]] = None


@dataclass
class InitializeParams:
    """Parameters for the initialize request."""
    process_id: Optional[int]
    root_path: Optional[str]
    root_uri: Optional[str]
    capabilities: Dict[str, Any]


@dataclass
class ServerCapabilities:
    """Server capabilities."""
    text_document_sync: Optional[Dict[str, Any]] = None
    hover_provider: Optional[bool] = None
    completion_provider: Optional[Dict[str, Any]] = None
    definition_provider: Optional[bool] = None
    references_provider: Optional[bool] = None
    rename_provider: Optional[bool] = None
    code_action_provider: Optional[bool] = None
    diagnostic_provider: Optional[Dict[str, Any]] = None


@dataclass
class InitializeResult:
    """Result of the initialize request."""
    capabilities: ServerCapabilities


@dataclass
class LSPRequest:
    """Generic LSP request."""
    id: Union[int, str]
    method: str
    params: Optional[Dict[str, Any]] = None


@dataclass
class LSPResponse:
    """Generic LSP response."""
    id: Union[int, str]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class LSPNotification:
    """Generic LSP notification."""
    method: str
    params: Optional[Dict[str, Any]] = None


# Helper functions for creating common LSP objects

def create_text_document_identifier(file_path: str) -> TextDocumentIdentifier:
    """Create a TextDocumentIdentifier from a file path."""
    uri = f"file://{file_path}" if not file_path.startswith("file://") else file_path
    return TextDocumentIdentifier(uri=uri)


def create_position(line: int, character: int) -> Position:
    """Create a Position (zero-based)."""
    return Position(line=line, character=character)


def create_range(start_line: int, start_char: int, end_line: int, end_char: int) -> Range:
    """Create a Range from start and end positions."""
    return Range(
        start=create_position(start_line, start_char),
        end=create_position(end_line, end_char)
    )


def create_text_document_position_params(file_path: str, line: int, character: int) -> TextDocumentPositionParams:
    """Create TextDocumentPositionParams from file path and position."""
    return TextDocumentPositionParams(
        text_document=create_text_document_identifier(file_path),
        position=create_position(line, character)
    )