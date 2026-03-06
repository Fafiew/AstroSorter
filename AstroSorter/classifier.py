"""
AstroSorter - Classifier with proper astrophotography logic
"""

import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import exifread
import numpy as np
from PIL import Image
from tqdm import tqdm


class ImageType(Enum):
    LIGHT = "Lights"
    DARK = "Darks"
    FLAT = "Flats"
    BIAS = "Biases"
    FLAT_DARK = "Flat-Darks"
    UNKNOWN = "Unknown"


RAW_EXTENSIONS = {'.cr2', '.cr3', '.crw', '.nef', '.nrw', '.arw', '.sr2', '.srf',
    '.raf', '.dng', '.orf', '.rw2', '.pef', '.raw'}
FITS_EXTENSIONS = {'.fit', '.fits', '.fts'}
IMAGE_EXTENSIONS = RAW_EXTENSIONS | FITS_EXTENSIONS | {'.tif', '.tiff', '.jpg', '.jpeg', '.png'}


@dataclass
class ImageMetadata:
    filename: str
    filepath: str
    file_ext: str
    
    # EXIF data
    exposure_time: Optional[float] = None
    iso: Optional[int] = None
    camera_model: Optional[str] = None
    date_time: Optional[str] = None
    
    # Statistics
    mean: Optional[float] = None
    std: Optional[float] = None
    max_val: Optional[float] = None
    
    # Classification
    classified_type: ImageType = ImageType.UNKNOWN
    confidence: float = 0.0
    selected_type: Optional[str] = None


def read_exif(filepath: str) -> dict:
    """Read EXIF from file"""
    result = {}
    try:
        with open(filepath, 'rb') as f:
            for tag, value in exifread.process_file(f, details=False).items():
                result[tag] = str(value)
    except:
        pass
    return result


def get_stats(filepath: str, ext: str) -> dict:
    """Get image statistics"""
    result = {'mean': None, 'std': None, 'max': None}
    try:
        if ext in RAW_EXTENSIONS:
            try:
                import rawpy
                with rawpy.imread(filepath) as raw:
                    data = raw.raw_image_visible.astype(np.float32)
                    result['mean'] = float(np.mean(data))
                    result['std'] = float(np.std(data))
                    result['max'] = float(np.max(data))
                    return result
            except:
                pass
        
        with Image.open(filepath) as img:
            gray = img.convert('L')
            arr = np.array(gray, dtype=np.float32)
            result['mean'] = float(np.mean(arr))
            result['std'] = float(np.std(arr))
            result['max'] = float(np.max(arr))
    except:
        pass
    return result


def extract_filename_info(filename: str) -> dict:
    """Extract info from filename"""
    fn = filename.upper()
    info = {}
    
    # ISO
    for iso in [100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]:
        if f'ISO{iso}' in fn:
            info['iso'] = iso
            break
    
    # Type patterns
    for pattern, itype in [('LIGHT', 'LIGHT'), ('DARK', 'DARK'), ('FLAT', 'FLAT'), 
                           ('BIAS', 'BIAS'), ('OFFSET', 'BIAS')]:
        if pattern in fn:
            info['type'] = itype
            break
    
    return info


def process_image(filepath: str) -> ImageMetadata:
    """Process single image"""
    path = Path(filepath)
    ext = path.suffix.lower()
    
    m = ImageMetadata(filename=path.name, filepath=str(path.absolute()), file_ext=ext)
    
    try:
        # Read EXIF
        exif = read_exif(filepath)
        
        # Parse exposure
        for tag in ['EXIF ExposureTime', 'Image ExposureTime']:
            if tag in exif:
                try:
                    val = exif[tag]
                    if '/' in val:
                        parts = val.split('/')
                        m.exposure_time = float(parts[0]) / float(parts[1])
                    else:
                        m.exposure_time = float(val)
                    break
                except:
                    pass
        
        # Parse ISO
        for tag in ['EXIF ISOSpeedRatings', 'Image ISOSpeedRatings']:
            if tag in exif:
                try:
                    m.iso = int(exif[tag])
                    break
                except:
                    pass
        
        # Camera
        if 'Image Model' in exif:
            m.camera_model = exif['Image Model']
        
        # Date
        if 'EXIF DateTimeOriginal' in exif:
            m.date_time = exif['EXIF DateTimeOriginal']
        
        # Filename info
        finfo = extract_filename_info(path.name)
        if not m.iso and 'iso' in finfo:
            m.iso = finfo['iso']
        
        # Statistics
        stats = get_stats(filepath, ext)
        m.mean = stats['mean']
        m.std = stats['std']
        m.max_val = stats['max']
        
        # Classification
        m.classified_type = classify_image(m, finfo)
        m.confidence = 1.0 if m.classified_type != ImageType.UNKNOWN else 0.0
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    
    return m


