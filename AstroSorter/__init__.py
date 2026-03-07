"""
AstroSorter - Astrophotography Image Classifier
Automatic sorting of astrophotography images into calibration types
"""

from .version import VERSION

__version__ = VERSION
__author__ = "AstroSorter Team"
__license__ = "MIT"

from .classifier import ImageMetadata, ImageType, classify_directory, get_summary
from .main import main

__all__ = [
    "ImageMetadata",
    "ImageType",
    "classify_directory",
    "get_summary",
    "main"
]
