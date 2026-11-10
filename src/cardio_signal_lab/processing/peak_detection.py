"""NeuroKit2 wrappers for ECG, PPG, and EDA peak detection.

Uses step-by-step NeuroKit2 functions (clean -> peaks) for better control
than the all-in-one process functions. Returns peak indices compatible with
PeakData model.

Ported from Hyperacousie_TCC and Acute_Tinnitus_PPG NeuroKit2 patterns.
"""
from __future__ import annotations

import numpy as np
from loguru import logger
from scipy.signal import peak_prominences

from cardio_signal_lab.processing.pipeline import register_operation


def _filter_low_amplitude_peaks(
    peak_indices: np.ndarray,
    cleaned: np.ndarray,
    min_height_ratio: float,
) -> tuple[np.ndarray, float]:
    """Drop peaks whose height falls below a fraction of the median height.

    Peak height is measured as prominence: the vertical distance from the peak
    to the higher of the two surrounding troughs (scipy.signal.peak_prominences).
    Prominence is robust to residual baseline offset and is the same quantity
    NeuroKit2 reports as "Height" in signal_findpeaks. Peaks with prominence
    below ``min_height_ratio * median(prominences)`` are rejected, removing
    low-amplitude spurious detections while retaining genuine beats.

    Args:
        peak_indices: Detected peak indices (integer sample positions)
        cleaned: The cleaned signal the peaks were detected on
        min_height_ratio: Height floor as a fraction of the median peak height

    Returns:
        (kept_indices, median_height): kept_indices is a subset of peak_indices;
        median_height is the median prominence the floor was computed from.
    """
    if len(peak_indices) == 0:
        return peak_indices, 0.0

    prominences = np.nan_to_num(
        peak_prominences(cleaned, peak_indices)[0], nan=0.0
    )

    median_height = float(np.median(prominences))
    if median_height <= 0 or min_height_ratio <= 0:
        return peak_indices, median_height

    floor = min_height_ratio * median_height
    kept = peak_indices[prominences >= floor]
    return kept, median_height


def detect_ecg_peaks(
    samples: np.ndarray,
    sampling_rate: float,
    *,
    clean_method: str = "neurokit",
    peak_method: str = "neurokit",
    min_height_ratio: float = 0.2,
) -> np.ndarray:
    """Detect R-peaks in ECG signal using NeuroKit2.

    Pipeline: clean -> detect peaks -> amplitude filter -> return indices.
    Default methods tested in Hyperacousie_TCC project.

    Args:
        samples: ECG signal samples (1D array)
        sampling_rate: Sampling rate in Hz
        clean_method: NeuroKit2 cleaning method
            ('neurokit', 'biosppy', 'pantompkins1985', 'hamilton2002')
        peak_method: Peak detection method
            ('neurokit', 'pantompkins1985', 'hamilton2002', 'martinez2004')
        min_height_ratio: Minimum peak prominence as a fraction of the median
            peak prominence (default 0.2). Peaks below this floor are dropped.

    Returns:
        Array of peak indices (sample positions)
    """
    import neurokit2 as nk

    try:
        # Step 1: Clean ECG signal
        ecg_cleaned = nk.ecg_clean(samples, sampling_rate=int(sampling_rate), method=clean_method)

        # Step 2: Detect R-peaks
        _, rpeaks = nk.ecg_peaks(ecg_cleaned, sampling_rate=int(sampling_rate), method=peak_method)

        peak_indices = rpeaks.get("ECG_R_Peaks", np.array([], dtype=int))
        if peak_indices is None:
            peak_indices = np.array([], dtype=int)
        peak_indices = np.asarray(peak_indices, dtype=int)
        n_detected = len(peak_indices)

        # Step 3: Reject low-amplitude peaks below the median-height floor
        peak_indices, median_height = _filter_low_amplitude_peaks(
            peak_indices, ecg_cleaned, min_height_ratio
        )
        n_rejected = n_detected - len(peak_indices)

        logger.info(
            f"ECG peak detection: {n_detected} R-peaks found, "
            f"{n_rejected} rejected below {min_height_ratio:.0%} of median height "
            f"({median_height:.3f}) -> {len(peak_indices)} kept "
            f"(clean={clean_method}, detect={peak_method})"
        )

        if len(peak_indices) < 3:
            logger.warning(
                f"Only {len(peak_indices)} peaks detected - may indicate signal quality issues "
                f"or inappropriate parameters"
            )

        return peak_indices

    except Exception as e:
        logger.error(f"ECG peak detection failed: {e}")
        logger.warning("Returning empty peak array - check signal quality and sampling rate")
        return np.array([], dtype=int)


