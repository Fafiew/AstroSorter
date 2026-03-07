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
        if 'LIGHT' in fn or 'L_' in fn or '_L.' in fn or 'NGC' in fn or 'M42' in fn or 'IC' in fn:
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
    
    # Classify each ISO group using exposure time + mean
    for iso_key, images in iso_groups.items():
        if not images:
            continue
        
        # Get statistics
        has_exposure = [m for m in images if m.exposure_time is not None]
        has_mean = [m for m in images if m.mean is not None]
        
        if not has_exposure and not has_mean:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
                m.confidence = 0.0
            continue
        
        # Calculate group statistics for comparison
        means = [m.mean for m in images if m.mean is not None]
        exposures = [m.exposure_time for m in images if m.exposure_time is not None]
        
        group_mean = sum(means) / len(means) if means else 0
        group_std = (sum((x - group_mean) ** 2 for x in means) / len(means)) ** 0.5 if means else 0
        min_exposure = min(exposures) if exposures else 0
        max_exposure = max(exposures) if exposures else 0
        
        # Classify by EXPOSURE TIME (primary factor):
        # - < 0.01s = BIAS
        # - 0.01-1s = could be FLAT or FLAT_DARK
        # - > 1s = could be LIGHT or DARK
        
        for m in images:
            exp = m.exposure_time
            
            if exp is not None:
                # BIAS: Very short exposure (< 0.01s / 10ms)
                if exp < 0.01:
                    m.classified_type = ImageType.BIAS
                    m.confidence = 0.95
                # FLAT: Short exposure (0.01s to 1s) with moderate mean
                elif exp < 1.0:
                    # Flats have specific mean range (typically 30-80% of max)
                    if m.mean is not None:
                        max_possible = 255  # 8-bit
                        mean_ratio = m.mean / max_possible
                        
                        # Flats should be moderately bright (15-90% of max)
                        if 0.15 < mean_ratio < 0.90:
                            m.classified_type = ImageType.FLAT
                            m.confidence = 0.8
                        # Very dark short exposure = flat-dark
                        elif mean_ratio < 0.15:
                            m.classified_type = ImageType.FLAT_DARK
                            m.confidence = 0.7
                        else:
                            # Very bright short exposure - could be light with short sub
                            # Check if it's the brightest in the group
                            if m.mean > group_mean + group_std:
                                m.classified_type = ImageType.LIGHT
                                m.confidence = 0.6
                            else:
                                m.classified_type = ImageType.FLAT
                                m.confidence = 0.5
                    else:
                        # No mean data - default short exposure to flat
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.5
                # LIGHT or DARK: Longer exposure (> 1s)
                else:
                    if m.mean is not None:
                        # Compare to group mean
                        if m.mean > group_mean:
                            m.classified_type = ImageType.LIGHT
                            m.confidence = 0.8
                        else:
                            m.classified_type = ImageType.DARK
                            m.confidence = 0.75
                    else:
                        # No mean - default to light (more common)
                        m.classified_type = ImageType.LIGHT
                        m.confidence = 0.5
            else:
                # No exposure data - use mean only
                if m.mean is not None:
                    if m.mean > group_mean:
                        m.classified_type = ImageType.LIGHT
                        m.confidence = 0.6
                    else:
                        m.classified_type = ImageType.DARK
                        m.confidence = 0.6
                else:
                    m.classified_type = ImageType.UNKNOWN
                    m.confidence = 0.0
        
        # Refinement: Use bias frames as reference if available
        bias_images = [m for m in images if m.classified_type == ImageType.BIAS]
        non_bias = [m for m in images if m.classified_type != ImageType.BIAS]
        
        if bias_images:
            bias_mean = sum(m.mean for m in bias_images if m.mean) / max(1, len([m for m in bias_images if m.mean]))
            
            for m in non_bias:
                # If significantly brighter than bias, it's likely a light
                if m.mean and m.mean > bias_mean * 3:
                    m.classified_type = ImageType.LIGHT
                    m.confidence = max(m.confidence, 0.85)
                # If slightly brighter than bias, could be flat
                elif m.mean and bias_mean < m.mean < bias_mean * 3:
                    if m.classified_type != ImageType.FLAT:
                        m.classified_type = ImageType.FLAT
                        m.confidence = max(m.confidence, 0.7)
                # If similar to or darker than bias, could be dark
                elif m.mean and m.mean <= bias_mean:
                    m.classified_type = ImageType.DARK
                    m.confidence = max(m.confidence, 0.8)
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
