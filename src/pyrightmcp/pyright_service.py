import json
import os
import subprocess
from pathlib import Path
from typing import Union

from pyrightmcp import model as m


def check_uv_installed() -> Union[bool, m.PyrightError]:
    """
    Check if uv is installed and available.

    Returns:
        Union[bool, PyrightError]: True if uv is available, or error.
    """
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return m.PyrightError(
            message="uv is not installed. Please install uv (https://github.com/astral-sh/uv) to use this tool."
        )
    except subprocess.TimeoutExpired:
        return m.PyrightError(message="Timeout checking uv installation")
    except Exception as e:
        return m.PyrightError(message=f"Error checking uv: {str(e)}")


def check_project_setup(project_path: Path) -> Union[bool, m.PyrightError]:
    """
    Check if the project is properly set up with pyproject.toml or setup.py.

    Args:
        project_path (Path): The project directory to check.

    Returns:
        Union[bool, PyrightError]: True if project is set up, or error.
    """
    pyproject_toml = project_path / "pyproject.toml"
    setup_py = project_path / "setup.py"
    
    if not (pyproject_toml.exists() or setup_py.exists()):
        return m.PyrightError(
            message=f"Project needs to be set up. No pyproject.toml or setup.py found in {project_path}. "
            f"Please run 'uv init' or create a proper Python project structure."
        )
    
    return True


def check_venv_exists(project_path: Path) -> Union[m.VenvStatus, m.PyrightError]:
    """
    Check if .venv directory exists in the project path.

    Args:
        project_path (Path): The project directory to check.

    Returns:
        Union[VenvStatus, PyrightError]: The virtual environment status or error.
    """
    if not project_path.exists():
        return m.PyrightError(message=f"Project path does not exist: {project_path}")

    venv_path = project_path / ".venv"
    exists = venv_path.exists() and venv_path.is_dir()

    return m.VenvStatus(exists=exists, path=venv_path, activated=False)


def install_pyright(venv_path: Path) -> Union[bool, m.PyrightError]:
    """
    Install pyright-langserver in the virtual environment using uv.

    Args:
        venv_path (Path): Path to the virtual environment.

    Returns:
        Union[bool, PyrightError]: True if successful, or error.
    """
    try:
        result = subprocess.run(
            ["uv", "add", "pyright"],
            cwd=venv_path.parent,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return m.PyrightError(message=f"Failed to install pyright: {result.stderr}")

        return True
    except subprocess.TimeoutExpired:
        return m.PyrightError(message="Timeout installing pyright")
    except Exception as e:
        return m.PyrightError(message=f"Error installing pyright: {str(e)}")


def check_pyright_installed(project_path: Path) -> Union[bool, m.PyrightError]:
    """
    Check if pyright is installed in the project environment.

    Args:
        project_path (Path): The project directory.

    Returns:
        Union[bool, PyrightError]: True if installed, False if not, or error.
    """
    try:
        result = subprocess.run(
            ["uv", "run", "pyright", "--version"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return m.PyrightError(message="Timeout checking pyright installation")
    except Exception as e:
        return m.PyrightError(message=f"Error checking pyright: {str(e)}")


def ensure_pyright_config(project_path: Path) -> Union[bool, m.PyrightError]:
    """
    Ensure pyrightconfig.json exists with reportUnusedImport set to warning.

    Args:
        project_path (Path): The project root directory.

    Returns:
        Union[bool, PyrightError]: True if config exists/created, or error.
    """
    config_path = project_path / "pyrightconfig.json"
    
    if config_path.exists():
        return True
    
    try:
        config = {
            "reportUnusedImport": "warning"
        }
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        return m.PyrightError(message=f"Error creating pyrightconfig.json: {str(e)}")


def run_pyright_on_directory(
    project_path: Path, target_dir: Path
) -> Union[m.PyrightResult, m.PyrightError]:
    """
    Run pyright on the specified directory within the project.

    Args:
        project_path (Path): The project root directory.
        target_dir (Path): The directory to run pyright on.

    Returns:
        Union[PyrightResult, PyrightError]: The pyright result or error.
    """
    if not target_dir.exists():
        return m.PyrightError(message=f"Target directory does not exist: {target_dir}")

    if not target_dir.is_relative_to(project_path):
        return m.PyrightError(
            message=f"Target directory {target_dir} is not within project {project_path}"
        )

    config_result = ensure_pyright_config(project_path)
    if isinstance(config_result, m.PyrightError):
        return config_result

    try:
        env = {"PYTHONPATH": str(project_path)}

        result = subprocess.run(
            ["uv", "run", "pyright", "--warnings", str(target_dir)],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, **env},
        )

        return m.PyrightResult(
            output=result.stdout + result.stderr,
            exit_code=result.returncode,
            directory=target_dir,
        )
    except subprocess.TimeoutExpired:
        return m.PyrightError(message="Timeout running pyright")
    except Exception as e:
        return m.PyrightError(message=f"Error running pyright: {str(e)}")


def setup_and_run_pyright(
    project_path: Path, target_dir: Path
) -> Union[m.PyrightResult, m.PyrightError]:
    """
    Complete setup and execution of pyright on a directory.

    Args:
        project_path (Path): The project root directory.
        target_dir (Path): The directory to run pyright on.

    Returns:
        Union[PyrightResult, PyrightError]: The pyright result or error.
    """
    # Check if uv is installed
    uv_check = check_uv_installed()
    if isinstance(uv_check, m.PyrightError):
        return uv_check

    # Check if project is properly set up
    project_setup = check_project_setup(project_path)
    if isinstance(project_setup, m.PyrightError):
        return project_setup

    venv_status = check_venv_exists(project_path=project_path)
    match venv_status:
        case m.PyrightError() as error:
            return error
        case m.VenvStatus() as status:
            if not status.exists:
                return m.PyrightError(
                    message=f"Virtual environment not found at {status.path}"
                )
        case _ as unreachable:
            assert False, f"Unreachable: {unreachable}"

    pyright_installed = check_pyright_installed(project_path=project_path)
    match pyright_installed:
        case m.PyrightError() as error:
            return error
        case bool() as installed:
            if not installed:
                install_result = install_pyright(venv_path=venv_status.path)
                match install_result:
                    case m.PyrightError() as error:
                        return error
                    case bool():
                        pass
                    case _ as unreachable:
                        assert False, f"Unreachable: {unreachable}"
        case _ as unreachable:
            assert False, f"Unreachable: {unreachable}"

    return run_pyright_on_directory(project_path=project_path, target_dir=target_dir)

