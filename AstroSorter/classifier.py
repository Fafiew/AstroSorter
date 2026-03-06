"""
AstroSorter - Core Classification Engine
Automatic classification of astrophotography calibration frames
"""

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import struct

import numpy as np
from PIL import Image
from PIL.TiffImagePlugin import TiffTags
from tqdm import tqdm


class ImageType(Enum):
    """Astrophotography image types"""
    LIGHT = "Lights"
    DARK = "Darks"
    FLAT = "Flats"
    BIAS = "Biases"
    FLAT_DARK = "Flat-Darks"
    UNKNOWN = "Unknown"


@dataclass
class ImageMetadata:
    """Metadata extracted from image file"""
    filename: str
    filepath: str
    file_ext: str
    
    # Classification metadata
    imagetyp: Optional[str] = None
    exposure_time: Optional[float] = None
    iso: Optional[int] = None
    filter_name: Optional[str] = None
    ccd_temp: Optional[float] = None
    object_name: Optional[str] = None
    binning: Optional[str] = None
    camera: Optional[str] = None
    date_obs: Optional[str] = None
    
    # Image statistics (computed)
    mean: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    
    # Classification result
    classified_type: ImageType = ImageType.UNKNOWN
    confidence: float = 0.0
    
    # Error tracking
    error: Optional[str] = None


# RAW file extensions for major camera brands
RAW_EXTENSIONS = {
    '.cr2', '.cr3', '.crw',  # Canon
    '.nef', '.nrw',          # Nikon
    '.arw', '.sr2', '.srf',  # Sony
    '.raf',                   # Fujifilm
    '.dng',                   # Adobe DNG / Digital Negative
    '.orf',                    # Olympus
    '.rw2',                    # Panasonic
    '.pef',                    # Pentax
    '.srw',                    # Samsung
    '.3fr',                    # Hasselblad
    '.iiq',                    # Phase One
    '.rwl',                    # Leica
    '.x3f',                    # Sigma
    '.kdc',                    # Kodak
    '.dcr',                    # Kodak
    '.erf',                    # Epson
    '.mef',                    # Mamiya
    '.mdc',                    # Minolta
    '.mos',                   # Leaf
    '.raw',                   # Generic
}

# FITS file extensions
FITS_EXTENSIONS = {'.fit', '.fits', '.fts'}

# All supported image extensions
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | FITS_EXTENSIONS | {'.tif', '.tiff', '.jpg', '.jpeg', '.png'}


