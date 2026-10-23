"""Import helpers for replacing or supplementing data loaded from XDF/CSV.

Two importers are provided:

load_events_csv(path)
    Replace XDF event markers with events from an external CSV.
    Auto-detects timestamp and label columns by common name patterns.

load_peaks_binary_csv(path, signal_length)
    Load pre-corrected peak positions from a binary (0/1) CSV column,
    as produced by the EKG_Peak_Corrector and similar tools.
    Column name is expected to contain "peak" (case-insensitive).
    All imported peaks are classified MANUAL.
    Also accepts this app's own RR/NN interval and annotation exports; peaks
    are mapped by their time columns onto the target signal's samples, and
    their classifications are preserved.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from cardio_signal_lab.core.data_models import EventData, PeakClassification, PeakData
from cardio_signal_lab.core.file_loader import detect_csv_delimiter


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

# Column name substrings (lower-case) tried in order for timestamp detection
_TIME_CANDIDATES = ["time_s", "time", "timestamp", "onset", "t"]
# Column name substrings tried in order for label detection
_LABEL_CANDIDATES = ["label", "event", "name", "description", "marker", "code"]


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column whose lower-cased name contains any candidate."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for col_low, col_orig in cols_lower.items():
            if cand in col_low:
                return col_orig
    return None


def load_events_csv(path: Path | str) -> list[EventData]:
    """Load event markers from a CSV file.

    Expected columns (detected by name, case-insensitive):
    - Timestamp: any column whose name contains 'time', 'timestamp', or 'onset'
    - Label:     any column whose name contains 'label', 'event', or 'name'

    If auto-detection fails, column 0 is used as timestamp and column 1 as label.

    Args:
        path: Path to the CSV file

    Returns:
        List of EventData sorted by timestamp

    Raises:
        ValueError: If the file has fewer than 2 columns or no numeric timestamp column
        FileNotFoundError: If path does not exist
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Events file not found: {path}")

    df = pd.read_csv(path, sep=detect_csv_delimiter(path))
    if df.empty:
        logger.warning(f"Events CSV is empty: {path}")
        return []

    # Detect timestamp column
    time_col = _find_column(df, _TIME_CANDIDATES)
    if time_col is None:
        # Fall back to first numeric column
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            raise ValueError(f"No numeric column found for timestamps in {path.name}")
        time_col = numeric_cols[0]
        logger.warning(f"Timestamp column not identified by name; using '{time_col}'")
    else:
        logger.debug(f"Using '{time_col}' as timestamp column")

    # Detect label column
    label_col = _find_column(df, _LABEL_CANDIDATES)
    if label_col is None:
        # Fall back to first non-numeric column, then first column
        str_cols = df.select_dtypes(exclude="number").columns.tolist()
        label_col = str_cols[0] if str_cols else df.columns[1] if len(df.columns) > 1 else time_col
        logger.warning(f"Label column not identified by name; using '{label_col}'")
    else:
        logger.debug(f"Using '{label_col}' as label column")

    events = []
    for _, row in df.iterrows():
        try:
            t = float(row[time_col])
            label = str(row[label_col]).strip()
            if label == "" or label == "nan":
                label = "event"
            events.append(EventData(timestamp=t, label=label))
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed event row: {row.to_dict()} ({e})")

    events.sort(key=lambda ev: ev.timestamp)
    logger.info(
        f"Loaded {len(events)} events from {path.name} "
        f"(time_col='{time_col}', label_col='{label_col}')"
    )
    return events


# ---------------------------------------------------------------------------
# Peaks
# ---------------------------------------------------------------------------

