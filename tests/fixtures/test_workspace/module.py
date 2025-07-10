"""Module file for cross-file reference testing."""

from sample import Calculator, process_data


class DataProcessor:
    """A data processing class."""
    
    def __init__(self):
        self.calc = Calculator("processor")
    
    def process_numbers(self, numbers: list[int]) -> int:
        """Process numbers using the calculator."""
        return self.calc.multiply(numbers)


def format_output(data: list[str]) -> str:
    """Format output using imported function."""
    processed = process_data(data)
    return f"Formatted: {processed}"


# Cross-file usage
processor = DataProcessor()
formatted = format_output(["test", "data"])