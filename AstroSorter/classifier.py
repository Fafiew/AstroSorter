"""
AstroSorter - Classifier with mean-based light/dark detection
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
    
    # Group by ISO
    iso_groups: Dict[int, List[ImageMetadata]] = {}
    for m in results:
        if m.iso:
            if m.iso not in iso_groups:
                iso_groups[m.iso] = []
            iso_groups[m.iso].append(m)
        else:
            if None not in iso_groups:
                iso_groups[None] = []
            iso_groups[None].append(m)
    
    # Classify each ISO group
    for iso, images in iso_groups.items():
        if len(images) < 3:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
            continue
        
        # Get exposure groups
        exp_map: Dict[float, List[ImageMetadata]] = {}
        for m in images:
            if m.exposure_time:
                exp = round(m.exposure_time, 2)
                if exp not in exp_map:
                    exp_map[exp] = []
                exp_map[exp].append(m)
        
        if not exp_map:
            _classify_by_mean(images)
            continue
        
        # Calculate mean for each exposure group
        exp_means = {}
        for exp, group in exp_map.items():
            means = [g.mean for g in group if g.mean is not None]
            if means:
                exp_means[exp] = sum(means) / len(means)
        
        if not exp_means:
            _classify_by_mean(images)
            continue
        
        # Find exposure with highest mean - that's LIGHTS
        # Rule: lights have HIGHER mean, darks have LOWER mean (<5000)
        max_mean_exp = max(exp_means.items(), key=lambda x: x[1] or 0)[0]
        max_mean_val = exp_means.get(max_mean_exp, 0)
        
        # Classify based on mean only - this is the KEY rule
        # HIGHER mean = LIGHTS, LOWER mean = DARKS
        sorted_exps = sorted(exp_means.items(), key=lambda x: x[1] or 0, reverse=True)
        
        if sorted_exps:
            # Highest mean = LIGHTS
            light_exp = sorted_exps[0][0]
            light_mean = sorted_exps[0][1]
            
            # Find minimum mean for darks
            min_exp = min(exp_means.keys())
            min_mean = exp_means[min_exp]
            
            for exp, group in exp_map.items():
                avg_mean = exp_means.get(exp)
                
                if exp == light_exp or (avg_mean and avg_mean >= 5000):
                    # Highest mean = LIGHTS
                    for g in group:
                        g.classified_type = ImageType.LIGHT
                        g.confidence = 0.9
                elif exp < 0.01:
                    # Very short = BIAS
                    for g in group:
                        g.classified_type = ImageType.BIAS
                        g.confidence = 0.9
                elif 0.01 <= exp < 5:
                    # Medium = FLATS
                    for g in group:
                        g.classified_type = ImageType.FLAT
                        g.confidence = 0.7
                elif avg_mean and avg_mean < 5000:
                    # Lower mean = DARKS
                    for g in group:
                        g.classified_type = ImageType.DARK
                        g.confidence = 0.85
                else:
                    for g in group:
                        g.classified_type = ImageType.UNKNOWN
    
    return results


def _classify_by_mean(images: List[ImageMetadata]):
    """Classify by mean brightness when no exposure data"""
    means = [m.mean for m in images if m.mean is not None]
    if not means:
        for m in images:
            m.classified_type = ImageType.UNKNOWN
        return
    
    avg_mean = sum(means) / len(means)
    
    for m in images:
        if m.mean:
            if m.mean >= 5000:
                m.classified_type = ImageType.LIGHT
                m.confidence = 0.6
            else:
                m.classified_type = ImageType.DARK
                m.confidence = 0.6
        else:
            m.classified_type = ImageType.UNKNOWN


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
