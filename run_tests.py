#!/usr/bin/env python3
"""Simple test runner for pyrightmcp"""

import subprocess
import sys
from pathlib import Path


def run_tests(test_file=None, verbose=True):
    """Run pytest with specified options."""
    cmd = ["uv", "run", "pytest"]
    
    if test_file:
        cmd.append(f"tests/{test_file}")
    else:
        cmd.append("tests/")
    
    if verbose:
        cmd.append("-v")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run pyrightmcp tests")
    parser.add_argument("test_file", nargs="?", help="Specific test file to run (e.g., test_basic_functionality.py)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Run with minimal output")
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    exit_code = run_tests(args.test_file, verbose)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())