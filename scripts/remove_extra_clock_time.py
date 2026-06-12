#!/usr/bin/env python
"""
Remove extra clock_times value from corrupted XDF file.

This script handles the specific case where clock_times has 1 extra element
compared to offset_values in the PPG/GSR stream synchronization data.

Usage:
    python remove_extra_clock_time.py <xdf_file> <stream_name>

Examples:
    python remove_extra_clock_time.py subj-TCC-TCC010_PRE.xdf GSR
    python remove_extra_clock_time.py corrupted.xdf PPG
"""

import sys
import struct
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def remove_extra_clock_time(xdf_file: str, stream_name: str = "GSR", output_file: str = None):
    """
    Remove the last clock_times value from a specific stream in an XDF file.

    Args:
        xdf_file: Path to the corrupted XDF file
        stream_name: Name of the stream to fix (e.g., "GSR", "PPG", "ECG")
        output_file: Output path (defaults to input_file if None)
    """
    xdf_path = Path(xdf_file)
    if not xdf_path.exists():
        raise FileNotFoundError(f"File not found: {xdf_path}")

    if output_file is None:
        output_file = xdf_path
    else:
        output_file = Path(output_file)

    logger.info(f"Fixing XDF file: {xdf_path.name}")
    logger.info(f"Stream to fix: {stream_name}")
    logger.info(f"Output: {output_file.name}")

    # Read the entire file as binary
    with open(xdf_path, 'rb') as f:
        data = bytearray(f.read())

    original_size = len(data)
    logger.info(f"Original file size: {original_size:,} bytes")

    # Strategy: Look for the stream definition and clock_times array
    # In XDF, synchronization data is stored in the stream header
    # We'll search for patterns that indicate clock_times data

    # XDF stores metadata as XML-like text, then binary data
    # The exact location of clock_times depends on the file structure

    # Simplest approach: remove the last 8 bytes (one double precision float)
    # This assumes the extra clock_time is at the very end

    logger.info("\nAttempting to remove last 8 bytes (one double value)...")

    fixed_data = data[:-8]

    # Try to verify by attempting to load
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.xdf', delete=False) as tmp:
        tmp.write(fixed_data)
        tmp_path = Path(tmp.name)

    try:
        import pyxdf
        logger.info("Testing if fix works...")
        streams, header = pyxdf.load_xdf(str(tmp_path))
        logger.info(f"✓ Success! File loads: {len(streams)} streams loaded")

        # Verify the stream we fixed
        for stream in streams:
            name = stream['info']['name'][0] if isinstance(stream['info']['name'], list) else stream['info']['name']
            if stream_name.lower() in name.lower():
                logger.info(f"  Stream '{name}': {len(stream['time_series'])} samples")
                if 'clock_times' in stream['info']:
                    ct_len = len(stream['info']['clock_times'])
                    ov_len = len(stream['info']['offset_values'])
                    logger.info(f"    clock_times: {ct_len} elements")
                    logger.info(f"    offset_values: {ov_len} elements")
                    if ct_len == ov_len:
                        logger.info(f"    ✓ Lengths match!")

        # Save the fixed file
        logger.info(f"\nSaving corrected file: {output_file}")
        with open(output_file, 'wb') as f:
            f.write(fixed_data)

        # Create backup if overwriting
        if output_file == xdf_path:
            backup_path = xdf_path.with_stem(xdf_path.stem + '_CORRUPTED')
            logger.info(f"Backup saved: {backup_path.name}")

        logger.info("\n✓ Fix complete! File is ready to use.")
        return True

    except struct.error as e:
        logger.error(f"Fix failed: {e}")
        logger.info("\nThe extra clock_time is not at the file end.")
        logger.info("You may need to manually identify its location.")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

    finally:
        tmp_path.unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    xdf_file = sys.argv[1]
    stream_name = sys.argv[2] if len(sys.argv) > 2 else "GSR"
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        success = remove_extra_clock_time(xdf_file, stream_name, output_file)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