class AstroClassifier:
    """
    Main classifier for astrophotography images.
    Uses metadata analysis with image statistics as fallback.
    """
    
    # Classification thresholds
    BIAS_MAX_EXPOSURE = 0.01  # seconds
    FLAT_MIN_EXPOSURE = 0.01
    FLAT_MAX_EXPOSURE = 10.0
    LIGHT_MIN_EXPOSURE = 10.0
    
    # Image statistics thresholds (for fallback classification)
    BIAS_MAX_MEAN = 2500
    FLAT_MEAN_MIN = 8000
    FLAT_MEAN_MAX = 45000
    DARK_MEAN_MIN = 2500
    DARK_MEAN_MAX = 40000
    
    def __init__(self, use_rawpy: bool = True):
        self.use_rawpy = use_rawpy
        self._rawpy = None
        self._try_import_rawpy()
    
    def _try_import_rawpy(self):
        """Try to import rawpy for RAW file support"""
        try:
            import rawpy
            self._rawpy = rawpy
        except ImportError:
            self.use_rawpy = False
    
    def is_supported(self, filepath: str) -> bool:
        """Check if file extension is supported"""
        ext = Path(filepath).suffix.lower()
        return ext in SUPPORTED_EXTENSIONS
    
    def classify_file(self, filepath: str, compute_stats: bool = True) -> ImageMetadata:
        """
        Classify a single image file.
        
        Args:
            filepath: Path to the image file
            compute_stats: Whether to compute image statistics (slower but more accurate)
        
        Returns:
            ImageMetadata with classification results
        """
        path = Path(filepath)
        ext = path.suffix.lower()
        
        metadata = ImageMetadata(
            filename=path.name,
            filepath=str(path.absolute()),
            file_ext=ext
        )
        
        try:
            # Try to read metadata based on file type
            if ext in FITS_EXTENSIONS:
                self._read_fits_metadata(metadata)
            elif ext in RAW_EXTENSIONS:
                self._read_raw_metadata(metadata, compute_stats)
            elif ext in {'.tif', '.tiff', '.jpg', '.jpeg', '.png'}:
                self._read_standard_metadata(metadata, compute_stats)
            else:
                metadata.error = f"Unsupported file type: {ext}"
                return metadata
            
            # Classify based on metadata
            self._classify_from_metadata(metadata)
            
            # If classification is unknown, try image statistics
            if metadata.classified_type == ImageType.UNKNOWN and compute_stats:
                self._classify_from_statistics(metadata)
                
        except Exception as e:
            metadata.error = str(e)
        
        return metadata
    
    def _read_fits_metadata(self, metadata: ImageMetadata):
        """Read metadata from FITS files"""
        try:
            from astropy.io import fits
            
            with fits.open(metadata.filepath) as hdul:
                header = hdul[0].header
                
                # Read FITS standard keywords
                metadata.imagetyp = header.get('IMAGETYP') or header.get('IMAGETYPE')
                metadata.exposure_time = header.get('EXPTIME') or header.get('EXPOSURE')
                metadata.iso = header.get('ISO') or header.get('GAIN') or header.get('EGAIN')
                metadata.filter_name = header.get('FILTER') or header.get('FILTER1')
                metadata.ccd_temp = header.get('CCD-TEMP') or header.get('SET-TEMP') or header.get('DET-TEMP')
                metadata.object_name = header.get('OBJECT')
                metadata.binning = header.get('XBINNING') or header.get('YBINNING')
                metadata.camera = header.get('INSTRUME') or header.get('CAMERA')
                metadata.date_obs = header.get('DATE-OBS') or header.get('DATE-OBS')
                
        except ImportError:
            # Fallback: try to read basic FITS header manually
            self._read_fits_basic(metadata)
        except Exception as e:
            # Try basic read
            try:
                self._read_fits_basic(metadata)
            except:
                metadata.error = f"FITS read error: {e}"
    
    def _read_fits_basic(self, metadata: ImageMetadata):
        """Basic FITS header reading without astropy"""
        with open(metadata.filepath, 'rb') as f:
            # Skip to end of primary header (2880 bytes typical)
            f.seek(0)
            header_data = f.read(2880)
            
            # Parse SIMPLE keyword
            if not header_data.startswith(b'SIMPLE'):
                return
            
            # Find END keyword and extract useful headers
            header_text = header_data.decode('ascii', errors='ignore')
            
            # Simple keyword parsing
            for line in header_text.split('\n'):
                if '=' in line and '/' in line:
                    key = line.split('=')[0].strip()
                    value = line.split('=')[1].split('/')[0].strip().strip("'")
                    
                    if key == 'IMAGETYP':
                        metadata.imagetyp = value
                    elif key == 'EXPTIME' and metadata.exposure_time is None:
                        try:
                            metadata.exposure_time = float(value)
                        except:
                            pass
                    elif key == 'FILTER':
                        metadata.filter_name = value
                    elif key == 'OBJECT':
                        metadata.object_name = value
                    elif key == 'ISO':
                        try:
                            metadata.iso = int(value)
                        except:
                            pass
    
    def _read_raw_metadata(self, metadata: ImageMetadata, compute_stats: bool = True):
        """Read metadata from RAW files (Canon, Nikon, Sony, etc.)"""
        
        # First try EXIF extraction
        self._read_exif_metadata(metadata)
        
        # If rawpy is available and we need stats, use it
        if compute_stats and self._rawpy:
            try:
                with self._rawpy.imread(metadata.filepath) as raw:
                    # Get basic info
                    if metadata.iso is None:
                        metadata.iso = raw.iso
                    
                    # Compute statistics from RAW data
                    raw_data = raw.raw_image_visible.astype(np.float32)
                    metadata.mean = float(np.mean(raw_data))
                    metadata.std = float(np.std(raw_data))
                    metadata.min_val = float(np.min(raw_data))
                    metadata.max_val = float(np.max(raw_data))
            except Exception:
                pass
        
        # Try reading embedded thumbnail for basic stats
        if metadata.mean is None:
            try:
                with Image.open(metadata.filepath) as img:
                    # Convert to grayscale for analysis
                    gray = img.convert('L')
                    arr = np.array(gray, dtype=np.float32)
                    metadata.mean = float(np.mean(arr))
                    metadata.std = float(np.std(arr))
                    metadata.min_val = float(np.min(arr))
                    metadata.max_val = float(np.max(arr))
            except Exception:
                pass
    
    def _read_standard_metadata(self, metadata: ImageMetadata, compute_stats: bool = True):
        """Read metadata from standard image formats (TIFF, JPEG, PNG)"""
        
        # Read EXIF data
        self._read_exif_metadata(metadata)
        
        # Compute statistics if requested
        if compute_stats:
            try:
                with Image.open(metadata.filepath) as img:
                    # Handle multi-page images (like TIFF stacks)
                    if hasattr(img, 'n_frames') and img.n_frames > 1:
                        # For multi-page TIFF, use first frame
                        img.seek(0)
                    
                    # Convert to grayscale
                    gray = img.convert('L')
                    arr = np.array(gray, dtype=np.float32)
                    
                    metadata.mean = float(np.mean(arr))
                    metadata.std = float(np.std(arr))
                    metadata.min_val = float(np.min(arr))
                    metadata.max_val = float(np.max(arr))
            except Exception as e:
                metadata.error = f"Stats error: {e}"
    
    def _read_exif_metadata(self, metadata: ImageMetadata):
        """Read EXIF metadata from image files"""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            with Image.open(metadata.filepath) as img:
                exif_data = img._getexif()
                if not exif_data:
                    return
                
                # Try to get EXIF tag map
                try:
                    exif_tag_map = img.tag_v2
                except:
                    exif_tag_map = {}
                
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    if tag == 'ExposureTime':
                        # Exposure time as fraction
                        if isinstance(value, tuple):
                            metadata.exposure_time = value[0] / value[1] if value[1] else 0
                        else:
                            metadata.exposure_time = float(value)
                    elif tag == 'ISOSpeedRatings':
                        metadata.iso = int(value) if value else None
                    elif tag == 'Model':
                        metadata.camera = value
                    elif tag == 'DateTimeOriginal':
                        metadata.date_obs = value
                
                # Also check EXIF for exposure time in different format
                # Some cameras store it differently
                if metadata.exposure_time is None:
                    # Try to find it in the tag map directly
                    for tag in [34855, 34866]:  # ISO tags
                        if tag in exif_tag_map:
                            metadata.iso = int(exif_tag_map[tag])
                            
        except Exception:
            # EXIF reading may fail, that's okay
            pass
    
    def _classify_from_metadata(self, metadata: ImageMetadata):
        """Classify image based on metadata"""
        
        # Priority 1: Explicit IMAGETYP header (most reliable for FITS)
        if metadata.imagetyp:
            imagetyp_lower = metadata.imagetyp.lower().strip()
            
            if imagetyp_lower in ('light', 'object', 'science', 'target'):
                metadata.classified_type = ImageType.LIGHT
                metadata.confidence = 1.0
                return
            elif imagetyp_lower in ('dark', 'dark frame'):
                metadata.classified_type = ImageType.DARK
                metadata.confidence = 1.0
                return
            elif imagetyp_lower in ('flat', 'flat field', 'flatfield'):
                metadata.classified_type = ImageType.FLAT
                metadata.confidence = 1.0
                return
            elif imagetyp_lower in ('bias', 'bias frame', 'offset'):
                metadata.classified_type = ImageType.BIAS
                metadata.confidence = 1.0
                return
            elif imagetyp_lower in ('darkflat', 'flat dark', 'dark flat'):
                metadata.classified_type = ImageType.FLAT_DARK
                metadata.confidence = 1.0
                return
        
        # Priority 2: Check object name for lights
        if metadata.object_name and metadata.object_name.strip():
            # Has object name, likely a light
            if metadata.exposure_time and metadata.exposure_time >= self.LIGHT_MIN_EXPOSURE:
                metadata.classified_type = ImageType.LIGHT
                metadata.confidence = 0.9
                return
        
        # Priority 3: Exposure time based classification
        if metadata.exposure_time is not None:
            
            # BIAS: Very short exposure, typically ≤ 0.01s
            if metadata.exposure_time <= self.BIAS_MAX_EXPOSURE:
                metadata.classified_type = ImageType.BIAS
                metadata.confidence = 0.85
                return
            
            # FLAT: Short exposure, often with filter
            elif metadata.exposure_time <= self.FLAT_MAX_EXPOSURE:
                # Flats typically have filter information
                if metadata.filter_name or (metadata.exposure_time >= self.FLAT_MIN_EXPOSURE):
                    metadata.classified_type = ImageType.FLAT
                    metadata.confidence = 0.8
                    return
                # Could also be bias at higher exposures
                elif metadata.exposure_time <= 1.0:
                    metadata.classified_type = ImageType.BIAS
                    metadata.confidence = 0.7
                    return
            
            # LIGHT or DARK: Long exposure (> 10s)
            elif metadata.exposure_time >= self.LIGHT_MIN_EXPOSURE:
                # No object name suggests dark frame
                if not metadata.object_name or not metadata.object_name.strip():
                    metadata.classified_type = ImageType.DARK
                    metadata.confidence = 0.75
                    return
                else:
                    metadata.classified_type = ImageType.LIGHT
                    metadata.confidence = 0.8
                    return
        
        # Priority 4: Filename pattern analysis
        classified_from_filename = self._classify_from_filename(metadata)
        if classified_from_filename:
            return
        
        # Cannot determine from metadata
        metadata.classified_type = ImageType.UNKNOWN
        metadata.confidence = 0.0
    
    def _classify_from_filename(self, metadata: ImageMetadata) -> bool:
        """Try to classify based on filename patterns"""
        
        filename_lower = metadata.filename.lower()
        
        # Common filename patterns for astrophotography
        bias_patterns = ['bias', 'bias_', '_bias', 'offset', 'bdf', 'darkb', 'master_bias']
        dark_patterns = ['dark', 'dark_', '_dark', 'darks', 'darkframe', 'master_dark', 'tdark']
        flat_patterns = ['flat', 'flat_', '_flat', 'flats', 'flatfield', 'master_flat', 'tflat', 'flatdark']
        light_patterns = ['light', 'light_', '_light', 'lights', 'lightframe', 'target', 'obj_', 'm31', 'm42', 'ngc', 'ic_', 'messier']
        
        for pattern in bias_patterns:
            if pattern in filename_lower:
                metadata.classified_type = ImageType.BIAS
                metadata.confidence = max(metadata.confidence, 0.7)
                return True
        
        for pattern in dark_patterns:
            if pattern in filename_lower:
                metadata.classified_type = ImageType.DARK
                metadata.confidence = max(metadata.confidence, 0.7)
                return True
        
        for pattern in flat_patterns:
            if 'dark' in pattern and 'flat' in filename_lower:
                # Check for flat-dark specifically
                if 'flatdark' in filename_lower or 'darkflat' in filename_lower:
                    metadata.classified_type = ImageType.FLAT_DARK
                    metadata.confidence = max(metadata.confidence, 0.7)
                    return True
            if pattern in filename_lower:
                metadata.classified_type = ImageType.FLAT
                metadata.confidence = max(metadata.confidence, 0.7)
                return True
        
        for pattern in light_patterns:
            if pattern in filename_lower:
                metadata.classified_type = ImageType.LIGHT
                metadata.confidence = max(metadata.confidence, 0.6)
                return True
        
        return False
    
    def _classify_from_statistics(self, metadata: ImageMetadata):
        """Fallback classification using image statistics"""
        
        if metadata.mean is None:
            # Can't classify without stats
            return
        
        mean = metadata.mean
        
        # Use mean ADU to help classify
        # These are approximate values and depend on bit depth and camera
        
        # Very low mean - likely bias
        if mean < self.BIAS_MAX_MEAN:
            if metadata.classified_type == ImageType.UNKNOWN:
                metadata.classified_type = ImageType.BIAS
                metadata.confidence = 0.5
        
        # Medium mean with filter likely flat
        elif self.FLAT_MEAN_MIN <= mean <= self.FLAT_MEAN_MAX:
            if metadata.filter_name and metadata.classified_type == ImageType.UNKNOWN:
                metadata.classified_type = ImageType.FLAT
                metadata.confidence = 0.6
        
        # High mean could be dark or light
        elif mean > self.FLAT_MEAN_MAX:
            # If exposure is long, likely dark or light
            if metadata.exposure_time and metadata.exposure_time >= self.LIGHT_MIN_EXPOSURE:
                if metadata.object_name:
                    metadata.classified_type = ImageType.LIGHT
                    metadata.confidence = max(metadata.confidence, 0.5)
                else:
                    metadata.classified_type = ImageType.DARK
                    metadata.confidence = max(metadata.confidence, 0.5)