def classify_image(metadata: ImageMetadata, filename_info: dict) -> ImageType:
    """Classify based on astrophotography rules"""
    
    # 1. Check explicit type from filename or EXIF
    if 'type' in filename_info:
        t = filename_info['type'].upper()
        if t == 'LIGHT': return ImageType.LIGHT
        if t == 'DARK': return ImageType.DARK
        if t == 'FLAT': return ImageType.FLAT
        if t == 'BIAS': return ImageType.BIAS
    
    # 2. If no ISO, can't classify properly
    if metadata.iso is None:
        return ImageType.UNKNOWN
    
    exp = metadata.exposure_time
    iso = metadata.iso
    mean = metadata.mean
    
    # Get all images to compare (we'll need to group by ISO)
    # For now, use simple rules based on typical values
    
    # BIAS: Very short exposure (typically < 0.01s)
    if exp is not None and exp < 0.01:
        return ImageType.BIAS
    
    # FLAT: No exposure time info but low mean (typical flat field ~10-20% histogram)
    if mean is not None and mean < 8000 and exp is not None and exp < 5:
        return ImageType.FLAT
    
    # If we have mean, use that for classification
    if mean is not None:
        # Very low mean = Bias
        if mean < 500:
            return ImageType.BIAS
        
        # Low mean with short exposure = Flat
        if exp is not None and exp < 10:
            return ImageType.FLAT
        
        # High mean with longer exposure = Light
        if exp is not None and exp >= 5:
            return ImageType.LIGHT
        
        # Default to Light if we have reasonable mean
        if mean > 1000:
            return ImageType.LIGHT
    
    return ImageType.UNKNOWN


def classify_directory(directory: str, recursive: bool = True, progress_callback=None) -> List[ImageMetadata]:
    """Classify all images in directory"""
    
    # Scan files
    path = Path(directory)
    files = []
    for ext in IMAGE_EXTENSIONS:
        if recursive:
            files.extend(path.rglob(f'*{ext}'))
            files.extend(path.rglob(f'*{ext.upper()}'))
        else:
            files.extend(path.glob(f'*{ext}'))
            files.extend(path.glob(f'*{ext.upper()}'))
    
    files = list(set(str(f) for f in files))
    
    # First pass: get all ISO values
    iso_groups = {}
    results = []
    
    for i, f in enumerate(files):
        m = process_image(f)
        results.append(m)
        
        if m.iso and m.iso not in iso_groups:
            iso_groups[m.iso] = []
        if m.iso:
            iso_groups[m.iso].append(m)
        
        if progress_callback:
            progress_callback(i + 1, len(files), f)
    
    # Second pass: re-classify based on ISO groups
    for iso, images in iso_groups.items():
        if len(images) < 3:
            continue
        
        # Find the most common exposure time for this ISO
        exposures = {}
        for m in images:
            if m.exposure_time:
                # Round to nearest second or fraction
                exp = round(m.exposure_time, 2)
                exposures[exp] = exposures.get(exp, 0) + 1
        
        if not exposures:
            continue
        
        # Most common exposure
        common_exp = max(exposures.items(), key=lambda x: x[1])[0]
        
        # Group by exposure
        exp_groups = {}
        for m in images:
            if m.exposure_time:
                exp = round(m.exposure_time, 2)
                if exp not in exp_groups:
                    exp_groups[exp] = []
                exp_groups[exp].append(m)
        
        # Classify each exposure group
        for exp, group in exp_groups.items():
            means = [m.mean for m in group if m.mean is not None]
            if not means:
                continue
            
            avg_mean = sum(means) / len(means)
            
            # Longest exposure = Light
            if exp >= 10:
                for m in group:
                    if m.classified_type == ImageType.UNKNOWN:
                        m.classified_type = ImageType.LIGHT
            # Shortest exposure = Bias
            elif exp < 0.1:
                for m in group:
                    if m.classified_type == ImageType.UNKNOWN:
                        m.classified_type = ImageType.BIAS
            # Medium = Flat
            else:
                for m in group:
                    if m.classified_type == ImageType.UNKNOWN:
                        m.classified_type = ImageType.FLAT
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    """Get classification summary"""
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
