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
    
    # Collect all filename hints FIRST
    for m in results:
        fn = m.filename.upper()
        
        # Check filename for type hints
        m._filename_hint = None
        if 'FLAT' in fn or 'F_' in fn or '_F.' in fn:
            m._filename_hint = ImageType.FLAT
        elif 'FLAT_DARK' in fn or 'FD_' in fn:
            m._filename_hint = ImageType.FLAT_DARK
        elif 'BIAS' in fn or 'OFFSET' in fn or 'B_' in fn or '_B.' in fn:
            m._filename_hint = ImageType.BIAS
        elif 'DARK' in fn or 'D_' in fn or '_D.' in fn:
            m._filename_hint = ImageType.DARK
        elif 'LIGHT' in fn or 'L_' in fn or '_L.' in fn or 'NGC' in fn or 'M42' in fn or 'IC' in fn:
            m._filename_hint = ImageType.LIGHT
    
    # Get images to classify (those without filename hints or all for scoring)
    unclassified = [m for m in results if m._filename_hint is None]
    
    # Group by ISO for fair comparison
    iso_groups: Dict[int, List[ImageMetadata]] = {}
    for m in unclassified:
        iso_key = m.iso if m.iso else 0
        if iso_key not in iso_groups:
            iso_groups[iso_key] = []
        iso_groups[iso_key].append(m)
    
    # Classify each ISO group using evidence-based scoring
    for iso_key, images in iso_groups.items():
        if not images:
            continue
        
        # Calculate group statistics for comparison
        means = [m.mean for m in images if m.mean is not None]
        exposures = [m.exposure_time for m in images if m.exposure_time is not None]
        
        if not means and not exposures:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
                m.confidence = 0.0
            continue
        
        group_mean = sum(means) / len(means) if means else 128
        group_std = (sum((x - group_mean) ** 2 for x in means) / len(means)) ** 0.5 if means else 50
        
        # Calculate evidence scores for each image
        for m in images:
            evidence = {ImageType.LIGHT: 0, ImageType.DARK: 0, ImageType.FLAT: 0, 
                      ImageType.BIAS: 0, ImageType.FLAT_DARK: 0}
            
            # Evidence 1: Exposure time
            exp = m.exposure_time
            if exp is not None:
                if exp < 0.01:  # < 10ms = very likely bias
                    evidence[ImageType.BIAS] += 3
                elif exp < 0.1:  # < 100ms = likely flat
                    evidence[ImageType.FLAT] += 2
                elif exp > 1.0:  # > 1s = likely light
                    evidence[ImageType.LIGHT] += 2
                else:
                    evidence[ImageType.FLAT] += 1
            
            # Evidence 2: Mean brightness vs group
            if m.mean is not None:
                z = (m.mean - group_mean) / max(group_std, 1)
                
                if z > 1.5:  # Much brighter than average
                    evidence[ImageType.LIGHT] += 2
                    evidence[ImageType.DARK] -= 1
                elif z > 0.5:
                    evidence[ImageType.LIGHT] += 1
                elif z < -1.5:  # Much darker than average
                    evidence[ImageType.DARK] += 2
                    evidence[ImageType.LIGHT] -= 1
                elif z < -0.5:
                    evidence[ImageType.DARK] += 1
                
                # Evidence 3: Absolute brightness
                if m.mean < 20:
                    evidence[ImageType.BIAS] += 1
                    evidence[ImageType.FLAT_DARK] += 1
                elif 30 < m.mean < 200:
                    evidence[ImageType.FLAT] += 1
            
            # Find best evidence
            best_type = max(evidence, key=evidence.get)
            best_score = evidence[best_type]
            
            if best_score > 0:
                m.classified_type = best_type
                # Normalize confidence: score / max possible
                m.confidence = min(best_score / 5.0, 0.9)
            else:
                m.classified_type = ImageType.UNKNOWN
                m.confidence = 0.0
    
    # Now apply filename hints with HIGH confidence (they're user-provided)
    for m in results:
        if m._filename_hint is not None:
            m.classified_type = m._filename_hint
            m.confidence = 0.99  # Filename hints are most reliable
    
    return results


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
