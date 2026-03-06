"""
AstroSorter - Complete Classifier Rewrite
Better metadata extraction and classification
"""

import os
import struct
import json
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import exifread
import numpy as np
from PIL import Image
from tqdm import tqdm


class ImageType(Enum):
    """Astrophotography image types"""
    LIGHT = "Lights"
    DARK = "Darks"
    FLAT = "Flats"
    BIAS = "Biases"
    FLAT_DARK = "Flat-Darks"
    UNKNOWN = "Unknown"


# RAW extensions
RAW_EXTENSIONS = {
    '.cr2', '.cr3', '.crw', '.nef', '.nrw', '.arw', '.sr2', '.srf',
    '.raf', '.dng', '.orf', '.rw2', '.pef', '.srw', '.3fr', '.iiq',
    '.rwl', '.x3f', '.kdc', '.dcr', '.erf', '.mef', '.mdc', '.mos', '.raw'
}

FITS_EXTENSIONS = {'.fit', '.fits', '.fts'}
IMAGE_EXTENSIONS = RAW_EXTENSIONS | FITS_EXTENSIONS | {'.tif', '.tiff', '.jpg', '.jpeg', '.png'}


@dataclass
class ImageMetadata:
    """Complete metadata for an image"""
    filename: str
    filepath: str
    file_ext: str
    
    # File info
    file_size: int = 0
    
    # EXIF/FITS data
    exposure_time: Optional[float] = None
    iso: Optional[int] = None
    f_number: Optional[float] = None
    focal_length: Optional[float] = None
    lens_model: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    date_time: Optional[str] = None
    
    # Astro-specific
    object_name: Optional[str] = None
    filter_name: Optional[str] = None
    ccd_temp: Optional[float] = None
    imagetyp: Optional[str] = None
    
    # Computed statistics
    mean: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    
    # Classification
    classified_type: ImageType = ImageType.UNKNOWN
    confidence: float = 0.0
    
    # For sorting
    selected_type: Optional[str] = None
    
    error: Optional[str] = None


def get_file_size(filepath: str) -> int:
    """Get file size in bytes"""
    try:
        return os.path.getsize(filepath)
    except:
        return 0


def read_raw_exif(filepath: str) -> dict:
    """Read EXIF data from any file using multiple methods"""
    result = {}
    
    # Method 1: exifread (works for JPEG, TIFF, some RAW)
    try:
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            for tag, value in tags.items():
                result[tag] = str(value)
    except:
        pass
    
    return result


def parse_exposure_time(value: str) -> Optional[float]:
    """Parse exposure time from EXIF value"""
    if not value:
        return None
    try:
        if '/' in value:
            parts = value.split('/')
            return float(parts[0]) / float(parts[1])
        return float(value)
    except:
        return None


def parse_iso(value: str) -> Optional[int]:
    """Parse ISO from EXIF value"""
    if not value:
        return None
    try:
        if '/' in value:
            parts = value.split('/')
            return int(float(parts[0]) / float(parts[1]))
        return int(value)
    except:
        return None


def read_canon_exif(filepath: str) -> dict:
    """Read Canon-specific EXIF data"""
    result = {}
    try:
        with open(filepath, 'rb') as f:
            # Skip to end of JPEG/RAW header to find Canon Maker Note
            # This is a simplified version - full implementation would parse Canon format
            pass
    except:
        pass
    return result


