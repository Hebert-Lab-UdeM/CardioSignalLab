# Structural Corruption Detection: Length Mismatch

## Problem

File: `subj-TCC-TCC010_PRE.xdf`

**Error:**
```
struct.error: unpack requires a buffer of 8 bytes
```

**Root Cause:**
- XDF file has a length mismatch between data samples and timestamps
- One data channel has either one extra sample or one missing sample compared to its timestamps
- File is truncated or corrupted at the binary level
- Occurs during pyxdf library parsing when trying to read timestamp values

## Detection Strategy

**Type of Corruption:**
- Structural/binary corruption (NOT timestamp value corruption)
- Cannot be fixed by filtering or repairing values
- Requires file to be properly re-saved

**When Detected:**
- During `pyxdf.load_xdf()` parsing
- Low-level struct unpacking error: `"unpack requires a buffer of 8 bytes"`
- Happens before our timestamp analysis code can run

## Solution: Inform User to Re-Save

Instead of attempting risky repairs, we:

1. **Catch the struct.error** in `_load_xdf_streams()`
2. **Detect the specific error pattern** (buffer size mismatch)
3. **Raise a clear ValueError** with instructions
4. **GUI shows helpful dialog** with step-by-step MATLAB fix instructions

## Implementation

**File Loader (`file_loader.py`):**
```python
if "unpack requires a buffer" in str(e):
    raise ValueError(
        "XDF file is corrupted with a length mismatch between data samples "
        "and timestamps. This cannot be automatically fixed. "
        "Please re-save the file in MATLAB..."
    )
```

**GUI (`main_window.py`):**
```
if "length mismatch" in error_msg.lower():
    QMessageBox.critical(
        "File Corrupted - Action Required",
        "This XDF file has structural corruption...\n\n"
        "Please fix the file by:\n"
        "1. Open the file in MATLAB\n"
        "2. Wait for exception and delete extra sample\n"
        "3. Re-save the file\n\n"
        "Then you can load it here."
    )
```

## Why Not Automate This?

1. **Binary-level corruption** - Requires understanding XDF binary format
2. **Multiple possible causes** - Could be missing/extra sample in any stream
3. **Risk of data loss** - Automatic patching could delete wrong data
4. **MATLAB is definitive** - MATLAB's error pinpoints exact location
5. **Safe and clean** - Re-save produces validated, properly-formatted file

## User Workflow

**When loading a corrupted file:**
1. Click File → Open
2. Select file
3. Error dialog appears with instructions
4. User opens file in MATLAB
5. MATLAB raises exception pointing to the issue
6. User deletes the extra sample as instructed
7. User re-saves (File → Save in MATLAB)
8. File can now be loaded in CardioSignalLab

## Error Messages

**Debug Log:**
```
File has structural corruption (length mismatch): unpack requires a buffer of 8 bytes
```

**User Dialog:**
```
File Corrupted - Action Required

This XDF file has a structural corruption (length mismatch between data and timestamps).

This cannot be automatically fixed.

Please fix the file by:
1. Open the file in MATLAB
2. Wait for MATLAB to raise an exception
3. Delete the extra sample value as indicated
4. Re-save the file

Then you can load it here.
```

## Technical Details

**Where Error Occurs:**
- `pyxdf.load_xdf()` parsing
- While reading clock values: `struct.unpack("<d", f.read(8))`
- Trying to read 8 bytes (double) but file has fewer bytes

**Why This Happens:**
- XDF format expects: samples[N] with timestamps[N]
- File has: samples[N] with timestamps[N-1] (or vice versa)
- Binary format stores samples then timestamps sequentially
- Length mismatch truncates the file before all timestamps read

## Recovery Path

```
Corrupted File (samples != timestamps)
    ↓
Load Error Detected ✓
    ↓
User Notified (Dialog) ✓
    ↓
MATLAB Opens File
    ↓
Exception Raised (points to problem)
    ↓
User Deletes Extra Sample
    ↓
User Re-Saves (MATLAB validates)
    ↓
File Now Valid ✓
    ↓
CardioSignalLab Loads Successfully ✓
```

## Related Files

- `subj-TCC-TCC010_PRE.xdf` (test case showing this corruption)
- `subj-AcuteTinnitus-S_AT_019_F_20250207.xdf` (different corruption: timestamp values, handled by fallback strategy)
