"""
AstroSorter - Classifier with correct astrophotography logic
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
    '.raf', '.dng', '.orf', '.rw2', '.pef', '.raw', '.dng'}
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
    
    # Group by ISO first
    iso_groups: Dict[int, List[ImageMetadata]] = {}
    for m in results:
        if m.iso:
            if m.iso not in iso_groups:
                iso_groups[m.iso] = []
            iso_groups[m.iso].append(m)
    
    # Classify each ISO group
    for iso, images in iso_groups.items():
        if len(images) < 3:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
                m.confidence = 0.0
            continue
        
        # Get all exposure times for this ISO
        exp_map: Dict[float, List[ImageMetadata]] = {}
        for m in images:
            if m.exposure_time:
                # Round to 2 decimal places
                exp = round(m.exposure_time, 2)
                if exp not in exp_map:
                    exp_map[exp] = []
                exp_map[exp].append(m)
        
        if not exp_map:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
            continue
        
        # Sort exposures
        sorted_exps = sorted(exp_map.keys())
        
        # Find longest (Lights) - typically >= 5s for astrophotography
        longest_exp = max(sorted_exps)
        
        # Find shortest (Bias) - typically < 0.01s
        shortest_exp = min(sorted_exps)
        
        # Identify exposure groups
        lights_exp = None
        bias_exp = None
        flat_exp = None
        
        for exp in sorted_exps:
            if exp >= 5:
                lights_exp = exp
                break
        
        for exp in sorted_exps:
            if exp < 0.1:
                bias_exp = exp
        
        # Medium exposures could be flats
        for exp in sorted_exps:
            if exp != lights_exp and exp != bias_exp:
                if exp >= 0.1 and exp < 5:
                    flat_exp = exp
                    break
        
        # Now classify each exposure group
        for exp, group in exp_map.items():
            # Check mean brightness to distinguish flats from darks
            means = [img.mean for img in group if img.mean is not None]
            if means:
                avg_mean = sum(means) / len(means)
            else:
                avg_mean = None
            
            if exp == shortest_exp or exp < 0.01:
                # BIAS - very short exposure
                for m in group:
                    m.classified_type = ImageType.BIAS
                    m.confidence = 0.9
            elif exp == longest_exp and exp >= 5:
                # LIGHTS - longest exposure (with stars)
                for m in group:
                    m.classified_type = ImageType.LIGHT
                    m.confidence = 0.85
            elif exp == lights_exp:
                # Same as lights exposure = DARKS
                for m in group:
                    m.classified_type = ImageType.DARK
                    m.confidence = 0.85
            elif exp == flat_exp or (exp >= 0.1 and exp < 5):
                # FLATS - medium short exposure with balanced histogram
                # Check mean - flats should have moderate brightness
                if avg_mean and 3000 < avg_mean < 25000:
                    for m in group:
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.8
                elif avg_mean and avg_mean < 3000:
                    # Could be dark for flat
                    for m in group:
                        m.classified_type = ImageType.FLAT_DARK
                        m.confidence = 0.7
                else:
                    for m in group:
                        m.classified_type = ImageType.FLAT
                        m.confidence = 0.7
            else:
                # Check if exposure matches lights but mean is different = Darks
                if lights_exp and abs(exp - lights_exp) < 0.5:
                    for m in group:
                        m.classified_type = ImageType.DARK
                        m.confidence = 0.8
                else:
                    for m in group:
                        m.classified_type = ImageType.UNKNOWN
                        m.confidence = 0.0
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
