# Workflow: Fixing Corrupted XDF Files

This document describes the complete workflow for handling two types of XDF file corruption and restoring them for use in CardioSignalLab.

## Overview

CardioSignalLab can now handle two types of XDF corruption through different workflows:

1. **Type 1: Timestamp Corruption** (backward jumps in LSL/device timestamps)
   - **Solution**: 4-tier fallback strategy in CardioSignalLab
   - **Result**: Affected streams may be skipped with a user warning
   - **Files**: `subj-AcuteTinnitus-S_AT_019_F_20250207.xdf`

2. **Type 2: Structural Corruption** (binary-level length mismatch in synchronization data)
   - **Solution**: Manual fix in MATLAB, then load via MatLoader in CardioSignalLab
   - **Result**: Full data recovery possible
   - **Files**: `subj-TCC-TCC010_PRE.xdf`

---

## Type 1: Timestamp Corruption (LSL/Device Timestamp Mismatches)

### Symptom
File loads but some signals have non-monotonic timestamps (backward jumps in time).

Example error: `timestamp values jump backward at certain points`

### Root Cause
LSL or device clock counter issues during recording (buffer overflows, clock adjustments, etc.).

### Solution: Automatic 4-Tier Fallback

CardioSignalLab implements a 4-tier fallback strategy:

1. **Use LSL timestamps if clean** - Preferred because they're synchronized by Lab Streaming Layer
2. **Repair LSL if fixable** - If <100 backward jumps AND <5% of samples affected, remove out-of-order samples
3. **Fall back to device timestamps** - Use the timestamps embedded in the device data stream
4. **Skip the stream** - If both fail, skip with a user warning dialog

### Expected Result

The file loads successfully with:
- ✓ Streams with clean timestamps display normally
- ✓ Streams with fixable corruption repaired and display normally
- ⚠️ Streams with unfixable corruption skipped with warning dialog
- ✓ User informed which streams failed and why

### Example: `subj-AcuteTinnitus-S_AT_019_F_20250207.xdf`

```
File loads with warning:
  - GSR: Loaded successfully (LSL timestamps clean)
  - Internal ADC A13: Loaded successfully (device timestamps fallback)
  - ECG: SKIPPED (timestamps too corrupted)
```

**User sees dialog:**
> "Warning: One or more signal streams failed to load
>  - ECG: Corrupted timestamps could not be repaired
>  The following signals loaded successfully: GSR, Internal ADC A13"

---

## Type 2: Structural Corruption (Binary Length Mismatch)

### Symptom
File fails to load with error:
```
struct.error: unpack requires a buffer of 8 bytes
```

### Root Cause
Binary-level mismatch in XDF file structure. Typically:
- `clock_times` array length ≠ `offset_values` array length
- One array has 1 extra element (e.g., clock_times: 13796, offset_values: 13795)

### Solution: MATLAB Manual Fix + MatLoader

This is a 3-step workflow:

#### Step 1: Identify and Fix in MATLAB

```matlab
% 1. Load the corrupted file (it will error)
[streams, header] = load_xdf('corrupted_file.xdf');
% -> Error: "unpack requires a buffer of 8 bytes"

% 2. The error message points to a specific stream. Check its sync arrays
i = 1;  % Change to correct stream index if needed
ct_len = length(streams{i}.info.clock_times)
ov_len = length(streams{i}.info.offset_values)
% -> Shows which array is too long

% 3. Delete the extra element(s)
if ct_len > ov_len
    streams{i}.info.clock_times(ov_len+1:end) = [];
else
    streams{i}.info.offset_values(ct_len+1:end) = [];
end

% 4. Verify they match now
assert(length(streams{i}.info.clock_times) == length(streams{i}.info.offset_values));

% 5. Save to .mat file (this is the key step!)
save('xdf_data.mat', 'streams', 'header');
```

#### Step 2: Load in CardioSignalLab

In CardioSignalLab's file dialog:
1. Select the `.mat` file you saved from MATLAB
2. File opens with all signals properly loaded
3. Data is ready for analysis/export

**Key insight**: The `.mat` file already contains the fixed data because MATLAB's `load_xdf()` partially loads before hitting the error. When you manually fix the mismatched arrays in the debugger and save, you're saving already-corrected data.

#### Step 3: Verify and Export

Once loaded in CardioSignalLab:
- ✓ All signals display correctly
- ✓ Timing is accurate (no gaps or jumps)
- ✓ Can export to CSV, NPY, or save session for later

