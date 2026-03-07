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
    min_val: Optional[float] = None
    range_val: Optional[float] = None
    p1: Optional[float] = None
    p99: Optional[float] = None
    
    classified_type: ImageType = ImageType.UNKNOWN
    confidence: float = 0.0
    selected_type: Optional[str] = None


def read_exif(filepath: str) -> dict:
    result = {}
    try:
        with open(filepath, 'rb') as f:
            for tag, value in exifread.process_file(f, details=False).items():
                result[tag] = str(value)
    except Exception as e:
        print(f"[EXIF] Failed to read {filepath}: {e}")
    return result


def get_stats(filepath: str, ext: str) -> dict:
    result = {'mean': None, 'std': None, 'max': None, 'min': None, 'range': None, 'p1': None, 'p99': None}
    try:
        if ext in RAW_EXTENSIONS:
            try:
                import rawpy
                import numpy as np
                with rawpy.imread(filepath) as raw:
                    # Use the raw image data directly (not postprocessed)
                    data = raw.raw_image_visible.astype(np.float32)
                    
                    # Get bit depth info
                    dtype = raw.raw_image_visible.dtype
                    max_raw = float(np.iinfo(dtype).max)
                    
                    # Normalize to 0-255 based on max value for this bit depth
                    scale_factor = 255.0 / max_raw
                    
                    data_scaled = data * scale_factor
                    
                    # Calculate stats including min/max for brightness analysis
                    result['mean'] = float(np.mean(data_scaled))
                    result['std'] = float(np.std(data_scaled))
                    result['max'] = float(np.minimum(np.max(data_scaled), 255))
                    result['min'] = float(np.min(data_scaled))
                    result['range'] = result['max'] - result['min']
                    result['p1'] = float(np.percentile(data_scaled, 1))
                    result['p99'] = float(np.percentile(data_scaled, 99))
                    return result
            except ImportError:
                # rawpy not available, fall through to PIL
                pass
            except Exception as e:
                print(f"[RAW] Failed to read {filepath}: {e}")
                return result
        
        if ext in FITS_EXTENSIONS:
            try:
                import numpy as np
                from astropy.io import fits
                with fits.open(filepath) as hdul:
                    # Get primary HDU data
                    data = hdul[0].data.astype(np.float32)
                    if data is None:
                        raise ValueError("No data in FITS file")
                    
                    # Normalize to 0-255 based on actual range
                    data_min, data_max = np.min(data), np.max(data)
                    if data_max > data_min:
                        data_scaled = ((data - data_min) / (data_max - data_min)) * 255.0
                    else:
                        data_scaled = data - data_min
                    
                    result['mean'] = float(np.mean(data_scaled))
                    result['std'] = float(np.std(data_scaled))
                    result['max'] = float(np.minimum(np.max(data_scaled), 255))
                    result['min'] = float(np.min(data_scaled))
                    result['range'] = result['max'] - result['min']
                    result['p1'] = float(np.percentile(data_scaled, 1))
                    result['p99'] = float(np.percentile(data_scaled, 99))
                    return result
            except ImportError:
                print(f"[FITS] astropy not installed for {filepath}")
            except Exception as e:
                print(f"[FITS] Failed to read {filepath}: {e}")
                return result
        
        with Image.open(filepath) as img:
            import numpy as np
            
            # Handle different bit depths properly
            if img.mode == 'I;16':
                # 16-bit grayscale - convert properly
                arr = np.array(img, dtype=np.float32)
                # Normalize to 0-255 based on actual range in the image
                arr_min, arr_max = arr.min(), arr.max()
                if arr_max > arr_min:
                    arr = ((arr - arr_min) / (arr_max - arr_min)) * 255.0
                else:
                    arr = arr - arr_min
            elif img.mode == 'I':
                # 32-bit grayscale
                arr = np.array(img, dtype=np.float32)
                arr_min, arr_max = arr.min(), arr.max()
                if arr_max > arr_min:
                    arr = ((arr - arr_min) / (arr_max - arr_min)) * 255.0
                else:
                    arr = arr - arr_min
            elif img.mode in ('RGB', 'RGBA', 'L'):
                # 8-bit images
                gray = img.convert('L')
                arr = np.array(gray, dtype=np.float32)
            else:
                # Fallback
                gray = img.convert('L')
                arr = np.array(gray, dtype=np.float32)
            
            result['mean'] = float(np.mean(arr))
            result['std'] = float(np.std(arr))
            result['max'] = float(np.minimum(np.max(arr), 255))
            result['min'] = float(np.min(arr))
            result['range'] = result['max'] - result['min']
            result['p1'] = float(np.percentile(arr, 1))
            result['p99'] = float(np.percentile(arr, 99))
    except Exception as e:
        print(f"[STATS] Failed to process {filepath}: {e}")
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
                except (ValueError, TypeError) as e:
                    print(f"[EXIF] Failed to parse exposure time: {e}")
        
        for tag in ['EXIF ISOSpeedRatings', 'Image ISOSpeedRatings']:
            if tag in exif:
                try:
                    m.iso = int(exif[tag])
                    break
                except (ValueError, TypeError) as e:
                    print(f"[EXIF] Failed to parse ISO: {e}")
        
        if 'Image Model' in exif:
            m.camera_model = exif['Image Model']
        
        if 'EXIF DateTimeOriginal' in exif:
            m.date_time = exif['EXIF DateTimeOriginal']
        
        finfo = extract_filename_info(path.name)
        if not m.iso and 'iso' in finfo:
            m.iso = finfo['iso']
        
        stats = get_stats(filepath, ext)
        
        # Store raw (untransformed) stats in metadata
        m.min_val = stats['min']
        m.max_val = stats['max']
        m.range_val = stats['range']
        m.mean = stats['mean']  # Raw mean, not transformed
        m.std = stats['std']
        m.p1 = stats.get('p1')
        m.p99 = stats.get('p99')
        
    except Exception as e:
        print(f"Error: {filepath}: {e}")
    
    return m


