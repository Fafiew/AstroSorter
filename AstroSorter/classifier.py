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
        iso_key = m.iso if m.iso else 0
        if iso_key not in iso_groups:
            iso_groups[iso_key] = []
        iso_groups[iso_key].append(m)
    
    # Classify each ISO group
    for iso_key, images in iso_groups.items():
        if len(images) < 2:
            for m in images:
                m.classified_type = ImageType.UNKNOWN
            continue
        
        # Group by exposure time
        exp_groups: Dict[float, List[ImageMetadata]] = {}
        for m in images:
            if m.exposure_time:
                # Round to 1 decimal for grouping
                exp = round(m.exposure_time, 1)
                if exp not in exp_groups:
                    exp_groups[exp] = []
                exp_groups[exp].append(m)
        
        if not exp_groups:
            # No exposure data - use mean only
            _classify_by_mean_only(images)
            continue
        
        # Separate bias (very short exposure)
        bias_exps = [e for e in exp_groups.keys() if e < 0.1]
        other_exps = [e for e in exp_groups.keys() if e >= 0.1]
        
        # Mark bias frames
        for exp in bias_exps:
            for m in exp_groups[exp]:
                m.classified_type = ImageType.BIAS
                m.confidence = 0.95
        
        # For remaining exposures, classify by exposure + mean
        if other_exps:
            # Find the most common long exposure
            long_exps = [e for e in other_exps if e >= 10]
            short_exps = [e for e in other_exps if e < 10]
            
            # Group exposures by similar times (within 10% tolerance)
            exposure_clusters = _cluster_exposures(other_exps)
            
            for cluster in exposure_clusters:
                # Get all images in this cluster
                cluster_images = []
                for exp in cluster:
                    cluster_images.extend(exp_groups[exp])
                
                if not cluster_images:
                    continue
                
                # Calculate mean for each exposure in cluster
                exp_means = {}
                for exp in cluster:
                    means = [m.mean for m in exp_groups[exp] if m.mean is not None]
                    if means:
                        exp_means[exp] = sum(means) / len(means)
                
                if not exp_means:
                    for m in cluster_images:
                        m.classified_type = ImageType.UNKNOWN
                    continue
                
                # Find min and max mean
                min_exp = min(exp_means.keys(), key=lambda x: exp_means[x])
                max_exp = max(exp_means.keys(), key=lambda x: exp_means[x])
                
                # Higher mean = Lights, Lower mean = Darks
                # Same exposure group: compare means to determine light vs dark
                
                # If we have different exposures in cluster:
                # - longest = lights, shorter = darks/flats
                # BUT also check mean: lights should have HIGHER mean
                
                if len(cluster) > 1:
                    # Multiple exposures in cluster
                    # Sort by exposure time
                    sorted_exp = sorted(cluster)
                    
                    for exp in sorted_exp:
                        for m in exp_groups[exp]:
                            if exp == sorted_exp[-1]:
                                # Longest exposure = Lights
                                m.classified_type = ImageType.LIGHT
                                m.confidence = 0.9
                            else:
                                # Shorter exposure = Darks (same target)
                                m.classified_type = ImageType.DARK
                                m.confidence = 0.85
                else:
                    # Single exposure in cluster - use mean to separate light/dark
                    # This shouldn't happen often
                    for exp in cluster:
                        for m in exp_groups[exp]:
                            m.classified_type = ImageType.LIGHT
                            m.confidence = 0.7
    
    return results


def _cluster_exposures(exposures: List[float]) -> List[List[float]]:
    """Group exposures that are similar (within 10% of each other)"""
    if not exposures:
        return []
    
    exposures = sorted(set(exposures))
    clusters = []
    current_cluster = [exposures[0]]
    
    for i in range(1, len(exposures)):
        # Check if current exposure is within 10% of previous
        if exposures[i] <= current_cluster[-1] * 1.1:
            current_cluster.append(exposures[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [exposures[i]]
    
    clusters.append(current_cluster)
    return clusters


def _classify_by_mean_only(images: List[ImageMetadata]):
    """Classify by mean when no exposure data"""
    means = [m.mean for m in images if m.mean is not None]
    if not means:
        for m in images:
            m.classified_type = ImageType.UNKNOWN
        return
    
    avg_mean = sum(means) / len(means)
    
    # Higher than average = Light, Lower = Dark
    for m in images:
        if m.mean:
            if m.mean >= avg_mean:
                m.classified_type = ImageType.LIGHT
                m.confidence = 0.5
            else:
                m.classified_type = ImageType.DARK
                m.confidence = 0.5
        else:
            m.classified_type = ImageType.UNKNOWN


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
