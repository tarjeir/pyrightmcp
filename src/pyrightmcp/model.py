from dataclasses import dataclass
from pathlib import Path


@dataclass
class PyrightError:
    """Error type for pyright operations."""
    
    message: str


@dataclass
class PyrightResult:
    """Result from running pyright."""
    
    output: str
    exit_code: int
    directory: Path


@dataclass
class VenvStatus:
    """Status of virtual environment."""
    
    exists: bool
    path: Path
    activated: bool