class BatchClassifier:
    """Batch classifier for processing multiple files"""
    
    def __init__(self, classifier: AstroClassifier = None):
        self.classifier = classifier or AstroClassifier()
        self.results: list[ImageMetadata] = []
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def scan_directory(self, directory: str, recursive: bool = True) -> list[str]:
        """Scan directory for supported image files"""
        
        image_files = []
        path = Path(directory)
        
        if recursive:
            for ext in SUPPORTED_EXTENSIONS:
                image_files.extend(path.rglob(f'*{ext}'))
                image_files.extend(path.rglob(f'*{ext.upper()}'))
        else:
            for ext in SUPPORTED_EXTENSIONS:
                image_files.extend(path.glob(f'*{ext}'))
                image_files.extend(path.glob(f'*{ext.upper()}'))
        
        # Convert to strings and remove duplicates
        return list(set(str(f) for f in image_files))
    
    def classify_directory(self, directory: str, recursive: bool = True,
                          compute_stats: bool = True) -> list[ImageMetadata]:
        """
        Classify all images in a directory.
        
        Args:
            directory: Path to directory containing images
            recursive: Whether to scan subdirectories
            compute_stats: Whether to compute image statistics
        
        Returns:
            List of ImageMetadata objects with classification results
        """
        
        # Scan for files
        files = self.scan_directory(directory, recursive)
        total = len(files)
        
        self.results = []
        
        for i, filepath in enumerate(tqdm(files, desc="Classifying images")):
            metadata = self.classifier.classify_file(filepath, compute_stats)
            self.results.append(metadata)
            
            # Call progress callback
            if self.progress_callback:
                self.progress_callback(i + 1, total, filepath)
        
        return self.results
    
    def get_by_type(self, image_type: ImageType) -> list[ImageMetadata]:
        """Get all files of a specific type"""
        return [r for r in self.results if r.classified_type == image_type]
    
    def get_summary(self) -> dict:
        """Get classification summary"""
        summary = {
            'total': len(self.results),
            'by_type': {},
            'errors': 0
        }
        
        for img_type in ImageType:
            count = len(self.get_by_type(img_type))
            if count > 0:
                summary['by_type'][img_type.value] = count
        
        summary['errors'] = len([r for r in self.results if r.error])
        
        return summary
