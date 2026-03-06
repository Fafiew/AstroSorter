"""
AstroSorter - Astrophotography Image Classifier
Automatic sorting of astrophotography images into calibration types
"""

__version__ = "1.0.1"
__author__ = "AstroSorter Team"
__license__ = "MIT"

from .classifier import AstroClassifier, BatchClassifier, ImageMetadata, ImageType
from .main import AstroSorterApp, main

VERSION = "1.0.1"

__all__ = [
    "AstroClassifier",
    "BatchClassifier", 
    "ImageMetadata",
    "ImageType",
    "AstroSorterApp",
    "main"
]