def detect_ppg_peaks(
    samples: np.ndarray,
    sampling_rate: float,
    *,
    clean_method: str = "elgendi",
    peak_method: str = "elgendi",
    min_height_ratio: float = 0.2,
) -> np.ndarray:
    """Detect systolic peaks in PPG signal using NeuroKit2.

    Pipeline: clean -> find peaks -> amplitude filter -> return indices.

    Args:
        samples: PPG signal samples (1D array)
        sampling_rate: Sampling rate in Hz
        clean_method: NeuroKit2 cleaning method ('elgendi')
        peak_method: Peak detection method ('elgendi')
        min_height_ratio: Minimum peak prominence as a fraction of the median
            peak prominence (default 0.2). Peaks below this floor are dropped.

    Returns:
        Array of peak indices (sample positions)
    """
    import neurokit2 as nk

    try:
        # Step 1: Clean PPG signal
        ppg_cleaned = nk.ppg_clean(samples, sampling_rate=int(sampling_rate), method=clean_method)

        # Step 2: Detect peaks
        info = nk.ppg_findpeaks(ppg_cleaned, sampling_rate=int(sampling_rate), method=peak_method)

        peak_indices = info.get("PPG_Peaks", np.array([], dtype=int))
        if peak_indices is None:
            peak_indices = np.array([], dtype=int)
        peak_indices = np.asarray(peak_indices, dtype=int)
        n_detected = len(peak_indices)

        # Step 3: Reject low-amplitude peaks below the median-height floor
        peak_indices, median_height = _filter_low_amplitude_peaks(
            peak_indices, ppg_cleaned, min_height_ratio
        )
        n_rejected = n_detected - len(peak_indices)

        logger.info(
            f"PPG peak detection: {n_detected} peaks found, "
            f"{n_rejected} rejected below {min_height_ratio:.0%} of median height "
            f"({median_height:.3f}) -> {len(peak_indices)} kept "
            f"(clean={clean_method}, detect={peak_method})"
        )

        if len(peak_indices) < 3:
            logger.warning(
                f"Only {len(peak_indices)} peaks detected - may indicate signal quality issues "
                f"or inappropriate parameters"
            )

        return peak_indices

    except Exception as e:
        logger.error(f"PPG peak detection failed: {e}")
        logger.warning("Returning empty peak array - check signal quality and sampling rate")
        return np.array([], dtype=int)


def detect_eda_features(
    samples: np.ndarray,
    sampling_rate: float,
    *,
    method: str = "neurokit",
    decompose_method: str = "highpass",
) -> np.ndarray:
    """Detect SCR (Skin Conductance Response) peaks in EDA signal.

    Uses nk.eda_process() for full processing, then extracts SCR peak indices.

    Args:
        samples: EDA signal samples (1D array)
        sampling_rate: Sampling rate in Hz
        method: NeuroKit2 processing method
        decompose_method: Phasic decomposition method ('highpass')

    Returns:
        Array of SCR peak indices (sample positions)
    """
    import neurokit2 as nk

    try:
        # Process EDA (clean + decompose + detect SCR peaks)
        signals, info = nk.eda_process(samples, sampling_rate=int(sampling_rate), method=method)

        peak_indices = info.get("SCR_Peaks", np.array([], dtype=int))
        if peak_indices is None:
            peak_indices = np.array([], dtype=int)
        peak_indices = np.asarray(peak_indices, dtype=int)

        # Filter out NaN values that NeuroKit2 sometimes returns
        peak_indices = peak_indices[~np.isnan(peak_indices.astype(float))].astype(int)

        logger.info(f"EDA feature detection: {len(peak_indices)} SCR peaks found")

        if len(peak_indices) == 0:
            logger.warning(
                "No SCR peaks detected - EDA signal may lack phasic responses "
                "or may be too short/noisy"
            )

        return peak_indices

    except Exception as e:
        logger.error(f"EDA feature detection failed: {e}")
        logger.warning("Returning empty peak array - check signal quality and sampling rate")
        return np.array([], dtype=int)


# Pipeline wrappers that return the processed signal unchanged but store peak
# indices as a side effect. Since peak detection doesn't modify the signal
# itself, we use a different approach: these are called directly from the GUI,
# not through the pipeline. But we register them for recording in processing
# history.

def _pipeline_detect_ecg_peaks(samples, sampling_rate, **params):
    """Pipeline wrapper - detects peaks but returns signal unchanged.

    Peak indices are stored via AppSignals.peaks_updated by the GUI layer.
    """
    detect_ecg_peaks(samples, sampling_rate, **params)
    return samples


def _pipeline_detect_ppg_peaks(samples, sampling_rate, **params):
    detect_ppg_peaks(samples, sampling_rate, **params)
    return samples


def _pipeline_detect_eda_features(samples, sampling_rate, **params):
    detect_eda_features(samples, sampling_rate, **params)
    return samples


register_operation("detect_ecg_peaks", _pipeline_detect_ecg_peaks)
register_operation("detect_ppg_peaks", _pipeline_detect_ppg_peaks)
register_operation("detect_eda_features", _pipeline_detect_eda_features)


def _pipeline_ecg_clean(samples, sampling_rate, **params):
    """Pipeline wrapper for nk.ecg_clean()."""
    import neurokit2 as nk
    return nk.ecg_clean(samples, sampling_rate=int(sampling_rate))


def _pipeline_ppg_clean(samples, sampling_rate, **params):
    """Pipeline wrapper for nk.ppg_clean()."""
    import neurokit2 as nk
    return nk.ppg_clean(samples, sampling_rate=int(sampling_rate))


def _pipeline_eda_clean(samples, sampling_rate, **params):
    """Pipeline wrapper for nk.eda_clean()."""
    import neurokit2 as nk
    return nk.eda_clean(samples, sampling_rate=int(sampling_rate))


def _pipeline_eda_decompose(samples, sampling_rate, method="highpass", **params):
    """Pipeline marker for EDA decomposition — returns signal unchanged.

    Decomposition is performed as a side effect in the GUI layer (both tonic
    and phasic are shown in the derived panel). This step is recorded in the
    pipeline so the derived panel can be reconstructed on session reload.
    """
    return samples


register_operation("ecg_clean", _pipeline_ecg_clean)
register_operation("ppg_clean", _pipeline_ppg_clean)
register_operation("eda_clean", _pipeline_eda_clean)
register_operation("eda_decompose", _pipeline_eda_decompose)