### Example: `subj-TCC-TCC010_PRE.xdf`

Original XDF file:
```
- Error: struct.error: unpack requires a buffer of 8 bytes
- GSR stream: clock_times=13796, offset_values=13795 (1 element too long)
```

After MATLAB fix:
```matlab
streams{2}.info.clock_times(13796) = [];  % Delete extra element
save('xdf_data.mat', 'streams', 'header');
```

Load `xdf_data.mat` in CardioSignalLab:
```
✓ GSR: 382,704 samples @ 64.0 Hz
✓ Internal ADC A13: 382,704 samples @ 64.0 Hz
✓ Ready for analysis
```

---

## Implementation Details

### CardioSignalLab Changes

#### 1. Enhanced XdfLoader (Timestamp Corruption Handling)

**File**: `src/cardio_signal_lab/core/file_loader.py` (XdfLoader class)

Key methods:
- `_assess_timestamp_corruption()` - Detects severity of backward jumps
- `_repair_lsl_timestamps()` - Removes out-of-order samples and verifies repair
- `_extract_signals_from_stream()` - Implements 4-tier fallback strategy

Behavior:
- ✓ Logs detailed diagnostics for each stream
- ✓ Skips streams with unfixable corruption
- ✓ Stores skipped stream names in `self.skipped_streams`

#### 2. New MatLoader (Binary Corruption Recovery)

**File**: `src/cardio_signal_lab/core/file_loader.py` (MatLoader class)

Capabilities:
- Loads `.mat` files containing corrected XDF streams
- Converts MATLAB structure format to pyxdf format
- Handles both single-channel and multi-channel streams
- Extracts channel names from Shimmer device metadata
- Applies same validation logic as XdfLoader

#### 3. GUI Warning Dialog

**File**: `src/cardio_signal_lab/gui/main_window.py`

When loading files:
- Detects struct.error (binary corruption) and shows MATLAB fix instructions
- Detects skipped streams (timestamp corruption) and lists them
- Provides clear guidance on next steps

---

## Complete Workflow Diagram

```
Corrupted XDF File
│
├─→ Load attempt in CardioSignalLab
│   │
│   ├─→ Type 1: Timestamp error (backward jumps)
│   │   │
│   │   └─→ 4-tier fallback:
│   │       1. Try LSL timestamps ✓
│   │       2. Try repair if fixable ✓
│   │       3. Try device timestamps ✓
│   │       4. Skip with warning ⚠️
│   │       │
│   │       └─→ File loads (some signals may be missing)
│   │
│   └─→ Type 2: Struct.error (binary corruption)
│       │
│       └─→ Show error dialog with MATLAB instructions
│           │
│           └─→ User manually fixes in MATLAB:
│               1. Load file (error expected)
│               2. Fix mismatched sync arrays
│               3. Save as .mat file
│               │
│               └─→ Load .mat file in CardioSignalLab
│                   │
│                   └─→ MatLoader converts MATLAB format
│                       │
│                       └─→ File loads successfully (all signals)
```

---

## Validation & Testing

### Type 1 Validation
- File: `subj-AcuteTinnitus-S_AT_019_F_20250207.xdf`
- Result: ✓ GSR + Internal ADC A13 loaded, ECG skipped
- Log output shows:
  ```
  GSR: timestamps are clean
  Internal ADC A13: corrupted timestamps repaired (removed 2 out-of-order samples)
  ECG: corrupted and cannot be repaired (SKIPPED)
  ```

### Type 2 Validation
- File: `subj-TCC-TCC010_PRE.xdf` → fix → `xdf_data.mat`
- Result: ✓ All signals loaded successfully
- MatLoader output shows:
  ```
  GSR: 382,704 samples @ 63.3 Hz (EDA)
  Internal ADC A13: 382,704 samples @ 63.3 Hz (PPG)
  Time range: -1.12s to 6041.69s
  ```

---

## Future Enhancements

- [ ] Add XDF re-export capability (currently blocked by pyxdf v1.17.0 limitations)
- [ ] Add pytest-qt GUI tests for warning dialogs
- [ ] Support for other MATLAB structural array formats
- [ ] Automated detection and suggested fixes for common corruption patterns

---

## References

- **XDF Format**: https://github.com/sccn/xdf
- **Lab Streaming Layer**: https://labstreaminglayer.org/
- **pyxdf Library**: https://github.com/xdf-modules/xdf-python
- **Shimmer Devices**: https://www.shimmersensing.com/
