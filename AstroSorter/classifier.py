"""
AstroSorter - Classifier using mean brightness for light/dark
"""

import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict
import exifread
import numpy as np
from PIL import Image


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
    
    exposure_time: Optional[float] = None
    iso: Optional[int] = None
    camera_model: Optional[str] = None
    date_time: Optional[str] = None
    
    mean: Optional[float] = None
    std: Optional[float] = None
    max_val: Optional[float] = None
    
    classified_type: ImageType = ImageType.UNKNOWN
    confidence: float = 0.0
    selected_type: Optional[str] = None


def read_exif(filepath: str) -> dict:
    result = {}
    try:
        with open(filepath, 'rb') as f:
            for tag, value in exifread.process_file(f, details=False).items():
                result[tag] = str(value)
    except:
        pass
    return result


def get_stats(filepath: str, ext: str) -> dict:
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
    fn = filename.upper()
    info = {}
    
    for iso in [100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]:
        if f'ISO{iso}' in fn:
            info['iso'] = iso
            break
    
    for pattern, itype in [('LIGHT', 'LIGHT'), ('DARK', 'DARK'), ('FLAT', 'FLAT'), 
                           ('BIAS', 'BIAS'), ('OFFSET', 'BIAS')]:
        if pattern in fn:
            info['type'] = itype
            break
    
    return info


def process_image(filepath: str) -> ImageMetadata:
    path = Path(filepath)
    ext = path.suffix.lower()
    
    m = ImageMetadata(filename=path.name, filepath=str(path.absolute()), file_ext=ext)
    
    try:
        exif = read_exif(filepath)
        
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
        
        for tag in ['EXIF ISOSpeedRatings', 'Image ISOSpeedRatings']:
            if tag in exif:
                try:
                    m.iso = int(exif[tag])
                    break
                except:
                    pass
        
        if 'Image Model' in exif:
            m.camera_model = exif['Image Model']
        
        if 'EXIF DateTimeOriginal' in exif:
            m.date_time = exif['EXIF DateTimeOriginal']
        
        finfo = extract_filename_info(path.name)
        if not m.iso and 'iso' in finfo:
            m.iso = finfo['iso']
        
        stats = get_stats(filepath, ext)
        m.mean = stats['mean']
        m.std = stats['std']
        m.max_val = stats['max']
        
    except Exception as e:
        print(f"Error: {filepath}: {e}")
    
    return m


def classify_directory(directory: str, recursive: bool = True, progress_callback=None) -> List[ImageMetadata]:
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
    results = []
    
    for i, f in enumerate(files):
        m = process_image(f)
        results.append(m)
        if progress_callback:
            progress_callback(i + 1, len(files), f)
    
    # First pass: Classify based on filename hints (most reliable)
    for m in results:
        fn = m.filename.upper()
        
        # Check filename for type hints
        if 'LIGHT' in fn or 'L_' in fn or '_L.' in fn:
            m.classified_type = ImageType.LIGHT
            m.confidence = 0.99
        elif 'DARK' in fn or 'D_' in fn or '_D.' in fn:
            m.classified_type = ImageType.DARK
            m.confidence = 0.99
        elif 'FLAT' in fn or 'F_' in fn or '_F.' in fn:
            m.classified_type = ImageType.FLAT
            m.confidence = 0.99
        elif 'BIAS' in fn or 'OFFSET' in fn or 'B_' in fn or '_B.' in fn:
            m.classified_type = ImageType.BIAS
            m.confidence = 0.99
        elif 'FLAT_DARK' in fn or 'FD_' in fn:
            m.classified_type = ImageType.FLAT_DARK
            m.confidence = 0.99
    
    # Get images still unclassified
    unclassified = [m for m in results if m.classified_type == ImageType.UNKNOWN]
    if not unclassified:
        return results
    
    # Group by ISO for fair comparison
    iso_groups: Dict[int, List[ImageMetadata]] = {}
    for m in unclassified:
        iso_key = m.iso if m.iso else 0
        if iso_key not in iso_groups:
            iso_groups[iso_key] = []
        iso_groups[iso_key].append(m)
    
    # Classify each ISO group using exposure + mean
    for iso_key, images in iso_groups.items():
        if not images:
            continue
        
        # Get exposure times and means
        has_exposure = [m for m in images if m.exposure_time is not None]
        has_mean = [m for m in images if m.mean is not None]
        
        if not has_exposure and not has_mean:
            # Nothing to work with
            for m in images:
                m.classified_type = ImageType.UNKNOWN
                m.confidence = 0.0
            continue
        
        # Classify by exposure time (primary factor)
        for m in images:
            # BIAS: Very short exposure (<0.01s) 
            if m.exposure_time and m.exposure_time < 0.01:
                m.classified_type = ImageType.BIAS
                m.confidence = 0.95
        
        # Get bias images to compare against
        bias_images = [m for m in images if m.classified_type == ImageType.BIAS]
        non_bias = [m for m in images if m.classified_type != ImageType.BIAS]
        
        if not bias_images:
            # No bias frames - use exposure time to separate
            # FLAT: Short exposure (<0.5s), typically used for flats
            # LIGHT: Longer exposures
            for m in non_bias:
                if m.exposure_time and m.exposure_time < 0.5:
                    # Check mean - flats should have moderate brightness
                    if m.mean and 20 < m.mean < 200:
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.7
                    else:
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.5
                else:
                    # Longer exposure = likely light
                    m.classified_type = ImageType.LIGHT
                    m.confidence = 0.5
        else:
            # We have bias frames - use them as reference
            bias_mean = sum(m.mean for m in bias_images if m.mean) / max(1, len([m for m in bias_images if m.mean]))
            bias_exposure = max(m.exposure_time for m in bias_images if m.exposure_time) if any(m.exposure_time for m in bias_images) else 0
            
            for m in non_bias:
                if m.exposure_time and m.exposure_time < 0.5:
                    # Short exposure - could be flat or dark
                    if m.mean and m.mean < bias_mean * 1.5:
                        # Very similar to bias = flat-dark
                        m.classified_type = ImageType.FLAT_DARK
                        m.confidence = 0.7
                    else:
                        # Moderate brightness = flat
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.7
                else:
                    # Longer exposure
                    if m.mean and m.mean > bias_mean * 2:
                        # Much brighter than bias = light
                        m.classified_type = ImageType.LIGHT
                        m.confidence = 0.85
                    else:
                        # Similar to bias or darker = dark
                        m.classified_type = ImageType.DARK
                        m.confidence = 0.8
        
        # If still unclassified, use mean-based heuristic with ISO context
        still_unclassified = [m for m in images if m.classified_type == ImageType.UNKNOWN]
        if still_unclassified and has_mean:
            means = [m.mean for m in images if m.mean is not None]
            if means:
                mean_mean = sum(means) / len(means)
                std_mean = (sum((x - mean_mean) ** 2 for x in means) / len(means)) ** 0.5
                
                for m in still_unclassified:
                    if m.mean is not None:
                        # Z-score based classification
                        z = (m.mean - mean_mean) / max(std_mean, 1)
                        
                        if z > 1:
                            m.classified_type = ImageType.LIGHT
                            m.confidence = 0.6
                        elif z < -1:
                            m.classified_type = ImageType.DARK
                            m.confidence = 0.6
                        else:
                            # Near average - default to light (most common)
                            m.classified_type = ImageType.LIGHT
                            m.confidence = 0.4
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