def classify_directory(directory: str, recursive: bool = True, progress_callback=None) -> List[ImageMetadata]:
    """Classify images in a directory using evidence-based scoring."""
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
    
    # Step 1: Apply filename hints (highest priority, confidence 0.99)
    for m in results:
        fn = m.filename.upper()
        
        # Check for unambiguous astrophotography keywords only
        if 'LIGHT' in fn:
            m.classified_type = ImageType.LIGHT
            m.confidence = 0.99
        elif 'FLAT_DARK' in fn or 'FLATDARK' in fn:
            m.classified_type = ImageType.FLAT_DARK
            m.confidence = 0.99
        elif 'FLAT' in fn:
            m.classified_type = ImageType.FLAT
            m.confidence = 0.99
        elif 'DARK' in fn:
            m.classified_type = ImageType.DARK
            m.confidence = 0.99
        elif 'BIAS' in fn or 'OFFSET' in fn:
            m.classified_type = ImageType.BIAS
            m.confidence = 0.99
        else:
            # Step 2 & 3: Evidence scoring for images without hints
            m.classified_type, m.confidence = _score_and_classify(m)
    
    return results


def _score_and_classify(m: ImageMetadata) -> tuple:
    exp = m.exposure_time

    # Use percentile-based range/average to ignore hot pixel outliers.
    # p99 - p1 gives the true dynamic range without being skewed by single bad pixels.
    if m.p1 is not None and m.p99 is not None:
        px_range = m.p99 - m.p1
        px_avg   = (m.p99 + m.p1) / 2.0
    else:
        px_range = None
        px_avg   = None

    # Fallback: no pixel stats available, use exposure only
    if px_range is None or px_avg is None:
        if exp is None:
            return ImageType.UNKNOWN, 0.0
        if exp < 0.1:
            return ImageType.BIAS, 0.75
        if exp <= 20:
            return ImageType.FLAT, 0.55
        return ImageType.LIGHT, 0.55

    # BIAS: exposure is near-zero AND image is uniform and dark
    if exp is not None and exp < 0.1 and px_range < 5 and px_avg < 12:
        return ImageType.BIAS, 0.97

    # FLAT_DARK: short exposure, dark and uniform (like a flat but no light)
    if exp is not None and 0.1 <= exp <= 20 and px_range < 10 and px_avg < 15:
        return ImageType.FLAT_DARK, 0.85

    # FLAT: short-to-medium exposure AND both p1 and p99 are bright (uniform illumination)
    if exp is not None and exp <= 30 and px_avg > 50 and px_range < 120:
        conf = min(0.6 + (px_avg - 50) / 150.0, 0.97)
        return ImageType.FLAT, conf

    # DARK: long exposure, but image is uniformly dark (p99 still low, narrow range)
    # This is the critical fix: darks have long exposure but tiny p99-p1 range
    if exp is not None and exp > 10 and px_range < 15 and px_avg < 15:
        conf = min(0.7 + exp / 1000.0, 0.95)
        return ImageType.DARK, conf

    # LIGHT: long exposure, wide dynamic range (dark sky p1 + bright star p99)
    if exp is not None and exp > 10 and px_range > 15:
        conf = min(0.6 + px_range / 200.0, 0.97)
        return ImageType.LIGHT, conf

    return ImageType.UNKNOWN, 0.0


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
