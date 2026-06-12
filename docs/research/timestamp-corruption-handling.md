# Timestamp Corruption Detection and Fallback Strategy

## Problem

The file `subj-AcuteTinnitus-S_AT_019_F_20250207.xdf` has corrupted timestamps in the ECG stream:
- **LSL timestamps**: 2 backward jumps (-0.600s and -0.390s)
- **Device timestamps**: 33,167 backward jumps (hardware counter overflow)
- **Result**: File failed to load completely, even though GSR data was clean

## Root Cause Analysis

**ECG Stream Corruption:**
1. LSL timestamps jumped backward at indices 428788 and 636180
2. Device timestamps (first column) overflowed from ~390k ms to 37 billion ms
3. When attempting to remove the 2 out-of-order LSL samples, the next sample still created a backward jump
   - Indicates the corruption extends beyond just those 2 isolated samples
   - Sampling rate variation of 1632% (mean: 198.96 Hz, max gap: 45.7 seconds)
   - Suggests underlying data quality issues or recording interruptions

**GSR Stream:** Clean timestamps in both LSL and device sources
**Device Timestamps**: Actually reliable in GSR (no overflow), but corrupted in ECG

## Solution: 4-Tier Fallback Strategy

Implemented in `file_loader.py::_extract_signals_from_stream()`:

### Tier 1: Use LSL timestamps if clean
- Check for backward jumps
- If none found → use as authoritative time axis ✓ (GSR uses this)

### Tier 2: Repair LSL timestamps if fixable
- "Fixable" = < 100 backward jumps AND < 5% of samples
- Strategy: Remove out-of-order samples
- **Verification**: Check that repaired timestamps are actually monotonic
- If repair fails → proceed to Tier 3

### Tier 3: Fall back to device timestamps
- Convert milliseconds to seconds: `device_ts / 1000.0`
- Check for corruption (same criteria as LSL)
- If clean → use as time axis
- If corrupted but fixable → attempt repair
- If too corrupt → proceed to Tier 4

### Tier 4: Skip the signal
- Log detailed error explaining why timestamp sources failed
- Remove stream from loaded data
- Continue loading remaining streams
- GUI shows empty plot subpanel for skipped signal

## Implementation Details

**Helper Methods Added:**

1. **`_assess_timestamp_corruption()`**
   - Counts backward jumps and severity
   - Returns: `is_clean`, `is_fixable`, backward jump count
   - Fixable threshold: < 100 jumps AND < 5% of samples

2. **`_repair_lsl_timestamps()`**
   - Removes out-of-order samples
   - Returns both repaired timestamps AND valid mask
   - Validates repair worked before returning
   - Filters both timestamps and signal samples using the mask

3. **Device timestamp handling**
   - Converts from milliseconds to seconds
   - Detects Shimmer device timestamp columns (first column)
   - Same corruption detection logic as LSL

**Sample Filtering:**
- When timestamps are repaired, signal samples are also filtered
- Uses boolean mask: `samples = samples[valid_mask]`
- Ensures samples and timestamps remain aligned

## Results

### For Problem File

**Before**: File failed to load completely
```
ValueError: timestamps must be strictly increasing. Non-monotonic at indices: [428788, 636180]
```

**After**: File loads successfully with available data
```
Loaded 2 signals:
  - GSR: 243,981 samples @ 64Hz, 3812.0s
  - Internal ADC A13: 243,981 samples @ 64Hz, 3812.0s

Skipped:
  - ECG: Both LSL and device timestamps too corrupted
  - Events: 26 markers loaded successfully
```

### Logging Output

```
LSL timestamps corrupted but fixable for 'ECG': 2 backward jumps
Repair failed for 'ECG': still 2 backward jumps after removing 2 samples. Corruption too extensive.
Device timestamps for 'ECG': 33167 backward jumps (4.39%) - severely corrupted
Both LSL and device timestamps severely corrupted for 'ECG' (33167 backward jumps) - skipping all channels
Using LSL timestamps for 'GSR' (clean)
```

## Design Rationale

1. **Graceful degradation**: Rather than failing completely, load what's usable
2. **Verification over assumptions**: Repair is only accepted if it actually works
3. **Device timestamps as fallback**: Preferred when LSL is corrupted (better for physiological analysis)
4. **Clear logging**: User can understand exactly why signals were skipped
5. **Signal alignment preserved**: Filtering samples ensures timestamps and data stay synchronized

## For Users

When a file loads with some signals missing:

1. **Check the debug log** (View → Log Panel, or keyboard shortcut L)
   - Clear explanation of which signals were skipped and why
   - Shows timestamp corruption severity

2. **Understand the plot visualization**
   - Available signals display normally
   - Empty subpanels indicate skipped streams (corruption detected)
   - Events display in all loaded signals if present

3. **Data quality awareness**
   - Timestamp corruption often indicates underlying recording issues
   - Large sampling rate variations suggest data gaps or hardware problems
   - Consider checking the raw file with advanced tools if detailed analysis needed

## Related Issues

- EKG_Peak_Corrector v2 also encounters this file corruption (same root cause)
- Suggests device-side issue during recording, not post-processing artifact
- Shimmer device timestamp overflow when recording extends beyond 37 billion ms (~440 days)
- LSL timestamp jumps may indicate network packet loss or synchronization issues during recording