def load_peaks_binary_csv(
    path: Path | str,
    signal_length: int,
    signal_timestamps: np.ndarray | None = None,
) -> PeakData:
    """Load corrected peaks from a binary (0/1) CSV column.

    The file must contain a column whose name includes 'peak' (case-insensitive),
    e.g. 'PPG_Peaks', 'ECG_Peaks', 'peaks'.  Each row corresponds to one signal
    sample: 1 = peak, 0 = no peak.

    All imported peaks are classified MANUAL (shown green, included in heart
    rate calculation).  If the file contains a 'classification' or 'label' column
    that matches PeakClassification names (AUTO/MANUAL/ECTOPIC/BAD), those values
    are used instead.

    Args:
        path: Path to the CSV file
        signal_length: Expected number of samples (used for bounds checking)
        signal_timestamps: Timestamps (s) of the target signal. Used to map
            peak times from this app's RR/NN/annotation exports onto samples,
            which is independent of the sampling rate at export time.

    Returns:
        PeakData with sorted indices and MANUAL classifications

    Raises:
        FileNotFoundError: If path does not exist
        ValueError: If no peaks column is found or peak indices are out of range
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Peaks file not found: {path}")

    df = pd.read_csv(path, sep=detect_csv_delimiter(path))
    if df.empty:
        logger.warning(f"Peaks CSV is empty: {path}")
        return PeakData(indices=np.array([], dtype=int), classifications=np.array([], dtype=int))

    # Per-peak / per-interval formats written by this app's own exporters
    # (core/exporter.py) bypass the binary-column path below.
    if {"peak1_index", "peak2_index"} <= set(df.columns) or "peak_index" in df.columns:
        return _load_peaks_from_export(df, path, signal_length, signal_timestamps)

    # Find the binary peaks column
    peak_col = None
    for col in df.columns:
        if "peak" in col.lower():
            peak_col = col
            break

    if peak_col is None:
        # Last resort: try first column if it contains only 0s and 1s
        first_col = df.columns[0]
        unique_vals = set(df[first_col].dropna().unique())
        if unique_vals <= {0, 1, 0.0, 1.0}:
            peak_col = first_col
            logger.warning(
                f"No column with 'peak' in name found; using '{peak_col}' "
                f"(contains only 0/1 values)"
            )
        else:
            raise ValueError(
                f"No peaks column found in {path.name}. "
                f"Expected a column whose name contains 'peak' (e.g. 'PPG_Peaks')."
            )

    logger.debug(f"Using '{peak_col}' as peaks column from {path.name}")

    # Coerce to float so that string "0"/"1" and boolean True/False all compare
    # correctly with == 1.  errors='coerce' turns unparseable cells into NaN.
    binary = pd.to_numeric(df[peak_col], errors="coerce").fillna(0).to_numpy()

    # Validate length: the binary array must have exactly one entry per signal
    # sample.  A mismatch means the CSV was generated at a different sampling
    # rate; peak indices would then map to wrong timestamps (spread out or
    # compressed) and many may fall outside the signal bounds.
    csv_length = len(binary)
    if csv_length != signal_length:
        logger.warning(
            f"Peak CSV row count ({csv_length}) does not match signal length "
            f"({signal_length}) — difference of {csv_length - signal_length} samples.  "
            f"Peak indices will be scaled by {signal_length}/{csv_length} "
            f"= {signal_length/csv_length:.6f} to correct for the sampling rate difference."
        )

    indices = np.where(binary == 1)[0].astype(int)

    # If the CSV and signal have different lengths (same duration, different effective
    # sampling rates due to resampling rounding), scale the peak indices so they map
    # to the correct timestamps in the signal.  Without this, peaks drift progressively
    # earlier/later as the index grows.
    if csv_length != signal_length:
        scale = signal_length / csv_length
        indices = np.round(indices * scale).astype(int)
    logger.debug(
        f"Binary peak column: {csv_length} rows, {len(indices)} peaks "
        f"(values seen: {np.unique(binary[:100]).tolist()})"
    )

    # Bounds check (should not trigger after the length check above, but kept
    # as a safety net for edge cases such as a partial signal crop).
    out_of_range = indices[indices >= signal_length]
    if len(out_of_range) > 0:
        logger.warning(
            f"{len(out_of_range)} peak indices >= signal_length ({signal_length}); "
            f"they will be dropped"
        )
        indices = indices[indices < signal_length]

    # Classification: MANUAL by default; honour a classification column if present
    classification_col = _find_column(df, ["classification", "class", "label"])
    _NAME_TO_VAL = {c.name: c.value for c in PeakClassification}

    if classification_col is not None and classification_col != peak_col:
        # Extract classification for peak rows only
        cls_series = df[classification_col].iloc[indices]
        classifications = np.full(len(indices), PeakClassification.MANUAL.value, dtype=int)
        for i, val in enumerate(cls_series):
            try:
                v = int(val)
                if v in {c.value for c in PeakClassification}:
                    classifications[i] = v
                    continue
            except (ValueError, TypeError):
                pass
            # Try string name
            name = str(val).strip().upper()
            if name in _NAME_TO_VAL:
                classifications[i] = _NAME_TO_VAL[name]
        logger.debug(f"Read classifications from '{classification_col}' column")
    else:
        classifications = np.full(len(indices), PeakClassification.MANUAL.value, dtype=int)

    logger.info(
        f"Loaded {len(indices)} peaks from {path.name} "
        f"(column='{peak_col}', all MANUAL)"
    )
    return PeakData(indices=indices, classifications=classifications)


def _parse_classification(value) -> int:
    """Map a numeric code (0-3) or name (AUTO/MANUAL/ECTOPIC/BAD) to a value.

    Unrecognized or missing values default to MANUAL.
    """
    valid_values = {c.value for c in PeakClassification}
    try:
        numeric_value = int(value)
        if numeric_value in valid_values:
            return numeric_value
    except (ValueError, TypeError):
        pass
    name = str(value).strip().upper()
    if name in PeakClassification.__members__:
        return PeakClassification[name].value
    return PeakClassification.MANUAL.value


def _nearest_sample_indices(peak_times: np.ndarray, signal_timestamps: np.ndarray) -> np.ndarray:
    """Map peak times (s) to the nearest sample index of the target signal.

    Times more than one median sample period outside the signal's time range
    are returned as -1 so the caller can drop them.
    """
    right = np.clip(np.searchsorted(signal_timestamps, peak_times), 1, len(signal_timestamps) - 1)
    left = right - 1
    nearest = np.where(
        peak_times - signal_timestamps[left] <= signal_timestamps[right] - peak_times, left, right
    )
    sample_period = np.median(np.diff(signal_timestamps))
    outside = (peak_times < signal_timestamps[0] - sample_period) | (
        peak_times > signal_timestamps[-1] + sample_period
    )
    return np.where(outside, -1, nearest)


def _load_peaks_from_export(
    df: pd.DataFrame,
    path: Path,
    signal_length: int,
    signal_timestamps: np.ndarray | None,
) -> PeakData:
    """Load peaks from the per-peak / per-interval CSV exports of core/exporter.py.

    Supported layouts:
    - RR/NN intervals (export_intervals): one row per interval with
      peak1_time_s, peak2_time_s, peak1_index, peak2_index,
      peak1_classification, peak2_classification. Peaks are the union of
      both columns of each pair.
    - Annotations (export_annotations): one row per peak with time_s,
      peak_index and classification (numeric code) / classification_label.

    Peak positions are taken from the time columns and mapped to the nearest
    sample of the target signal. The index columns refer to the signal as it
    was at export time, which is usually cropped and resampled (e.g. the
    Standard Processing macro resamples to 250 Hz), so they do not match the
    raw signal's sample grid. Crop/resample keep the original time base, so
    times remain valid. Index columns are only used if no timestamps are
    supplied or the file has no time columns.

    Classifications are read from the file; missing ones default to MANUAL.

    Note: an NN-interval export only contains intervals that passed the
    validity filters, so peaks bounding only excluded intervals (e.g. ECTOPIC
    or BAD peaks) are absent from the file and cannot be recovered.
    """
    if "peak_index" in df.columns:
        layout = "annotations"
        time_cols, index_cols = ["time_s"], ["peak_index"]
        class_col = next(
            (c for c in ("classification", "classification_label") if c in df.columns), None
        )
        class_cols = [class_col]
    else:
        layout = "intervals"
        time_cols, index_cols = ["peak1_time_s", "peak2_time_s"], ["peak1_index", "peak2_index"]
        class_cols = ["peak1_classification", "peak2_classification"]
        if "nn_interval_ms" in df.columns:
            logger.warning(
                f"{path.name} is an NN-interval export; peaks bounding only excluded "
                f"intervals (ectopic/bad/invalid) are not in the file and will be missing"
            )

    def _stack(columns: list[str | None], numeric: bool) -> np.ndarray:
        parts = []
        for col in columns:
            if col is None or col not in df.columns:
                parts.append(np.full(len(df), np.nan if numeric else None, dtype=float if numeric else object))
            elif numeric:
                parts.append(pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float))
            else:
                parts.append(df[col].to_numpy())
        return np.concatenate(parts)

    class_values = _stack(class_cols, numeric=False)
    use_times = signal_timestamps is not None and all(c in df.columns for c in time_cols)

    if use_times:
        source_values = _stack(time_cols, numeric=True)
    else:
        source_values = _stack(index_cols, numeric=True)
        logger.warning(
            f"Using sample-index columns from {path.name}; positions are only correct if "
            f"the signal has the same sampling rate and crop as at export time"
        )

    valid_mask = ~np.isnan(source_values)
    source_values = source_values[valid_mask]
    class_values = class_values[valid_mask]

    if use_times:
        index_values = _nearest_sample_indices(source_values, np.asarray(signal_timestamps))
    else:
        index_values = source_values.astype(int)

    # Deduplicate (each interior peak appears in two consecutive intervals);
    # np.unique also sorts, keeping the classification of the first occurrence.
    indices, first_occurrence = np.unique(index_values, return_index=True)
    classifications = np.array(
        [_parse_classification(class_values[i]) for i in first_occurrence], dtype=int
    )

    out_of_range_mask = (indices < 0) | (indices >= signal_length)
    if out_of_range_mask.any():
        logger.warning(
            f"{int(out_of_range_mask.sum())} peak(s) fall outside the current signal; "
            f"they will be dropped (was the file exported from a different signal/crop?)"
        )
        indices = indices[~out_of_range_mask]
        classifications = classifications[~out_of_range_mask]

    logger.info(
        f"Loaded {len(indices)} peaks from {path.name} "
        f"({layout} export, mapped by {'time' if use_times else 'sample index'})"
    )
    return PeakData(indices=indices, classifications=classifications)