def read_fits_metadata(filepath: str) -> dict:
    """Read FITS header metadata"""
    result = {}
    try:
        with open(filepath, 'rb') as f:
            # Read primary header (typically 2880 bytes)
            header_data = f.read(2880)
            
            if not header_data.startswith(b'SIMPLE'):
                return result
            
            # Parse header keywords
            lines = header_data.decode('ascii', errors='ignore').split('\n')
            for line in lines:
                if '=' in line and '/' in line:
                    key = line.split('=')[0].strip()
                    value = line.split('=')[1].split('/')[0].strip().strip("'")
                    
                    if key in ['EXPTIME', 'EXPOSURE', 'TELAPSE']:
                        try:
                            result['EXPOSURE'] = float(value)
                        except:
                            pass
                    elif key == 'IMAGETYP':
                        result['IMAGETYP'] = value.upper()
                    elif key == 'OBJECT':
                        result['OBJECT'] = value
                    elif key == 'FILTER':
                        result['FILTER'] = value
                    elif key == 'ISO' or key == 'GAIN':
                        try:
                            result['ISO'] = int(value)
                        except:
                            pass
                    elif key == 'CCD-TEMP' or key == 'DET-TEMP':
                        try:
                            result['CCD-TEMP'] = float(value)
                        except:
                            pass
                    elif key == 'INSTRUME':
                        result['INSTRUMENT'] = value
                    elif key == 'DATE-OBS':
                        result['DATE-OBS'] = value
                        
    except:
        pass
    
    return result


def extract_filename_info(filename: str) -> dict:
    """Extract info from filename patterns"""
    result = {}
    fn = filename.upper()
    
    # ISO patterns
    iso_patterns = ['ISO100', 'ISO200', 'ISO400', 'ISO800', 'ISO1600', 'ISO3200', 'ISO6400', 'ISO12800', 'ISO25600']
    for pattern in iso_patterns:
        if pattern in fn:
            result['ISO'] = int(pattern.replace('ISO', ''))
            break
    
    # Type patterns
    type_patterns = {
        'LIGHT': ['LIGHT_', '_LIGHT', 'LIGHT', 'OBJ_', 'TARGET_'],
        'DARK': ['DARK_', '_DARK', 'DARK', 'DARKS'],
        'FLAT': ['FLAT_', '_FLAT', 'FLAT', 'FLATS'],
        'BIAS': ['BIAS_', '_BIAS', 'BIAS', 'OFFSET_', '_OFFSET'],
        'FLAT-DARK': ['FLAT_DARK', 'DARK_FLAT', 'FLATDARK']
    }
    
    for img_type, patterns in type_patterns.items():
        for pattern in patterns:
            if pattern in fn:
                result['IMAGETYP'] = img_type
                break
    
    # Object name (common targets)
    targets = ['M31', 'M42', 'M13', 'M45', 'M51', 'M57', 'M27', 'M8', 'M20', 'NGC', 'IC_', 'MESSIER']
    for target in targets:
        if target in fn:
            result['OBJECT'] = target
            break
    
    return result


def compute_image_stats(filepath: str, file_ext: str) -> dict:
    """Compute image statistics"""
    result = {'mean': None, 'std': None, 'min': None, 'max': None}
    
    try:
        if file_ext in RAW_EXTENSIONS:
            # Try with rawpy first
            try:
                import rawpy
                with rawpy.imread(filepath) as raw:
                    # Get visible raw data
                    data = raw.raw_image_visible.astype(np.float32)
                    result['mean'] = float(np.mean(data))
                    result['std'] = float(np.std(data))
                    result['min'] = float(np.min(data))
                    result['max'] = float(np.max(data))
                    return result
            except:
                pass
        
        # Fallback to PIL (uses embedded thumbnail/preview)
        with Image.open(filepath) as img:
            # Try to get best quality
            if hasattr(img, '_getexif'):
                # Try 16-bit if available
                pass
            
            # Convert to grayscale
            gray = img.convert('L')
            arr = np.array(gray, dtype=np.float32)
            
            result['mean'] = float(np.mean(arr))
            result['std'] = float(np.std(arr))
            result['min'] = float(np.min(arr))
            result['max'] = float(np.max(arr))
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def classify_image(metadata: ImageMetadata) -> ImageType:
    """Classify image based on metadata"""
    
    # 1. Explicit IMAGETYP (FITS files)
    if metadata.imagetyp:
        typ = metadata.imagetyp.upper()
        if typ in ['LIGHT', 'OBJECT', 'SCIENCE', 'TARGET']:
            return ImageType.LIGHT
        elif typ in ['DARK', 'DARK FRAME']:
            return ImageType.DARK
        elif typ in ['FLAT', 'FLAT FIELD', 'FLATFIELD']:
            return ImageType.FLAT
        elif typ in ['BIAS', 'BIAS FRAME', 'OFFSET']:
            return ImageType.BIAS
        elif typ in ['DARKFLAT', 'FLAT DARK', 'DARK FLAT']:
            return ImageType.FLAT_DARK
    
    # 2. Object name present = Light
    if metadata.object_name and len(metadata.object_name.strip()) > 0:
        return ImageType.LIGHT
    
    # 3. Exposure time based classification
    exp = metadata.exposure_time
    
    if exp is not None:
        # Very short = Bias
        if exp <= 0.001:
            return ImageType.BIAS
        
        # Short with filter = Flat
        if metadata.filter_name and exp < 60:
            return ImageType.FLAT
        
        # Medium exposure no filter = could be dark
        if exp >= 1 and not metadata.filter_name:
            # Check statistics
            if metadata.mean is not None:
                # Dark frames have higher mean than bias but not as high as lights
                if metadata.mean < 3000:
                    return ImageType.BIAS
                elif metadata.mean < 10000:
                    return ImageType.DARK
                else:
                    return ImageType.LIGHT
            return ImageType.DARK
        
        # Long exposure = Light or Dark
        if exp >= 10:
            return ImageType.LIGHT
    
    # 4. Statistics-based classification
    if metadata.mean is not None:
        mean = metadata.mean
        
        # Very low mean = Bias
        if mean < 100:
            return ImageType.BIAS
        
        # Low-medium mean with no object = likely Dark
        if mean < 5000:
            return ImageType.DARK
        
        # Medium-high mean = could be Flat or Light
        if mean < 30000:
            if metadata.filter_name:
                return ImageType.FLAT
            return ImageType.LIGHT
        
        # Very high mean = Light
        return ImageType.LIGHT
    
    # 5. Fallback: can't determine
    return ImageType.UNKNOWN


