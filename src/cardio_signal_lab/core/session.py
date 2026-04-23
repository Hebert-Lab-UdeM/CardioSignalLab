"""Session save/load for resuming work.

Saves and restores per-channel:
- Source file path + SHA-256 checksum for integrity verification
- Processing pipeline (per channel)
- Peak corrections (per channel)
- Bad segments (per channel)
- Session metadata (app version, save timestamp, operator name)
- View state (optional)

Schema versions:
  1 - original single-channel format
  2 - per-channel dict, no metadata
  3 - per-channel dict + meta block (app_version, saved_at, operator)
      + source_file_sha256 checksum
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from cardio_signal_lab.core.data_models import BadSegment, PeakData

CURRENT_SCHEMA_VERSION = 3


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _serialize_channel_state(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize a single channel's in-memory state to a JSON-compatible dict."""
    from cardio_signal_lab.processing.pipeline import ProcessingPipeline

    peaks = state.get("peaks")
    bad_segments = state.get("bad_segments", [])

    pipeline = ProcessingPipeline()
    pipeline.steps = list(state.get("pipeline_steps", []))

    return {
        "pipeline": pipeline.serialize(),
        "peaks": (
            {
                "indices": peaks.indices.tolist(),
                "classifications": peaks.classifications.tolist(),
            }
            if peaks is not None and peaks.num_peaks > 0
            else None
        ),
        "bad_segments": [
            {"start_idx": seg.start_idx, "end_idx": seg.end_idx, "source": seg.source}
            for seg in bad_segments
        ],
        "reviewed": state.get("reviewed", False),
    }


def _deserialize_channel_state(data: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct channel state dict from saved JSON."""
    from cardio_signal_lab.processing.pipeline import ProcessingPipeline

    pipeline = ProcessingPipeline.deserialize(data.get("pipeline", {}))

    peaks_data = data.get("peaks")
    peaks = None
    if peaks_data:
        peaks = PeakData(
            indices=np.array(peaks_data["indices"], dtype=int),
            classifications=np.array(peaks_data["classifications"], dtype=int),
        )

    bad_segments = [
        BadSegment(
            start_idx=seg["start_idx"],
            end_idx=seg["end_idx"],
            source=seg.get("source", "manual"),
        )
        for seg in data.get("bad_segments", [])
    ]

    return {
        "pipeline_steps": pipeline.steps,
        "peaks": peaks,
        "bad_segments": bad_segments,
        "reviewed": data.get("reviewed", False),
        # Fields not persisted are left None; main_window re-derives them when
        # the pipeline is replayed on load.
        "raw_samples": None,
        "eda_tonic": None,
        "eda_phasic": None,
        "structural_ops": [],
        "original_samples": None,
        "original_timestamps": None,
        "original_sampling_rate": None,
    }


def save_session(
    source_file: Path | str,
    channel_states: dict[tuple, dict[str, Any]],
    output_path: Path | str,
    view_state: dict[str, Any] | None = None,
    operator_name: str = "",
    notes: str = "",
    derived_channels: list[dict] | None = None,
) -> Path:
    """Save session to JSON file for resuming work.

    Args:
        source_file: Path to original data file
        channel_states: Per-channel state dict keyed by (signal_type, channel_name).
        output_path: Output session file path (.csl.json)
        view_state: Optional view state (zoom range, selected signal)
        operator_name: Name of the operator (recorded in metadata)
        notes: Free-text session notes

    Returns:
        Path to created session file
    """
    import cardio_signal_lab

    output_path = Path(output_path)
    source_file = Path(source_file)

    channels: dict[str, Any] = {}
    for (signal_type, channel_name), state in channel_states.items():
        key = f"{signal_type}|{channel_name}"
        channels[key] = _serialize_channel_state(state)

    checksum = _sha256(source_file)

    session_data = {
        "version": CURRENT_SCHEMA_VERSION,
        "meta": {
            "app_version": cardio_signal_lab.__version__,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "operator": operator_name,
        },
        "source_file": str(source_file.absolute()),
        "source_file_sha256": checksum,
        "notes": notes,
        "channels": channels,
        "derived_channels": derived_channels or [],
        "view_state": view_state or {},
    }

    with open(output_path, "w") as f:
        json.dump(session_data, f, indent=2)

    n_channels = len(channels)
    logger.info(f"Saved session to {output_path} ({n_channels} channel(s))")
    return output_path


def load_session(session_path: Path | str) -> dict[str, Any]:
    """Load session from JSON file.

    Returns:
        Dict with keys:
            source_file (str),
            source_file_sha256 (str | None),
            channels (dict of (signal_type_str, channel_name) -> deserialized state),
            view_state (dict),
            meta (dict with app_version, saved_at, operator),
            notes (str),
            version (int)
    """
    session_path = Path(session_path)

    with open(session_path, "r") as f:
        raw = json.load(f)

    version = raw.get("version", 1)

    if version == 1:
        raw = _migrate_v1(raw)
    elif version == 2:
        raw = _migrate_v2(raw)

    channels: dict[tuple, dict[str, Any]] = {}
    for key, state_data in raw.get("channels", {}).items():
        signal_type_str, channel_name = key.split("|", 1)
        channels[(signal_type_str, channel_name)] = _deserialize_channel_state(state_data)

    result = {
        "version": CURRENT_SCHEMA_VERSION,
        "meta": raw.get("meta", {}),
        "source_file": raw["source_file"],
        "source_file_sha256": raw.get("source_file_sha256"),
        "notes": raw.get("notes", ""),
        "channels": channels,
        "derived_channels": raw.get("derived_channels", []),
        "view_state": raw.get("view_state", {}),
    }

    n_channels = len(channels)
    logger.info(f"Loaded session from {session_path} ({n_channels} channel(s))")
    return result


def verify_source_checksum(source_path: Path, expected_sha256: str | None) -> bool:
    """Check whether the source file matches the checksum stored in the session.

    Returns True if checksums match or if no expected checksum is available
    (e.g., session saved by an older version).  Returns False on mismatch.
    """
    if expected_sha256 is None:
        return True
    actual = _sha256(source_path)
    match = actual == expected_sha256
    if not match:
        logger.warning(
            f"Source file checksum mismatch for {source_path.name}: "
            f"expected {expected_sha256[:12]}..., got {actual[:12]}..."
        )
    return match


def _migrate_v1(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a v1 session (single pipeline + peaks) to v3 structure."""
    view_state = raw.get("view_state", {})
    signal_type = view_state.get("signal_type", "unknown")
    channel_name = view_state.get("channel_name", "unknown")
    key = f"{signal_type}|{channel_name}"

    channel_data: dict[str, Any] = {
        "pipeline": raw.get("processing_pipeline", {}),
        "peaks": raw.get("peaks"),
        "bad_segments": [],
    }

    logger.info(f"Migrating v1 session: single channel mapped to key '{key}'")
    return {
        "version": CURRENT_SCHEMA_VERSION,
        "meta": {},
        "source_file": raw["source_file"],
        "source_file_sha256": None,
        "notes": "",
        "channels": {key: channel_data},
        "view_state": view_state,
    }


def _migrate_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """Add meta block and checksum fields missing from v2 sessions."""
    logger.info("Migrating v2 session to v3 (adding meta/checksum fields)")
    raw["version"] = CURRENT_SCHEMA_VERSION
    raw.setdefault("meta", {})
    raw.setdefault("source_file_sha256", None)
    raw.setdefault("notes", "")
    return raw
