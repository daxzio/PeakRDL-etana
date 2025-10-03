"""
HWIF Wrapper Generator - Standalone Tool
Generates wrapper modules that flatten hwif structs into individual signals
"""
from .generator import generate_wrapper

__version__ = "0.1.0"

__all__ = ["generate_wrapper"]