def calculate_confidence(metadata: ImageMetadata) -> float:
    """Calculate classification confidence"""
    confidence = 0.0
    
    # Has explicit IMAGETYP = 100%
    if metadata.imagetyp:
        return 1.0
    
    # Has object name = high confidence
    if metadata.object_name:
        confidence = 0.9
    
    # Has filter = good indicator for flats
    elif metadata.filter_name:
        confidence = 0.85
    
    # Has exposure time
    if metadata.exposure_time is not None:
        if metadata.exposure_time <= 0.001:
            confidence = max(confidence, 0.9)  # Bias
        elif metadata.exposure_time >= 10:
            confidence = max(confidence, 0.8)  # Light/Dark
    
    # Has statistics
    if metadata.mean is not None:
        if metadata.mean < 100:
            confidence = max(confidence, 0.7)
        elif metadata.mean > 10000:
            confidence = max(confidence, 0.6)
    
    return confidence


def process_image(filepath: str) -> ImageMetadata:
    """Process a single image and return metadata"""
    path = Path(filepath)
    ext = path.suffix.lower()
    
    metadata = ImageMetadata(
        filename=path.name,
        filepath=str(path.absolute()),
        file_ext=ext,
        file_size=get_file_size(filepath)
    )
    
    try:
        # 1. Read EXIF/FITS data
        if ext in FITS_EXTENSIONS:
            fits_data = read_fits_metadata(filepath)
            metadata.exposure_time = fits_data.get('EXPOSURE')
            metadata.imagetyp = fits_data.get('IMAGETYP')
            metadata.object_name = fits_data.get('OBJECT')
            metadata.filter_name = fits_data.get('FILTER')
            metadata.ccd_temp = fits_data.get('CCD-TEMP')
            metadata.camera_model = fits_data.get('INSTRUMENT')
            metadata.date_time = fits_data.get('DATE-OBS')
            if 'ISO' in fits_data:
                metadata.iso = fits_data['ISO']
        
        # 2. Read standard EXIF (works for JPEG, TIFF, and embedded in some RAW)
        exif_data = read_raw_exif(filepath)
        
        if not metadata.exposure_time:
            if 'EXIF ExposureTime' in exif_data:
                metadata.exposure_time = parse_exposure_time(exif_data['EXIF ExposureTime'])
            elif 'Image ExposureTime' in exif_data:
                metadata.exposure_time = parse_exposure_time(exif_data['Image ExposureTime'])
        
        if not metadata.iso:
            if 'EXIF ISOSpeedRatings' in exif_data:
                metadata.iso = parse_iso(exif_data['EXIF ISOSpeedRatings'])
            elif 'Image ISOSpeedRatings' in exif_data:
                metadata.iso = parse_iso(exif_data['Image ISOSpeedRatings'])
        
        if not metadata.camera_model:
            if 'Image Model' in exif_data:
                metadata.camera_model = exif_data['Image Model']
        
        if not metadata.camera_make:
            if 'Image Make' in exif_data:
                metadata.camera_make = exif_data['Image Make']
        
        if not metadata.date_time:
            if 'EXIF DateTimeOriginal' in exif_data:
                metadata.date_time = exif_data['EXIF DateTimeOriginal']
            elif 'Image DateTime' in exif_data:
                metadata.date_time = exif_data['Image DateTime']
        
        if not metadata.focal_length:
            if 'EXIF FocalLength' in exif_data:
                metadata.focal_length = parse_exposure_time(exif_data['EXIF FocalLength'])
        
        if not metadata.f_number:
            if 'EXIF FNumber' in exif_data:
                metadata.f_number = parse_exposure_time(exif_data['EXIF FNumber'])
        
        # 3. Extract from filename
        filename_info = extract_filename_info(path.name)
        
        if not metadata.iso and 'ISO' in filename_info:
            metadata.iso = filename_info['ISO']
        
        if not metadata.imagetyp and 'IMAGETYP' in filename_info:
            metadata.imagetyp = filename_info['IMAGETYP']
        
        if not metadata.object_name and 'OBJECT' in filename_info:
            metadata.object_name = filename_info['OBJECT']
        
        # 4. Compute statistics
        stats = compute_image_stats(filepath, ext)
        metadata.mean = stats.get('mean')
        metadata.std = stats.get('std')
        metadata.min_val = stats.get('min')
        metadata.max_val = stats.get('max')
        
        # 5. Classify
        metadata.classified_type = classify_image(metadata)
        metadata.confidence = calculate_confidence(metadata)
        
    except Exception as e:
        metadata.error = str(e)
    
    return metadata


