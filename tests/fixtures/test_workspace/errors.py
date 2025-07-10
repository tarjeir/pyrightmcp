"""File with intentional type errors for diagnostics testing."""

def function_with_errors():
    """Function with various type errors."""
    # Type error: cannot assign int to str
    name: str = 123
    
    # Type error: undefined variable
    result = undefined_variable + 5
    
    # Type error: wrong argument type
    numbers = [1, 2, 3]
    length = len("not a list")
    
    # Type error: attribute doesn't exist
    text = "hello"
    upper_text = text.non_existent_method()
    
    return name, result, length, upper_text


def unused_function():
    """Function that is never called."""
    unused_variable = "this is unused"
    return unused_variable


# Unused import
import os
import sys

# Using undefined variable
invalid_usage = some_undefined_variable