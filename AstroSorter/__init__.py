"""
AstroSorter - Astrophotography Image Classifier
Automatic sorting of astrophotography images into calibration types
"""

__version__ = "1.0.1"
__author__ = "AstroSorter Team"
__license__ = "MIT"

from .classifier import ImageMetadata, ImageType, classify_directory, get_summary
from .main import main

VERSION = "1.1.2"

__all__ = [
    "ImageMetadata",
    "ImageType",
    "classify_directory",
    "get_summary",
    "main"
]