def scan_directory(directory: str, recursive: bool = True) -> List[str]:
    """Scan directory for image files"""
    path = Path(directory)
    files = []
    
    if recursive:
        for ext in IMAGE_EXTENSIONS:
            files.extend(path.rglob(f'*{ext}'))
            files.extend(path.rglob(f'*{ext.upper()}'))
    else:
        for ext in IMAGE_EXTENSIONS:
            files.extend(path.glob(f'*{ext}'))
            files.extend(path.glob(f'*{ext.upper()}'))
    
    return list(set(str(f) for f in files))


def classify_directory(directory: str, recursive: bool = True, 
                        progress_callback=None) -> List[ImageMetadata]:
    """Classify all images in a directory"""
    
    files = scan_directory(directory, recursive)
    results = []
    
    for i, filepath in enumerate(files):
        metadata = process_image(filepath)
        results.append(metadata)
        
        if progress_callback:
            progress_callback(i + 1, len(files), filepath)
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    """Get classification summary"""
    summary = {
        'total': len(results),
        'by_type': {},
        'errors': 0
    }
    
    for img_type in ImageType:
        count = sum(1 for r in results if r.classified_type == img_type)
        if count > 0:
            summary['by_type'][img_type.value] = count
    
    summary['errors'] = sum(1 for r in results if r.error)
    
    return summary


# Testing
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        print(f"Processing: {directory}")
        
        results = classify_directory(directory)
        
        for r in results[:5]:
            print(f"\n{r.filename}:")
            print(f"  Type: {r.classified_type.value}")
            print(f"  Exposure: {r.exposure_time}")
            print(f"  ISO: {r.iso}")
            print(f"  Camera: {r.camera_model}")
            print(f"  Mean: {r.mean}")
            print(f"  Object: {r.object_name}")
            print(f"  Filter: {r.filter_name}")
        
        print(f"\n{get_summary(results)}")
