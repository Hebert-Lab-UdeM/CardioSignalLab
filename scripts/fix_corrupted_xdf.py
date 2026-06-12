#!/usr/bin/env python
"""
Fix corrupted XDF files with clock synchronization mismatches.

Usage:
    python fix_corrupted_xdf.py <input_file> [output_file]

If output_file is not specified, overwrites the input file.

This script handles XDF files where clock_times and offset_values arrays
have mismatched lengths (e.g., one is 1 element longer than the other).
"""

import sys
import struct
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class XDFRepair:
    """Repair corrupted XDF files by fixing synchronization data mismatches."""

    def __init__(self, input_path: Path):
        self.input_path = Path(input_path)
        if not self.input_path.exists():
            raise FileNotFoundError(f"File not found: {self.input_path}")

        logger.info(f"Analyzing XDF file: {self.input_path.name}")

    def detect_mismatch(self) -> Tuple[bool, Optional[str]]:
        """
        Detect if file has a clock/offset mismatch.

        Returns:
            Tuple of (has_mismatch, description)
        """
        try:
            import pyxdf
            logger.info("Attempting to load XDF with pyxdf...")
            streams, header = pyxdf.load_xdf(str(self.input_path))
            logger.info("File loaded successfully - no mismatch detected")
            return False, "File is valid"

        except struct.error as e:
            if "unpack requires a buffer" in str(e):
                logger.warning(f"Struct error detected: {e}")
                return True, f"Clock/offset length mismatch: {e}"
            raise
        except Exception as e:
            logger.error(f"Unexpected error during load: {e}")
            raise

    def repair(self, output_path: Optional[Path] = None) -> bool:
        """
        Repair the XDF file by trimming mismatched arrays.

        Args:
            output_path: Path to save repaired file (defaults to input_path)

        Returns:
            True if repair successful, False otherwise
        """
        if output_path is None:
            output_path = self.input_path

        has_mismatch, description = self.detect_mismatch()

        if not has_mismatch:
            logger.info("File is already valid - no repair needed")
            return True

        logger.info(f"Mismatch detected: {description}")
        logger.info("Attempting repair...")

        # Try to use pyxdf with lenient loading
        try:
            import pyxdf

            # Create a backup
            backup_path = self.input_path.with_suffix('.xdf.backup')
            shutil.copy2(self.input_path, backup_path)
            logger.info(f"Backup created: {backup_path.name}")

            # Try loading with increased buffer tolerance
            # We'll catch the error and attempt to fix at the binary level
            self._repair_binary(output_path)

            return True

        except Exception as e:
            logger.error(f"Repair failed: {e}")
            return False

    def _repair_binary(self, output_path: Path):
        """
        Repair by detecting and trimming the extra clock/offset value at binary level.

        This is done by:
        1. Reading the entire file
        2. Attempting to identify where the mismatch occurs
        3. Trimming the extra value
        4. Writing a corrected file
        """
        logger.info("Attempting binary-level repair...")

        with open(self.input_path, 'rb') as f:
            data = bytearray(f.read())

        original_size = len(data)
        logger.info(f"File size: {original_size:,} bytes")

        # Strategy: Try removing the last 8 bytes (one double precision float)
        # This is where the extra value typically is

        # Make a test copy and try trimming
        test_data = data[:-8]  # Remove last 8 bytes

        # Try to load the truncated version
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.xdf', delete=False) as tmp:
            tmp.write(test_data)
            tmp_path = Path(tmp.name)

        try:
            import pyxdf
            logger.info("Testing removal of last 8 bytes...")
            streams, header = pyxdf.load_xdf(str(tmp_path))

            # Success! The truncated version loaded
            logger.info(f"Success! File loads after removing last 8 bytes")
            logger.info(f"Loaded {len(streams)} streams")

            # Save the corrected file
            shutil.copy2(tmp_path, output_path)
            logger.info(f"Repaired file saved: {output_path}")

            tmp_path.unlink()
            return

        except struct.error as e:
            logger.warning(f"Truncation at end didn't work: {e}")
            tmp_path.unlink()
            raise ValueError(
                "Could not automatically determine which value to remove. "
                "Please use MATLAB to identify and remove the extra value:\n"
                "  1. Load with xdf() - it will raise an exception\n"
                "  2. Check lengths: length(streams{i}.info.clock_times) vs offset_values\n"
                "  3. Delete the extra value from the longer array\n"
                "  4. Re-save the file"
            )

        except Exception as e:
            logger.error(f"Unexpected error during repair: {e}")
            tmp_path.unlink()
            raise

    def verify(self, file_path: Path) -> bool:
        """Verify that a file can be loaded successfully."""
        try:
            import pyxdf
            streams, header = pyxdf.load_xdf(str(file_path))
            logger.info(f"Verification successful: {len(streams)} streams loaded")
            return True
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False


def main():
    """Command-line interface for XDF repair."""
    if len(sys.argv) < 2:
        print("Usage: python fix_corrupted_xdf.py <input_file> [output_file]")
        print("\nExamples:")
        print("  python fix_corrupted_xdf.py corrupted.xdf")
        print("  python fix_corrupted_xdf.py corrupted.xdf repaired.xdf")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else input_file

    try:
        repair = XDFRepair(input_file)

        # Detect mismatch
        has_mismatch, description = repair.detect_mismatch()

        if not has_mismatch:
            logger.info("File is valid - no repair needed")
            sys.exit(0)

        # Attempt repair
        logger.info("Starting repair process...")
        success = repair.repair(output_file)

        if success:
            # Verify the repaired file
            if repair.verify(output_file):
                logger.info("✓ Repair completed successfully!")
                if output_file != input_file:
                    logger.info(f"Repaired file: {output_file}")
                sys.exit(0)
            else:
                logger.error("Repair created file but verification failed")
                sys.exit(1)
        else:
            logger.error("Repair failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
