# XDF Corruption Repair Scripts

This directory contains scripts to help repair corrupted XDF files with synchronization data mismatches.

## Problem

Some XDF files have a **length mismatch** between `clock_times` and `offset_values` arrays. This causes the file to fail loading with:

```
struct.error: unpack requires a buffer of 8 bytes
```

This typically happens when:
- File writing was interrupted
- Device clock counter overflowed
- Recording device crashed during save
- One sample is duplicated or missing

## Solution

### Option 1: Python Script (Recommended for Quick Checks)

```bash
python fix_corrupted_xdf.py corrupted.xdf
```

The script will:
1. Detect if the file is corrupted
2. Try to automatically fix by trimming the last 8 bytes
3. Verify the fix works
4. Save the corrected file

**Note:** This only works if the extra value is at the very end of the file. If it fails, use Option 2.

### Option 2: MATLAB Script (Most Reliable)

```matlab
fix_corrupted_xdf('corrupted.xdf')           % overwrites input
fix_corrupted_xdf('corrupted.xdf', 'fixed.xdf')  % saves to output
```

The script will:
1. Attempt to load the file (will error)
2. Inspect the partially-loaded data
3. **Automatically identify which array is too long**
4. **Show you exactly which elements are mismatched**
5. Remove the extra element(s)
6. Verify the fix works
7. Save the corrected file

**This is the most reliable method** because it identifies the exact location of the mismatch.

## Detailed MATLAB Workflow

If you prefer to manually identify and fix the mismatch:

```matlab
% 1. Try to load - it will error
[streams, header] = xdf('corrupted.xdf');

% 2. The error will point to a specific stream. Check its sync data:
i = 1;  % change to the stream index that had the error
ct = streams{i}.info.clock_times;      % timestamps
ov = streams{i}.info.offset_values;    % offsets

% 3. Check which is longer
fprintf('clock_times: %d elements\n', length(ct));
fprintf('offset_values: %d elements\n', length(ov));

% 4. Remove the extra element(s)
if length(ct) > length(ov)
    ct(length(ov)+1:end) = [];  % trim clock_times
else
    ov(length(ct)+1:end) = [];  % trim offset_values
end

% 5. Update the stream
streams{i}.info.clock_times = ct;
streams{i}.info.offset_values = ov;

% 6. Verify they match
assert(length(streams{i}.info.clock_times) == length(streams{i}.info.offset_values));

% 7. Re-save the file
xdf_write('fixed.xdf', streams);

% 8. Verify the fix worked
[streams_test, header_test] = xdf('fixed.xdf');
disp('Success!');
```

## Files

- `fix_corrupted_xdf.py` — Python script for automatic repair
- `fix_corrupted_xdf.m` — MATLAB script for interactive repair
- `README_XDF_REPAIR.md` — This file

## Troubleshooting

### Python script says "Truncation at end didn't work"
→ The extra value is not at the file end. Use the MATLAB script instead.

### MATLAB says `xdf_write not found`
→ Your MATLAB XDF toolbox may not have a write function. Options:
  1. Check if your toolbox has a different write function name
  2. Use the Python script if it worked
  3. Manually re-save in your XDF acquisition software

### Still getting errors after repair?
→ The corruption may be more severe than a single sample mismatch. You may need to:
  1. Contact the device manufacturer
  2. Re-record the session
  3. Use the original acquisition software's error recovery

## What the Scripts Do

### Detection
- Attempts to load with `xdf()` / `pyxdf.load_xdf()`
- Catches the specific struct unpacking error
- Confirms it's a length mismatch issue

### Diagnosis (MATLAB script)
- Inspects each stream's `clock_times` vs `offset_values` lengths
- **Shows you exactly which one is too long**
- Reports the discrepancy

### Repair
- Removes extra element(s) from the longer array
- **Most commonly**: removes the last N elements

### Verification
- Re-loads the corrected file
- Confirms all streams load without errors
- Saves the verified file to output location

## Backup

Both scripts create a backup:
- Python: `corrupted.xdf.backup`
- MATLAB: `corrupted_CORRUPTED.xdf`

The original file is preserved in case something goes wrong.

## Questions?

If the scripts don't work for your file, it may have a different type of corruption. The CardioSignalLab loader provides detailed error messages to help diagnose the issue.
