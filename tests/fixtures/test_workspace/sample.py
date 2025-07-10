"""Sample Python file for testing pyrightmcp functionality."""

from typing import List


def calculate_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle."""
    return length * width


class Calculator:
    """A simple calculator class."""
    
    def __init__(self, name: str):
        self.name = name
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def multiply(self, numbers: List[int]) -> int:
        """Multiply a list of numbers."""
        result = 1
        for num in numbers:
            result *= num
        return result


def process_data(data: List[str]) -> str:
    """Process a list of strings."""
    return ", ".join(data)


# Variables for testing
user_name: str = "test_user"
age: int = 25
is_active: bool = True

# Function calls for references
calc = Calculator("test")
area = calculate_area(10.0, 5.0)
result = calc.add(1, 2)
processed = process_data(["hello", "world"])