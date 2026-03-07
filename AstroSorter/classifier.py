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
                    
                    # Subsample to ~80k pixels — accurate stats, ~100x faster read
                    data_scaled = data_scaled.flatten()[::max(1, data_scaled.size // 80000)]
                    
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
                    
                    # Subsample to ~80k pixels
                    data_scaled = data_scaled.flatten()[::max(1, data_scaled.size // 80000)]
                    
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
            
            # Subsample to ~80k pixels
            arr = arr.flatten()[::max(1, arr.size // 80000)]

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

        # Bias frames are classified purely on exposure time — skip pixel read entirely
        if m.exposure_time is not None and m.exposure_time < 0.1:
            return m

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
    """
    Classify astrophotography images using a two-phase approach:
      Phase 1 — per-image rules (bias, flat, flat-dark are unambiguous from stats alone).
      Phase 2 — session-level comparison for long-exposure frames, because dark frames and
                 light frames are pixel-statistically near-identical per image (both dominated
                 by the camera bias pedestal). Only by comparing frames against each other —
                 or against bias frames — can we reliably separate them.
    """
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

    # Use all CPU cores as parallel workers.
    # Falls back to sequential for small batches to avoid process-spawn overhead.
    if len(files) > 20:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        import os
        max_workers = os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_image, f): f for f in files}
            for i, future in enumerate(as_completed(futures)):
                results.append(future.result())
                if progress_callback:
                    progress_callback(i + 1, len(files), futures[future])
    else:
        for i, f in enumerate(files):
            m = process_image(f)
            results.append(m)
            if progress_callback:
                progress_callback(i + 1, len(files), f)

    # Phase 1a: Filename hints — highest priority, unambiguous keywords only
    hinted = set()
    for m in results:
        fn = m.filename.upper()
        if 'FLAT_DARK' in fn or 'FLATDARK' in fn:
            m.classified_type = ImageType.FLAT_DARK
            m.confidence = 0.99
            hinted.add(m.filename)
        elif 'LIGHT' in fn:
            m.classified_type = ImageType.LIGHT
            m.confidence = 0.99
            hinted.add(m.filename)
        elif 'FLAT' in fn:
            m.classified_type = ImageType.FLAT
            m.confidence = 0.99
            hinted.add(m.filename)
        elif 'DARK' in fn:
            m.classified_type = ImageType.DARK
            m.confidence = 0.99
            hinted.add(m.filename)
        elif 'BIAS' in fn or 'OFFSET' in fn:
            m.classified_type = ImageType.BIAS
            m.confidence = 0.99
            hinted.add(m.filename)

    # Phase 1b: Per-image classification for non-hinted images
    for m in results:
        if m.filename not in hinted:
            m.classified_type, m.confidence = _classify_single(m)

    # Phase 2: Session-level correction for long-exposure frames.
    # Cannot reliably distinguish darks from lights on a per-image basis —
    # both frame types sit at the camera pedestal with nearly the same mean.
    # Light frames have a small but consistent mean elevation from sky background.
    # Threshold lowered to 1s to support lucky imaging (lights/darks at 5-30s).
    # Include UNKNOWN frames — these are medium-exposure dark frames that
    # _classify_single intentionally left unresolved for Phase 2.
    long_exp = [m for m in results
                if m.filename not in hinted
                and m.exposure_time is not None and m.exposure_time > 1
                and m.classified_type in (ImageType.UNKNOWN, ImageType.LIGHT, ImageType.DARK)
                and m.mean is not None]
    if long_exp:
        _correct_long_exposure(results, long_exp)

    return results


def _classify_single(m: ImageMetadata) -> tuple:
    """
    Per-image classification. Handles bias, flat, and flat-dark unambiguously.
    Long-exposure frames (darks vs lights) are only tentatively classified here
    and will be overwritten by the session-level correction in Phase 2.
    """
    exp  = m.exposure_time
    mean = m.mean if m.mean is not None else 0.0

    px_range = (m.p99 - m.p1) if (m.p1 is not None and m.p99 is not None) else None
    px_avg   = ((m.p99 + m.p1) / 2.0) if (m.p1 is not None and m.p99 is not None) else None

    # No pixel stats at all — exposure-only fallback
    if px_range is None:
        if exp is None:
            return ImageType.UNKNOWN, 0.0
        if exp < 0.1:
            return ImageType.BIAS, 0.70
        # Do not guess FLAT — medium/long exposures could be lucky imaging lights or darks.
        # Return UNKNOWN so Phase 2 resolves them via session-level comparison.
        return ImageType.UNKNOWN, 0.30

    # BIAS — camera minimum shutter speed, records only readout noise
    if exp is not None and exp < 0.1:
        return ImageType.BIAS, 0.97

    # FLAT — both ends of the histogram are elevated: even the darkest pixels are bright.
    # This is the unmistakable signature of a uniformly illuminated flat field.
    if px_avg > 50:
        return ImageType.FLAT, min(0.65 + (px_avg - 50) / 200.0, 0.97)

    # Short-to-medium exposure, dark image
    if exp is not None and exp <= 30:
        # FLAT_DARK: only for very short exposures (<=3s).
        # Lucky imaging darks are typically 5-30s — a tight bound stops them
        # being caught here. Phase 2 will correctly classify them instead.
        if exp <= 3 and px_range < 8 and px_avg < 15:
            return ImageType.FLAT_DARK, 0.80
        # Moderately bright at short exposure — likely underexposed flat
        if px_avg > 25:
            return ImageType.FLAT, 0.55
        # Dark at medium exposure: could be lucky imaging dark or flat-dark.
        # Return UNKNOWN so Phase 2 resolves via session context.
        return ImageType.UNKNOWN, 0.30

    # Long exposure (> 30s): tentative only — Phase 2 will overwrite this.
    # Use std signal as a weak initial estimate.
    if exp is not None and exp > 30:
        std = m.std if m.std is not None else 0.0
        rel_std   = std / max(mean, 1.0)
        p99_excess = ((m.p99 - mean) / max(mean, 1.0)) if m.p99 is not None else 0.0
        light_signal = rel_std + p99_excess * 0.5
        if light_signal > 0.15:
            return ImageType.LIGHT, 0.55
        return ImageType.DARK, 0.55

    return ImageType.UNKNOWN, 0.0


def _correct_long_exposure(all_results: List, long_exp: List) -> None:
    """
    Session-level dark vs light correction.

    Why this is necessary
    ─────────────────────
    Dark and light frames share nearly identical pixel statistics per-image — both
    sit at the camera bias pedestal. Only session-level comparison can separate them.

    Exposure-time grouping
    ──────────────────────
    Frames from different session types (e.g. lucky imaging at 20s and deep-sky at
    480s) must NOT be mixed in the same cluster analysis — their pedestals and mean
    offsets differ, so mixing them produces wrong midpoints. We split long_exp into
    exposure-time groups first: any gap > 4x between consecutive sorted exposure
    times marks a new group. Each group is classified independently.

    Per-group strategy
    ──────────────────
    Strategy A (preferred) — bias frames present:
        Threshold = bias_mean + max(6σ, 6% of bias_mean).
        Below → Dark. Above → Light.

    Strategy B — no bias frames:
        If mean spread ≥ 5% of group minimum → two clusters, split at largest gap.
        Else → single cluster, use relative std (darks: low; lights: higher).
    """
    if not long_exp:
        return

    # ── Split into exposure-time groups ─────────────────────────────────────────
    sorted_frames = sorted(long_exp, key=lambda m: m.exposure_time)
    groups = [[sorted_frames[0]]]
    for m in sorted_frames[1:]:
        # New group when exposure time jumps by more than 4x
        if m.exposure_time > groups[-1][-1].exposure_time * 4:
            groups.append([])
        groups[-1].append(m)

    bias_frames = [m for m in all_results
                   if m.classified_type == ImageType.BIAS and m.mean is not None]
    bias_mean = None
    bias_std  = None
    if bias_frames:
        bias_mean = sum(m.mean for m in bias_frames) / len(bias_frames)
        bias_var  = sum((m.mean - bias_mean) ** 2 for m in bias_frames) / len(bias_frames)
        bias_std  = bias_var ** 0.5

    for group in groups:
        _classify_exposure_group(group, bias_mean, bias_std)


def _classify_exposure_group(group: List, bias_mean, bias_std) -> None:
    """Classify one exposure-time group as darks or lights."""

    # ── Strategy A: bias frames available ───────────────────────────────────────
    if bias_mean is not None and bias_std is not None:
        sigma_margin   = max(bias_std * 6.0, bias_mean * 0.06)
        dark_threshold = bias_mean + sigma_margin
        for m in group:
            if m.mean <= dark_threshold:
                margin = (dark_threshold - m.mean) / max(sigma_margin, 0.01)
                m.classified_type = ImageType.DARK
                m.confidence = min(0.75 + margin * 0.15, 0.95)
            else:
                sky_signal = (m.mean - dark_threshold) / max(bias_mean, 1.0)
                m.classified_type = ImageType.LIGHT
                m.confidence = min(0.72 + sky_signal, 0.95)
        return

    # ── Strategy B: no bias frames ───────────────────────────────────────────────
    means    = sorted(m.mean for m in group)
    min_mean = means[0]
    max_mean = means[-1]
    spread   = max_mean - min_mean

    if spread >= min_mean * 0.05:
        # Two clusters present — find the largest gap in sorted means and split there.
        # This is more robust than a simple midpoint when clusters are unequal in size.
        gaps = [(means[i+1] - means[i], i) for i in range(len(means) - 1)]
        split_idx = max(gaps, key=lambda x: x[0])[1]
        split_val = (means[split_idx] + means[split_idx + 1]) / 2.0
        for m in group:
            if m.mean <= split_val:
                m.classified_type = ImageType.DARK
                m.confidence = min(0.70 + (split_val - m.mean) / max(spread, 0.01), 0.92)
            else:
                m.classified_type = ImageType.LIGHT
                m.confidence = min(0.70 + (m.mean - split_val) / max(spread, 0.01), 0.92)
    else:
        # Single cluster — use relative std.
        # Dark frames: Gaussian thermal noise → low rel_std.
        # Light frames: stars + sky gradient → higher rel_std.
        valid = [m for m in group if m.std is not None]
        avg_rel_std = (
            sum(m.std / max(m.mean, 1.0) for m in valid) / len(valid)
        ) if valid else 0.0
        img_type = ImageType.LIGHT if avg_rel_std > 0.08 else ImageType.DARK
        conf = min(0.50 + abs(avg_rel_std - 0.08) * 3.0, 0.78)
        for m in group:
            m.classified_type = img_type
            m.confidence = conf


def get_summary(results: List[ImageMetadata]) -> dict:
    summary = {'total': len(results), 'by_type': {}, 'errors': 0}
    for t in ImageType:
        c = sum(1 for r in results if r.classified_type == t)
        if c > 0:
            summary['by_type'][t.value] = c
    return summary
