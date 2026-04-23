#!/usr/bin/env python
"""
Convert a MATLAB .mat file (containing XDF streams structure) back to XDF format.

Workflow:
1. In MATLAB: Load XDF, manually fix the corrupted arrays in debugger
2. In MATLAB: save('xdf_data.mat', 'streams', 'header')
3. In Python: python mat_to_xdf.py xdf_data.mat output.xdf

Usage:
    python mat_to_xdf.py <input.mat> [output.xdf]

If output.xdf is not specified, it defaults to input_name.xdf
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def mat_to_xdf(mat_file: str, xdf_file: str = None):
    """
    Convert MATLAB .mat file (with corrected XDF streams) to XDF format.

    Args:
        mat_file: Path to .mat file containing 'streams' and 'header'
        xdf_file: Output XDF path (defaults to mat_file with .xdf extension)
    """
    mat_path = Path(mat_file)
    if not mat_path.exists():
        raise FileNotFoundError(f"File not found: {mat_path}")

    if xdf_file is None:
        xdf_file = mat_path.with_suffix('.xdf')
    else:
        xdf_file = Path(xdf_file)

    logger.info(f"Loading MATLAB file: {mat_path.name}")

    # Load MATLAB file
    try:
        import scipy.io
        mat_data = scipy.io.loadmat(str(mat_path), squeeze_me=True)
        logger.info(f"Loaded MATLAB file")
    except ImportError:
        logger.error("scipy not installed. Install with: pip install scipy")
        raise

    # Extract streams and header
    if 'streams' not in mat_data:
        raise ValueError("MATLAB file must contain 'streams' variable")

    streams_mat = mat_data['streams']
    header = mat_data.get('header', None)

    logger.info(f"Extracted {len(streams_mat) if hasattr(streams_mat, '__len__') else 1} stream(s)")

    # Convert MATLAB structure to Python format for pyxdf
    logger.info("Converting MATLAB structure to XDF format...")

    streams = _matlab_to_xdf_structure(streams_mat)

    logger.info(f"Converted structure: {len(streams)} streams")

    # Write XDF using pyxdf or alternative method
    try:
        import pyxdf
        logger.info(f"Writing to XDF: {xdf_file.name}")

        # Check if save_xdf is available
        if hasattr(pyxdf, 'save_xdf'):
            pyxdf.save_xdf(str(xdf_file), streams, header)
            logger.info("✓ Successfully wrote XDF file")
            logger.info(f"Output: {xdf_file}")
            return True
        else:
            logger.error("pyxdf.save_xdf() not available in this version of pyxdf")
            logger.error("\nAlternative: Use MATLAB to re-save the corrected file directly:")
            logger.error("  1. After manually fixing the data in MATLAB debugger")
            logger.error("  2. Call: xdf_write('fixed_filename.xdf', streams, header)")
            logger.error("  3. Or save to a new XDF file using your acquisition software")
            raise ValueError("pyxdf write function not available")

    except Exception as e:
        logger.error(f"Failed to write XDF: {e}")
        raise


def _matlab_to_xdf_structure(streams_mat):
    """
    Convert MATLAB streams structure to pyxdf format.

    MATLAB structure format (from load_xdf):
    streams{i}.info - stream metadata
    streams{i}.time_series - signal data
    streams{i}.time_stamps - timestamps

    pyxdf expects:
    streams[i]['info'] - dict with metadata
    streams[i]['time_series'] - numpy array
    streams[i]['time_stamps'] - numpy array
    """
    import numpy as np

    # Handle scipy.io loaded MATLAB structures
    # scipy returns numpy arrays of objects for cell arrays

    # Ensure streams_mat is iterable
    try:
        # Check if it's a numpy array of objects (cell array)
        if hasattr(streams_mat, 'shape') and len(streams_mat.shape) > 0:
            # It's an array, iterate through it
            streams_list = list(streams_mat)
        elif isinstance(streams_mat, (list, tuple)):
            streams_list = list(streams_mat)
        elif isinstance(streams_mat, dict):
            # Single structure
            streams_list = [streams_mat]
        else:
            # Try to iterate
            streams_list = [streams_mat]
    except:
        streams_list = [streams_mat]

    streams = []
    for stream_mat in streams_list:
        try:
            # Extract fields from MATLAB structure
            info_data = stream_mat.get('info') if hasattr(stream_mat, 'get') else stream_mat['info']
            time_series_data = stream_mat.get('time_series') if hasattr(stream_mat, 'get') else stream_mat['time_series']
            time_stamps_data = stream_mat.get('time_stamps') if hasattr(stream_mat, 'get') else stream_mat['time_stamps']

            stream = {
                'info': _convert_info_struct(info_data) if info_data is not None else {},
                'time_series': np.asarray(time_series_data) if time_series_data is not None else np.array([]),
                'time_stamps': np.asarray(time_stamps_data) if time_stamps_data is not None else np.array([])
            }
            streams.append(stream)
        except Exception as e:
            logger.warning(f"Error processing stream: {e}, skipping")
            continue

    return streams


def _convert_info_struct(info_mat):
    """Convert MATLAB info structure to Python dict."""
    info = {}

    if isinstance(info_mat, dict):
        for key, value in info_mat.items():
            # Convert MATLAB cell arrays and nested structures to Python
            if hasattr(value, 'size'):  # numpy array
                if value.size == 1:
                    info[key] = value.item()
                else:
                    info[key] = value.tolist()
            elif isinstance(value, dict):
                info[key] = _convert_info_struct(value)
            else:
                info[key] = value

    return info


def _write_xdf_alternative(xdf_file, streams, header):
    """
    Alternative write method if pyxdf.save_xdf not available.
    This is a fallback - may not work for all XDF structures.
    """
    logger.warning("Using alternative XDF write method (may be incomplete)")

    import struct
    import time

    with open(xdf_file, 'wb') as f:
        # XDF magic number
        f.write(b'XDF:')

        # Write streams
        for stream in streams:
            # Simplified stream writing - THIS IS INCOMPLETE
            # A proper XDF writer is complex, this is just for testing

            logger.warning("Alternative write is limited - recommend using scipy/pyxdf")
            break

        logger.info("Note: Alternative write method may not produce valid XDF")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mat_file = sys.argv[1]
    xdf_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        success = mat_to_xdf(mat_file, xdf_file)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
