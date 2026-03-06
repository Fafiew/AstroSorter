"""
AstroSorter - Astrophotography Image Classifier
Automatic sorting of astrophotography images into calibration types
"""

__version__ = "1.0.1"
__author__ = "AstroSorter Team"
__license__ = "MIT"

from .version import VERSION
from .classifier import ImageMetadata, ImageType, classify_directory, get_summary
from .main import main

__all__ = [
    "ImageMetadata",
    "ImageType",
    "classify_directory",
    "get_summary",
    "main"
]
